"""
HTTP/SSE server wrapping the LangChain AAEP integration.

Mirrors the python-minimal server interface so the conformance suite can
verify the LangChain integration with:

    aaep-conformance producer --endpoint http://localhost:8081 --profile langchain-mode

Endpoints are identical to python-minimal:
    POST /sessions   - Start a new session
    GET  /events     - SSE event stream
    POST /messages   - Reply messages
    GET  /healthz    - Health check

The session execution differs: this server drives a LangChain-style
callback sequence (matching example_agent.py) rather than a manual loop.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from typing import Any
from uuid import uuid4

from aiohttp import web

# Reuse the EventBroadcaster and supporting infrastructure
from aaep_minimal_producer.server import (
    EventBroadcaster,
    _cors_middleware,
    _cors_headers,
    handle_events_sse,
    handle_healthz,
)

from aaep_langchain.callback_handler import LangChainAAEPHandler


logger = logging.getLogger("aaep_langchain.server")


# === Application state ===

def _build_app() -> web.Application:
    app = web.Application()
    broadcaster = EventBroadcaster()
    handler = LangChainAAEPHandler(
        send_event=broadcaster.publish,
        agent_id="aaep-langchain-server",
        agent_name="AAEP LangChain Server",
        model="demo-model",
    )

    app["broadcaster"] = broadcaster
    app["handler"] = handler

    app.router.add_post("/sessions", handle_start_session)
    app.router.add_get("/events", handle_events_sse)
    app.router.add_post("/messages", handle_reply_message)
    app.router.add_get("/healthz", handle_healthz)

    app.middlewares.append(_cors_middleware)

    return app


# === Request handlers ===

async def handle_start_session(request: web.Request) -> web.Response:
    """POST /sessions { "user_message": "..." } -> { "status": "started" }"""
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

    handler: LangChainAAEPHandler = request.app["handler"]

    # Schedule the simulated LangChain run as a background task
    asyncio.create_task(_simulate_langchain_run(handler, user_message))
    await asyncio.sleep(0.05)

    return web.json_response({
        "status": "started",
        "user_message": user_message,
    }, status=202)


async def handle_reply_message(request: web.Request) -> web.Response:
    """POST /messages - reply messages routed to the emitter."""
    try:
        message = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400)

    reply_token = message.get("reply_token", "")
    if not reply_token:
        return web.json_response(
            {"error": "reply_token is required"}, status=400
        )

    handler: LangChainAAEPHandler = request.app["handler"]
    msg_type = message.get("type", "")

    if msg_type == "confirmation.reply":
        decision = message.get("decision", "")
        if decision not in ("accept", "reject"):
            return web.json_response(
                {"error": "decision must be accept or reject"}, status=400
            )
        handler.emitter.submit_reply(reply_token, decision)
        return web.json_response({"status": "received"})

    if msg_type == "clarification.reply":
        response = message.get("response")
        if response is None:
            return web.json_response(
                {"error": "response field required"}, status=400
            )
        handler.emitter.submit_reply(reply_token, str(response))
        return web.json_response({"status": "received"})

    return web.json_response(
        {"error": f"unsupported message type: {msg_type}"}, status=400
    )


# === Simulated LangChain run ===

async def _simulate_langchain_run(
    handler: LangChainAAEPHandler,
    user_message: str,
) -> None:
    """
    Simulate a complete LangChain agent run to exercise the callback handler.

    Drives the handler with on_chain_start -> tool (if applicable) -> LLM
    streaming -> on_chain_end. Matches the patterns example_agent.py
    demonstrates, but adapted for the conformance suite's prompt variety.
    """
    chain_run_id = uuid4()
    try:
        handler.on_chain_start(
            serialized={"name": "OpenAITools Agent"},
            inputs={"input": user_message},
            run_id=chain_run_id,
            parent_run_id=None,
        )

        # Decide on a tool based on the user_message text
        tool_name, tool_args, tool_output = _pick_tool(user_message)
        if tool_name is not None:
            tool_run_id = uuid4()
            handler.on_tool_start(
                serialized={"name": tool_name},
                input_str=str(tool_args),
                run_id=tool_run_id,
                parent_run_id=chain_run_id,
                inputs=tool_args,
            )
            await asyncio.sleep(0.1)

            # Simulate occasional tool errors based on input
            if "error" in user_message.lower() or "fail" in user_message.lower():
                handler.on_tool_error(
                    error=ConnectionError("Simulated tool failure"),
                    run_id=tool_run_id,
                    parent_run_id=chain_run_id,
                )
                handler.on_chain_error(
                    error=ConnectionError("Simulated tool failure"),
                    run_id=chain_run_id,
                    parent_run_id=None,
                )
                return

            handler.on_tool_end(
                output=tool_output,
                run_id=tool_run_id,
                parent_run_id=chain_run_id,
            )

        # LLM streaming output
        llm_run_id = uuid4()
        handler.on_llm_start(
            serialized={"name": "ChatOpenAI"},
            prompts=[user_message],
            run_id=llm_run_id,
            parent_run_id=chain_run_id,
        )

        response_tokens = _generate_response_tokens(user_message, tool_output)
        for token in response_tokens:
            handler.on_llm_new_token(token, run_id=llm_run_id)
            await asyncio.sleep(0.02)

        handler.on_llm_end(response=None, run_id=llm_run_id)

        handler.on_chain_end(
            outputs={"output": "".join(response_tokens)},
            run_id=chain_run_id,
            parent_run_id=None,
        )

    except Exception as exc:
        # Defensive: if anything goes wrong during simulation, emit an error
        logger.exception("Simulated run failed: %s", exc)
        try:
            handler.on_chain_error(
                error=exc,
                run_id=chain_run_id,
                parent_run_id=None,
            )
        except Exception:
            pass


def _pick_tool(user_message: str) -> tuple[str | None, dict[str, Any], str]:
    """Pick a mock tool to call based on the user message keywords."""
    lower = user_message.lower()
    if any(kw in lower for kw in ("balance", "account")):
        return "fetch_balance", {"account": "checking"}, "$3,247.18"
    if any(kw in lower for kw in ("email", "send mail")):
        return "send_email", {"to": "user@example.com", "subject": "Test"}, "Email sent"
    if any(kw in lower for kw in ("transfer", "move money")):
        return (
            "transfer_funds",
            {"from": "checking", "to": "savings", "amount": 500},
            "Transfer complete",
        )
    if any(kw in lower for kw in ("search", "find", "look up")):
        return "search_records", {"query": user_message[:40]}, "Found 3 results"
    return None, {}, ""


def _generate_response_tokens(user_message: str, tool_output: str) -> list[str]:
    """Generate a plausible token-by-token response."""
    if tool_output:
        return [
            "I ", "found ", "that ", "result. ",
            tool_output + ". ",
            "Anything ", "else ", "I ", "can ", "help ", "with?",
        ]
    return [
        "Thanks ", "for ", "your ", "question. ",
        "Here ", "is ", "what ", "I ", "know. ",
        "Let ", "me ", "know ", "if ", "you ", "need ", "more ", "detail.",
    ]


# === CLI entry point ===

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="aaep-langchain-server",
        description="Run the AAEP LangChain integration HTTP/SSE server",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8081)
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
    logger.info("Starting AAEP LangChain server on http://%s:%d", args.host, args.port)
    logger.info("Test with: aaep-conformance producer --endpoint http://%s:%d --profile langchain-mode",
                args.host, args.port)

    web.run_app(app, host=args.host, port=args.port, print=None)
    return 0


if __name__ == "__main__":
    sys.exit(main())
