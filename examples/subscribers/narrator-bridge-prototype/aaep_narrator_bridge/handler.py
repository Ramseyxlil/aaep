"""
handler.py — AAEP event routing for the Narrator bridge.

Translates AAEP events into Narrator announcement requests. Unlike NVDA's
direct speech API, Narrator integration goes through the announcer's UIA
window, so the handler's output is "announcement strings" with priority
hints rather than direct speech.speak() calls.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Protocol

logger = logging.getLogger("aaep_narrator_bridge.handler")


class AnnouncementPriority(Enum):
    """Priority hint for the UIA announcer."""

    POLITE = "polite"        # Queue; Narrator reads when current speech finishes
    ASSERTIVE = "assertive"  # Interrupt; Narrator reads now
    LOG_ONLY = "log_only"    # Don't announce; only log (e.g., low-value progress)


@dataclass
class Configuration:
    """User preferences for the Narrator bridge."""

    preferred_languages: list[str] = field(default_factory=lambda: ["en"])
    announce_normal_events: bool = True
    announce_progress: bool = False
    play_critical_chime: bool = True
    log_file_path: str | None = None
    auto_reject_after_seconds: int = 0  # 0 = wait indefinitely
    auto_connect_on_start: bool = True
    endpoints: list[str] = field(default_factory=lambda: ["http://localhost:8080"])


class AnnouncerCallback(Protocol):
    """Interface the announcer provides to the handler."""

    def __call__(
        self,
        text: str,
        priority: AnnouncementPriority,
    ) -> None: ...


class ReplyCallback(Protocol):
    """Interface for sending replies back to the AAEP producer."""

    def __call__(
        self,
        reply_token: str,
        message_type: str,
        payload: dict[str, Any],
    ) -> None: ...


class ConfirmCallback(Protocol):
    """Interface for showing a confirmation dialog and getting user response."""

    def __call__(
        self,
        action: str,
        consequence: str,
        timeout_seconds: int,
    ) -> str: ...  # returns "accept" or "reject"


class NarratorEventHandler:
    """
    Translates AAEP events into announcement requests and confirmation
    dialogs.

    Compared to the NVDA handler, this is simpler because the announcer
    layer handles the actual screen reader integration via UIA. The handler
    decides what to say and which priority to use; the announcer figures
    out how to expose it to Narrator.
    """

    def __init__(
        self,
        *,
        announce: AnnouncerCallback,
        reply: ReplyCallback,
        confirm_dialog: ConfirmCallback | None = None,
        config: Configuration | None = None,
    ):
        self.config = config or Configuration()
        self._announce = announce
        self._reply = reply
        self._confirm_dialog = confirm_dialog

    def handle(self, event: dict[str, Any]) -> None:
        """Process one AAEP event."""
        event_type = event.get("type", "")
        urgency = event.get("urgency", "normal")
        priority = self._priority_for(event_type, urgency)
        text = self._select_text(event)

        try:
            handler = self._dispatch.get(event_type)
            if handler is None:
                if text:
                    self._announce(text, priority)
                return
            handler(self, event, text, priority)
        except Exception:
            logger.exception("Error handling event: %s", event_type)

    # === Per-event handlers ===

    def _on_session_started(self, event, text, priority) -> None:
        if self.config.announce_normal_events and text:
            self._announce(text, priority)

    def _on_session_completed(self, event, text, priority) -> None:
        if self.config.announce_normal_events and text:
            self._announce(text, priority)

    def _on_session_errored(self, event, text, priority) -> None:
        msg = text or "Agent error."
        recoverable = event.get("recoverable", False)
        if recoverable:
            msg += " (Recoverable.)"
        self._announce(msg, AnnouncementPriority.ASSERTIVE)

    def _on_session_cancelled(self, event, text, priority) -> None:
        self._announce(text or "Session cancelled.", priority)

    def _on_state_changed(self, event, text, priority) -> None:
        if self.config.announce_progress and text:
            self._announce(text, AnnouncementPriority.LOG_ONLY)

    def _on_progress_updated(self, event, text, priority) -> None:
        if self.config.announce_progress and text:
            self._announce(text, AnnouncementPriority.LOG_ONLY)

    def _on_tool_invoked(self, event, text, priority) -> None:
        if self.config.announce_normal_events and text:
            self._announce(text, priority)

    def _on_tool_completed(self, event, text, priority) -> None:
        status = event.get("status", "unknown")
        if status != "success" or self.config.announce_progress:
            if text:
                self._announce(text, priority)

    def _on_output_streaming(self, event, text, priority) -> None:
        chunk = event.get("chunk", "")
        if chunk:
            self._announce(chunk, AnnouncementPriority.POLITE)

    def _on_awaiting_confirmation(self, event, text, priority) -> None:
        action = event.get("action", "")
        consequence = event.get("consequence", "")
        timeout = event.get("timeout_seconds", 300)
        reply_token = event.get("reply_token", "")

        if not reply_token:
            logger.warning("awaiting.confirmation without reply_token; cannot respond")
            return

        # Announce immediately so Narrator surfaces it
        full_text = (
            f"Confirmation required: {action}. {consequence} "
            f"A dialog will appear; choose Accept or Reject."
        )
        self._announce(full_text, AnnouncementPriority.ASSERTIVE)

        # Show the confirmation dialog (synchronous; blocks until user replies
        # or timeout)
        if self._confirm_dialog is not None:
            decision = self._confirm_dialog(action, consequence, timeout)
        else:
            # No dialog available — use auto-reject fallback
            decision = "reject"
            logger.warning(
                "No confirmation dialog available; defaulting to reject "
                "(set up confirm_dialog to enable interactive flow)",
            )

        self._reply(reply_token, "confirmation.reply", {"decision": decision})
        self._announce(
            "Accepted." if decision == "accept" else "Rejected.",
            AnnouncementPriority.ASSERTIVE,
        )

    def _on_awaiting_clarification(self, event, text, priority) -> None:
        question = event.get("question", text or "Clarification needed.")
        # For the prototype, we don't implement a full clarification dialog.
        # We announce the question and let the user respond through whatever
        # configured input channel exists. Future versions: open a text-input
        # dialog with options as buttons.
        self._announce(
            f"{question} (Clarification UI not yet implemented in v0.1.)",
            AnnouncementPriority.ASSERTIVE,
        )

    def _on_handoff_requested(self, event, text, priority) -> None:
        target = event.get("handoff_target", "")
        reason = event.get("reason", "")
        msg = text or "Agent requesting handoff."
        if target:
            msg += f" Target: {target}."
        if reason:
            msg += f" Reason: {reason}."
        self._announce(msg, AnnouncementPriority.ASSERTIVE)

    # === Helpers ===

    def _priority_for(
        self,
        event_type: str,
        urgency: str,
    ) -> AnnouncementPriority:
        if urgency == "critical":
            return AnnouncementPriority.ASSERTIVE
        return AnnouncementPriority.POLITE

    def _select_text(self, event: dict[str, Any]) -> str:
        event_lang = event.get("language", "en")
        if event_lang in self.config.preferred_languages:
            return event.get("summary_normal", "") or ""
        # Try the multilingual extension
        try:
            from aaep_ext_african_languages import select_summary
            return select_summary(
                event,
                preferred_languages=self.config.preferred_languages,
            )
        except ImportError:
            return event.get("summary_normal", "") or ""

    # === Dispatch table ===

    _dispatch: dict[str, Callable] = {
        "aaep:agent.session.started": lambda self, e, t, p: self._on_session_started(e, t, p),
        "aaep:agent.session.completed": lambda self, e, t, p: self._on_session_completed(e, t, p),
        "aaep:agent.session.errored": lambda self, e, t, p: self._on_session_errored(e, t, p),
        "aaep:agent.session.cancelled": lambda self, e, t, p: self._on_session_cancelled(e, t, p),
        "aaep:agent.state.changed": lambda self, e, t, p: self._on_state_changed(e, t, p),
        "aaep:agent.progress.updated": lambda self, e, t, p: self._on_progress_updated(e, t, p),
        "aaep:agent.tool.invoked": lambda self, e, t, p: self._on_tool_invoked(e, t, p),
        "aaep:agent.tool.completed": lambda self, e, t, p: self._on_tool_completed(e, t, p),
        "aaep:agent.output.streaming": lambda self, e, t, p: self._on_output_streaming(e, t, p),
        "aaep:agent.awaiting.confirmation": lambda self, e, t, p: self._on_awaiting_confirmation(e, t, p),
        "aaep:agent.awaiting.clarification": lambda self, e, t, p: self._on_awaiting_clarification(e, t, p),
        "aaep:agent.handoff.requested": lambda self, e, t, p: self._on_handoff_requested(e, t, p),
    }
