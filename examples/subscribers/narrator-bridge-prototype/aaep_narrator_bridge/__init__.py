"""
AAEP Narrator Bridge.

Standalone Windows bridge that subscribes to AAEP producers and exposes
their events to Microsoft Narrator via Windows UI Automation (UIA).
Unlike the NVDA add-on, this is a separate process — Narrator does not
have a third-party add-on mechanism.

Public API:

    from aaep_narrator_bridge import (
        AAEPNarratorBridge,        # Main bridge class
        NarratorAnnouncer,         # UIA window wrapper
        NarratorEventHandler,      # Event-to-announcement translator
        Configuration,             # User preferences
    )

CLI entry point:

    aaep-narrator-bridge --endpoint http://localhost:8080

See README.md for architecture, limitations, and Windows-specific notes.
"""

from __future__ import annotations

__version__ = "0.1.0"
__author__ = "Abdulrafiu Izuafa"
__email__ = "Abdulrafiu@izusoft.tech"
__license__ = "MIT"
__aaep_spec_version__ = "1.0.0"


from aaep_narrator_bridge.handler import (
    Configuration,
    NarratorEventHandler,
)
from aaep_narrator_bridge.announcer import NarratorAnnouncer


__all__ = [
    "__version__",
    "__author__",
    "__email__",
    "__license__",
    "__aaep_spec_version__",
    "Configuration",
    "NarratorEventHandler",
    "NarratorAnnouncer",
]
