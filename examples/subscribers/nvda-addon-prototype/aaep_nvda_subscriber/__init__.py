"""
AAEP Subscriber for NVDA.

Bridges between AAEP-emitting AI agents and NVDA's speech engine. Designed to
run as an NVDA add-on but structured so individual modules can be imported and
tested outside NVDA (the NVDA modules are imported with graceful fallback in
the integration layer).

Public API:

    from aaep_nvda_subscriber import (
        AAEPEventHandler,        # Core event-to-speech translator
        AAEPSSEClient,            # SSE consumer
        SpeechPriority,           # Priority levels
        Configuration,            # User preferences
    )

The NVDA integration entry point is in aaep_nvda_subscriber.globalPlugin,
which is what NVDA's add-on loader instantiates.
"""

from __future__ import annotations

__version__ = "0.1.0"
__author__ = "Abdulrafiu Izuafa"
__email__ = "Abdulrafiu@izusoft.tech"
__license__ = "MIT"
__aaep_spec_version__ = "1.0.0"


from aaep_nvda_subscriber.handler import (
    AAEPEventHandler,
    Configuration,
    SpeechPriority,
)
from aaep_nvda_subscriber.sse_client import AAEPSSEClient


__all__ = [
    "__version__",
    "__author__",
    "__email__",
    "__license__",
    "__aaep_spec_version__",
    "AAEPEventHandler",
    "Configuration",
    "SpeechPriority",
    "AAEPSSEClient",
]
