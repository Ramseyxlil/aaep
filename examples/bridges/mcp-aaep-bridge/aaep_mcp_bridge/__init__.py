"""
MCP ↔ AAEP Bridge.

Bidirectional bridge between the Model Context Protocol and AAEP. Translates
MCP tool calls and lifecycle events into AAEP events, and forwards AAEP
confirmation decisions back to gate MCP tool execution.

Public API:

    from aaep_mcp_bridge import MCPToAAEPBridge, RiskConfig

    bridge = MCPToAAEPBridge(
        mcp_server_cmd="npx -y @modelcontextprotocol/server-filesystem /workspace",
        send_event=my_aaep_transport,
        risk_config=RiskConfig.from_file("risks.json"),
    )

    await bridge.start()
    # ... bridge runs until cancelled ...
    await bridge.stop()

CLI entry point:

    aaep-mcp-bridge --mcp-server "..." --aaep-port 8090

See README.md for the full translation table and architecture.
"""

from __future__ import annotations

__version__ = "1.0.0"
__author__ = "Abdulrafiu Izuafa"
__email__ = "Abdulrafiu@izusoft.tech"
__license__ = "MIT"
__aaep_spec_version__ = "1.0.0"


from aaep_mcp_bridge.bridge import (
    BridgeSession,
    MCPToAAEPBridge,
)
from aaep_mcp_bridge.risk import (
    RiskAssessment,
    RiskConfig,
)


__all__ = [
    "__version__",
    "__author__",
    "__email__",
    "__license__",
    "__aaep_spec_version__",
    "MCPToAAEPBridge",
    "BridgeSession",
    "RiskConfig",
    "RiskAssessment",
]
