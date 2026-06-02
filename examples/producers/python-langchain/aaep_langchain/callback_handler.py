"""
LangChainAAEPHandler — translates LangChain callbacks into AAEP events.

LangChain calls into our handler at each lifecycle point of an agent run:
- on_chain_start / on_chain_end / on_chain_error
- on_llm_start / on_llm_end / on_llm_error / on_llm_new_token
- on_tool_start / on_tool_end / on_tool_error

For each, we emit the appropriate AAEP event(s). The handler is a pure
observer; it never modifies LangChain's behavior.

Run/Session mapping:
  Top-level chain run (parent_run_id is None) -> new AAEP session
  Nested chain runs                            -> additional events in same session

Tool call_id mapping:
  LangChain run_id (UUID) <-> AAEP tool_call_id

For non-tool/output callbacks that don't carry direct AAEP semantics
(e.g., on_chat_model_start), we emit state.changed events for the most
useful AT signal.
"""

from __future__ import annotations

import time
from typing import Any
from uuid import UUID

try:
    from langchain_core.callbacks import BaseCallbackHandler
except ImportError:  # pragma: no cover
    # Provide a graceful fallback for environments without langchain installed
    class BaseCallbackHandler:  # type: ignore[no-redef]
        pass

from aaep_minimal_producer.emitter import (
    AAEPEmitter,
    StreamCoalescer,
    classify_error_category,
    classify_risk,
    make_id,
    safe_args_summary,
)


# Mapping from LangChain tool name to a quick risk heuristic.
# In production, override this with explicit metadata from your tool registry.
HIGH_RISK_TOOL_NAMES = {
    "send_email", "transfer_funds", "delete_record", "delete_file",
    "publish_post", "make_payment", "execute_trade", "delete_calendar_event",
}


