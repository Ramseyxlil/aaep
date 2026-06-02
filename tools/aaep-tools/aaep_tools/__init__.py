"""
AAEP command-line tools.

This package provides three command-line utilities for working with AAEP
event streams: validate, capture, and replay. Each is exposed as a console
script after `pip install aaep-tools` and also as a Python function for
programmatic use.

CLI entry points (registered in pyproject.toml):

    aaep-validate     - aaep_tools.validate:main
    aaep-capture      - aaep_tools.capture:main
    aaep-replay       - aaep_tools.replay:main

Programmatic API (this module re-exports for convenience):

    from aaep_tools import (
        validate_event,        # validate a single event dict
        validate_stream,       # validate a JSONL TextIO
        ValidationResult,      # outcome dataclass
        capture_stream,        # async SSE capture
        load_events,           # load JSONL into list[dict]
        run_replay,            # async replay loop
        ReplayState,           # shared replay state
    )

You can also import from the individual modules directly:

    from aaep_tools.validate import validate_event
    from aaep_tools.capture import capture_stream
    from aaep_tools.replay import load_events, run_replay

Direct submodule imports are preferred when you only need one tool's API,
as they avoid loading the other tools' dependencies (e.g., importing
aaep_tools.validate doesn't load aiohttp).

See README.md for usage examples and design philosophy.
"""

from __future__ import annotations

__version__ = "1.0.0"
__author__ = "Abdulrafiu Izuafa"
__email__ = "Abdulrafiu@izusoft.tech"
__license__ = "MIT"
__aaep_spec_version__ = "1.0.0"


# Re-export the public programmatic API for convenience.
# Each submodule remains importable directly for callers who want to avoid
# the transitive import cost of the others.
from aaep_tools.validate import (
    ValidationResult,
    validate_event,
    validate_stream,
)
from aaep_tools.capture import capture_stream
from aaep_tools.replay import (
    ReplayState,
    load_events,
    run_replay,
)


__all__ = [
    # Metadata
    "__version__",
    "__author__",
    "__email__",
    "__license__",
    "__aaep_spec_version__",
    # Validate API
    "validate_event",
    "validate_stream",
    "ValidationResult",
    # Capture API
    "capture_stream",
    # Replay API
    "load_events",
    "run_replay",
    "ReplayState",
]
