"""
globalPlugin.py — NVDA integration layer.

This is the actual NVDA add-on entry point. When packaged as a .nvda-addon
file and installed in NVDA, NVDA loads this module's GlobalPlugin class.

The module imports NVDA APIs with graceful fallback so it can be imported
outside NVDA for testing (the AAEPGlobalPlugin class will use stub
implementations when NVDA isn't available).
"""

from __future__ import annotations

import logging
import threading
from typing import Any

from aaep_nvda_subscriber.handler import (
    AAEPEventHandler,
    Configuration,
    SpeechPriority,
)
from aaep_nvda_subscriber.sse_client import AAEPSSEClient, send_reply

logger = logging.getLogger("aaep_nvda_subscriber.globalPlugin")


# === NVDA imports with graceful fallback ===

try:
    import globalPluginHandler
    import speech
    import addonHandler
    import ui
    import gui
    from scriptHandler import script
    from logHandler import log as nvda_log
    HAS_NVDA = True
    _BASE_CLASS: Any = globalPluginHandler.GlobalPlugin
    addonHandler.initTranslation()
except ImportError:
    HAS_NVDA = False
    _BASE_CLASS = object
    speech = None  # type: ignore[assignment]
    ui = None  # type: ignore[assignment]
    nvda_log = logger

    def script(**kwargs):  # type: ignore[no-redef]
        """Stub @script decorator for testing outside NVDA."""
        def decorator(func):
            func.__script_kwargs__ = kwargs
            return func
        return decorator


# === Priority mapping ===

def _nvda_priority(priority: SpeechPriority) -> Any:
    """Translate our SpeechPriority enum to NVDA's speech.priorities constants."""
    if not HAS_NVDA:
        return priority.value
    mapping = {
        SpeechPriority.NEXT: speech.priorities.Spri.NEXT,
        SpeechPriority.NOW: speech.priorities.Spri.NOW,
        SpeechPriority.LOW: speech.priorities.Spri.NEXT,  # NVDA has no LOW
    }
    return mapping.get(priority, speech.priorities.Spri.NEXT)


# === The plugin class ===

