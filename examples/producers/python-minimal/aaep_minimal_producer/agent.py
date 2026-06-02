"""
Production-grade agent loop that uses AAEPEmitter to drive real sessions.

This is the manual-loop pattern from the Implementer's Guide §2.5 implemented
as a deployable reference. It includes a mock LLM client so the example runs
without depending on any real provider. Replace _MockLLM with your real client
(Anthropic, OpenAI, etc.) for production use.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Callable

from aaep_minimal_producer.emitter import (
    AAEPEmitter,
    StreamCoalescer,
    classify_error_category,
    classify_risk,
    make_id,
    safe_args_summary,
)


# === Agent loop ===

@dataclass
class ToolDescriptor:
    """Description of a tool the agent can call."""

    name: str
    description: str
    handler: Callable
    risk_level: str = "low"
    irreversible: bool = False


class AgentLoop:
    """
    A production-grade agent loop with full AAEP emission.

    This implementation is intentionally explicit. Every state transition,
    every tool call, every output emission appears in the code. If you find
    parts that should be abstracted, fork this file and abstract them — but
    the unmodified version remains the reference.
    """

    def __init__(
        self,
        emitter: AAEPEmitter,
        llm_client: Any | None = None,
        tools: list[ToolDescriptor] | None = None,
    ):
        self.emitter = emitter
        self.llm = llm_client or _MockLLM()
        self.tools: dict[str, ToolDescriptor] = {
            t.name: t for t in (tools or _default_tools())
        }
        self._active_sessions: dict[str, asyncio.Task] = {}

    async def run(
        self,
        user_message: str,
        *,
        user_id: str | None = None,
    ) -> str:
        """
        Run a complete agent session. Returns the session_id.

        The session is fully owned by this method: it emits all lifecycle
        events including the terminal event, even on exception or cancellation.
        """
        session_id = self.emitter.start_session(
            summary_normal=f"Processing: {user_message[:80]}",
            request_text=user_message,
            requested_by=f"user:{user_id}" if user_id else None,
            tools_available=list(self.tools.keys()),
        )

        # Track the session task so it can be cancelled externally
        task = asyncio.current_task()
        if task is not None:
            self._active_sessions[session_id] = task

        try:
            await self._run_loop(session_id, user_message)
        finally:
            self._active_sessions.pop(session_id, None)

        return session_id

    async def cancel(self, session_id: str) -> bool:
        """Cancel an in-progress session. Returns True if a task was cancelled."""
        task = self._active_sessions.get(session_id)
        if task is None or task.done():
            return False
        task.cancel()
        return True

    async def _run_loop(self, session_id: str, user_message: str) -> None:
        """The main thinking-and-acting loop."""
        start_time = time.monotonic()
        current_state = "idle"
        tool_count = 0
        coalescer: StreamCoalescer | None = None
        messages = [{"role": "user", "content": user_message}]

        try:
            while True:
                # Transition to thinking
                if current_state != "thinking":
                    self.emitter.state_changed(
                        session_id=session_id,
                        from_state=current_state,
                        to_state="thinking",
                        summary_normal="Considering the request.",
                    )
                    current_state = "thinking"

                response = await self.llm.complete(messages, tools=list(self.tools.values()))

                if response.tool_calls:
                    # Tools requested
                    self.emitter.state_changed(
                        session_id=session_id,
                        from_state="thinking",
                        to_state="calling_tool",
                        summary_normal=f"Preparing to call {len(response.tool_calls)} tool(s).",
                    )
                    current_state = "calling_tool"

                    tool_results = []
                    for tool_call in response.tool_calls:
                        result = await self._execute_tool(session_id, tool_call)
                        tool_count += 1
                        tool_results.append({
                            "tool_call_id": tool_call["id"],
                            "result": result,
                        })

                    messages.append({
                        "role": "assistant",
                        "content": response.text,
                        "tool_calls": response.tool_calls,
                    })
                    messages.append({"role": "tool_results", "content": tool_results})
                    continue  # back to thinking

                # No more tools; stream output
                self.emitter.state_changed(
                    session_id=session_id,
                    from_state="thinking",
                    to_state="writing_output",
                    summary_normal="Generating response.",
                )
                current_state = "writing_output"

                output_id = make_id("out")
                coalescer = StreamCoalescer(
                    emitter=self.emitter,
                    session_id=session_id,
                    output_id=output_id,
                    coalesce_at="sentence",
                )

                async for chunk in self.llm.stream(response):
                    coalescer.add_token(chunk)
                coalescer.finish()
                coalescer = None
                break

            # Success
            duration_ms = int((time.monotonic() - start_time) * 1000)
            self.emitter.complete_session(
                session_id=session_id,
                summary_normal="Response complete.",
                duration_ms=duration_ms,
                tool_invocations_count=tool_count,
            )

        except asyncio.CancelledError:
            if coalescer is not None:
                coalescer.finish()
            self.emitter.cancelled_session(
                session_id=session_id,
                cancelled_by="system",
                summary_normal="Session cancelled.",
            )
            raise

        except Exception as exc:
            if coalescer is not None:
                try:
                    coalescer.finish()
                except Exception:
                    pass
            self.emitter.error_session(
                session_id=session_id,
                error_category=classify_error_category(exc),
                summary_normal=f"Error: {type(exc).__name__}",
                error_message=str(exc)[:1000],
                recoverable=isinstance(exc, (TimeoutError, ConnectionError)),
            )
            raise

    async def _execute_tool(self, session_id: str, tool_call: dict[str, Any]) -> Any:
        """Execute one tool with full AAEP emission cycle."""
        tool_name = tool_call["name"]
        descriptor = self.tools.get(tool_name)
        aaep_tool_call_id = make_id("call")
        args = tool_call.get("arguments", {})

        # Use descriptor metadata when available; fall back to name-based heuristic
        if descriptor:
            risk_level = descriptor.risk_level
            irreversible = descriptor.irreversible
        else:
            risk_level, irreversible = classify_risk(tool_name)

        # Emit tool.invoked BEFORE any side effect
        self.emitter.tool_invoked(
            session_id=session_id,
            tool=tool_name,
            tool_call_id=aaep_tool_call_id,
            args_summary=safe_args_summary(args),
            risk_level=risk_level,
            irreversible=irreversible,
            summary_normal=f"Calling {tool_name}.",
        )

        # Confirmation gating for irreversible or high-risk
        if irreversible or risk_level == "high":
            reply_token = self.emitter.await_confirmation(
                session_id=session_id,
                action=f"Call {tool_name} with arguments: {safe_args_summary(args, 200)}",
                consequence=(
                    "This action cannot be easily undone."
                    if irreversible
                    else "This action will be executed."
                ),
                timeout_seconds=300,
                default_decision="reject",
                risk_level=risk_level,
                irreversible=irreversible,
                summary_normal=f"Confirm: call {tool_name}?",
            )

            try:
                decision = await asyncio.wait_for(
                    self.emitter.wait_for_decision(reply_token),
                    timeout=300,
                )
            except asyncio.TimeoutError:
                decision = "reject"  # timeout applies default_decision

            if decision != "accept":
                self.emitter.tool_completed(
                    session_id=session_id,
                    tool=tool_name,
                    tool_call_id=aaep_tool_call_id,
                    status="error",
                    error_message="User declined to authorize this action.",
                )
                return f"<user declined to call {tool_name}>"

        # Execute the tool
        try:
            if descriptor:
                result = await _maybe_await(descriptor.handler(**args))
            else:
                result = f"<no handler for tool {tool_name!r}>"

            self.emitter.tool_completed(
                session_id=session_id,
                tool=tool_name,
                tool_call_id=aaep_tool_call_id,
                status="success",
                summary_normal=str(result)[:200],
            )
            return result

        except asyncio.TimeoutError:
            self.emitter.tool_completed(
                session_id=session_id,
                tool=tool_name,
                tool_call_id=aaep_tool_call_id,
                status="timeout",
                error_message="Tool exceeded timeout",
            )
            raise

        except Exception as exc:
            self.emitter.tool_completed(
                session_id=session_id,
                tool=tool_name,
                tool_call_id=aaep_tool_call_id,
                status="error",
                error_message=str(exc)[:1000],
            )
            raise


# === Helpers ===

async def _maybe_await(value: Any) -> Any:
    """Await value if it's awaitable, otherwise return as-is."""
    if asyncio.iscoroutine(value):
        return await value
    return value


