"""
bridge.py — MCPToAAEPBridge implementation.

The core translator. Wraps an MCP client and an AAEP emitter; intercepts
every MCP tool call, classifies risk, optionally gates execution behind an
AAEP confirmation event, and surfaces the result as an AAEP tool.completed.

When the MCP SDK isn't installed, falls back to a synthetic mock so this
module can be imported and inspected anywhere. Real MCP integration requires
`pip install mcp`.
"""

from __future__ import annotations

import asyncio
import logging
import shlex
import time
from typing import Any, Callable

try:
    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client
    HAS_MCP = True
except ImportError:
    HAS_MCP = False
    ClientSession = None  # type: ignore[assignment,misc]
    StdioServerParameters = None  # type: ignore[assignment,misc]
    stdio_client = None  # type: ignore[assignment]

from aaep_minimal_producer.emitter import (
    AAEPEmitter,
    classify_error_category,
    make_id,
    safe_args_summary,
)

from aaep_mcp_bridge.risk import RiskAssessment, RiskConfig


logger = logging.getLogger("aaep_mcp_bridge.bridge")


class BridgeSession:
    """
    Represents one logical AAEP session that may issue multiple MCP tool calls.

    A bridge instance can host many concurrent sessions; each session has its
    own AAEP session_id, tool count, and start time.
    """

    __slots__ = ("session_id", "start_time", "tool_count", "current_state")

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.start_time = time.monotonic()
        self.tool_count = 0
        self.current_state = "idle"