class GlobalPlugin(_BASE_CLASS):
    """
    AAEP Subscriber NVDA Global Plugin.

    Loaded automatically by NVDA when this add-on is installed. Subscribes
    to configured AAEP producers, routes their events to NVDA's speech
    engine, and provides keyboard gestures for replying to confirmations
    and clarifications.
    """

    scriptCategory = "AAEP Subscriber"

    def __init__(self):
        if HAS_NVDA:
            super().__init__()

        # Load configuration (from NVDA config when available, defaults otherwise)
        self.config = self._load_config()

        # Build the handler with NVDA-bound speech and reply callbacks
        self.handler = AAEPEventHandler(
            speech_callback=self._on_speak,
            reply_callback=self._on_reply,
            config=self.config,
        )

        # SSE clients (one per configured endpoint)
        self.clients: list[AAEPSSEClient] = []
        self._lock = threading.Lock()

        if HAS_NVDA:
            nvda_log.info("AAEP Subscriber plugin loaded")
        else:
            logger.info("AAEP Subscriber plugin loaded (no NVDA host detected)")

        # Auto-start if configured
        if self.config.__dict__.get("auto_start", True):
            self.start_subscriptions()

    def terminate(self):
        """Called by NVDA when the add-on is unloaded."""
        self.stop_subscriptions()
        if HAS_NVDA:
            super().terminate()

    # === Subscription management ===

    def start_subscriptions(self):
        """Connect to all configured AAEP producer endpoints."""
        endpoints = self.config.__dict__.get("endpoints", [])
        with self._lock:
            self.stop_subscriptions()
            for endpoint in endpoints:
                client = AAEPSSEClient(
                    endpoint=endpoint,
                    on_event=self.handler.handle,
                    on_status=lambda status, ep=endpoint: self._on_status(ep, status),
                )
                client.start()
                self.clients.append(client)

    def stop_subscriptions(self):
        """Disconnect from all producers."""
        for client in self.clients:
            client.stop(timeout=2.0)
        self.clients.clear()

    # === Speech and reply callbacks ===

    def _on_speak(self, text: str, priority: SpeechPriority) -> None:
        """Forward a handler speech command to NVDA's speech engine."""
        if not text:
            return
        if HAS_NVDA:
            speech.speak(
                [text],
                priority=_nvda_priority(priority),
            )
        else:
            logger.info("[mock-speech %s] %s", priority.value, text)

    def _on_reply(
        self,
        reply_token: str,
        message_type: str,
        payload: dict[str, Any],
    ) -> None:
        """Send a reply message back to the originating producer."""
        # Use the most-recently-active endpoint
        endpoints = self.config.__dict__.get("endpoints", [])
        if not endpoints:
            logger.warning("No endpoints configured; reply dropped")
            return
        # In a multi-endpoint setup we'd track which endpoint emitted the
        # awaiting event; for now we use the first configured endpoint.
        endpoint = endpoints[0]
        success = send_reply(
            endpoint=endpoint,
            reply_token=reply_token,
            message_type=message_type,
            payload=payload,
        )
        if not success and HAS_NVDA:
            ui.message("AAEP reply failed to send.")

    def _on_status(self, endpoint: str, status: str) -> None:
        """Surface connection status changes to the user (verbose mode only)."""
        if self.config.__dict__.get("verbose_status", False) and HAS_NVDA:
            ui.message(f"AAEP {endpoint}: {status}")
        logger.info("AAEP %s: %s", endpoint, status)

    # === Gesture scripts ===

    @script(
        description="Accept the pending AAEP confirmation",
        gesture="kb:NVDA+shift+a",
    )
    def script_accept_confirmation(self, gesture):  # type: ignore[no-untyped-def]
        sent = self.handler.on_accept_gesture()
        if not sent and HAS_NVDA:
            ui.message("No pending AAEP confirmation.")

    @script(
        description="Reject the pending AAEP confirmation",
        gesture="kb:NVDA+shift+r",
    )
    def script_reject_confirmation(self, gesture):  # type: ignore[no-untyped-def]
        sent = self.handler.on_reject_gesture()
        if not sent and HAS_NVDA:
            ui.message("No pending AAEP confirmation.")

    @script(
        description="Enter free-form response for AAEP clarification",
        gesture="kb:NVDA+shift+c",
    )
    def script_clarify_response(self, gesture):  # type: ignore[no-untyped-def]
        if HAS_NVDA:
            # In a real NVDA integration this would open a dialog; for the
            # prototype we use a stub.
            from gui.message import messageBox
            ui.message("Clarification dialog not yet implemented in v0.1.0.")

    @script(
        description="Toggle AAEP subscriptions on/off",
        gesture="kb:NVDA+shift+s",
    )
    def script_toggle_subscriptions(self, gesture):  # type: ignore[no-untyped-def]
        if self.clients:
            self.stop_subscriptions()
            if HAS_NVDA:
                ui.message("AAEP subscriptions paused.")
        else:
            self.start_subscriptions()
            if HAS_NVDA:
                ui.message("AAEP subscriptions resumed.")

    # Numbered option scripts for clarification
    for i in range(1, 10):
        exec(f"""
@script(
    description="Select AAEP clarification option {i}",
    gesture="kb:NVDA+shift+{i}",
)
def script_select_option_{i}(self, gesture):
    sent = self.handler.on_option_selected({i})
    if not sent and HAS_NVDA:
        ui.message("No pending AAEP clarification.")
""")

    # === Configuration ===

    def _load_config(self) -> Configuration:
        """Load configuration from NVDA's config system or defaults."""
        if HAS_NVDA:
            try:
                from gui.settingsDialogs import SettingsPanel  # noqa: F401
                # In production this would read from config.conf
                # For the prototype, use sensible defaults
                pass
            except ImportError:
                pass

        # Default configuration; users adjust in Settings dialog (not yet implemented)
        config = Configuration(
            preferred_languages=["en"],
            interrupt_on_critical=True,
            speak_progress_updates=False,
        )
        # Attach prototype fields for endpoints (not yet in Configuration dataclass)
        config.__dict__["endpoints"] = ["http://localhost:8080"]
        config.__dict__["auto_start"] = True
        config.__dict__["verbose_status"] = False
        return config
