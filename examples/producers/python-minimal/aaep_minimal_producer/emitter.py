"""
AAEP emitter helpers.

This module contains the core helpers used by AAEP producers:

- AAEPEmitter: one method per AAEP event type; emits via a callable
- StreamCoalescer: buffers streaming chunks and emits at boundaries
- make_id: generates AAEP-format identifiers
- classify_error_category: maps Python exceptions to AAEP error categories

These are deliberately small and explicit. The whole module is under 400 lines
and has no framework dependencies. Read it top to bottom and you'll understand
exactly how AAEP events are produced.
"""

from __future__ import annotations

import asyncio
import re
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable


CONTEXT_URL = "https://aaep-protocol.org/context/v1"
AAEP_VERSION = "1.0.0"

# ABNF-compliant ID prefixes (Chapter 3 §3.2)
ID_PREFIX_PATTERN = re.compile(r"^[a-z]+$")

# Risk classification
HIGH_RISK_TOOL_PATTERNS = (
    "send_email", "transfer_funds", "delete_record", "delete_file",
    "drop_table", "send_payment", "publish_post", "make_call",
)
MEDIUM_RISK_TOOL_PATTERNS = (
    "update_profile", "create_record", "send_message", "publish_draft",
)


def make_id(prefix: str) -> str:
    """
    Generate an AAEP-format identifier with the given prefix.

    Examples:
        make_id("evt")  -> "evt_8a3f5b22c91e4d7a"
        make_id("sess") -> "sess_2c91a7b4d23f1e88"
        make_id("rpl")  -> "rpl_4f8a2e7d9c1b6a3f"
    """
    if not ID_PREFIX_PATTERN.match(prefix):
        raise ValueError(f"ID prefix must be lowercase letters only, got {prefix!r}")
    # 16 hex chars = 8 random bytes; enough entropy for collision resistance
    return f"{prefix}_{secrets.token_hex(8)}"


def now_iso() -> str:
    """Return current time in AAEP-compliant RFC 3339 format with millisecond precision."""
    t = datetime.now(timezone.utc)
    return t.strftime("%Y-%m-%dT%H:%M:%S.") + f"{t.microsecond // 1000:03d}Z"


def classify_error_category(exc: BaseException) -> str:
    """
    Map a Python exception to an AAEP error_category value.

    Returns one of: timeout, network, authentication, authorization,
    rate_limit, invalid_input, internal, transient, unknown.
    """
    if isinstance(exc, asyncio.TimeoutError) or isinstance(exc, TimeoutError):
        return "timeout"
    if isinstance(exc, ConnectionError):
        return "network"
    if isinstance(exc, PermissionError):
        return "authorization"
    if isinstance(exc, (ValueError, TypeError, KeyError)):
        return "invalid_input"
    if isinstance(exc, MemoryError):
        return "internal"
    return "unknown"


def classify_risk(tool_name: str) -> tuple[str, bool]:
    """
    Classify a tool's risk level and reversibility based on its name.

    Returns (risk_level, irreversible).

    This is a heuristic. Real production code should use an explicit
    tool registry with metadata rather than name-matching.
    """
    lower = tool_name.lower()
    for pattern in HIGH_RISK_TOOL_PATTERNS:
        if pattern in lower:
            return "high", True
    for pattern in MEDIUM_RISK_TOOL_PATTERNS:
        if pattern in lower:
            return "medium", False
    return "low", False


def safe_args_summary(args: dict[str, Any], max_chars: int = 1000) -> str:
    """
    Produce a safe summary of tool arguments, redacting secret-looking values.

    Field names containing any of these substrings have their values redacted:
    password, secret, token, key, auth, credential
    """
    SECRET_FIELDS = ("password", "secret", "token", "key", "auth", "credential")

    parts = []
    for k, v in args.items():
        if any(s in k.lower() for s in SECRET_FIELDS):
            parts.append(f"{k}=[redacted]")
        else:
            v_str = str(v)
            if len(v_str) > 80:
                v_str = v_str[:77] + "..."
            parts.append(f"{k}={v_str}")
    return ", ".join(parts)[:max_chars]


# === Stream coalescing ===

