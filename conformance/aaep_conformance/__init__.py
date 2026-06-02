"""
AAEP Conformance Test Suite.

The official test suite for verifying implementations of the Agent Accessibility
Event Protocol (AAEP). This package provides:

- A CLI tool (`aaep-conformance`) for running tests against producers and subscribers
- Programmatic test runner for embedding in CI pipelines
- Schema validators for ad-hoc AAEP event validation
- Report generators (JSON and HTML)

For typical usage, install the package and run the CLI:

    $ pip install aaep-conformance
    $ aaep-conformance producer --endpoint http://localhost:8080/agent --level 2

For programmatic usage:

    from aaep_conformance import Runner, Level, validate_event

    runner = Runner(target_kind="producer", endpoint="http://localhost:8080/agent")
    report = runner.run(level=Level.LEVEL_2)
    report.save_json("conformance-report.json")
    report.save_html("conformance-report.html")

See https://aaep-protocol.org/conformance/ for full documentation.
"""

from __future__ import annotations

__version__ = "1.0.0"
__author__ = "Abdulrafiu Izuafa"
__email__ = "Abdulrafiu@izusoft.tech"
__license__ = "MIT"
__url__ = "https://github.com/Ramseyxlil/aaep"
__aaep_spec_version__ = "1.0.0"

# Public API
from aaep_conformance.runner import Runner, RunnerConfig
from aaep_conformance.reporter import (
    Report,
    TestResult,
    Severity,
    Verdict,
)
from aaep_conformance.checks.envelope import (
    validate_event,
    validate_envelope_only,
)

# Level constants
class Level:
    """AAEP conformance levels."""

    LEVEL_1 = 1
    """Notification level: producers emit events, subscribers consume."""

    LEVEL_2 = 2
    """Interactive level: adds confirmation and clarification reply flow."""

    LEVEL_3 = 3
    """Negotiated level: adds full subscription handshake and capability negotiation."""

    ALL = (LEVEL_1, LEVEL_2, LEVEL_3)


# Public exports — what `from aaep_conformance import *` provides
__all__ = [
    # Metadata
    "__version__",
    "__author__",
    "__email__",
    "__license__",
    "__url__",
    "__aaep_spec_version__",
    # Test execution
    "Runner",
    "RunnerConfig",
    "Level",
    # Reports
    "Report",
    "TestResult",
    "Severity",
    "Verdict",
    # Validators
    "validate_event",
    "validate_envelope_only",
]


def get_version() -> str:
    """Return the conformance suite version."""
    return __version__


def get_aaep_spec_version() -> str:
    """Return the AAEP specification version this suite tests against."""
    return __aaep_spec_version__
