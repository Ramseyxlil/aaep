"""
HTTP/SSE server wrapping the AnthropicAAEPAdapter for conformance testing.

Endpoints (identical to the other example servers):
    POST /sessions   - Start a new session
    GET  /events     - SSE event stream
    POST /messages   - Reply messages
    GET  /healthz    - Health check

Run with:
    python -m aaep_anthropic_sdk.server --port 8082

Then test with:
    aaep-conformance producer --endpoint http://localhost:8082 --level 2

The server uses mock mode by default (no Anthropic API calls during
conformance testing). Set ANTHROPIC_API_KEY to enable real Claude calls.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from typing import Any

from aiohttp import web

from aaep_minimal_producer.server import (
    EventBroadcaster,
    _cors_middleware,
    _cors_headers,
    handle_events_sse,
    handle_healthz,
)

from aaep_anthropic_sdk.adapter import AnthropicAAEPAdapter


logger = logging.getLogger("aaep_anthropic_sdk.server")


# === Tools available in the test agent ===
# These match the ones in example_agent.py for consistency.

DEMO_TOOLS = [
    {
        "name": "fetch_balance",
        "description": "Look up an account balance",
        "input_schema": {
            "type": "object",
            "properties": {"account": {"type": "string"}},
            "required": ["account"],
        },
    },
    {
        "name": "send_email",
        "description": "Send an email (HIGH-RISK, irreversible)",
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {"type": "string"},
                "subject": {"type": "string"},
                "body": {"type": "string"},
            },
            "required": ["to", "subject"],
        },
    },
    {
        "name": "search_records",
        "description": "Search records by query",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
]


def _fetch_balance(account: str = "checking") -> str:
    balances = {"checking": "$3,247.18", "savings": "$12,891.40"}
    return f"Balance for {account}: {balances.get(account, '$0.00')}"


def _send_email(to: str = "", subject: str = "", body: str = "") -> str:
    return f"Email to {to} with subject {subject!r} sent successfully"


def _search_records(query: str = "") -> str:
    return f"Found 3 records matching {query!r}"


DEMO_HANDLERS = {
    "fetch_balance": _fetch_balance,
    "send_email": _send_email,
    "search_records": _search_records,
}


# === Application state ===

def _build_app() -> web.Application:
    app = web.Application()
    broadcaster = EventBroadcaster()
    adapter = AnthropicAAEPAdapter(
        send_event=broadcaster.publish,
        model=os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-7"),
        agent_id="aaep-anthropic-server",
        agent_name="AAEP Anthropic Test Server",
    )

    app["broadcaster"] = broadcaster
    app["adapter"] = adapter

    app.router.add_post("/sessions", handle_start_session)
    app.router.add_get("/events", handle_events_sse)
    app.router.add_post("/messages", handle_reply_message)
    app.router.add_get("/healthz", handle_healthz)

    app.middlewares.append(_cors_middleware)

    return app


# === Request handlers ===

async def handle_start_session(request: web.Request) -> web.Response:
    """POST /sessions { "user_message": "..." }"""
    try:
        payload = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON body"}, status=400)

    user_message = payload.get("user_message", "")
    if not isinstance(user_message, str) or not user_message.strip():
        return web.json_response(
            {"error": "user_message must be a non-empty string"}, status=400
        )

    adapter: AnthropicAAEPAdapter = request.app["adapter"]

    async def _run():
        try:
            await adapter.run_session(
                user_message=user_message,
                tools=DEMO_TOOLS,
                tool_handlers=DEMO_HANDLERS,
                user_id=payload.get("user_id"),
            )
        except Exception as exc:
            logger.exception("Session failed: %s", exc)

    asyncio.create_task(_run())
    await asyncio.sleep(0.05)

    return web.json_response({
        "status": "started",
        "user_message": user_message,
        "mock_mode": adapter.mock_mode,
    }, status=202)


async def handle_reply_message(request: web.Request) -> web.Response:
    """POST /messages - Confirmation/clarification replies."""
    try:
        message = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400)

    reply_token = message.get("reply_token", "")
    if not reply_token:
        return web.json_response({"error": "reply_token is required"}, status=400)

    adapter: AnthropicAAEPAdapter = request.app["adapter"]
    msg_type = message.get("type", "")

    if msg_type == "confirmation.reply":
        decision = message.get("decision", "")
        if decision not in ("accept", "reject"):
            return web.json_response(
                {"error": "decision must be accept or reject"}, status=400
            )
        adapter.emitter.submit_reply(reply_token, decision)
        return web.json_response({"status": "received"})

    if msg_type == "clarification.reply":
        response = message.get("response")
        if response is None:
            return web.json_response(
                {"error": "response field required"}, status=400
            )
        adapter.emitter.submit_reply(reply_token, str(response))
        return web.json_response({"status": "received"})

    return web.json_response(
        {"error": f"unsupported message type: {msg_type}"}, status=400
    )


# === CLI entry point ===

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="aaep-anthropic-server",
        description="Run the AAEP Anthropic SDK integration HTTP/SSE server",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8082)
    parser.add_argument(
        "--log-level", default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(name)s [%(levelname)s] %(message)s",
    )

    app = _build_app()
    adapter: AnthropicAAEPAdapter = app["adapter"]

    logger.info("Starting AAEP Anthropic SDK server on http://%s:%d",
                args.host, args.port)
    logger.info("Mode: %s",
                "MOCK (no ANTHROPIC_API_KEY)" if adapter.mock_mode else "REAL (Anthropic API)")
    logger.info("Test with: aaep-conformance producer --endpoint http://%s:%d --level 2",
                args.host, args.port)

    web.run_app(app, host=args.host, port=args.port, print=None)
    return 0


if __name__ == "__main__":
    sys.exit(main())