@dataclass
class StreamCoalescer:
    """
    Buffers streaming tokens and emits agent.output.streaming events at
    coalesce boundaries (default: sentence boundaries).

    Usage:
        coalescer = StreamCoalescer(emitter, session_id="sess_x", output_id="out_y")
        coalescer.add_token("Hello ")
        coalescer.add_token("world. ")
        coalescer.add_token("How are you?")
        coalescer.finish()
    """

    emitter: "AAEPEmitter"
    session_id: str
    output_id: str
    coalesce_at: str = "sentence"  # one of: word, sentence, paragraph, completion
    language: str | None = None

    _buffer: str = field(default="", init=False)
    _position: int = field(default=0, init=False)
    _finished: bool = field(default=False, init=False)

    def add_token(self, token: str) -> None:
        """Add a token. May emit one or more events if coalesce boundaries are hit."""
        if self._finished:
            raise RuntimeError("Cannot add tokens to a finished coalescer")
        self._buffer += token
        self._flush_at_boundary()

    def finish(self) -> None:
        """Flush any remaining buffer and emit the final completion event."""
        if self._finished:
            return
        self._emit_chunk(self._buffer, complete=True)
        self._buffer = ""
        self._finished = True

    def _flush_at_boundary(self) -> None:
        """Emit events at every coalesce boundary present in the buffer."""
        boundaries = self._find_boundaries()
        for boundary_end in boundaries:
            chunk = self._buffer[:boundary_end]
            self._buffer = self._buffer[boundary_end:]
            self._emit_chunk(chunk, complete=False)

    def _find_boundaries(self) -> list[int]:
        """Find positions (end-indices) of coalesce boundaries in the buffer."""
        if self.coalesce_at == "completion":
            return []  # only flushed on .finish()
        if self.coalesce_at == "word":
            return [m.end() for m in re.finditer(r"\S+\s+", self._buffer)]
        if self.coalesce_at == "sentence":
            # End of sentence: ., !, ? followed by whitespace or end
            return [m.end() for m in re.finditer(r"[.!?](\s|$)", self._buffer)]
        if self.coalesce_at == "paragraph":
            return [m.end() for m in re.finditer(r"\n\n", self._buffer)]
        return []

    def _emit_chunk(self, chunk: str, *, complete: bool) -> None:
        if not chunk and not complete:
            return
        self.emitter.output_streaming(
            session_id=self.session_id,
            output_id=self.output_id,
            chunk=chunk,
            position=self._position,
            complete=complete,
            coalesce_hint=self.coalesce_at if not complete else "completion",
            language=self.language,
        )
        self._position += len(chunk)


# === The Emitter ===

# Type alias for the send-event callable
SendEventFn = Callable[[dict[str, Any]], Awaitable[None] | None]


