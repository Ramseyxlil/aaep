"""
AAEP CLI Debug Subscriber.

A simple reference subscriber that connects to any AAEP producer's SSE
endpoint and prints the event stream in a readable terminal format.

Public API:

    from aaep_cli_debug.listener import listen, format_event, send_reply

CLI entry point:

    aaep-listen --endpoint http://localhost:8080

See README.md for full usage and design notes.
"""

from __future__ import annotations

__version__ = "1.0.0"
__author__ = "Abdulrafiu Izuafa"
__email__ = "Abdulrafiu@izusoft.tech"
__license__ = "MIT"
__aaep_spec_version__ = "1.0.0"


from aaep_cli_debug.listener import (
    format_event,
    listen,
    send_reply,
)


__all__ = [
    "__version__",
    "__author__",
    "__email__",
    "__license__",
    "__aaep_spec_version__",
    "listen",
    "format_event",
    "send_reply",
]
