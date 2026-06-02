"""
bridge.py — AAEP-to-OTEL bridge subscriber loop and CLI entry.

Connects to an AAEP producer's /events SSE endpoint, consumes events,
and feeds them through AAEPToOTELTranslator. Behaves as a standard AAEP
subscriber from the producer's perspective.

Configuration uses standard OTEL environment variables (OTEL_EXPORTER_OTLP_*,
OTEL_SERVICE_NAME, etc.), so this bridge composes with any existing OTEL
collector setup.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import signal
import sys
from typing import Any

try:
    import httpx
except ImportError as e:
    print(f"httpx is required: pip install httpx (got: {e})", file=sys.stderr)
    sys.exit(2)

try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import (
        BatchSpanProcessor,
        ConsoleSpanExporter,
    )
    from opentelemetry.sdk.resources import Resource
    HAS_OTEL_SDK = True
except ImportError:
    HAS_OTEL_SDK = False

try:
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    HAS_OTLP_EXPORTER = True
except ImportError:
    HAS_OTLP_EXPORTER = False

from aaep_otel_bridge.translator import AAEPToOTELTranslator


logger = logging.getLogger("aaep_otel_bridge.bridge")


# === OTEL setup ===

def _configure_otel(*, service_name: str, console: bool) -> None:
    """Configure the global OTEL tracer provider with the appropriate exporter."""
    if not HAS_OTEL_SDK:
        logger.warning(
            "opentelemetry-sdk not installed; running with mock tracer. "
            "Install with: pip install aaep-otel-bridge[otel]"
        )
        return

    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)

    if console:
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
        logger.info("OTEL: using console exporter")
    elif HAS_OTLP_EXPORTER:
        endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
        exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        logger.info("OTEL: using OTLP exporter to %s", endpoint)
    else:
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
        logger.warning(
            "OTLP exporter not installed; falling back to console. "
            "Install with: pip install opentelemetry-exporter-otlp-proto-grpc"
        )

    trace.set_tracer_provider(provider)


# === Subscriber loop ===

async def run_bridge(
    *,
    aaep_endpoint: str,
    service_name: str = "aaep-bridge",
    console_exporter: bool = False,
    cancel_event: asyncio.Event | None = None,
) -> int:
    """
    Run the bridge: consume AAEP SSE events, translate to OTEL, export.

    Returns an integer exit code.
    """
    _configure_otel(service_name=service_name, console=console_exporter)

    translator = AAEPToOTELTranslator()
    events_url = aaep_endpoint.rstrip("/") + "/events"
    events_processed = 0

    if cancel_event is None:
        cancel_event = asyncio.Event()

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(None, connect=10.0)) as client:
            async with client.stream(
                "GET",
                events_url,
                headers={"Accept": "text/event-stream"},
            ) as response:
                response.raise_for_status()
                logger.info("Connected to AAEP producer at %s", events_url)

                buffer = ""
                async for chunk in response.aiter_text():
                    if cancel_event.is_set():
                        logger.info("Cancellation signaled; shutting down")
                        break
                    buffer += chunk
                    while "\n\n" in buffer:
                        message, buffer = buffer.split("\n\n", 1)
                        event = _parse_sse_message(message)
                        if event is None:
                            continue
                        translator.translate(event)
                        events_processed += 1
                        if events_processed % 100 == 0:
                            logger.debug("Processed %d events", events_processed)

    except httpx.ConnectError as e:
        logger.error("Could not connect to AAEP producer: %s", e)
        return 1
    except httpx.HTTPStatusError as e:
        logger.error("HTTP error from AAEP producer: %d", e.response.status_code)
        return 1
    except asyncio.CancelledError:
        logger.info("Bridge cancelled")
    finally:
        logger.info("Bridge shut down. Total events processed: %d", events_processed)

    return 0


def _parse_sse_message(message: str) -> dict[str, Any] | None:
    """Extract the data field from an SSE message and parse as JSON."""
    data_parts: list[str] = []
    for line in message.split("\n"):
        if line.startswith("data:"):
            data_parts.append(line[5:].lstrip())
        elif line.startswith(":"):
            continue
    if not data_parts:
        return None
    try:
        result = json.loads("\n".join(data_parts))
        return result if isinstance(result, dict) else None
    except json.JSONDecodeError:
        return None


# === CLI entry ===

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="aaep-otel-bridge",
        description="Bridge AAEP event streams to OpenTelemetry traces",
        epilog=(
            "Examples:\n"
            "  aaep-otel-bridge --endpoint http://localhost:8080\n"
            "  aaep-otel-bridge --endpoint http://localhost:8080 --console\n"
            "  OTEL_EXPORTER_OTLP_ENDPOINT=http://collector:4317 \\\n"
            "      aaep-otel-bridge --endpoint http://localhost:8080\n"
            "\n"
            "Standard OTEL environment variables are respected:\n"
            "  OTEL_EXPORTER_OTLP_ENDPOINT, OTEL_SERVICE_NAME,\n"
            "  OTEL_RESOURCE_ATTRIBUTES, OTEL_TRACES_EXPORTER\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--endpoint", "-e", required=True,
        help="AAEP producer base URL (e.g., http://localhost:8080)",
    )
    parser.add_argument(
        "--service-name", default=os.environ.get("OTEL_SERVICE_NAME", "aaep-bridge"),
        help="OTEL service name (default: aaep-bridge or $OTEL_SERVICE_NAME)",
    )
    parser.add_argument(
        "--console", action="store_true",
        help="Export to console instead of OTLP (for local development)",
    )
    parser.add_argument(
        "--log-level", default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    parser.add_argument(
        "--version", action="version",
        version="aaep-otel-bridge 1.0.0 (AAEP spec 1.0.0)",
    )

    args = parser.parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(name)s [%(levelname)s] %(message)s",
    )

    if os.environ.get("OTEL_TRACES_EXPORTER", "").lower() == "console":
        args.console = True

    cancel_event = asyncio.Event()

    def _handle_signal(*_args: Any) -> None:
        cancel_event.set()

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.add_signal_handler(signal.SIGINT, _handle_signal)
            loop.add_signal_handler(signal.SIGTERM, _handle_signal)
        except NotImplementedError:
            # Windows
            pass
        exit_code = loop.run_until_complete(run_bridge(
            aaep_endpoint=args.endpoint,
            service_name=args.service_name,
            console_exporter=args.console,
            cancel_event=cancel_event,
        ))
        return exit_code
    except KeyboardInterrupt:
        print("\n  Interrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
