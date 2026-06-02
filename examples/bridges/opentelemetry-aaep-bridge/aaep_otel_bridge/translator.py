"""
translator.py — AAEP → OpenTelemetry translator.

Stateful translator that consumes AAEP events one at a time and emits
the corresponding OTEL spans, span events, and attributes.

The translator is privacy-preserving by default: text content
(user messages, output chunks, args beyond redacted summaries) is replaced
with counts. See README.md §"Privacy-preserving translation" for details.

When the opentelemetry SDK isn't installed, falls back to a console-printing
mock tracer so the translator can be inspected without the dependency.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from typing import Any

try:
    from opentelemetry import trace
    from opentelemetry.trace import Status, StatusCode, Span
    HAS_OTEL = True
except ImportError:
    HAS_OTEL = False
    trace = None  # type: ignore[assignment]
    Status = StatusCode = Span = None  # type: ignore[assignment,misc]


logger = logging.getLogger("aaep_otel_bridge.translator")


# AAEP event types that warrant CRITICAL severity in OTEL
_CRITICAL_EVENT_TYPES = frozenset({
    "aaep:agent.session.errored",
    "aaep:agent.awaiting.confirmation",
    "aaep:agent.awaiting.clarification",
    "aaep:agent.handoff.requested",
})


@dataclass
class SessionSpanState:
    """Tracks open OTEL spans for one AAEP session."""

    session_id: str
    session_span: Any = None  # opentelemetry.trace.Span when HAS_OTEL
    session_context: Any = None  # context manager for the session span
    open_tool_spans: dict[str, Any] = field(default_factory=dict)
    open_tool_contexts: dict[str, Any] = field(default_factory=dict)


class _MockTracer:
    """Fallback when opentelemetry isn't installed; prints to logger."""

    def start_as_current_span(self, name, **kwargs):
        return _MockSpan(name)

    def start_span(self, name, **kwargs):
        return _MockSpan(name)


class _MockSpan:
    def __init__(self, name: str):
        self.name = name
        self.events: list[tuple[str, dict]] = []
        self.attributes: dict[str, Any] = {}
        self.status_code = "Ok"

    def __enter__(self):
        logger.debug("[mock-otel] span START: %s", self.name)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        logger.debug(
            "[mock-otel] span END:   %s  status=%s  events=%d",
            self.name, self.status_code, len(self.events),
        )

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def add_event(self, name: str, attributes: dict | None = None) -> None:
        self.events.append((name, attributes or {}))

    def set_status(self, status: Any) -> None:
        self.status_code = str(status)

    def end(self) -> None:
        logger.debug("[mock-otel] span END:   %s  status=%s", self.name, self.status_code)


# === The translator ===

