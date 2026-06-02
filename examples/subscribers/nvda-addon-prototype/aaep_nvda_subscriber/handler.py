"""
handler.py — AAEP event-to-speech translation.

Converts AAEP events into instructions for NVDA's speech engine. Designed to
be NVDA-independent: the handler emits abstract "speak this with this
priority" commands that the NVDA integration layer translates to real
speech.speak() calls.

This separation makes the handler unit-testable without NVDA.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Protocol

logger = logging.getLogger("aaep_nvda_subscriber.handler")


class SpeechPriority(Enum):
    """Priority levels for spoken output, matching NVDA's speech.priorities."""

    NEXT = "next"          # Queue at end of current speech
    NOW = "now"            # Interrupt current speech, speak immediately
    LOW = "low"            # Queue at low priority (background info)


@dataclass
class Configuration:
    """User preferences for the AAEP NVDA subscriber."""

    preferred_languages: list[str] = field(default_factory=lambda: ["en"])
    interrupt_on_critical: bool = True
    speak_progress_updates: bool = False
    accept_gesture: str = "NVDA+Shift+A"
    reject_gesture: str = "NVDA+Shift+R"
    clarify_gesture: str = "NVDA+Shift+C"
    confirmation_timeout_warning_seconds: int = 30


class SpeechCallback(Protocol):
    """Interface a host (NVDA or test) provides to actually emit speech."""

    def __call__(
        self,
        text: str,
        priority: SpeechPriority,
    ) -> None: ...


class ReplyCallback(Protocol):
    """Interface for sending an AAEP reply message back to the producer."""

    def __call__(
        self,
        reply_token: str,
        message_type: str,
        payload: dict[str, Any],
    ) -> None: ...


