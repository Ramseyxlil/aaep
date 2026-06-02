# Pattern: Manual Loop AAEP Integration

**Use this pattern when you control the agent loop directly with no framework abstraction.**

This is the most explicit pattern. Every state transition, every tool call, every output chunk is emitted by code you wrote. There is no framework helping or hiding what's happening. The tradeoff: total clarity in exchange for verbosity.

The [Quickstart](../QUICKSTART.md) demonstrates this pattern in its simplest form. This guide promotes that to a production-grade reference.

---

## When manual loop is the right choice

Pick manual loop when:

- You wrote the agent loop yourself and aren't using a framework
- You're prototyping and don't want framework overhead
- You're embedding an agent in a constrained environment (CLI tool, edge device, plugin)
- You need exact control over event ordering and timing
- You're building the reference implementation for some other adoption pathway

Pick something else when:

- You're using LangChain, MAF, AutoGen, Semantic Kernel, or any other framework (use that framework's natural pattern)
- The verbosity becomes unmaintainable (refactor into one of the other patterns)

---

## Anatomy of a production manual loop

A complete production manual loop:

1. Starts the session and emits `agent.session.started`
2. Runs the LLM-reasoning-and-tool-calling loop:
   - Emits `agent.state.changed` (idle → thinking)
   - Calls the LLM
   - If tools were requested: emits `agent.state.changed` (thinking → calling_tool), invokes each, emits tool events, returns to thinking
   - Otherwise: emits `agent.state.changed` (thinking → writing_output), streams output, breaks
3. Emits `agent.session.completed` on success, or:
4. Emits `agent.session.errored` on failure, or `agent.session.cancelled` on cancellation

Production loops also handle: concurrent tool calls, recovery from transient failures, partial-result emission on cancellation, and reconnection if the transport drops.

---

## Complete production-grade implementation