def _default_tools() -> list[ToolDescriptor]:
    """Mock tool registry used by the example. Replace for real usage."""
    return [
        ToolDescriptor(
            name="fetch_balance",
            description="Look up an account balance",
            handler=_mock_fetch_balance,
            risk_level="low",
            irreversible=False,
        ),
        ToolDescriptor(
            name="search_records",
            description="Search internal records",
            handler=_mock_search_records,
            risk_level="low",
            irreversible=False,
        ),
        ToolDescriptor(
            name="send_email",
            description="Send an email",
            handler=_mock_send_email,
            risk_level="high",
            irreversible=True,
        ),
        ToolDescriptor(
            name="transfer_funds",
            description="Move money between accounts",
            handler=_mock_transfer_funds,
            risk_level="high",
            irreversible=True,
        ),
    ]


async def _mock_fetch_balance(account: str = "checking") -> str:
    await asyncio.sleep(0.3)
    balances = {"checking": "$3,247.18", "savings": "$12,891.40"}
    return balances.get(account, "$0.00")


async def _mock_search_records(query: str = "") -> str:
    await asyncio.sleep(0.5)
    return f"Found 3 records matching '{query}'"


async def _mock_send_email(to: str = "", subject: str = "", body: str = "") -> str:
    await asyncio.sleep(0.5)
    return f"Email sent to {to} with subject '{subject}'"


