"""
server.py — HTTP server combining /mcp (JSON-RPC) and AAEP transport endpoints.

Endpoints:
    POST /mcp         - JSON-RPC requests routed through the bridge
    GET  /events      - SSE stream of AAEP events
    POST /messages    - AAEP reply messages (confirmation, clarification)
    GET  /healthz     - Health check

Run with:
    aaep-mcp-bridge --mcp-server "npx -y @modelcontextprotocol/server-filesystem /path"

The /mcp endpoint accepts standard JSON-RPC 2.0 requests for tools/call,
tools/list, and other MCP methods. Each tools/call passes through the bridge,
emitting AAEP events along the way. Other methods are forwarded with minimal
ceremony (no AAEP translation needed).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any

from aiohttp import web

from aaep_minimal_producer.server import (
    EventBroadcaster,
    _cors_middleware,
    handle_events_sse,
    handle_healthz,
)

from aaep_mcp_bridge.bridge import MCPToAAEPBridge
from aaep_mcp_bridge.risk import RiskConfig


logger = logging.getLogger("aaep_mcp_bridge.server")


# === Application builder ===

def build_app(
    *,
    mcp_server_cmd: str,
    risk_config: RiskConfig | None = None,
) -> web.Application:
    """Construct the aiohttp application wiring the bridge to HTTP routes."""
    app = web.Application()
    broadcaster = EventBroadcaster()
    bridge = MCPToAAEPBridge(
        mcp_server_cmd=mcp_server_cmd,
        send_event=broadcaster.publish,
        risk_config=risk_config,
    )

    app["broadcaster"] = broadcaster
    app["bridge"] = bridge
    # Track active session_id per HTTP client by remote address (best-effort).
    # In production, use proper session affinity.
    app["session_by_client"] = {}

    app.router.add_get("/events", handle_events_sse)
    app.router.add_get("/healthz", handle_healthz)
    app.router.add_post("/messages", handle_reply_message)
    app.router.add_post("/mcp", handle_mcp_request)

    app.middlewares.append(_cors_middleware)
    app.on_startup.append(_on_startup)
    app.on_cleanup.append(_on_cleanup)

    return app


async def _on_startup(app: web.Application) -> None:
    bridge: MCPToAAEPBridge = app["bridge"]
    await bridge.start()
    if bridge.mock_mode:
        logger.warning("Bridge running in MOCK MODE (MCP SDK not installed)")
    else:
        logger.info("Bridge connected to MCP server")


async def _on_cleanup(app: web.Application) -> None:
    bridge: MCPToAAEPBridge = app["bridge"]
    await bridge.stop()
    logger.info("Bridge disconnected from MCP server")


# === Request handlers ===

async def handle_mcp_request(request: web.Request) -> web.Response:
    """
    POST /mcp - accept a JSON-RPC request and relay through the bridge.

    For tools/call, this passes through MCPToAAEPBridge.call_tool() so that
    AAEP events are emitted. For other methods (tools/list, resources/*,
    prompts/*), this forwards directly to the MCP session.
    """
    try:
        payload = await request.json()
    except Exception:
        return _jsonrpc_error(None, -32700, "Parse error")

    if not isinstance(payload, dict):
        return _jsonrpc_error(None, -32600, "Invalid Request")

    rpc_id = payload.get("id")
    method = payload.get("method")
    params = payload.get("params", {})

    if method == "tools/call":
        return await _handle_tools_call(request, rpc_id, params)

    if method in ("tools/list", "resources/list", "resources/read",
                  "prompts/list", "prompts/get"):
        return await _handle_passthrough(request, rpc_id, method, params)

    # Begin/end session helpers (non-standard MCP extensions for testing)
    if method == "aaep/begin_session":
        return await _handle_begin_session(request, rpc_id, params)

    if method == "aaep/end_session":
        return await _handle_end_session(request, rpc_id, params)

    return _jsonrpc_error(rpc_id, -32601, f"Method not found: {method}")


async def _handle_tools_call(
    request: web.Request,
    rpc_id: Any,
    params: dict[str, Any],
) -> web.Response:
    """Relay a tools/call through the bridge with AAEP translation."""
    bridge: MCPToAAEPBridge = request.app["bridge"]
    session_map: dict[str, str] = request.app["session_by_client"]

    tool_name = params.get("name")
    arguments = params.get("arguments", {})
    if not isinstance(tool_name, str):
        return _jsonrpc_error(rpc_id, -32602, "params.name must be a string")
    if not isinstance(arguments, dict):
        return _jsonrpc_error(rpc_id, -32602, "params.arguments must be an object")

    # Determine session: explicit aaep_session_id wins; else best-effort by client IP
    aaep_session_id = params.get("aaep_session_id")
    client_key = request.remote or "unknown"
    if not aaep_session_id:
        aaep_session_id = session_map.get(client_key)
    if not aaep_session_id:
        aaep_session_id = bridge.begin_session(
            user_message=f"tools/call {tool_name}",
        )
        session_map[client_key] = aaep_session_id

    try:
        result = await bridge.call_tool(
            session_id=aaep_session_id,
            tool_name=tool_name,
            arguments=arguments,
        )
        return _jsonrpc_result(rpc_id, result)
    except Exception as exc:
        logger.exception("tools/call failed")
        bridge.error_session(aaep_session_id, error=exc)
        session_map.pop(client_key, None)
        return _jsonrpc_error(rpc_id, -32000, str(exc))


async def _handle_passthrough(
    request: web.Request,
    rpc_id: Any,
    method: str,
    params: dict[str, Any],
) -> web.Response:
    """Forward an MCP request that doesn't need AAEP translation."""
    bridge: MCPToAAEPBridge = request.app["bridge"]
    if not bridge.mock_mode and bridge._mcp_session is not None:
        try:
            # Translate method to the SDK call
            if method == "tools/list":
                response = await bridge._mcp_session.list_tools()
            elif method == "resources/list":
                response = await bridge._mcp_session.list_resources()
            elif method == "resources/read":
                response = await bridge._mcp_session.read_resource(params.get("uri", ""))
            elif method == "prompts/list":
                response = await bridge._mcp_session.list_prompts()
            elif method == "prompts/get":
                response = await bridge._mcp_session.get_prompt(
                    params.get("name", ""),
                    arguments=params.get("arguments", {}),
                )
            else:
                return _jsonrpc_error(rpc_id, -32601, f"Method not implemented: {method}")
            result = response.model_dump() if hasattr(response, "model_dump") else dict(response)
            return _jsonrpc_result(rpc_id, result)
        except Exception as exc:
            return _jsonrpc_error(rpc_id, -32000, str(exc))
    # Mock mode response
    return _jsonrpc_result(rpc_id, {"result": "mock", "method": method})


async def _handle_begin_session(
    request: web.Request,
    rpc_id: Any,
    params: dict[str, Any],
) -> web.Response:
    bridge: MCPToAAEPBridge = request.app["bridge"]
    aaep_session_id = bridge.begin_session(
        user_message=str(params.get("user_message", "")),
        user_id=params.get("user_id"),
    )
    session_map: dict[str, str] = request.app["session_by_client"]
    session_map[request.remote or "unknown"] = aaep_session_id
    return _jsonrpc_result(rpc_id, {"aaep_session_id": aaep_session_id})


async def _handle_end_session(
    request: web.Request,
    rpc_id: Any,
    params: dict[str, Any],
) -> web.Response:
    bridge: MCPToAAEPBridge = request.app["bridge"]
    aaep_session_id = params.get("aaep_session_id")
    summary = str(params.get("summary", "Done."))
    if not aaep_session_id:
        return _jsonrpc_error(rpc_id, -32602, "aaep_session_id required")
    bridge.end_session(aaep_session_id, summary=summary)
    session_map: dict[str, str] = request.app["session_by_client"]
    for k, v in list(session_map.items()):
        if v == aaep_session_id:
            session_map.pop(k, None)
    return _jsonrpc_result(rpc_id, {"status": "ended"})


async def handle_reply_message(request: web.Request) -> web.Response:
    """POST /messages — confirmation/clarification replies."""
    try:
        message = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400)

    reply_token = message.get("reply_token")
    if not isinstance(reply_token, str) or not reply_token:
        return web.json_response({"error": "reply_token required"}, status=400)

    bridge: MCPToAAEPBridge = request.app["bridge"]
    msg_type = message.get("type", "")

    if msg_type == "confirmation.reply":
        decision = message.get("decision")
        if decision not in ("accept", "reject"):
            return web.json_response(
                {"error": "decision must be accept or reject"}, status=400
            )
        bridge.emitter.submit_reply(reply_token, decision)
        return web.json_response({"status": "received"})

    if msg_type == "clarification.reply":
        response = message.get("response")
        if response is None:
            return web.json_response({"error": "response required"}, status=400)
        bridge.emitter.submit_reply(reply_token, str(response))
        return web.json_response({"status": "received"})

    return web.json_response(
        {"error": f"unsupported message type: {msg_type}"}, status=400
    )


# === JSON-RPC helpers ===

def _jsonrpc_result(rpc_id: Any, result: Any) -> web.Response:
    return web.json_response({
        "jsonrpc": "2.0",
        "id": rpc_id,
        "result": result,
    })


def _jsonrpc_error(rpc_id: Any, code: int, message: str) -> web.Response:
    return web.json_response({
        "jsonrpc": "2.0",
        "id": rpc_id,
        "error": {"code": code, "message": message},
    })


# === CLI entry ===

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="aaep-mcp-bridge",
        description="Bridge between an MCP server and AAEP subscribers",
        epilog=(
            "Example:\n"
            "  aaep-mcp-bridge \\\n"
            "      --mcp-server 'npx -y @modelcontextprotocol/server-filesystem /work' \\\n"
            "      --aaep-port 8090\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--mcp-server", required=True,
        help='Command to start the MCP server (e.g., "npx -y @modelcontextprotocol/server-filesystem /workspace")',
    )
    parser.add_argument(
        "--risk-config", default=None,
        help="Path to a JSON file with per-tool risk overrides",
    )
    parser.add_argument(
        "--host", default="127.0.0.1",
        help="Host to bind (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--aaep-port", "-p", type=int, default=8090,
        help="Port to bind (default: 8090)",
    )
    parser.add_argument(
        "--log-level", default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    parser.add_argument(
        "--version", action="version",
        version="aaep-mcp-bridge 1.0.0 (AAEP spec 1.0.0)",
    )

    args = parser.parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(name)s [%(levelname)s] %(message)s",
    )

    risk_config = None
    if args.risk_config:
        try:
            risk_config = RiskConfig.from_file(args.risk_config)
            logger.info("Loaded risk config from %s", args.risk_config)
        except (OSError, json.JSONDecodeError) as e:
            print(f"aaep-mcp-bridge: cannot load risk config: {e}", file=sys.stderr)
            return 2

    app = build_app(
        mcp_server_cmd=args.mcp_server,
        risk_config=risk_config,
    )

    logger.info("Starting MCP-AAEP bridge on http://%s:%d", args.host, args.aaep_port)
    logger.info("MCP server command: %s", args.mcp_server)
    logger.info("Subscribers connect to: http://%s:%d/events", args.host, args.aaep_port)
    logger.info("Agents POST MCP requests to: http://%s:%d/mcp", args.host, args.aaep_port)

    web.run_app(app, host=args.host, port=args.aaep_port, print=None)
    return 0


if __name__ == "__main__":
    sys.exit(main())