class LangChainAAEPHandler(BaseCallbackHandler):
    """
    LangChain BaseCallbackHandler that emits AAEP events.

    Instantiate once per AAEP transport endpoint. Reuse the same handler
    across multiple LangChain runs; the handler tracks state per-run via
    LangChain's UUID-based run_id.

    Example:
        handler = LangChainAAEPHandler(send_event=my_transport_fn)
        agent_executor.invoke(
            {"input": "What's the weather?"},
            config={"callbacks": [handler]},
        )
    """

    # We want to receive token-level events from streaming LLMs
    ignore_llm = False
    ignore_chain = False
    ignore_agent = False
    ignore_retriever = True  # not currently mapped to an AAEP event

    def __init__(
        self,
        send_event,
        *,
        agent_id: str = "aaep-langchain-producer",
        agent_version: str = "1.0.0",
        agent_name: str = "AAEP LangChain Producer",
        model: str | None = None,
        tool_risk_overrides: dict[str, str] | None = None,
    ):
        super().__init__()
        self.emitter = AAEPEmitter(
            send_event=send_event,
            agent_id=agent_id,
            agent_version=agent_version,
            agent_name=agent_name,
            model=model,
        )
        self.tool_risk_overrides = tool_risk_overrides or {}

        # Per-run state. LangChain's run_id (UUID) is the key.
        self._run_to_session: dict[UUID, str] = {}      # run_id -> aaep session_id
        self._run_to_tool_call: dict[UUID, str] = {}    # tool run_id -> aaep tool_call_id
        self._run_to_tool_name: dict[UUID, str] = {}    # tool run_id -> tool name
        self._coalescers: dict[UUID, StreamCoalescer] = {}  # llm run_id -> coalescer
        self._session_state: dict[str, str] = {}        # session_id -> last known state
        self._session_tool_count: dict[str, int] = {}   # session_id -> tools invoked
        self._session_start_time: dict[str, float] = {} # session_id -> start time

    # === Chain callbacks ===

    def on_chain_start(
        self,
        serialized: dict[str, Any],
        inputs: dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        """A LangChain Chain begins executing."""
        if parent_run_id is None:
            # Outermost chain — start a new AAEP session
            user_input = self._extract_user_input(inputs)
            session_id = self.emitter.start_session(
                summary_normal=f"Processing: {user_input[:80]}",
                request_text=user_input,
            )
            self._run_to_session[run_id] = session_id
            self._session_state[session_id] = "idle"
            self._session_tool_count[session_id] = 0
            self._session_start_time[session_id] = time.monotonic()
            self._transition(session_id, "thinking", "Considering the request.")
        else:
            # Nested chain — use the parent's session
            parent_session = self._find_session_for_run(parent_run_id)
            if parent_session:
                self._run_to_session[run_id] = parent_session

    def on_chain_end(
        self,
        outputs: dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        """A LangChain Chain finished successfully."""
        session_id = self._run_to_session.get(run_id)
        if session_id is None:
            return

        if parent_run_id is None:
            # Outermost chain ended — complete the session
            duration_ms = int(
                (time.monotonic() - self._session_start_time.get(session_id, 0)) * 1000
            )
            self.emitter.complete_session(
                session_id=session_id,
                summary_normal="Response complete.",
                duration_ms=duration_ms,
                tool_invocations_count=self._session_tool_count.get(session_id, 0),
            )
            self._cleanup_session(session_id)

        # Always remove this run from tracking
        self._run_to_session.pop(run_id, None)

    def on_chain_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        """A LangChain Chain raised an exception."""
        session_id = self._run_to_session.get(run_id)
        if session_id is None:
            return

        if parent_run_id is None:
            self.emitter.error_session(
                session_id=session_id,
                error_category=classify_error_category(error),
                summary_normal=f"Error: {type(error).__name__}",
                error_message=str(error)[:1000],
                recoverable=isinstance(error, (TimeoutError, ConnectionError)),
            )
            self._cleanup_session(session_id)

        self._run_to_session.pop(run_id, None)

    # === LLM callbacks ===

    def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        """An LLM call is starting. We don't emit a state change here because
        the chain-level state.changed already captured 'thinking'."""
        # We DO prepare to receive streaming tokens
        session_id = self._find_session_for_run(run_id) or self._find_session_for_run(
            parent_run_id
        )
        if session_id is None:
            return
        self._run_to_session.setdefault(run_id, session_id)

    def on_llm_new_token(
        self,
        token: str,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        """A streaming LLM emitted a new token."""
        session_id = self._run_to_session.get(run_id)
        if session_id is None:
            return

        # Lazily create a coalescer for this LLM call
        if run_id not in self._coalescers:
            # Transition to writing_output the first time we receive a token
            if self._session_state.get(session_id) != "writing_output":
                self._transition(session_id, "writing_output", "Generating response.")

            self._coalescers[run_id] = StreamCoalescer(
                emitter=self.emitter,
                session_id=session_id,
                output_id=make_id("out"),
                coalesce_at="sentence",
            )

        self._coalescers[run_id].add_token(token)

    def on_llm_end(
        self,
        response: Any,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        """An LLM call finished."""
        # Flush the coalescer if streaming was used
        coalescer = self._coalescers.pop(run_id, None)
        if coalescer is not None:
            coalescer.finish()
        self._run_to_session.pop(run_id, None)

    def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        """An LLM call raised an exception."""
        # Drop any pending coalescer; the chain-level error handler will
        # emit the session.errored event
        coalescer = self._coalescers.pop(run_id, None)
        if coalescer is not None:
            try:
                coalescer.finish()
            except Exception:
                pass
        self._run_to_session.pop(run_id, None)

    # === Tool callbacks ===

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        inputs: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """A tool is about to be invoked."""
        session_id = self._find_session_for_run(parent_run_id) or self._find_session_for_run(
            run_id
        )
        if session_id is None:
            return

        tool_name = serialized.get("name", "unknown_tool")
        aaep_tool_call_id = make_id("call")
        self._run_to_tool_call[run_id] = aaep_tool_call_id
        self._run_to_tool_name[run_id] = tool_name
        self._run_to_session[run_id] = session_id

        # Risk classification: prefer override, then heuristic
        risk_level, irreversible = self._classify_tool(tool_name)

        # Args summary - prefer the structured inputs dict if available
        args_str = (
            safe_args_summary(inputs) if inputs else input_str[:1000]
        )

        self._transition(session_id, "calling_tool", f"Preparing to call {tool_name}.")

        self.emitter.tool_invoked(
            session_id=session_id,
            tool=tool_name,
            tool_call_id=aaep_tool_call_id,
            args_summary=args_str,
            risk_level=risk_level,
            irreversible=irreversible,
            summary_normal=f"Calling {tool_name}.",
        )

        self._session_tool_count[session_id] = (
            self._session_tool_count.get(session_id, 0) + 1
        )

    def on_tool_end(
        self,
        output: Any,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        """A tool finished successfully."""
        session_id = self._run_to_session.get(run_id)
        tool_call_id = self._run_to_tool_call.pop(run_id, None)
        tool_name = self._run_to_tool_name.pop(run_id, "unknown")

        if session_id is None or tool_call_id is None:
            return

        self.emitter.tool_completed(
            session_id=session_id,
            tool=tool_name,
            tool_call_id=tool_call_id,
            status="success",
            summary_normal=str(output)[:200],
        )
        # Transition back to thinking for any next step
        self._transition(session_id, "thinking", "Considering the result.")

    def on_tool_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        """A tool raised an exception."""
        session_id = self._run_to_session.get(run_id)
        tool_call_id = self._run_to_tool_call.pop(run_id, None)
        tool_name = self._run_to_tool_name.pop(run_id, "unknown")

        if session_id is None or tool_call_id is None:
            return

        status = "timeout" if isinstance(error, TimeoutError) else "error"
        self.emitter.tool_completed(
            session_id=session_id,
            tool=tool_name,
            tool_call_id=tool_call_id,
            status=status,
            error_message=str(error)[:1000],
        )

    # === Helpers ===

    def _transition(self, session_id: str, to_state: str, summary: str) -> None:
        """Emit state.changed only if the state actually differs."""
        from_state = self._session_state.get(session_id, "idle")
        if from_state == to_state:
            return
        self.emitter.state_changed(
            session_id=session_id,
            from_state=from_state,
            to_state=to_state,
            summary_normal=summary,
        )
        self._session_state[session_id] = to_state

    def _find_session_for_run(self, run_id: UUID | None) -> str | None:
        """Find the AAEP session_id for a LangChain run_id, walking up if needed."""
        if run_id is None:
            return None
        return self._run_to_session.get(run_id)

    def _classify_tool(self, tool_name: str) -> tuple[str, bool]:
        """Return (risk_level, irreversible) for a tool, using overrides first."""
        override = self.tool_risk_overrides.get(tool_name)
        if override == "high":
            return "high", True
        if override == "medium":
            return "medium", False
        if override == "low":
            return "low", False
        if tool_name in HIGH_RISK_TOOL_NAMES:
            return "high", True
        return classify_risk(tool_name)

    @staticmethod
    def _extract_user_input(inputs: dict[str, Any]) -> str:
        """Pull the user-facing input from a LangChain inputs dict."""
        for key in ("input", "question", "query", "user_message"):
            value = inputs.get(key)
            if isinstance(value, str) and value.strip():
                return value
        # Fallback: stringify the whole dict
        return str(inputs)[:500]

    def _cleanup_session(self, session_id: str) -> None:
        """Remove all per-session bookkeeping."""
        self._session_state.pop(session_id, None)
        self._session_tool_count.pop(session_id, None)
        self._session_start_time.pop(session_id, None)


# === Convenience factory ===

def make_aaep_handler(
    send_event,
    *,
    agent_id: str = "aaep-langchain-producer",
    agent_name: str = "AAEP LangChain Producer",
    model: str | None = None,
    tool_risk_overrides: dict[str, str] | None = None,
) -> LangChainAAEPHandler:
    """Create a LangChainAAEPHandler with sensible defaults."""
    return LangChainAAEPHandler(
        send_event=send_event,
        agent_id=agent_id,
        agent_name=agent_name,
        model=model,
        tool_risk_overrides=tool_risk_overrides,
    )


__all__ = ["LangChainAAEPHandler", "make_aaep_handler", "HIGH_RISK_TOOL_NAMES"]
