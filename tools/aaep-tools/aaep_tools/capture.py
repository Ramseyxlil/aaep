"""
aaep-capture — capture the SSE event stream from a running AAEP producer.

Connects to a producer's /events endpoint, parses the Server-Sent Events
protocol, and writes each event as one JSON-per-line in a JSONL file.

Usage:
    aaep-capture --endpoint http://localhost:8080 --output session.jsonl
    aaep-capture --endpoint http://localhost:8080 --output session.jsonl --timeout 60
    aaep-capture --endpoint http://localhost:8080 --output session.jsonl --max-events 100
    aaep-capture --endpoint http://localhost:8080 --output session.jsonl --filter-type tool.invoked
    aaep-capture --endpoint http://localhost:8080 --output -    # stdout

Press Ctrl-C to stop capture early. The output file is always closed cleanly
on interruption (no partial JSON lines).

Exit codes:
    0 - capture completed (reached timeout, max events, or Ctrl-C)
    1 - network error or producer rejected the connection
    2 - usage error or I/O failure
"""

from __future__ import annotations

import argparse
import asyncio
import json
import signal
import sys
import time
from pathlib import Path
from typing import Any, TextIO

try:
    import httpx
except ImportError as e:
    print(f"httpx is required: pip install httpx (got: {e})", file=sys.stderr)
    sys.exit(2)


# === Async capture loop ===

async def capture_stream(
    endpoint: str,
    output: TextIO,
    *,
    timeout_seconds: float | None = None,
    max_events: int | None = None,
    filter_types: set[str] | None = None,
    filter_urgency: str | None = None,
    filter_session: str | None = None,
    progress_callback=None,
) -> tuple[int, str]:
    """
    Connect to an AAEP producer's /events SSE endpoint and write events as
    JSONL to `output`.

    Returns (events_captured, stop_reason).

    stop_reason is one of: "timeout", "max_events", "interrupted",
    "connection_lost", "completed".
    """
    events_captured = 0
    events_skipped = 0
    start_time = time.monotonic()
    stop_reason = "completed"
    cancel_event = asyncio.Event()

    # Set up Ctrl-C handler
    loop = asyncio.get_running_loop()
    try:
        loop.add_signal_handler(signal.SIGINT, cancel_event.set)
    except NotImplementedError:
        # Windows doesn't support add_signal_handler
        pass

    events_url = endpoint.rstrip("/") + "/events"

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(None, connect=10.0)) as client:
            async with client.stream(
                "GET",
                events_url,
                headers={"Accept": "text/event-stream"},
            ) as response:
                response.raise_for_status()

                buffer = ""
                async for chunk in response.aiter_text():
                    if cancel_event.is_set():
                        stop_reason = "interrupted"
                        break
                    if timeout_seconds is not None:
                        elapsed = time.monotonic() - start_time
                        if elapsed >= timeout_seconds:
                            stop_reason = "timeout"
                            break

                    buffer += chunk

                    # SSE messages are separated by blank lines
                    while "\n\n" in buffer:
                        message, buffer = buffer.split("\n\n", 1)
                        event = _parse_sse_message(message)
                        if event is None:
                            continue

                        # Apply filters
                        if not _matches_filters(
                            event,
                            filter_types=filter_types,
                            filter_urgency=filter_urgency,
                            filter_session=filter_session,
                        ):
                            events_skipped += 1
                            continue

                        output.write(json.dumps(event, ensure_ascii=False) + "\n")
                        output.flush()
                        events_captured += 1

                        if progress_callback is not None:
                            progress_callback(events_captured, events_skipped)

                        if max_events is not None and events_captured >= max_events:
                            stop_reason = "max_events"
                            break
                    else:
                        # Inner while ended normally; continue outer loop
                        continue
                    # Inner while broke due to max_events
                    break
                else:
                    # aiter_text exhausted naturally
                    stop_reason = "connection_lost"

    except httpx.ConnectError as e:
        return events_captured, f"connection_error: {e}"
    except httpx.HTTPStatusError as e:
        return events_captured, f"http_{e.response.status_code}"
    except asyncio.CancelledError:
        stop_reason = "interrupted"
        raise

    return events_captured, stop_reason


