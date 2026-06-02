"""
Test runner — orchestrates the execution of conformance tests.

The Runner takes a configuration (target_kind, endpoint, level), loads
the appropriate test cases, executes them against the target, and
produces a Report.

Test cases come from level_1.py, level_2.py, and level_3.py. Each test
is a callable that takes a TestContext and returns one or more TestResults.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

from aaep_conformance.reporter import (
    Report,
    Severity,
    TestResult,
    Verdict,
)


# === Configuration ===

@dataclass
class RunnerConfig:
    """Configuration for a conformance test run."""

    target_kind: str
    """Either 'producer' or 'subscriber'."""

    endpoint: str
    """URL or connection string for the target."""

    level: int
    """Conformance level: 1, 2, or 3."""

    timeout_seconds: int = 300
    """Per-test timeout."""

    profile: str = "default"
    """Test profile (default, langchain-mode, middleware-mode, etc.)."""

    filter_pattern: str | None = None
    """If set, run only tests whose ID contains this substring."""

    verbose: bool = False
    """Print per-test progress to console."""

    extra: dict[str, Any] = field(default_factory=dict)
    """Profile-specific extra parameters."""

    def __post_init__(self) -> None:
        if self.target_kind not in ("producer", "subscriber"):
            raise ValueError(
                f"target_kind must be 'producer' or 'subscriber', got {self.target_kind!r}"
            )
        if self.level not in (1, 2, 3):
            raise ValueError(f"level must be 1, 2, or 3, got {self.level}")
        if self.timeout_seconds < 1:
            raise ValueError(f"timeout_seconds must be >= 1, got {self.timeout_seconds}")


# === Test context ===

@dataclass
class TestContext:
    """Context passed to each test case during execution."""

    config: RunnerConfig
    transport: "Transport"
    timeout_seconds: int

    async def send(self, message: dict[str, Any]) -> None:
        """Send a message to the target."""
        await self.transport.send(message)

    async def receive(self, timeout: float | None = None) -> dict[str, Any] | None:
        """Receive a message from the target."""
        return await self.transport.receive(timeout=timeout or self.timeout_seconds)

    async def request_session(self, user_message: str) -> str:
        """Trigger a session on the target and return its session_id once observed."""
        await self.send({"kind": "user_input", "text": user_message})
        # Wait for the first event from the session
        event = await self.receive(timeout=10)
        if event is None:
            raise TimeoutError("Producer did not emit any event")
        return event.get("session_id", "")


# === Transport abstraction ===

class Transport:
    """
    Abstract transport to a target endpoint.

    Concrete subclasses handle HTTP, WebSocket, stdio JSON-RPC, etc.
    """

    async def connect(self) -> None:
        raise NotImplementedError

    async def close(self) -> None:
        raise NotImplementedError

    async def send(self, message: dict[str, Any]) -> None:
        raise NotImplementedError

    async def receive(self, timeout: float) -> dict[str, Any] | None:
        raise NotImplementedError


class HTTPTransport(Transport):
    """HTTP/HTTPS transport (SSE for receive, POST for send)."""

    def __init__(self, endpoint: str):
        self.endpoint = endpoint
        self.client = None
        self.event_buffer: asyncio.Queue = asyncio.Queue()
        self._sse_task: asyncio.Task | None = None

    async def connect(self) -> None:
        import httpx
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(30.0))
        # Start SSE stream as background task
        self._sse_task = asyncio.create_task(self._sse_consumer())

    async def _sse_consumer(self) -> None:
        """Background task that consumes SSE events from the endpoint."""
        import json
        try:
            async with self.client.stream("GET", f"{self.endpoint}/events") as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        try:
                            event = json.loads(line[6:])
                            await self.event_buffer.put(event)
                        except json.JSONDecodeError:
                            pass
        except Exception:
            pass  # Stream closed

    async def close(self) -> None:
        if self._sse_task:
            self._sse_task.cancel()
        if self.client:
            await self.client.aclose()

    async def send(self, message: dict[str, Any]) -> None:
        response = await self.client.post(f"{self.endpoint}/messages", json=message)
        response.raise_for_status()

    async def receive(self, timeout: float) -> dict[str, Any] | None:
        try:
            return await asyncio.wait_for(self.event_buffer.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None


class WebSocketTransport(Transport):
    """WebSocket transport for full-duplex communication."""

    def __init__(self, endpoint: str):
        self.endpoint = endpoint
        self.websocket = None

    async def connect(self) -> None:
        import websockets
        self.websocket = await websockets.connect(self.endpoint)

    async def close(self) -> None:
        if self.websocket:
            await self.websocket.close()

    async def send(self, message: dict[str, Any]) -> None:
        import json
        await self.websocket.send(json.dumps(message))

    async def receive(self, timeout: float) -> dict[str, Any] | None:
        import json
        try:
            raw = await asyncio.wait_for(self.websocket.recv(), timeout=timeout)
            return json.loads(raw)
        except asyncio.TimeoutError:
            return None


def _build_transport(endpoint: str) -> Transport:
    """Pick the right transport based on the endpoint scheme."""
    if endpoint.startswith(("http://", "https://")):
        return HTTPTransport(endpoint)
    if endpoint.startswith(("ws://", "wss://")):
        return WebSocketTransport(endpoint)
    raise ValueError(
        f"Unsupported endpoint scheme in {endpoint!r}. "
        f"Use http://, https://, ws://, or wss://."
    )


# === Test case loading ===

# Type alias for a test function
TestFunction = Callable[[TestContext], "asyncio.Future[Iterable[TestResult]]"]


def _load_test_cases(level: int, target_kind: str, profile: str) -> list[tuple[str, TestFunction]]:
    """
    Load the test cases for a given level.

    Returns a list of (test_id, test_function) tuples. Lower levels are
    included in higher levels (Level 3 tests run all of Level 1, 2, and 3).
    """
    cases: list[tuple[str, TestFunction]] = []

    # Always include Level 1
    from aaep_conformance import level_1
    cases.extend(level_1.get_tests(target_kind=target_kind, profile=profile))

    if level >= 2:
        from aaep_conformance import level_2
        cases.extend(level_2.get_tests(target_kind=target_kind, profile=profile))

    if level >= 3:
        from aaep_conformance import level_3
        cases.extend(level_3.get_tests(target_kind=target_kind, profile=profile))

    return cases


def _filter_tests(
    tests: list[tuple[str, TestFunction]],
    pattern: str | None,
) -> list[tuple[str, TestFunction]]:
    if pattern is None:
        return tests
    return [(tid, fn) for tid, fn in tests if pattern in tid]


# === The Runner ===

class Runner:
    """Orchestrates a conformance test run."""

    def __init__(self, config: RunnerConfig):
        self.config = config

    def run(self) -> Report:
        """Run all applicable tests and return a Report. Blocking call."""
        return asyncio.run(self._run_async())

    async def _run_async(self) -> Report:
        start_time = time.monotonic()

        # Load applicable test cases
        cases = _load_test_cases(
            level=self.config.level,
            target_kind=self.config.target_kind,
            profile=self.config.profile,
        )
        cases = _filter_tests(cases, self.config.filter_pattern)

        if not cases:
            return Report(
                conformance_level=self.config.level,
                endpoint=self.config.endpoint,
                verdict=Verdict.SKIPPED,
                duration_seconds=0.0,
                test_results=[],
                metadata={"reason": "No tests matched filter or level"},
            )

        # Connect transport
        transport = _build_transport(self.config.endpoint)
        try:
            await transport.connect()
        except Exception as exc:
            return Report(
                conformance_level=self.config.level,
                endpoint=self.config.endpoint,
                verdict=Verdict.FAIL,
                duration_seconds=time.monotonic() - start_time,
                test_results=[TestResult(
                    test_id="SETUP",
                    description="Transport connection failed",
                    passed=False,
                    severity=Severity.ERROR,
                    message=f"Could not connect to {self.config.endpoint}: {exc}",
                )],
                metadata={},
            )

        # Run each test case
        all_results: list[TestResult] = []
        try:
            for test_id, test_fn in cases:
                ctx = TestContext(
                    config=self.config,
                    transport=transport,
                    timeout_seconds=self.config.timeout_seconds,
                )

                try:
                    results = await asyncio.wait_for(
                        test_fn(ctx),
                        timeout=self.config.timeout_seconds,
                    )
                    for result in results:
                        result.test_id = result.test_id or test_id
                        all_results.append(result)
                        if self.config.verbose:
                            self._log_result(result)
                except asyncio.TimeoutError:
                    all_results.append(TestResult(
                        test_id=test_id,
                        description=f"Test timed out after {self.config.timeout_seconds}s",
                        passed=False,
                        severity=Severity.ERROR,
                        message="Timeout",
                    ))
                except Exception as exc:
                    all_results.append(TestResult(
                        test_id=test_id,
                        description=f"Test raised exception: {type(exc).__name__}",
                        passed=False,
                        severity=Severity.ERROR,
                        message=str(exc),
                    ))
        finally:
            await transport.close()

        # Build the final report
        duration = time.monotonic() - start_time
        return Report.from_results(
            test_results=all_results,
            conformance_level=self.config.level,
            endpoint=self.config.endpoint,
            duration_seconds=duration,
            metadata={
                "target_kind": self.config.target_kind,
                "profile": self.config.profile,
                "filter": self.config.filter_pattern,
            },
        )

    def _log_result(self, result: TestResult) -> None:
        """Print a single result during verbose execution."""
        status = "✓" if result.passed else "✗"
        print(f"  {status} {result.test_id}: {result.description}")


__all__ = ["Runner", "RunnerConfig", "TestContext", "Transport"]