class AAEPEventHandler:
    """
    Translates AAEP events into NVDA speech commands.

    State machine:
        - Idle: pass events to speak callback
        - Awaiting reply: store reply_token, wait for user gesture
        - On gesture: invoke reply callback, return to idle
    """

    def __init__(
        self,
        *,
        speech_callback: SpeechCallback,
        reply_callback: ReplyCallback,
        config: Configuration | None = None,
    ):
        self.config = config or Configuration()
        self._speak = speech_callback
        self._reply = reply_callback
        self._pending_reply_token: str | None = None
        self._pending_reply_type: str | None = None
        self._pending_options: list[str] = []

    # === Main event dispatch ===

    def handle(self, event: dict[str, Any]) -> None:
        """Process one AAEP event."""
        event_type = event.get("type", "")
        urgency = event.get("urgency", "normal")
        priority = self._priority_for(event_type, urgency)
        summary = self._select_text(event)

        try:
            dispatch = self._dispatch.get(event_type)
            if dispatch is not None:
                dispatch(self, event, summary, priority)
            else:
                # Unknown event type: just speak the summary if there is one
                if summary:
                    self._speak(summary, priority)
        except Exception:
            logger.exception("Error handling event %s", event_type)

    # === Per-event-type handlers ===

    def _on_session_started(self, event, summary, priority) -> None:
        if summary:
            self._speak(summary, priority)

    def _on_session_completed(self, event, summary, priority) -> None:
        if summary:
            self._speak(summary, priority)
        self._clear_pending_reply()

    def _on_session_errored(self, event, summary, priority) -> None:
        # Always announce errors, even if user has progress disabled
        text = summary or "Agent error."
        recoverable = event.get("recoverable", False)
        if recoverable:
            text += " (Recoverable.)"
        self._speak(text, SpeechPriority.NOW)
        self._clear_pending_reply()

    def _on_session_cancelled(self, event, summary, priority) -> None:
        self._speak(summary or "Session cancelled.", priority)
        self._clear_pending_reply()

    def _on_state_changed(self, event, summary, priority) -> None:
        # State changes are background info; only speak if user opted in
        if self.config.speak_progress_updates and summary:
            self._speak(summary, SpeechPriority.LOW)

    def _on_progress_updated(self, event, summary, priority) -> None:
        if self.config.speak_progress_updates and summary:
            self._speak(summary, SpeechPriority.LOW)

    def _on_tool_invoked(self, event, summary, priority) -> None:
        # Tool invocations: speak if normal urgency or higher
        if summary:
            self._speak(summary, priority)

    def _on_tool_completed(self, event, summary, priority) -> None:
        status = event.get("status", "unknown")
        if status != "success" or self.config.speak_progress_updates:
            if summary:
                self._speak(summary, priority)

    def _on_output_streaming(self, event, summary, priority) -> None:
        # Streaming output: speak the chunk text directly
        chunk = event.get("chunk", "")
        if chunk:
            self._speak(chunk, SpeechPriority.NEXT)

    def _on_awaiting_confirmation(self, event, summary, priority) -> None:
        # Critical: interrupt, announce, await gesture
        self._pending_reply_token = event.get("reply_token")
        self._pending_reply_type = "confirmation.reply"
        action = event.get("action", "")
        consequence = event.get("consequence", "")
        prompt = (
            f"{summary or 'Confirmation needed.'} "
            f"Action: {action}. {consequence} "
            f"Press {self.config.accept_gesture} to accept, "
            f"{self.config.reject_gesture} to reject."
        )
        self._speak(prompt, SpeechPriority.NOW)

    def _on_awaiting_clarification(self, event, summary, priority) -> None:
        self._pending_reply_token = event.get("reply_token")
        self._pending_reply_type = "clarification.reply"
        self._pending_options = event.get("options", []) or []
        question = event.get("question", summary or "Clarification needed.")
        parts = [question]
        if self._pending_options:
            parts.append("Options:")
            for i, option in enumerate(self._pending_options, start=1):
                parts.append(f"{i}: {option}")
            parts.append(
                f"Press NVDA+Shift+1 through NVDA+Shift+9 to select, "
                f"or {self.config.clarify_gesture} for free-form."
            )
        else:
            parts.append(f"Press {self.config.clarify_gesture} to respond.")
        self._speak(" ".join(parts), SpeechPriority.NOW)

    def _on_handoff_requested(self, event, summary, priority) -> None:
        text = summary or "Agent requesting handoff."
        target = event.get("handoff_target", "")
        reason = event.get("reason", "")
        if target:
            text += f" Target: {target}."
        if reason:
            text += f" Reason: {reason}."
        self._speak(text, SpeechPriority.NOW)

    # === Gesture responses ===

    def on_accept_gesture(self) -> bool:
        """User pressed the accept gesture. Returns True if a reply was sent."""
        if self._pending_reply_token and self._pending_reply_type == "confirmation.reply":
            self._reply(self._pending_reply_token, "confirmation.reply", {"decision": "accept"})
            self._speak("Accepted.", SpeechPriority.NOW)
            self._clear_pending_reply()
            return True
        return False

    def on_reject_gesture(self) -> bool:
        """User pressed the reject gesture. Returns True if a reply was sent."""
        if self._pending_reply_token and self._pending_reply_type == "confirmation.reply":
            self._reply(self._pending_reply_token, "confirmation.reply", {"decision": "reject"})
            self._speak("Rejected.", SpeechPriority.NOW)
            self._clear_pending_reply()
            return True
        return False

    def on_option_selected(self, option_index: int) -> bool:
        """User selected a numbered clarification option (1-based)."""
        if (self._pending_reply_token
                and self._pending_reply_type == "clarification.reply"
                and 1 <= option_index <= len(self._pending_options)):
            response = self._pending_options[option_index - 1]
            self._reply(self._pending_reply_token, "clarification.reply", {"response": response})
            self._speak(f"Selected: {response}", SpeechPriority.NOW)
            self._clear_pending_reply()
            return True
        return False

    def on_freeform_response(self, text: str) -> bool:
        """User entered a free-form clarification response."""
        if self._pending_reply_token and self._pending_reply_type == "clarification.reply":
            self._reply(self._pending_reply_token, "clarification.reply", {"response": text})
            self._speak("Response sent.", SpeechPriority.NOW)
            self._clear_pending_reply()
            return True
        return False

    # === Helpers ===

    def _clear_pending_reply(self) -> None:
        self._pending_reply_token = None
        self._pending_reply_type = None
        self._pending_options = []

    def _priority_for(self, event_type: str, urgency: str) -> SpeechPriority:
        if urgency == "critical" and self.config.interrupt_on_critical:
            return SpeechPriority.NOW
        return SpeechPriority.NEXT

    def _select_text(self, event: dict[str, Any]) -> str:
        # Use the multilingual extension if available and a preferred language matches
        event_lang = event.get("language", "en")
        if event_lang in self.config.preferred_languages:
            return event.get("summary_normal", "")
        # Try to fall back through preferred languages via extension table
        try:
            from aaep_ext_african_languages import select_summary
            return select_summary(
                event,
                preferred_languages=self.config.preferred_languages,
            )
        except ImportError:
            return event.get("summary_normal", "")

    # === Dispatch table ===

    _dispatch: dict[str, Callable] = {
        "aaep:agent.session.started": lambda self, e, s, p: self._on_session_started(e, s, p),
        "aaep:agent.session.completed": lambda self, e, s, p: self._on_session_completed(e, s, p),
        "aaep:agent.session.errored": lambda self, e, s, p: self._on_session_errored(e, s, p),
        "aaep:agent.session.cancelled": lambda self, e, s, p: self._on_session_cancelled(e, s, p),
        "aaep:agent.state.changed": lambda self, e, s, p: self._on_state_changed(e, s, p),
        "aaep:agent.progress.updated": lambda self, e, s, p: self._on_progress_updated(e, s, p),
        "aaep:agent.tool.invoked": lambda self, e, s, p: self._on_tool_invoked(e, s, p),
        "aaep:agent.tool.completed": lambda self, e, s, p: self._on_tool_completed(e, s, p),
        "aaep:agent.output.streaming": lambda self, e, s, p: self._on_output_streaming(e, s, p),
        "aaep:agent.awaiting.confirmation": lambda self, e, s, p: self._on_awaiting_confirmation(e, s, p),
        "aaep:agent.awaiting.clarification": lambda self, e, s, p: self._on_awaiting_clarification(e, s, p),
        "aaep:agent.handoff.requested": lambda self, e, s, p: self._on_handoff_requested(e, s, p),
    }