def _parse_sse_message(message: str) -> dict[str, Any] | None:
    """Extract the data field from an SSE message and parse as JSON."""
    data_parts: list[str] = []
    for line in message.split("\n"):
        if line.startswith("data:"):
            data_parts.append(line[5:].lstrip())
        elif line.startswith(":"):
            # SSE comment line; ignore
            continue
    if not data_parts:
        return None
    data = "\n".join(data_parts)
    try:
        result = json.loads(data)
        return result if isinstance(result, dict) else None
    except json.JSONDecodeError:
        return None


def _matches_filters(
    event: dict[str, Any],
    *,
    filter_types: set[str] | None,
    filter_urgency: str | None,
    filter_session: str | None,
) -> bool:
    """Apply CLI filters; return True if the event should be captured."""
    if filter_types is not None:
        event_type = event.get("type", "")
        # Allow short matches: "tool.invoked" matches "aaep:agent.tool.invoked"
        if not any(t == event_type or event_type.endswith(t) for t in filter_types):
            return False
    if filter_urgency is not None and event.get("urgency") != filter_urgency:
        return False
    if filter_session is not None and event.get("session_id") != filter_session:
        return False
    return True


# === CLI ===

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="aaep-capture",
        description="Capture AAEP event streams from a running producer",
        epilog=(
            "Examples:\n"
            "  aaep-capture --endpoint http://localhost:8080 -o session.jsonl\n"
            "  aaep-capture --endpoint http://localhost:8080 -o stream.jsonl --timeout 60\n"
            "  aaep-capture --endpoint http://localhost:8080 -o critical.jsonl \\\n"
            "      --filter-urgency critical\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--endpoint", "-e", required=True,
        help="Base URL of the AAEP producer (e.g., http://localhost:8080)",
    )
    parser.add_argument(
        "--output", "-o", required=True,
        help="Output JSONL file path, or '-' for stdout",
    )
    parser.add_argument(
        "--timeout", type=float, default=None,
        help="Maximum capture duration in seconds (default: unlimited)",
    )
    parser.add_argument(
        "--max-events", type=int, default=None,
        help="Stop after capturing this many events",
    )
    parser.add_argument(
        "--filter-type", action="append", default=[],
        help="Only capture events of this type (repeatable)",
    )
    parser.add_argument(
        "--filter-urgency", choices=["normal", "critical"], default=None,
        help="Only capture events with this urgency",
    )
    parser.add_argument(
        "--filter-session", default=None,
        help="Only capture events for this session_id",
    )
    parser.add_argument(
        "--quiet", "-q", action="store_true",
        help="Suppress progress output",
    )
    parser.add_argument(
        "--version", action="version",
        version="aaep-capture 1.0.0 (AAEP spec 1.0.0)",
    )

    args = parser.parse_args(argv)

    # Set up output file
    output_handle: TextIO
    if args.output == "-":
        output_handle = sys.stdout
        output_should_close = False
    else:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            output_handle = open(output_path, "w", encoding="utf-8")
        except OSError as e:
            print(f"aaep-capture: cannot open output file: {e}", file=sys.stderr)
            return 2
        output_should_close = True

    filter_types = set(args.filter_type) if args.filter_type else None

    def progress(captured: int, skipped: int) -> None:
        if args.quiet or args.output == "-":
            return
        if captured % 10 == 0 or captured == 1:
            sys.stderr.write(
                f"\rCaptured: {captured}  Skipped (filtered): {skipped}     "
            )
            sys.stderr.flush()

    try:
        captured, stop_reason = asyncio.run(capture_stream(
            endpoint=args.endpoint,
            output=output_handle,
            timeout_seconds=args.timeout,
            max_events=args.max_events,
            filter_types=filter_types,
            filter_urgency=args.filter_urgency,
            filter_session=args.filter_session,
            progress_callback=progress,
        ))

        if not args.quiet and args.output != "-":
            sys.stderr.write(
                f"\nCaptured {captured} event(s). Stop reason: {stop_reason}\n"
            )

        if stop_reason.startswith("connection_error") or stop_reason.startswith("http_"):
            print(f"aaep-capture: {stop_reason}", file=sys.stderr)
            return 1

        return 0

    except KeyboardInterrupt:
        # Should be handled inside capture_stream, but just in case
        print("\nInterrupted.", file=sys.stderr)
        return 0
    finally:
        if output_should_close:
            output_handle.close()


if __name__ == "__main__":
    sys.exit(main())