```python
"""
Production-grade manual loop AAEP integration.

Adapt the LLM call site to your provider (Anthropic, OpenAI, etc.) and
the tool registry to your tools. The AAEP emission code is provider-agnostic.
"""

import asyncio
import time
from typing import Any

from aaep_helpers import (
    AAEPEmitter,
    StreamCoalescer,
    make_id,
    classify_error_category,
)


class AgentLoop:
    """A production-grade agent loop with AAEP emissions."""

    def __init__(
        self,
        emitter: AAEPEmitter,
        llm_client,
        tool_registry: dict,
    ):
        self.emitter = emitter
        self.llm = llm_client
        self.tools = tool_registry

    async def run(self, user_message: str, *, user_id: str | None = None):
        """Run a complete agent session for the given user message."""

        session_id = self.emitter.start_session(
            summary_normal=f"Processing: {user_message[:80]}",
            request_text=user_message,
            requested_by=f"user:{user_id}" if user_id else None,
        )

        start_time = time.monotonic()
        current_state = "idle"
        coalescer = None

        try:
            messages = [{"role": "user", "content": user_message}]

            # Main loop: think, optionally call tools, eventually produce output
            while True:
                # → thinking
                if current_state != "thinking":
                    self.emitter.state_changed(
                        session_id=session_id,
                        from_state=current_state,
                        to_state="thinking",
                        summary_normal="Considering.",
                    )
                    current_state = "thinking"

                # Call the LLM (streaming or not)
                response = await self._call_llm(messages, session_id)

                if response.has_tool_calls:
                    # → calling_tool
                    self.emitter.state_changed(
                        session_id=session_id,
                        from_state="thinking",
                        to_state="calling_tool",
                        summary_normal=f"Calling {len(response.tool_calls)} tool(s).",
                    )
                    current_state = "calling_tool"

                    tool_results = await self._execute_tools(
                        response.tool_calls, session_id
                    )
                    messages.append({"role": "assistant", "content": response.text,
                                    "tool_calls": response.tool_calls})
                    messages.append({"role": "user", "content": tool_results})
                    # Loop back to thinking
                    continue

                # No more tools; stream the final output
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
                )

                async for chunk in self._stream_response(response):
                    coalescer.add_token(chunk)

                coalescer.finish()
                coalescer = None
                break

            # Success path
            duration_ms = int((time.monotonic() - start_time) * 1000)
            self.emitter.complete_session(
                session_id=session_id,
                summary_normal="Response complete.",
                duration_ms=duration_ms,
                tool_invocations_count=self._count_tools_invoked(messages),
            )

        except asyncio.CancelledError:
            # Flush any pending output before propagating
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
                coalescer.finish()
            self.emitter.error_session(
                session_id=session_id,
                error_category=classify_error_category(exc),
                summary_normal=f"Error: {type(exc).__name__}",
                error_message=str(exc)[:1000],
                recoverable=self._is_recoverable(exc),
                remediation_hint=self._remediation_for(exc),
            )
            raise

    async def _call_llm(self, messages, session_id):
        """Call the LLM and return the response. Adapt to your provider."""
        return await self.llm.complete(messages)

    async def _stream_response(self, response):
        """Yield tokens as the response streams. Adapt to your provider."""
        async for chunk in response:
            yield chunk.text

    async def _execute_tools(self, tool_calls, session_id):
        """Execute tools (possibly concurrently) and emit AAEP events for each."""
        results = []
        # For independence: each tool runs sequentially with its own emit cycle
        for call in tool_calls:
            result = await self._execute_one_tool(call, session_id)
            results.append({"tool_call_id": call.id, "result": result})
        return results

    async def _execute_one_tool(self, call, session_id):
        """Execute one tool with full AAEP emission cycle."""
        tool_fn = self.tools.get(call.name)
        if tool_fn is None:
            return f"<unknown tool: {call.name}>"

        aaep_tool_call_id = make_id("call")
        risk_level = getattr(tool_fn, "_aaep_risk_level", "low")
        irreversible = getattr(tool_fn, "_aaep_irreversible", False)

        # Emit tool.invoked BEFORE side effects
        self.emitter.tool_invoked(
            session_id=session_id,
            tool=call.name,
            tool_call_id=aaep_tool_call_id,
            args_summary=self._safe_args(call.arguments),
            risk_level=risk_level,
            irreversible=irreversible,
            summary_normal=f"Calling {call.name}.",
        )

        # Confirmation for irreversible or high-risk
        if irreversible or risk_level == "high":
            reply_token = self.emitter.await_confirmation(
                session_id=session_id,
                action=f"Call {call.name} with args {self._safe_args(call.arguments)}",
                consequence="This action cannot be easily undone." if irreversible
                           else "This action will be executed.",
                timeout_seconds=300,
                default_decision="reject",
                risk_level=risk_level,
                irreversible=irreversible,
                summary_normal=f"Confirm: call {call.name}?",
            )
            decision = await self.emitter.wait_for_decision(reply_token)
            if decision != "accept":
                self.emitter.tool_completed(
                    session_id=session_id,
                    tool=call.name,
                    tool_call_id=aaep_tool_call_id,
                    status="error",
                    error_message="User declined.",
                )
                return f"<user declined to call {call.name}>"

        # Execute and emit completed
        try:
            result = await tool_fn(**call.arguments)
            self.emitter.tool_completed(
                session_id=session_id,
                tool=call.name,
                tool_call_id=aaep_tool_call_id,
                status="success",
                summary_normal=self._safe_result(result),
            )
            return result

        except asyncio.TimeoutError:
            self.emitter.tool_completed(
                session_id=session_id,
                tool=call.name,
                tool_call_id=aaep_tool_call_id,
                status="timeout",
                error_message="Tool exceeded timeout.",
            )
            raise

        except Exception as exc:
            self.emitter.tool_completed(
                session_id=session_id,
                tool=call.name,
                tool_call_id=aaep_tool_call_id,
                status="error",
                error_message=str(exc)[:1000],
            )
            raise

    @staticmethod
    def _safe_args(args: dict) -> str:
        parts = []
        for k, v in args.items():
            if any(s in k.lower() for s in ("password", "token", "key", "secret")):
                parts.append(f"{k}=[redacted]")
            else:
                parts.append(f"{k}={str(v)[:80]}")
        return ", ".join(parts)[:1000]

    @staticmethod
    def _safe_result(result) -> str:
        return str(result)[:200] if result is not None else ""

    @staticmethod
    def _count_tools_invoked(messages) -> int:
        return sum(
            len(m.get("tool_calls") or [])
            for m in messages
            if m.get("role") == "assistant"
        )

    @staticmethod
    def _is_recoverable(exc: Exception) -> bool:
        return isinstance(exc, (TimeoutError, ConnectionError, asyncio.TimeoutError))

    @staticmethod
    def _remediation_for(exc: Exception) -> str | None:
        if isinstance(exc, TimeoutError):
            return "Try the request again in a few moments."
        if isinstance(exc, PermissionError):
            return "Sign in or grant permissions, then retry."
        return None
```