class AAEPEmitter:
    """
    Emits AAEP events via a configured transport callback.

    The send_event callable receives a dict (a complete AAEP event) and must
    deliver it to subscribers. It can be sync or async; the emitter handles both.
    """

    def __init__(
        self,
        send_event: SendEventFn,
        *,
        agent_id: str = "aaep-minimal-producer",
        agent_version: str = "1.0.0",
        agent_name: str = "AAEP Minimal Producer",
        model: str | None = None,
    ):
        self._send = send_event
        self._sequence_numbers: dict[str, int] = {}
        self._reply_decisions: dict[str, asyncio.Future] = {}
        self.producer_info = {
            "agent_id": agent_id,
            "agent_version": agent_version,
            "agent_name": agent_name,
        }
        if model:
            self.producer_info["model"] = model

    # === Session lifecycle ===

    def start_session(
        self,
        *,
        summary_normal: str,
        request_text: str | None = None,
        requested_by: str | None = None,
        expected_duration_ms: int | None = None,
        tools_available: list[str] | None = None,
    ) -> str:
        """Emit agent.session.started; returns the new session_id."""
        session_id = make_id("sess")
        self._emit({
            "@context": CONTEXT_URL,
            "aaep_version": AAEP_VERSION,
            "type": "aaep:agent.session.started",
            "event_id": make_id("evt"),
            "session_id": session_id,
            "sequence_number": self._next_seq(session_id),
            "timestamp": now_iso(),
            "producer": dict(self.producer_info),
            "urgency": "normal",
            "summary_normal": summary_normal,
            **({"request_text": request_text} if request_text else {}),
            **({"requested_by": requested_by} if requested_by else {}),
            **({"expected_duration_ms": expected_duration_ms} if expected_duration_ms else {}),
            **({"tools_available": tools_available} if tools_available else {}),
        })
        return session_id

    def complete_session(
        self,
        *,
        session_id: str,
        summary_normal: str,
        duration_ms: int | None = None,
        tool_invocations_count: int | None = None,
    ) -> None:
        """Emit agent.session.completed."""
        self._emit({
            "@context": CONTEXT_URL,
            "type": "aaep:agent.session.completed",
            "event_id": make_id("evt"),
            "session_id": session_id,
            "sequence_number": self._next_seq(session_id),
            "timestamp": now_iso(),
            "producer": dict(self.producer_info),
            "urgency": "normal",
            "summary_normal": summary_normal,
            **({"duration_ms": duration_ms} if duration_ms is not None else {}),
            **({"tool_invocations_count": tool_invocations_count}
               if tool_invocations_count is not None else {}),
        })

    def error_session(
        self,
        *,
        session_id: str,
        error_category: str,
        summary_normal: str,
        error_message: str | None = None,
        recoverable: bool = False,
        remediation_hint: str | None = None,
    ) -> None:
        """Emit agent.session.errored with urgency='critical'."""
        self._emit({
            "@context": CONTEXT_URL,
            "type": "aaep:agent.session.errored",
            "event_id": make_id("evt"),
            "session_id": session_id,
            "sequence_number": self._next_seq(session_id),
            "timestamp": now_iso(),
            "producer": dict(self.producer_info),
            "urgency": "critical",  # MUST be critical per Chapter 4 §4.1.3
            "error_category": error_category,
            "summary_normal": summary_normal,
            **({"error_message": error_message} if error_message else {}),
            "recoverable": recoverable,
            **({"remediation_hint": remediation_hint} if remediation_hint else {}),
        })

    def cancelled_session(
        self,
        *,
        session_id: str,
        cancelled_by: str = "system",
        summary_normal: str = "Session cancelled.",
    ) -> None:
        """Emit agent.session.cancelled."""
        self._emit({
            "@context": CONTEXT_URL,
            "type": "aaep:agent.session.cancelled",
            "event_id": make_id("evt"),
            "session_id": session_id,
            "sequence_number": self._next_seq(session_id),
            "timestamp": now_iso(),
            "producer": dict(self.producer_info),
            "urgency": "normal",
            "cancelled_by": cancelled_by,
            "summary_normal": summary_normal,
        })

    # === State and progress ===

    def state_changed(
        self,
        *,
        session_id: str,
        from_state: str,
        to_state: str,
        summary_normal: str,
    ) -> None:
        """Emit agent.state.changed."""
        self._emit({
            "@context": CONTEXT_URL,
            "type": "aaep:agent.state.changed",
            "event_id": make_id("evt"),
            "session_id": session_id,
            "sequence_number": self._next_seq(session_id),
            "timestamp": now_iso(),
            "producer": dict(self.producer_info),
            "urgency": "normal",
            "from_state": from_state,
            "to_state": to_state,
            "summary_normal": summary_normal,
        })

    # === Tool invocations ===

    def tool_invoked(
        self,
        *,
        session_id: str,
        tool: str,
        tool_call_id: str,
        args_summary: str,
        risk_level: str = "low",
        irreversible: bool = False,
        summary_normal: str | None = None,
    ) -> None:
        """Emit agent.tool.invoked."""
        self._emit({
            "@context": CONTEXT_URL,
            "type": "aaep:agent.tool.invoked",
            "event_id": make_id("evt"),
            "session_id": session_id,
            "sequence_number": self._next_seq(session_id),
            "timestamp": now_iso(),
            "producer": dict(self.producer_info),
            "urgency": "normal",
            "tool": tool,
            "tool_call_id": tool_call_id,
            "args_summary": args_summary,
            "risk_level": risk_level,
            "irreversible": irreversible,
            "summary_normal": summary_normal or f"Calling {tool}.",
        })

    def tool_completed(
        self,
        *,
        session_id: str,
        tool: str,
        tool_call_id: str,
        status: str,
        summary_normal: str = "",
        error_message: str | None = None,
    ) -> None:
        """Emit agent.tool.completed. status must be 'success', 'error', or 'timeout'."""
        if status not in ("success", "error", "timeout"):
            raise ValueError(f"status must be success/error/timeout, got {status!r}")
        self._emit({
            "@context": CONTEXT_URL,
            "type": "aaep:agent.tool.completed",
            "event_id": make_id("evt"),
            "session_id": session_id,
            "sequence_number": self._next_seq(session_id),
            "timestamp": now_iso(),
            "producer": dict(self.producer_info),
            "urgency": "normal",
            "tool": tool,
            "tool_call_id": tool_call_id,
            "status": status,
            **({"summary_normal": summary_normal} if summary_normal else {}),
            **({"error_message": error_message} if error_message else {}),
        })

    # === Streaming output ===

    def output_streaming(
        self,
        *,
        session_id: str,
        output_id: str,
        chunk: str,
        position: int,
        complete: bool,
        coalesce_hint: str = "none",
        language: str | None = None,
    ) -> None:
        """Emit agent.output.streaming."""
        event = {
            "@context": CONTEXT_URL,
            "type": "aaep:agent.output.streaming",
            "event_id": make_id("evt"),
            "session_id": session_id,
            "sequence_number": self._next_seq(session_id),
            "timestamp": now_iso(),
            "producer": dict(self.producer_info),
            "urgency": "normal",
            "chunk": chunk,
            "position": position,
            "complete": complete,
            "coalesce_hint": coalesce_hint,
            "output_id": output_id,
        }
        if language:
            event["language"] = language
        self._emit(event)

    # === Confirmation ===

    def await_confirmation(
        self,
        *,
        session_id: str,
        action: str,
        consequence: str,
        timeout_seconds: int = 300,
        default_decision: str = "reject",
        risk_level: str = "low",
        irreversible: bool = False,
        summary_normal: str | None = None,
    ) -> str:
        """
        Emit agent.awaiting.confirmation; returns the reply_token for awaiting decision.

        Enforces the safety rule: irreversible+high or irreversible+medium MUST
        default to reject. The schema also enforces this, but we check at runtime
        as defense in depth.
        """
        if irreversible and risk_level in ("high", "medium") and default_decision != "reject":
            raise ValueError(
                f"Irreversible {risk_level}-risk confirmations MUST have "
                f"default_decision='reject' (got {default_decision!r}). "
                "This is enforced both by the schema and at runtime."
            )

        reply_token = make_id("rpl")
        self._reply_decisions[reply_token] = asyncio.Future()

        self._emit({
            "@context": CONTEXT_URL,
            "type": "aaep:agent.awaiting.confirmation",
            "event_id": make_id("evt"),
            "session_id": session_id,
            "sequence_number": self._next_seq(session_id),
            "timestamp": now_iso(),
            "producer": dict(self.producer_info),
            "urgency": "critical",  # MUST be critical per Chapter 4 §4.4.1
            "action": action,
            "consequence": consequence,
            "reply_token": reply_token,
            "timeout_seconds": timeout_seconds,
            "default_decision": default_decision,
            "risk_level": risk_level,
            "irreversible": irreversible,
            "summary_normal": summary_normal or f"Confirm: {action}",
        })
        return reply_token

    def submit_reply(self, reply_token: str, decision: str) -> None:
        """Called by the transport when a confirmation reply arrives."""
        future = self._reply_decisions.get(reply_token)
        if future and not future.done():
            future.set_result(decision)

    async def wait_for_decision(self, reply_token: str) -> str:
        """Block until the reply arrives (or timeout, handled by caller)."""
        future = self._reply_decisions.get(reply_token)
        if future is None:
            raise KeyError(f"Unknown reply_token: {reply_token}")
        try:
            return await future
        finally:
            self._reply_decisions.pop(reply_token, None)

    # === Internals ===

    def _next_seq(self, session_id: str) -> int:
        """Get the next sequence number for a session."""
        seq = self._sequence_numbers.get(session_id, 0)
        self._sequence_numbers[session_id] = seq + 1
        return seq

    def _emit(self, event: dict[str, Any]) -> None:
        """Internal: send the event through the configured transport."""
        result = self._send(event)
        if asyncio.iscoroutine(result):
            asyncio.create_task(result)
