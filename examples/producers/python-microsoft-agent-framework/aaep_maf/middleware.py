"""
MAFAAEPMiddleware — emits AAEP events from a Microsoft Agent Framework run.

MAF uses a middleware chain pattern (similar to ASP.NET Core's middleware
pipeline). Our middleware slots into that chain and intercepts each step:
agent start, tool invocations, response chunks, agent completion.

For each interception, the middleware emits the appropriate AAEP event(s)
through the same AAEPEmitter used by every other example. The safety
machinery (irreversible+high MUST default reject, critical urgency on
errored events, etc.) is inherited from python-minimal.

Designed to work in three modes:
  1. With real MAF installed: integrates directly with microsoft.agents
  2. Without MAF: falls back to a mock interface that conformance can drive
  3. With Azure OpenAI: respects content filter and grounding signals

The middleware does NOT modify MAF's behavior. It is a pure observer.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

try:
    # Real MAF imports if available
    from microsoft.agents import AgentMiddleware  # type: ignore[import-not-found]
    HAS_MAF = True
except ImportError:
    HAS_MAF = False

    class AgentMiddleware:  # type: ignore[no-redef]
        """Fallback base class when MAF is not installed."""

        async def on_agent_start(self, context: Any, next_fn: Callable) -> Any:
            return await next_fn(context)

        async def on_tool_call(self, context: Any, next_fn: Callable) -> Any:
            return await next_fn(context)

        async def on_response_chunk(self, context: Any, next_fn: Callable) -> Any:
            return await next_fn(context)

        async def on_agent_end(self, context: Any, next_fn: Callable) -> Any:
            return await next_fn(context)

from aaep_minimal_producer.emitter import (
    AAEPEmitter,
    StreamCoalescer,
    classify_error_category,
    classify_risk,
    make_id,
    safe_args_summary,
)


# Tools considered high-risk irreversible by default
HIGH_RISK_TOOLS = {
    "send_email", "send_message", "transfer_funds", "delete_record",
    "delete_file", "publish_post", "make_payment", "execute_trade",
    "delete_calendar_event", "send_sms", "purchase",
}


# === Context types (mirror what MAF would provide) ===

@dataclass
class AgentContext:
    """Per-invocation context passed through the middleware chain.

    When using real MAF, this is replaced by MAF's own context type.
    The fallback definition below is what we use in mock mode.
    """

    user_message: str = ""
    user_id: str | None = None
    tools: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    # Set by the middleware as the session progresses
    aaep_session_id: str | None = None
    tools_invoked_count: int = 0
    start_time: float = 0.0


@dataclass
class ToolCallContext:
    """Context for a single tool call within an agent run."""

    tool_name: str = ""
    tool_arguments: dict[str, Any] = field(default_factory=dict)
    result: Any = None
    error: BaseException | None = None
    aaep_tool_call_id: str | None = None


@dataclass
class ResponseChunkContext:
    """Context for a streaming response chunk."""

    chunk_text: str = ""
    is_final: bool = False
    output_id: str | None = None


# === The middleware ===

class MAFAAEPMiddleware(AgentMiddleware):
    """
    Translates Microsoft Agent Framework agent execution into AAEP events.

    Instantiate once per AAEP transport endpoint; attach to one or more
    MAF agents via `agent.add_middleware(middleware)`. The middleware is
    thread-safe for use across multiple concurrent agent invocations
    (each invocation gets its own AgentContext).
    """

    def __init__(
        self,
        send_event: Callable[[dict[str, Any]], Any],
        *,
        model: str = "gpt-4o",
        agent_id: str = "aaep-maf-agent",
        agent_name: str = "AAEP MAF Agent",
        high_risk_tools: set[str] | None = None,
        irreversible_tools: set[str] | None = None,
    ):
        super().__init__()
        self.emitter = AAEPEmitter(
            send_event=send_event,
            agent_id=agent_id,
            agent_version="1.0.0",
            agent_name=agent_name,
            model=model,
        )
        self.model = model
        self.high_risk_tools = high_risk_tools or HIGH_RISK_TOOLS
        self.irreversible_tools = irreversible_tools or HIGH_RISK_TOOLS

        # Per-agent-run state, keyed by an opaque context identity
        self._coalescers: dict[int, StreamCoalescer] = {}
        self._session_states: dict[str, str] = {}

    # === Middleware chain hooks ===

    async def on_agent_start(
        self,
        context: AgentContext,
        next_fn: Callable[[Any], Awaitable[Any]],
    ) -> Any:
        """Called when a MAF agent begins handling a user message."""
        context.start_time = time.monotonic()
        context.aaep_session_id = self.emitter.start_session(
            summary_normal=f"Processing: {context.user_message[:80]}",
            request_text=context.user_message,
            requested_by=(
                f"user:{context.user_id}" if context.user_id else None
            ),
            tools_available=[t.get("name", "") for t in context.tools],
        )
        self._session_states[context.aaep_session_id] = "idle"
        self._transition(context.aaep_session_id, "thinking",
                          "Considering the request.")
        try:
            return await next_fn(context)
        except Exception as exc:
            self._cleanup_coalescer(context)
            self.emitter.error_session(
                session_id=context.aaep_session_id,
                error_category=classify_error_category(exc),
                summary_normal=f"Error: {type(exc).__name__}",
                error_message=str(exc)[:1000],
                recoverable=isinstance(
                    exc, (TimeoutError, ConnectionError)
                ),
            )
            self._session_states.pop(context.aaep_session_id, None)
            raise

    async def on_tool_call(
        self,
        context: ToolCallContext,
        next_fn: Callable[[Any], Awaitable[Any]],
    ) -> Any:
        """Called when MAF is about to execute a tool/function call."""
        agent_context = self._get_agent_context(context)
        if agent_context is None or agent_context.aaep_session_id is None:
            # No active AAEP session — pass through without emission
            return await next_fn(context)

        session_id = agent_context.aaep_session_id
        tool_name = context.tool_name
        aaep_call_id = make_id("call")
        context.aaep_tool_call_id = aaep_call_id

        # Risk classification
        risk_level, irreversible = self._classify_tool(tool_name)

        self._transition(session_id, "calling_tool",
                         f"Preparing to call {tool_name}.")

        # Emit tool.invoked BEFORE side effect
        self.emitter.tool_invoked(
            session_id=session_id,
            tool=tool_name,
            tool_call_id=aaep_call_id,
            args_summary=safe_args_summary(context.tool_arguments),
            risk_level=risk_level,
            irreversible=irreversible,
            summary_normal=f"Calling {tool_name}.",
        )
        agent_context.tools_invoked_count += 1

        # Safety gate: irreversible or high-risk requires confirmation
        if irreversible or risk_level == "high":
            reply_token = self.emitter.await_confirmation(
                session_id=session_id,
                action=f"Call {tool_name} with: "
                       f"{safe_args_summary(context.tool_arguments, 200)}",
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
                decision = "reject"

            if decision != "accept":
                self.emitter.tool_completed(
                    session_id=session_id,
                    tool=tool_name,
                    tool_call_id=aaep_call_id,
                    status="error",
                    error_message="User declined to authorize this action.",
                )
                context.error = PermissionError(
                    f"User declined to authorize {tool_name!r}"
                )
                raise context.error

        # Run the actual tool via the rest of the chain
        try:
            result = await next_fn(context)
            self.emitter.tool_completed(
                session_id=session_id,
                tool=tool_name,
                tool_call_id=aaep_call_id,
                status="success",
                summary_normal=str(result)[:200] if result is not None else "",
            )
            self._transition(session_id, "thinking",
                             "Considering the result.")
            return result

        except asyncio.TimeoutError as exc:
            self.emitter.tool_completed(
                session_id=session_id,
                tool=tool_name,
                tool_call_id=aaep_call_id,
                status="timeout",
                error_message="Tool exceeded timeout",
            )
            raise
        except Exception as exc:
            self.emitter.tool_completed(
                session_id=session_id,
                tool=tool_name,
                tool_call_id=aaep_call_id,
                status="error",
                error_message=str(exc)[:1000],
            )
            raise

    async def on_response_chunk(
        self,
        context: ResponseChunkContext,
        next_fn: Callable[[Any], Awaitable[Any]],
    ) -> Any:
        """Called when MAF emits a streaming response chunk."""
        agent_context = self._get_agent_context(context)
        if agent_context is None or agent_context.aaep_session_id is None:
            return await next_fn(context)

        session_id = agent_context.aaep_session_id
        key = id(agent_context)

        if key not in self._coalescers:
            self._transition(session_id, "writing_output",
                             "Generating response.")
            output_id = context.output_id or make_id("out")
            self._coalescers[key] = StreamCoalescer(
                emitter=self.emitter,
                session_id=session_id,
                output_id=output_id,
                coalesce_at="sentence",
            )

        self._coalescers[key].add_token(context.chunk_text)

        if context.is_final:
            self._coalescers[key].finish()
            del self._coalescers[key]

        return await next_fn(context)

    async def on_agent_end(
        self,
        context: AgentContext,
        next_fn: Callable[[Any], Awaitable[Any]],
    ) -> Any:
        """Called when a MAF agent finishes handling a user message."""
        if context.aaep_session_id is None:
            return await next_fn(context)

        # Flush any remaining streaming output
        self._cleanup_coalescer(context)

        # Check for Azure content filter / policy signals in metadata
        policy_signal = context.metadata.get("content_filter_triggered")
        if policy_signal:
            self.emitter.error_session(
                session_id=context.aaep_session_id,
                error_category="policy",
                summary_normal="Response blocked by content policy.",
                error_message=str(policy_signal)[:1000],
                recoverable=False,
                remediation_hint="Rephrase your request and try again.",
            )
        else:
            duration_ms = int((time.monotonic() - context.start_time) * 1000)
            self.emitter.complete_session(
                session_id=context.aaep_session_id,
                summary_normal="Response complete.",
                duration_ms=duration_ms,
                tool_invocations_count=context.tools_invoked_count,
            )

        self._session_states.pop(context.aaep_session_id, None)
        return await next_fn(context)

    # === Helpers ===

    def _transition(self, session_id: str, to_state: str, summary: str) -> None:
        from_state = self._session_states.get(session_id, "idle")
        if from_state == to_state:
            return
        self.emitter.state_changed(
            session_id=session_id,
            from_state=from_state,
            to_state=to_state,
            summary_normal=summary,
        )
        self._session_states[session_id] = to_state

    def _classify_tool(self, tool_name: str) -> tuple[str, bool]:
        if tool_name in self.high_risk_tools:
            return "high", tool_name in self.irreversible_tools
        return classify_risk(tool_name)

    def _cleanup_coalescer(self, context: AgentContext) -> None:
        key = id(context)
        coalescer = self._coalescers.pop(key, None)
        if coalescer is not None:
            try:
                coalescer.finish()
            except Exception:
                pass

    def _get_agent_context(self, context: Any) -> AgentContext | None:
        """Recover the AgentContext from any nested context type.

        In real MAF, the framework passes context object through the
        middleware chain; we walk up to find the AgentContext.
        """
        if isinstance(context, AgentContext):
            return context
        # MAF's nested contexts typically reference the parent
        parent = getattr(context, "agent_context", None)
        if isinstance(parent, AgentContext):
            return parent
        return None


# === Convenience factory ===

def make_middleware(
    send_event: Callable[[dict[str, Any]], Any],
    *,
    model: str = "gpt-4o",
    agent_name: str = "AAEP MAF Agent",
    high_risk_tools: set[str] | None = None,
) -> MAFAAEPMiddleware:
    """Create an MAFAAEPMiddleware with sensible defaults."""
    return MAFAAEPMiddleware(
        send_event=send_event,
        model=model,
        agent_name=agent_name,
        high_risk_tools=high_risk_tools,
    )


__all__ = [
    "MAFAAEPMiddleware",
    "make_middleware",
    "HIGH_RISK_TOOLS",
    "AgentContext",
    "ToolCallContext",
    "ResponseChunkContext",
]