---

## Concurrent tool calls

When the LLM returns multiple tool calls in a single response, you can execute them concurrently:

```python
async def _execute_tools_concurrent(self, tool_calls, session_id):
    """Execute tools concurrently. Each emits its own AAEP cycle."""
    results = await asyncio.gather(*[
        self._execute_one_tool(call, session_id) for call in tool_calls
    ], return_exceptions=True)
    return [
        {"tool_call_id": call.id, "result": res if not isinstance(res, Exception) else str(res)}
        for call, res in zip(tool_calls, results)
    ]
```

Each concurrent tool emits its own `agent.tool.invoked` / `agent.tool.completed` pair with distinct `tool_call_id` values. Subscribers handle interleaved tool events naturally because each event carries its own correlation.

---

## Multi-turn conversations

For a multi-turn conversation, each user message starts a new AAEP session. The conversation history is in the producer's `messages` list, but each session is independent from AAEP's perspective:

```python
agent = AgentLoop(emitter, llm, tools)

async def chat():
    while True:
        user_message = await get_user_input()
        if user_message is None:
            break
        await agent.run(user_message)
        # Each call to .run() starts a fresh AAEP session
```

If you want to model the multi-turn conversation as a single AAEP session, design your agent loop to handle multiple user inputs within one session lifecycle — but the simpler, more common pattern is one session per user message.

---

## Recovery and resumption

If your agent might be killed mid-session (e.g., a long-running task interrupted by deployment), you can resume cleanly:

```python
async def run_with_recovery(self, user_message: str, session_id: str | None = None):
    """Resume a session if session_id is provided, otherwise start fresh."""
    if session_id is None:
        session_id = self.emitter.start_session(...)
    else:
        # Don't emit session.started; emit a state.changed indicating resumption
        self.emitter.state_changed(
            session_id=session_id,
            from_state="cancelled",
            to_state="thinking",
            summary_normal="Resuming previous session.",
        )
    # ... rest of the loop
```

Persist `session_id` in your job storage so you can pass it back in on resumption.

---

## Common pitfalls

| Mistake | Consequence | Fix |
|---|---|---|
| Emitting `session.started` after the LLM call | Subscriber misses the start | Emit before any agent work |
| Forgetting to flush coalescer on early return | Last output fragment lost | Wrap in try/finally, call `coalescer.finish()` |
| Calling tools without `await self.emitter.wait_for_decision(...)` | Producer bypasses confirmation contract | Always await before executing the tool function |
| Reusing the same `tool_call_id` for concurrent calls | Subscribers can't pair invoked/completed | Generate unique `tool_call_id` per call |
| Catching exceptions without emitting terminal event | Session orphaned in subscriber state | Always emit `session.errored` or `session.cancelled` before re-raising |

---

## Testing

```bash
aaep-conformance producer \
    --endpoint <your-endpoint> \
    --manual-mode \
    --level 2
```

The conformance suite exercises your manual loop with synthetic prompts covering: tool-heavy sessions, streaming-heavy sessions, sessions that error at various points, sessions cancelled mid-execution, and concurrent sessions.

---

## See also

- [Implementer's Guide §2.5](../IMPLEMENTERS_GUIDE.md) — overview of the manual loop pattern
- [`../QUICKSTART.md`](../QUICKSTART.md) — the minimal version of this pattern
- [`../../examples/producers/python-minimal/`](../../examples/producers/python-minimal/) — production-grade reference of this pattern
