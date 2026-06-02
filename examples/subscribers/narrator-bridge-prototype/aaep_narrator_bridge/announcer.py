"""
announcer.py — UIA announcement window for Narrator.

Creates a hidden window with the proper Windows UI Automation properties
that Narrator monitors. When announcement text is updated, Narrator picks
up the change through the accessibility tree and announces it.

This module has three operating modes:
    1. PRODUCTION (Windows + pywin32): real UIA via Windows API
    2. FALLBACK (Windows + tkinter): tk window with accessibility attributes
    3. MOCK (any platform): log-only mode for testing and inspection

The mode is selected automatically based on what's installed. Use
NarratorAnnouncer.mode to inspect.
"""

from __future__ import annotations

import logging
import platform
import sys
from threading import Event
from typing import Any

from aaep_narrator_bridge.handler import AnnouncementPriority

logger = logging.getLogger("aaep_narrator_bridge.announcer")


# === Mode detection ===

_IS_WINDOWS = sys.platform == "win32" or platform.system() == "Windows"

try:
    if _IS_WINDOWS:
        import win32gui  # type: ignore[import-untyped]
        import win32con  # type: ignore[import-untyped]
        HAS_WIN32 = True
    else:
        HAS_WIN32 = False
except ImportError:
    HAS_WIN32 = False

try:
    import tkinter as tk
    HAS_TK = True
except ImportError:
    HAS_TK = False


# === Announcer ===

class NarratorAnnouncer:
    """
    Hidden window exposing accessibility text to Narrator.

    The announcer runs in the bridge process and updates its accessible
    name and live-region properties when announce() is called. Narrator
    detects the change and reads it aloud.

    Three modes available depending on installed dependencies:
        - production: pywin32 + UIA (Windows only)
        - fallback:   tkinter window with accessibility attrs (Windows only)
        - mock:       log-only (any platform)
    """

    def __init__(
        self,
        *,
        title: str = "AAEP Narrator Bridge",
        prefer_mock: bool = False,
    ):
        self.title = title
        self._stop_event = Event()
        self._announcement_count = 0

        # Decide which mode to run in
        if prefer_mock or not _IS_WINDOWS:
            self.mode = "mock"
        elif HAS_WIN32:
            self.mode = "production"
        elif HAS_TK:
            self.mode = "fallback"
        else:
            self.mode = "mock"
            logger.warning(
                "No UIA backend available (need win32gui or tkinter); "
                "falling back to mock mode (log-only announcements)",
            )

        # Mode-specific state
        self._tk_root: Any = None
        self._tk_label: Any = None
        self._hwnd: int | None = None

        logger.info("NarratorAnnouncer initialized in %s mode", self.mode)

    def start(self) -> None:
        """Create the announcement window if needed for the active mode."""
        if self.mode == "production":
            self._start_win32()
        elif self.mode == "fallback":
            self._start_tk()
        # mock mode needs no window

    def stop(self) -> None:
        """Tear down the announcement window."""
        self._stop_event.set()
        if self._tk_root is not None:
            try:
                self._tk_root.quit()
                self._tk_root.destroy()
            except Exception:
                logger.exception("Error closing tk window")
            self._tk_root = None
        if self._hwnd is not None and HAS_WIN32:
            try:
                win32gui.DestroyWindow(self._hwnd)
            except Exception:
                logger.exception("Error destroying win32 window")
            self._hwnd = None

    def announce(
        self,
        text: str,
        priority: AnnouncementPriority,
    ) -> None:
        """
        Update the accessible text so Narrator announces it.

        For LOG_ONLY priority, the announcement is logged but not exposed
        to Narrator. For POLITE and ASSERTIVE, the announcement is exposed
        via the accessible name (Narrator picks it up via UIA polling).
        """
        if not text:
            return
        self._announcement_count += 1

        if priority == AnnouncementPriority.LOG_ONLY:
            logger.debug("[log-only] %s", text)
            return

        if self.mode == "mock":
            logger.info("[mock-narrator %s] %s", priority.value, text)
            return

        if self.mode == "production" and self._hwnd is not None:
            self._announce_win32(text, priority)
            return

        if self.mode == "fallback" and self._tk_label is not None:
            self._announce_tk(text, priority)
            return

        # Fallback if start() wasn't called or failed
        logger.info("[uninitialized %s] %s", priority.value, text)

    @property
    def announcement_count(self) -> int:
        """Total announcements made (useful for tests and metrics)."""
        return self._announcement_count

    # === Production mode (Win32) ===

    def _start_win32(self) -> None:
        """Create a hidden Win32 window for UIA exposure."""
        try:
            class_name = "AAEPNarratorBridge"
            wnd_class = win32gui.WNDCLASS()
            wnd_class.lpszClassName = class_name
            wnd_class.lpfnWndProc = self._wnd_proc
            try:
                win32gui.RegisterClass(wnd_class)
            except Exception:
                # Class may already be registered from a previous run; ignore
                pass

            self._hwnd = win32gui.CreateWindow(
                class_name,
                self.title,
                win32con.WS_OVERLAPPED,
                0, 0, 1, 1,
                0, 0, 0, None,
            )
            # Hide but keep accessible
            win32gui.ShowWindow(self._hwnd, win32con.SW_HIDE)
            logger.info("Win32 announcer window created: hwnd=%s", self._hwnd)
        except Exception:
            logger.exception("Failed to create Win32 announcer window")
            self.mode = "mock"

    def _wnd_proc(self, hwnd: int, msg: int, wparam: int, lparam: int) -> int:
        """Minimal window procedure. Real UIA work happens via SetWindowText."""
        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

    def _announce_win32(
        self,
        text: str,
        priority: AnnouncementPriority,
    ) -> None:
        """Update the Win32 window's title (which Narrator reads via UIA)."""
        try:
            prefix = "[Critical] " if priority == AnnouncementPriority.ASSERTIVE else ""
            win32gui.SetWindowText(self._hwnd, f"{prefix}{text}")
        except Exception:
            logger.exception("Failed to update Win32 announcement")

    # === Fallback mode (tkinter) ===

    def _start_tk(self) -> None:
        """Create a hidden tk window with accessible label widget."""
        try:
            self._tk_root = tk.Tk()
            self._tk_root.title(self.title)
            self._tk_root.geometry("1x1+0+0")
            self._tk_root.withdraw()  # Hide the window
            self._tk_label = tk.Label(self._tk_root, text="")
            self._tk_label.pack()
            logger.info("Tk announcer window created")
        except Exception:
            logger.exception("Failed to create tk announcer window")
            self.mode = "mock"

    def _announce_tk(
        self,
        text: str,
        priority: AnnouncementPriority,
    ) -> None:
        """Update the tk label's text. Narrator reads via UIA tree polling."""
        try:
            prefix = "[Critical] " if priority == AnnouncementPriority.ASSERTIVE else ""
            self._tk_label.config(text=f"{prefix}{text}")
            self._tk_root.title(f"{prefix}{text}")
            self._tk_root.update_idletasks()
        except Exception:
            logger.exception("Failed to update tk announcement")
