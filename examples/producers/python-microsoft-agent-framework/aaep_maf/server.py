"""
HTTP/SSE server wrapping the MAF AAEP middleware for conformance testing.

Endpoints (identical to the other example servers):
    POST /sessions   - Start a new session
    GET  /events     - SSE event stream
    POST /messages   - Reply messages
    GET  /healthz    - Health check

Run with:
    python -m aaep_maf.server --port 8083

Then test with:
    aaep-conformance producer --endpoint http://localhost:8083 --level 2

The server uses mock MAF mode by default (no Azure API calls during
conformance testing). Set AZURE_OPENAI_API_KEY and install the [maf] extra
for real MAF integration.
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
    handle_events_sse,
    handle_healthz,
)

from aaep_maf.middleware import (
    AgentContext,
    MAFAAEPMiddleware,
    ResponseChunkContext,
    ToolCallContext,
)


logger = logging.getLogger("aaep_maf.server")


# === Tools the test agent advertises ===

DEMO_TOOLS = [
    {"name": "list_calendar_events"},
    {"name": "send_email"},
    {"name": "search_records"},
]

# Tool keyword routing — picks a tool based on user message content
TOOL_KEYWORDS = {
    "list_calendar_events": ("calendar", "schedule", "meeting", "agenda"),
    "send_email": ("email", "send mail", "send message", "compose"),
    "search_records": ("search", "find", "look up", "query"),
}


# Mock tool results
def _mock_tool_result(tool_name: str, args: dict[str, Any]) -> Any:
    if tool_name == "list_calendar_events":
        return "3 events: standup at 9am, design review at 2pm, gym at 6pm"
    if tool_name == "send_email":
        return f"Email sent to {args.get('to', 'recipient')} successfully"
    if tool_name == "search_records":
        return f"Found 3 records matching {args.get('query', '...')!r}"
    return "Tool executed"


# === Application setup ===

def _build_app() -> web.Application:
    app = web.Application()
    broadcaster = EventBroadcaster()
    middleware = MAFAAEPMiddleware(
        send_event=broadcaster.publish,
        model=os.environ.get("MAF_MODEL", "gpt-4o"),
        agent_id="aaep-maf-server",
        agent_name="AAEP MAF Test Server",
    )

    app["broadcaster"] = broadcaster
    app["middleware"] = middleware

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

    middleware: MAFAAEPMiddleware = request.app["middleware"]

    async def _run():
        try:
            await _drive_test_session(
                middleware=middleware,
                user_message=user_message,
                user_id=payload.get("user_id"),
            )
        except Exception as exc:
            logger.exception("Session failed: %s", exc)

    asyncio.create_task(_run())
    await asyncio.sleep(0.05)

    return web.json_response({
        "status": "started",
        "user_message": user_message,
    }, status=202)


async def handle_reply_message(request: web.Request) -> web.Response:
    """POST /messages - Reply messages routed to the emitter."""
    try:
        message = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400)

    reply_token = message.get("reply_token", "")
    if not reply_token:
        return web.json_response(
            {"error": "reply_token is required"}, status=400
        )

    middleware: MAFAAEPMiddleware = request.app["middleware"]
    msg_type = message.get("type", "")

    if msg_type == "confirmation.reply":
        decision = message.get("decision", "")
        if decision not in ("accept", "reject"):
            return web.json_response(
                {"error": "decision must be accept or reject"}, status=400
            )
        middleware.emitter.submit_reply(reply_token, decision)
        return web.json_response({"status": "received"})

    if msg_type == "clarification.reply":
        response = message.get("response")
        if response is None:
            return web.json_response(
                {"error": "response field required"}, status=400
            )
        middleware.emitter.submit_reply(reply_token, str(response))
        return web.json_response({"status": "received"})

    return web.json_response(
        {"error": f"unsupported message type: {msg_type}"}, status=400
    )


# === Mock MAF session driver ===

async def _drive_test_session(
    middleware: MAFAAEPMiddleware,
    user_message: str,
    user_id: str | None = None,
) -> None:
    """
    Drive the middleware chain through a simulated MAF session for
    conformance testing.
    """
    context = AgentContext(
        user_message=user_message,
        user_id=user_id,
        tools=DEMO_TOOLS,
        metadata={},
    )

    # Pick a tool based on user_message keywords (if any)
    selected_tool = None
    selected_args = {}
    lower = user_message.lower()
    for tool_name, keywords in TOOL_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            selected_tool = tool_name
            if tool_name == "list_calendar_events":
                selected_args = {"date": "today"}
            elif tool_name == "send_email":
                selected_args = {
                    "to": "user@example.com",
                    "subject": "Test",
                }
            elif tool_name == "search_records":
                selected_args = {"query": user_message[:40]}
            break

    # Simulate an error if the user_message asks for one
    trigger_error = "error" in lower or "fail" in lower

    async def _run_agent(ctx: AgentContext) -> str:
        if selected_tool:
            tool_ctx = ToolCallContext(
                tool_name=selected_tool,
                tool_arguments=selected_args,
            )
            tool_ctx.agent_context = ctx  # type: ignore[attr-defined]

            async def _execute(c: ToolCallContext) -> Any:
                await asyncio.sleep(0.1)
                if trigger_error:
                    raise ConnectionError("Simulated tool failure")
                return _mock_tool_result(selected_tool, selected_args)

            try:
                await middleware.on_tool_call(tool_ctx, _execute)
            except (PermissionError, ConnectionError):
                if trigger_error:
                    raise

        # Streaming response
        if selected_tool and not trigger_error:
            chunks = [
                "I checked. ",
                "Here is what I found. ",
                f"{_mock_tool_result(selected_tool, selected_args)}. ",
                "Anything else?",
            ]
        else:
            chunks = [
                "Thanks for the question. ",
                "Here is my answer. ",
                "Let me know if you need more detail.",
            ]

        for i, chunk_text in enumerate(chunks):
            chunk_ctx = ResponseChunkContext(
                chunk_text=chunk_text,
                is_final=(i == len(chunks) - 1),
            )
            chunk_ctx.agent_context = ctx  # type: ignore[attr-defined]

            async def _no_op(c: ResponseChunkContext) -> None:
                await asyncio.sleep(0.02)

            await middleware.on_response_chunk(chunk_ctx, _no_op)

        return "Done"

    async def _end(c: AgentContext) -> None:
        pass

    try:
        await middleware.on_agent_start(context, _run_agent)
        await middleware.on_agent_end(context, _end)
    except Exception as exc:
        logger.info("Session ended with exception: %s", exc)


# === CLI entry point ===

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="aaep-maf-server",
        description="Run the AAEP Microsoft Agent Framework HTTP/SSE server",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8083)
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
    logger.info("Starting AAEP MAF server on http://%s:%d", args.host, args.port)
    logger.info("Test with: aaep-conformance producer --endpoint http://%s:%d --level 2",
                args.host, args.port)

    web.run_app(app, host=args.host, port=args.port, print=None)
    return 0


if __name__ == "__main__":
    sys.exit(main())
