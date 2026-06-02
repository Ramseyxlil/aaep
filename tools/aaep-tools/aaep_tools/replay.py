"""
aaep-replay — replay a captured AAEP event stream as an SSE server.

Reads a JSONL file of AAEP events and serves them as a Server-Sent Events
stream at /events. Subscribers connecting during replay receive the rest
of the stream from the current point.

By default, events are replayed at their original pace by computing the
delta between consecutive event timestamps. Use --speed to multiply (10x
faster, 0.5x = half-speed) or --no-delay for instant replay.

Usage:
    aaep-replay --file captured.jsonl --port 9000
    aaep-replay --file captured.jsonl --port 9000 --speed 10
    aaep-replay --file captured.jsonl --port 9000 --no-delay
    aaep-replay --file captured.jsonl --port 9000 --loop

Then point a subscriber at http://localhost:9000/events.

Exit codes:
    0 - replay completed (or interrupted)
    2 - usage error, I/O error, or invalid input file
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from aiohttp import web
except ImportError as e:
    print(f"aiohttp is required: pip install aiohttp (got: {e})", file=sys.stderr)
    sys.exit(2)


logger = logging.getLogger("aaep_replay")


# === Event loading ===

def load_events(path: Path) -> list[dict[str, Any]]:
    """Load events from a JSONL file. Raises on malformed lines."""
    events: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line_no, raw_line in enumerate(f, start=1):
            stripped = raw_line.strip()
            if not stripped:
                continue
            try:
                event = json.loads(stripped)
            except json.JSONDecodeError as e:
                raise ValueError(
                    f"Invalid JSON at {path}:{line_no}: {e.msg}"
                ) from e
            if not isinstance(event, dict):
                raise ValueError(
                    f"Expected JSON object at {path}:{line_no}, got {type(event).__name__}"
                )
            events.append(event)
    return events


def _parse_timestamp(ts: str) -> datetime:
    """Parse an RFC 3339 timestamp."""
    # Handle trailing Z (UTC) and explicit timezone offsets
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    return datetime.fromisoformat(ts)


def _compute_delays(
    events: list[dict[str, Any]],
    *,
    speed: float,
) -> list[float]:
    """
    Compute the wait time (seconds) before emitting each event, based on
    timestamp deltas from the previous event. The first event has delay=0.
    """
    delays: list[float] = []
    prev_ts: datetime | None = None
    for event in events:
        ts_str = event.get("timestamp")
        if not isinstance(ts_str, str):
            delays.append(0.0)
            prev_ts = None
            continue
        try:
            ts = _parse_timestamp(ts_str)
        except (ValueError, TypeError):
            delays.append(0.0)
            prev_ts = None
            continue
        if prev_ts is None:
            delays.append(0.0)
        else:
            delta = (ts - prev_ts).total_seconds()
            delays.append(max(0.0, delta / speed))
        prev_ts = ts
    return delays


# === Replay state ===

class ReplayState:
    """Shared state across the server and replay loop."""

    def __init__(self) -> None:
        self.subscribers: set[asyncio.Queue] = set()
        self.events_emitted = 0
        self.replay_done = False


# === HTTP handlers ===

async def handle_events(request: web.Request) -> web.StreamResponse:
    """GET /events — serve the SSE stream."""
    state: ReplayState = request.app["state"]

    response = web.StreamResponse(
        status=200,
        headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
        },
    )
    await response.prepare(request)

    queue: asyncio.Queue = asyncio.Queue()
    state.subscribers.add(queue)
    logger.info("Subscriber connected (total: %d)", len(state.subscribers))

    try:
        while not state.replay_done or not queue.empty():
            try:
                event = await asyncio.wait_for(queue.get(), timeout=30.0)
            except asyncio.TimeoutError:
                # Send keepalive comment to detect dead connections
                try:
                    await response.write(b": keepalive\n\n")
                except (ConnectionResetError, asyncio.CancelledError):
                    break
                continue

            if event is None:
                # Sentinel: replay finished
                break

            try:
                payload = f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                await response.write(payload.encode("utf-8"))
            except (ConnectionResetError, asyncio.CancelledError):
                break

    finally:
        state.subscribers.discard(queue)
        logger.info("Subscriber disconnected (total: %d)", len(state.subscribers))

    return response


async def handle_healthz(request: web.Request) -> web.Response:
    state: ReplayState = request.app["state"]
    return web.json_response({
        "status": "ok",
        "events_emitted": state.events_emitted,
        "active_subscribers": len(state.subscribers),
        "replay_done": state.replay_done,
    })


# === Replay loop ===

async def run_replay(
    state: ReplayState,
    events: list[dict[str, Any]],
    delays: list[float],
    *,
    loop_forever: bool,
) -> None:
    """Emit events to all subscriber queues with the computed delays."""
    while True:
        for event, delay in zip(events, delays):
            if delay > 0:
                await asyncio.sleep(delay)
            # Fan-out to all subscribers
            dead_queues: list[asyncio.Queue] = []
            for queue in list(state.subscribers):
                try:
                    queue.put_nowait(event)
                except asyncio.QueueFull:
                    dead_queues.append(queue)
            for q in dead_queues:
                state.subscribers.discard(q)

            state.events_emitted += 1

        if not loop_forever:
            break
        logger.info("Replay completed; restarting (--loop)")

    state.replay_done = True
    # Signal each subscriber to finish via sentinel
    for queue in list(state.subscribers):
        try:
            queue.put_nowait(None)
        except asyncio.QueueFull:
            pass


# === CLI ===

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="aaep-replay",
        description="Replay captured AAEP event streams as an SSE server",
        epilog=(
            "Examples:\n"
            "  aaep-replay --file captured.jsonl --port 9000\n"
            "  aaep-replay --file captured.jsonl --port 9000 --speed 10\n"
            "  aaep-replay --file captured.jsonl --port 9000 --no-delay --loop\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--file", "-f", required=True,
        help="JSONL file of captured AAEP events",
    )
    parser.add_argument(
        "--host", default="127.0.0.1",
        help="Host to bind (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port", "-p", type=int, default=9000,
        help="Port to bind (default: 9000)",
    )
    parser.add_argument(
        "--speed", type=float, default=1.0,
        help="Replay speed multiplier (1.0 = original pace, 10 = 10x faster)",
    )
    parser.add_argument(
        "--no-delay", action="store_true",
        help="Replay events as fast as possible (overrides --speed)",
    )
    parser.add_argument(
        "--loop", action="store_true",
        help="Loop replay continuously",
    )
    parser.add_argument(
        "--log-level", default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    parser.add_argument(
        "--version", action="version",
        version="aaep-replay 1.0.0 (AAEP spec 1.0.0)",
    )

    args = parser.parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(name)s [%(levelname)s] %(message)s",
    )

    # Load events
    path = Path(args.file)
    if not path.is_file():
        print(f"aaep-replay: file not found: {path}", file=sys.stderr)
        return 2
    try:
        events = load_events(path)
    except ValueError as e:
        print(f"aaep-replay: {e}", file=sys.stderr)
        return 2

    if not events:
        print(f"aaep-replay: {path} contains no events", file=sys.stderr)
        return 2

    logger.info("Loaded %d event(s) from %s", len(events), path)

    # Compute delays
    if args.no_delay:
        delays = [0.0] * len(events)
    else:
        delays = _compute_delays(events, speed=args.speed)

    # Build app
    app = web.Application()
    state = ReplayState()
    app["state"] = state
    app.router.add_get("/events", handle_events)
    app.router.add_get("/healthz", handle_healthz)

    async def _start_replay(app: web.Application) -> None:
        app["replay_task"] = asyncio.create_task(
            run_replay(state, events, delays, loop_forever=args.loop)
        )

    async def _stop_replay(app: web.Application) -> None:
        task = app.get("replay_task")
        if task is not None:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass

    app.on_startup.append(_start_replay)
    app.on_cleanup.append(_stop_replay)

    logger.info("Serving replay on http://%s:%d/events", args.host, args.port)
    logger.info("Speed: %sx, Loop: %s, Events: %d",
                "infinite" if args.no_delay else args.speed,
                args.loop, len(events))

    try:
        web.run_app(app, host=args.host, port=args.port, print=None)
    except KeyboardInterrupt:
        logger.info("Interrupted")
    return 0


if __name__ == "__main__":
    sys.exit(main())