async def _mock_transfer_funds(
    from_account: str = "", to_account: str = "", amount: float = 0.0
) -> str:
    await asyncio.sleep(0.7)
    return f"Transferred ${amount:.2f} from {from_account} to {to_account}"


# === Mock LLM ===

@dataclass
class _LLMResponse:
    """A mock LLM response."""

    text: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)


class _MockLLM:
    """
    A minimal mock LLM client used by the example. Not a real model;
    just produces realistic-looking agent behavior to exercise AAEP emissions.

    Replace with a real client (Anthropic, OpenAI, etc.) for production.
    """

    def __init__(self) -> None:
        self._calls = 0

    async def complete(self, messages: list[dict], tools: list = None) -> _LLMResponse:
        """Pretend to think; sometimes call a tool, sometimes finish."""
        await asyncio.sleep(0.4)
        self._calls += 1

        # On the first call, sometimes call a tool to demonstrate the flow
        last_message = messages[-1].get("content", "") if messages else ""
        wants_tool = (
            self._calls == 1
            and isinstance(last_message, str)
            and any(kw in last_message.lower() for kw in (
                "balance", "search", "email", "transfer", "send", "find"
            ))
        )

        if wants_tool:
            # Pick a relevant mock tool to call
            if "balance" in last_message.lower():
                return _LLMResponse(
                    text="Let me check that for you.",
                    tool_calls=[{
                        "id": f"tool_{self._calls}",
                        "name": "fetch_balance",
                        "arguments": {"account": "checking"},
                    }],
                )
            if "email" in last_message.lower():
                return _LLMResponse(
                    text="I'll send that email.",
                    tool_calls=[{
                        "id": f"tool_{self._calls}",
                        "name": "send_email",
                        "arguments": {
                            "to": "recipient@example.com",
                            "subject": "Re: your request",
                            "body": "Following up as requested.",
                        },
                    }],
                )
            if "transfer" in last_message.lower():
                return _LLMResponse(
                    text="I'll prepare that transfer.",
                    tool_calls=[{
                        "id": f"tool_{self._calls}",
                        "name": "transfer_funds",
                        "arguments": {
                            "from_account": "checking-7821",
                            "to_account": "savings-3344",
                            "amount": 500.00,
                        },
                    }],
                )

        # Final output
        return _LLMResponse(text="", tool_calls=[])

    async def stream(self, response: _LLMResponse) -> AsyncIterator[str]:
        """Stream the response text token by token."""
        chunks = (
            "Here's what I found. ",
            "Your account is in good standing ",
            "with no pending issues. ",
            "Is there anything else ",
            "I can help you with?",
        )
        for chunk in chunks:
            await asyncio.sleep(0.05)
            yield chunk
