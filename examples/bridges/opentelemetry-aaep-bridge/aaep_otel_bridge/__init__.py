"""
OpenTelemetry ↔ AAEP Bridge.

Converts AAEP event streams into OpenTelemetry traces and spans for unified
observability in SRE/compliance backends (Jaeger, Tempo, Datadog, Honeycomb,
etc.).

Public API:

    from aaep_otel_bridge import AAEPToOTELTranslator, run_bridge

    # Translator alone (use within your own subscriber loop)
    translator = AAEPToOTELTranslator(tracer=my_tracer)
    translator.translate(event)

    # Full bridge (connects to AAEP producer, emits to OTEL)
    await run_bridge(aaep_endpoint="http://localhost:8080")

CLI entry point:

    aaep-otel-bridge --endpoint http://localhost:8080

See README.md for the full translation table and privacy policy.
"""

from __future__ import annotations

__version__ = "1.0.0"
__author__ = "Abdulrafiu Izuafa"
__email__ = "Abdulrafiu@izusoft.tech"
__license__ = "MIT"
__aaep_spec_version__ = "1.0.0"


from aaep_otel_bridge.translator import (
    AAEPToOTELTranslator,
    SessionSpanState,
)
from aaep_otel_bridge.bridge import (
    run_bridge,
)


__all__ = [
    "__version__",
    "__author__",
    "__email__",
    "__license__",
    "__aaep_spec_version__",
    "AAEPToOTELTranslator",
    "SessionSpanState",
    "run_bridge",
]
