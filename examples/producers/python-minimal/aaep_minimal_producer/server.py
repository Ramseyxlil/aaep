"""
HTTP/SSE server exposing the AAEP minimal producer.

Endpoints:
  POST /sessions   - Start a new agent session
  GET  /events     - Server-Sent Events stream of AAEP events
  POST /messages   - Receive confirmation/clarification replies
  GET  /healthz    - Liveness check

This server is intentionally minimal. For production, add authentication,
rate limiting, structured logging, and your preferred observability stack.
The agent logic in agent.py is transport-independent.

Run with:
  python -m aaep_minimal_producer.server --port 8080
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from typing import Any

from aiohttp import web

from aaep_minimal_producer.agent import AgentLoop
from aaep_minimal_producer.emitter import AAEPEmitter


logger = logging.getLogger("aaep_minimal_producer.server")


# === SSE event broadcaster ===

class EventBroadcaster:
    """
    Broadcasts AAEP events to all connected SSE subscribers.

    Each subscriber has its own asyncio.Queue. The broadcaster pushes
    events into all queues; each subscriber drains its queue independently.
    Slow subscribers can drop events when their queue fills.
    """

    QUEUE_MAX_SIZE = 1000

    def __init__(self) -> None:
        self._subscribers: list[asyncio.Queue] = []

    def subscribe(self) -> asyncio.Queue:
        """Create a new subscriber queue."""
        q: asyncio.Queue = asyncio.Queue(maxsize=self.QUEUE_MAX_SIZE)
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        """Remove a subscriber queue."""
        if q in self._subscribers:
            self._subscribers.remove(q)

    def publish(self, event: dict[str, Any]) -> None:
        """Push an event to all subscribers, dropping for slow consumers."""
        for q in self._subscribers:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                # Critical events MUST NOT be dropped (Chapter 5 §5.6.3)
                if event.get("urgency") == "critical":
                    # Force-make room by dropping oldest non-critical
                    try:
                        q.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                    try:
                        q.put_nowait(event)
                    except asyncio.QueueFull:
                        logger.warning(
                            "Could not deliver critical event %s to subscriber",
                            event.get("event_id"),
                        )

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)


# === Application state ===

def _build_app() -> web.Application:
    app = web.Application()
    broadcaster = EventBroadcaster()
    emitter = AAEPEmitter(send_event=broadcaster.publish)
    agent = AgentLoop(emitter)

    app["broadcaster"] = broadcaster
    app["emitter"] = emitter
    app["agent"] = agent
    app["session_tasks"] = {}

    app.router.add_post("/sessions", handle_start_session)
    app.router.add_get("/events", handle_events_sse)
    app.router.add_post("/messages", handle_reply_message)
    app.router.add_get("/healthz", handle_healthz)

    # CORS
    app.middlewares.append(_cors_middleware)

    return app


@web.middleware
async def _cors_middleware(request: web.Request, handler):
    """Permissive CORS for development. Restrict in production."""
    if request.method == "OPTIONS":
        return web.Response(headers=_cors_headers())
    response = await handler(request)
    response.headers.update(_cors_headers())
    return response


def _cors_headers() -> dict[str, str]:
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization",
    }


# === Request handlers ===

async def handle_start_session(request: web.Request) -> web.Response:
    """POST /sessions { "user_message": "..." } -> { "session_id": "..." }"""
    try:
        payload = await request.json()
    except Exception:
        return web.json_response(
            {"error": "Invalid JSON body"}, status=400
        )

    user_message = payload.get("user_message", "")
    if not isinstance(user_message, str) or not user_message.strip():
        return web.json_response(
            {"error": "user_message must be a non-empty string"}, status=400
        )

    user_id = payload.get("user_id")
    agent: AgentLoop = request.app["agent"]

    async def _run():
        try:
            await agent.run(user_message, user_id=user_id)
        except Exception as exc:
            logger.exception("Session failed: %s", exc)

    task = asyncio.create_task(_run())
    # Wait briefly for the first event to capture the session_id
    await asyncio.sleep(0.05)

    return web.json_response({
        "status": "started",
        "user_message": user_message,
    }, status=202)


async def handle_events_sse(request: web.Request) -> web.StreamResponse:
    """GET /events - Server-Sent Events stream of AAEP events."""
    response = web.StreamResponse(
        status=200,
        reason="OK",
        headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            **_cors_headers(),
        },
    )
    await response.prepare(request)

    broadcaster: EventBroadcaster = request.app["broadcaster"]
    queue = broadcaster.subscribe()
    logger.info("New SSE subscriber (total: %d)", broadcaster.subscriber_count)

    try:
        # Send a heartbeat comment so the client knows the connection is alive
        await response.write(b": connected\n\n")

        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=30.0)
                payload = json.dumps(event, ensure_ascii=False)
                # SSE format: "data: <json>\n\n"
                await response.write(
                    f"data: {payload}\n\n".encode("utf-8")
                )
            except asyncio.TimeoutError:
                # Heartbeat to keep the connection alive
                await response.write(b": heartbeat\n\n")
            except ConnectionResetError:
                break

    except asyncio.CancelledError:
        pass
    finally:
        broadcaster.unsubscribe(queue)
        logger.info("SSE subscriber disconnected (total: %d)",
                    broadcaster.subscriber_count)

    return response


async def handle_reply_message(request: web.Request) -> web.Response:
    """POST /messages - Receive confirmation.reply or clarification.reply."""
    try:
        message = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400)

    msg_type = message.get("type", "")
    reply_token = message.get("reply_token", "")

    if not reply_token:
        return web.json_response(
            {"error": "reply_token is required"}, status=400
        )

    emitter: AAEPEmitter = request.app["emitter"]

    if msg_type == "confirmation.reply":
        decision = message.get("decision", "")
        if decision not in ("accept", "reject"):
            return web.json_response(
                {"error": f"decision must be 'accept' or 'reject', got {decision!r}"},
                status=400,
            )
        emitter.submit_reply(reply_token, decision)
        return web.json_response({"status": "received"})

    if msg_type == "clarification.reply":
        response = message.get("response")
        if response is None:
            return web.json_response(
                {"error": "response field required for clarification.reply"},
                status=400,
            )
        emitter.submit_reply(reply_token, str(response))
        return web.json_response({"status": "received"})

    return web.json_response(
        {"error": f"unsupported message type: {msg_type}"}, status=400
    )


async def handle_healthz(request: web.Request) -> web.Response:
    """GET /healthz - liveness check."""
    broadcaster: EventBroadcaster = request.app["broadcaster"]
    return web.json_response({
        "status": "ok",
        "subscribers": broadcaster.subscriber_count,
        "aaep_version": "1.0.0",
    })


# === CLI entry point ===

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="aaep-minimal-producer",
        description="Run the AAEP minimal producer HTTP/SSE server",
    )
    parser.add_argument(
        "--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port", type=int, default=8080, help="Bind port (default: 8080)"
    )
    parser.add_argument(
        "--log-level", default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(name)s [%(levelname)s] %(message)s",
    )

    app = _build_app()
    logger.info("Starting AAEP minimal producer on http://%s:%d", args.host, args.port)
    logger.info("Endpoints:")
    logger.info("  POST   /sessions   - start a session")
    logger.info("  GET    /events     - SSE event stream")
    logger.info("  POST   /messages   - reply messages")
    logger.info("  GET    /healthz    - health check")

    web.run_app(app, host=args.host, port=args.port, print=None)
    return 0


if __name__ == "__main__":
    sys.exit(main())