class AAEPToOTELTranslator:
    """
    Translate AAEP events into OTEL spans + span events.

    Maintain state across events: a session span is opened on
    session.started, child tool spans are opened on tool.invoked,
    everything closes on the corresponding completion/error event.

    Privacy: text content is replaced with size/hash; only safe attributes
    are forwarded.
    """

    def __init__(self, tracer: Any | None = None):
        if tracer is not None:
            self.tracer = tracer
        elif HAS_OTEL:
            self.tracer = trace.get_tracer("aaep-otel-bridge", "1.0.0")
        else:
            logger.warning("OpenTelemetry SDK not installed; using mock tracer")
            self.tracer = _MockTracer()
        self.sessions: dict[str, SessionSpanState] = {}

    # === Entry point ===

    def translate(self, event: dict[str, Any]) -> None:
        """Process one AAEP event."""
        event_type = event.get("type", "")
        session_id = event.get("session_id")
        if not isinstance(session_id, str):
            logger.debug("Skipping event without session_id: %s", event_type)
            return

        handler = self._handlers.get(event_type)
        if handler is None:
            logger.debug("No handler for event type: %s", event_type)
            return
        try:
            handler(self, event, session_id)
        except Exception:
            logger.exception("Error translating event: %s", event_type)

    # === Session lifecycle ===

    def _on_session_started(self, event: dict[str, Any], session_id: str) -> None:
        if session_id in self.sessions:
            return
        state = SessionSpanState(session_id=session_id)
        span = self.tracer.start_span("aaep.session")
        span.set_attribute("aaep.session_id", session_id)
        producer = event.get("producer", {})
        if isinstance(producer, dict):
            for key in ("agent_id", "agent_name", "agent_version", "model"):
                if key in producer:
                    span.set_attribute(f"aaep.{key}", producer[key])
        if "requested_by" in event:
            span.set_attribute("aaep.requested_by", event["requested_by"])
        request_text = event.get("request_text")
        if isinstance(request_text, str):
            span.set_attribute("aaep.request_text_length", len(request_text))
            span.set_attribute("aaep.request_text_hash", _short_hash(request_text))
        state.session_span = span
        self.sessions[session_id] = state

    def _on_session_completed(self, event: dict[str, Any], session_id: str) -> None:
        state = self.sessions.pop(session_id, None)
        if state is None:
            return
        span = state.session_span
        for key in ("duration_ms", "tool_invocations_count"):
            if key in event:
                span.set_attribute(f"aaep.{key}", event[key])
        if HAS_OTEL:
            span.set_status(Status(StatusCode.OK))
        else:
            span.set_status("Ok")
        span.end()

    def _on_session_errored(self, event: dict[str, Any], session_id: str) -> None:
        state = self.sessions.pop(session_id, None)
        if state is None:
            return
        span = state.session_span
        span.set_attribute("aaep.error_category", event.get("error_category", "unknown"))
        if "error_message" in event:
            span.set_attribute("aaep.error_message", event["error_message"])
        span.set_attribute("aaep.recoverable", event.get("recoverable", False))
        if "remediation_hint" in event:
            span.set_attribute("aaep.remediation_hint", event["remediation_hint"])
        self._add_critical_event(span, "session.errored", event)
        if HAS_OTEL:
            span.set_status(Status(StatusCode.ERROR, event.get("summary_normal", "")))
        else:
            span.set_status("Error")
        span.end()

    def _on_session_cancelled(self, event: dict[str, Any], session_id: str) -> None:
        state = self.sessions.pop(session_id, None)
        if state is None:
            return
        span = state.session_span
        span.set_attribute("aaep.cancelled_by", event.get("cancelled_by", "system"))
        if "cancellation_reason" in event:
            span.set_attribute("aaep.cancellation_reason", event["cancellation_reason"])
        if HAS_OTEL:
            span.set_status(Status(StatusCode.OK, "cancelled"))
        else:
            span.set_status("Cancelled")
        span.end()

    # === State and progress ===

    def _on_state_changed(self, event: dict[str, Any], session_id: str) -> None:
        state = self.sessions.get(session_id)
        if state is None:
            return
        state.session_span.add_event("state.changed", attributes={
            "aaep.from_state": event.get("from_state", ""),
            "aaep.to_state": event.get("to_state", ""),
        })

    def _on_progress_updated(self, event: dict[str, Any], session_id: str) -> None:
        state = self.sessions.get(session_id)
        if state is None:
            return
        attrs = {}
        for key in ("progress_percent", "estimated_remaining_ms"):
            if key in event:
                attrs[f"aaep.{key}"] = event[key]
        if "progress_message" in event:
            attrs["aaep.progress_message"] = event["progress_message"]
        state.session_span.add_event("progress", attributes=attrs)

    # === Tool spans ===

    def _on_tool_invoked(self, event: dict[str, Any], session_id: str) -> None:
        state = self.sessions.get(session_id)
        if state is None:
            return
        tool_call_id = event.get("tool_call_id", "")
        tool_name = event.get("tool", "<unknown>")
        span = self.tracer.start_span(f"aaep.tool.{tool_name}")
        span.set_attribute("aaep.tool", tool_name)
        span.set_attribute("aaep.tool_call_id", tool_call_id)
        span.set_attribute("aaep.risk_level", event.get("risk_level", "low"))
        span.set_attribute("aaep.irreversible", event.get("irreversible", False))
        # args_summary is already redacted by the producer; safe to forward
        if "args_summary" in event:
            span.set_attribute("aaep.args_summary", event["args_summary"])
        state.open_tool_spans[tool_call_id] = span

    def _on_tool_completed(self, event: dict[str, Any], session_id: str) -> None:
        state = self.sessions.get(session_id)
        if state is None:
            return
        tool_call_id = event.get("tool_call_id", "")
        span = state.open_tool_spans.pop(tool_call_id, None)
        if span is None:
            return
        status = event.get("status", "unknown")
        span.set_attribute("aaep.status", status)
        if "error_message" in event:
            span.set_attribute("aaep.error_message", event["error_message"])
        if HAS_OTEL:
            if status == "success":
                span.set_status(Status(StatusCode.OK))
            else:
                span.set_status(Status(StatusCode.ERROR, status))
        else:
            span.set_status("Ok" if status == "success" else "Error")
        span.end()

    # === Streaming and awaiting events ===

    def _on_output_streaming(self, event: dict[str, Any], session_id: str) -> None:
        state = self.sessions.get(session_id)
        if state is None:
            return
        chunk = event.get("chunk", "")
        # Privacy: forward size only, not content
        state.session_span.add_event("output.chunk", attributes={
            "aaep.chunk_size_bytes": len(chunk.encode("utf-8")) if isinstance(chunk, str) else 0,
            "aaep.position": event.get("position", 0),
            "aaep.complete": event.get("complete", False),
            "aaep.coalesce_hint": event.get("coalesce_hint", "none"),
        })

    def _on_awaiting_confirmation(self, event: dict[str, Any], session_id: str) -> None:
        state = self.sessions.get(session_id)
        if state is None:
            return
        attrs = {
            "aaep.severity_text": "CRITICAL",
            "aaep.severity_number": 21,
            "aaep.urgency": "critical",
            "aaep.action": event.get("action", ""),
            "aaep.consequence": event.get("consequence", ""),
            "aaep.risk_level": event.get("risk_level", "unknown"),
            "aaep.irreversible": event.get("irreversible", False),
            "aaep.default_decision": event.get("default_decision", "reject"),
            "aaep.timeout_seconds": event.get("timeout_seconds", 0),
        }
        state.session_span.add_event("confirmation.requested", attributes=attrs)

    def _on_awaiting_clarification(self, event: dict[str, Any], session_id: str) -> None:
        state = self.sessions.get(session_id)
        if state is None:
            return
        attrs = {
            "aaep.severity_text": "CRITICAL",
            "aaep.severity_number": 21,
            "aaep.urgency": "critical",
            "aaep.question_length": len(event.get("question", "")),
            "aaep.has_options": "options" in event and bool(event["options"]),
            "aaep.multi_select": event.get("multi_select", False),
            "aaep.free_form_allowed": event.get("free_form_allowed", True),
            "aaep.timeout_seconds": event.get("timeout_seconds", 0),
        }
        state.session_span.add_event("clarification.requested", attributes=attrs)

    def _on_handoff_requested(self, event: dict[str, Any], session_id: str) -> None:
        state = self.sessions.get(session_id)
        if state is None:
            return
        attrs = {
            "aaep.severity_text": "CRITICAL",
            "aaep.severity_number": 21,
            "aaep.urgency": "critical",
            "aaep.reason": event.get("reason", ""),
            "aaep.handoff_target": event.get("handoff_target", ""),
        }
        if "context_summary" in event:
            attrs["aaep.context_summary"] = event["context_summary"]
        state.session_span.add_event("handoff.requested", attributes=attrs)

    # === Helper ===

    def _add_critical_event(self, span: Any, name: str, event: dict[str, Any]) -> None:
        """Add a generic CRITICAL-severity event to a span."""
        span.add_event(name, attributes={
            "aaep.severity_text": "CRITICAL",
            "aaep.severity_number": 21,
            "aaep.urgency": event.get("urgency", "critical"),
            "aaep.summary": event.get("summary_normal", ""),
        })

    # === Dispatch table ===

    _handlers: dict[str, Any] = {
        "aaep:agent.session.started": lambda self, e, s: self._on_session_started(e, s),
        "aaep:agent.session.completed": lambda self, e, s: self._on_session_completed(e, s),
        "aaep:agent.session.errored": lambda self, e, s: self._on_session_errored(e, s),
        "aaep:agent.session.cancelled": lambda self, e, s: self._on_session_cancelled(e, s),
        "aaep:agent.state.changed": lambda self, e, s: self._on_state_changed(e, s),
        "aaep:agent.progress.updated": lambda self, e, s: self._on_progress_updated(e, s),
        "aaep:agent.tool.invoked": lambda self, e, s: self._on_tool_invoked(e, s),
        "aaep:agent.tool.completed": lambda self, e, s: self._on_tool_completed(e, s),
        "aaep:agent.output.streaming": lambda self, e, s: self._on_output_streaming(e, s),
        "aaep:agent.awaiting.confirmation": lambda self, e, s: self._on_awaiting_confirmation(e, s),
        "aaep:agent.awaiting.clarification": lambda self, e, s: self._on_awaiting_clarification(e, s),
        "aaep:agent.handoff.requested": lambda self, e, s: self._on_handoff_requested(e, s),
    }


def _short_hash(text: str) -> str:
    """SHA-256 hex digest, truncated to 16 chars (for privacy-preserving identification)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