class MCPToAAEPBridge:
    """
    Bidirectional bridge between MCP and AAEP.

    Construction does not start the bridge; call await bridge.start() to
    connect to the MCP server, and bridge.stop() to disconnect cleanly.
    """

    def __init__(
        self,
        *,
        mcp_server_cmd: str,
        send_event: Callable[[dict[str, Any]], Any],
        risk_config: RiskConfig | None = None,
        agent_id: str = "aaep-mcp-bridge",
        agent_name: str = "MCP↔AAEP Bridge",
        confirmation_timeout_seconds: int = 300,
    ):
        self.mcp_server_cmd = mcp_server_cmd
        self.risk_config = risk_config or RiskConfig()
        self.confirmation_timeout_seconds = confirmation_timeout_seconds
        self.emitter = AAEPEmitter(
            send_event=send_event,
            agent_id=agent_id,
            agent_version="1.0.0",
            agent_name=agent_name,
            model="mcp-bridge",
        )
        self._sessions: dict[str, BridgeSession] = {}
        self._mcp_session: Any = None  # ClientSession when started
        self._mcp_context = None  # async context manager
        self._stdio_context = None
        self._running = False

    @property
    def mock_mode(self) -> bool:
        """True if the MCP SDK is not available (mock responses used)."""
        return not HAS_MCP

    # === Lifecycle ===

    async def start(self) -> None:
        """Connect to the MCP server."""
        if self._running:
            return
        self._running = True

        if not HAS_MCP:
            logger.warning("MCP SDK not installed; running in mock mode")
            return

        parts = shlex.split(self.mcp_server_cmd)
        if not parts:
            raise ValueError("mcp_server_cmd must not be empty")

        params = StdioServerParameters(command=parts[0], args=parts[1:])
        self._stdio_context = stdio_client(params)
        read, write = await self._stdio_context.__aenter__()
        self._mcp_context = ClientSession(read, write)
        self._mcp_session = await self._mcp_context.__aenter__()
        await self._mcp_session.initialize()
        logger.info("MCP session initialized")

    async def stop(self) -> None:
        """Disconnect from the MCP server."""
        if not self._running:
            return
        self._running = False

        if self._mcp_context is not None:
            try:
                await self._mcp_context.__aexit__(None, None, None)
            except Exception:
                logger.exception("Error closing MCP session")
            self._mcp_context = None
            self._mcp_session = None
        if self._stdio_context is not None:
            try:
                await self._stdio_context.__aexit__(None, None, None)
            except Exception:
                logger.exception("Error closing stdio transport")
            self._stdio_context = None

    # === Session management ===

    def begin_session(
        self,
        *,
        user_message: str = "",
        user_id: str | None = None,
    ) -> str:
        """
        Open a new AAEP session. The session represents a logical unit of work
        (e.g., one user request) that may involve multiple MCP tool calls.
        """
        aaep_sid = self.emitter.start_session(
            summary_normal=(
                f"Processing: {user_message[:80]}" if user_message
                else "Bridge session opened"
            ),
            request_text=user_message or None,
            requested_by=f"user:{user_id}" if user_id else None,
        )
        self._sessions[aaep_sid] = BridgeSession(aaep_sid)
        self._transition(aaep_sid, "thinking", "Bridge ready to relay tool calls.")
        return aaep_sid

    def end_session(self, session_id: str, *, summary: str = "Done.") -> None:
        """Close an AAEP session normally."""
        session = self._sessions.pop(session_id, None)
        if session is None:
            return
        duration_ms = int((time.monotonic() - session.start_time) * 1000)
        self.emitter.complete_session(
            session_id=session_id,
            summary_normal=summary,
            duration_ms=duration_ms,
            tool_invocations_count=session.tool_count,
        )

    def error_session(
        self,
        session_id: str,
        *,
        error: BaseException,
        summary: str | None = None,
    ) -> None:
        """Close an AAEP session due to error."""
        session = self._sessions.pop(session_id, None)
        if session is None:
            return
        self.emitter.error_session(
            session_id=session_id,
            error_category=classify_error_category(error),
            summary_normal=summary or f"Error: {type(error).__name__}",
            error_message=str(error)[:1000],
            recoverable=isinstance(error, (TimeoutError, ConnectionError)),
        )

    # === The translation core: relay a tool call ===

    async def call_tool(
        self,
        *,
        session_id: str,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Relay one MCP tools/call through the bridge with full AAEP translation.

        Returns the MCP response (typically a dict with content list), or
        an error result if the user declined the action or the call failed.
        """
        session = self._sessions.get(session_id)
        if session is None:
            raise ValueError(f"Unknown AAEP session: {session_id}")

        args = arguments or {}
        risk = self.risk_config.classify(tool_name)
        aaep_call_id = make_id("call")

        # Transition + emit tool.invoked BEFORE the call
        self._transition(
            session_id, "calling_tool",
            f"Preparing to call {tool_name} via MCP.",
        )
        self.emitter.tool_invoked(
            session_id=session_id,
            tool=tool_name,
            tool_call_id=aaep_call_id,
            args_summary=safe_args_summary(args),
            risk_level=risk.risk_level,
            irreversible=risk.irreversible,
            summary_normal=f"Calling {tool_name} via MCP.",
        )
        session.tool_count += 1

        # Gate the call behind confirmation if risk warrants
        if risk.requires_confirmation:
            reply_token = self.emitter.await_confirmation(
                session_id=session_id,
                action=f"Call {tool_name} via MCP with: {safe_args_summary(args, 200)}",
                consequence=(
                    "This action cannot be easily undone."
                    if risk.irreversible
                    else "This action will be executed."
                ),
                timeout_seconds=self.confirmation_timeout_seconds,
                default_decision="reject",
                risk_level=risk.risk_level,
                irreversible=risk.irreversible,
                summary_normal=f"Confirm: call {tool_name}?",
            )
            try:
                decision = await asyncio.wait_for(
                    self.emitter.wait_for_decision(reply_token),
                    timeout=self.confirmation_timeout_seconds,
                )
            except asyncio.TimeoutError:
                decision = "reject"

            if decision != "accept":
                # User declined; emit tool.completed(error) and return without calling MCP
                self.emitter.tool_completed(
                    session_id=session_id,
                    tool=tool_name,
                    tool_call_id=aaep_call_id,
                    status="error",
                    error_message="User declined to authorize this action.",
                )
                self._transition(session_id, "thinking", "Action declined.")
                return {
                    "isError": True,
                    "content": [{"type": "text", "text": "User declined the action."}],
                    "aaep_decision": "rejected",
                }

        # Perform the actual MCP call
        try:
            if HAS_MCP and self._mcp_session is not None:
                response = await self._mcp_session.call_tool(tool_name, arguments=args)
                # MCP responses are typically: {"content": [...], "isError": bool}
                response_dict = (
                    response.model_dump() if hasattr(response, "model_dump")
                    else dict(response)
                )
            else:
                # Mock mode
                response_dict = await self._mock_call_tool(tool_name, args)

            is_error = bool(response_dict.get("isError", False))
            summary = _summarize_mcp_response(response_dict)

            self.emitter.tool_completed(
                session_id=session_id,
                tool=tool_name,
                tool_call_id=aaep_call_id,
                status="error" if is_error else "success",
                summary_normal=summary,
                error_message=summary if is_error else None,
            )
            self._transition(session_id, "thinking", "Tool call complete.")
            return response_dict

        except asyncio.TimeoutError as exc:
            self.emitter.tool_completed(
                session_id=session_id,
                tool=tool_name,
                tool_call_id=aaep_call_id,
                status="timeout",
                error_message=str(exc)[:1000] or "Tool call timed out",
            )
            raise
        except Exception as exc:
            self.emitter.tool_completed(
                session_id=session_id,
                tool=tool_name,
                tool_call_id=aaep_call_id,
                status="error",
                error_message=str(exc)[:1000],
            )
            raise

    # === Mock helpers (used when MCP SDK isn't installed) ===

    async def _mock_call_tool(
        self,
        tool_name: str,
        args: dict[str, Any],
    ) -> dict[str, Any]:
        """Simulate an MCP response for offline testing."""
        await asyncio.sleep(0.1)
        if "fail" in tool_name.lower() or "fail" in str(args).lower():
            return {
                "isError": True,
                "content": [{"type": "text", "text": "Simulated MCP error"}],
            }
        return {
            "isError": False,
            "content": [{
                "type": "text",
                "text": f"Mock result for {tool_name}({safe_args_summary(args)})",
            }],
        }

    # === State transition helper ===

    def _transition(self, session_id: str, to_state: str, summary: str) -> None:
        session = self._sessions.get(session_id)
        if session is None or session.current_state == to_state:
            return
        self.emitter.state_changed(
            session_id=session_id,
            from_state=session.current_state,
            to_state=to_state,
            summary_normal=summary,
        )
        session.current_state = to_state


def _summarize_mcp_response(response: dict[str, Any]) -> str:
    """Extract a human-readable summary from an MCP tools/call response."""
    content = response.get("content", [])
    if not isinstance(content, list):
        return "MCP response received."
    parts: list[str] = []
    for item in content:
        if isinstance(item, dict):
            if item.get("type") == "text":
                parts.append(str(item.get("text", "")))
            elif item.get("type") == "image":
                parts.append("[image]")
            elif item.get("type") == "resource":
                parts.append("[resource]")
    if not parts:
        return "MCP response received."
    summary = " ".join(parts)
    return summary if len(summary) <= 200 else summary[:197] + "..."
