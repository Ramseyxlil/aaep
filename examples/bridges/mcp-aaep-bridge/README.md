# MCP ↔ AAEP Bridge

A bidirectional bridge between the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) and the Agent Accessibility Event Protocol (AAEP). Demonstrates that the two protocols address orthogonal concerns and compose cleanly.

If you build agents that use MCP for tool integration and want them to also speak AAEP for accessibility, this bridge shows how.

---

## Why this bridge exists

MCP and AAEP solve different problems:

| Protocol | Addresses | Standardizes |
|---|---|---|
| **MCP** | Agent ↔ Tool/Resource | Tool discovery, invocation, resources, prompts |
| **AAEP** | Agent ↔ Assistive Technology | Lifecycle events, safety gating, output streaming for AT |

They are complementary, not competing. An agent using MCP for tool integration can simultaneously use AAEP for accessibility announcements; the two protocols address orthogonal concerns and do not conflict.

This bridge makes their cooperation concrete. It runs between an MCP-aware agent and an AAEP-aware AT, translating relevant signals in both directions.

---

## What the bridge does

The bridge is a small process that:

1. **Wraps an MCP client** that connects to MCP servers exposing tools the agent uses
2. **Embeds an AAEP producer** that emits events to AT subscribers
3. **Observes MCP traffic** as the agent calls tools, and translates the relevant traffic into AAEP events

Specifically:

| MCP event | AAEP event emitted |
|---|---|
| `tools/list` returns server capabilities | (no emission; metadata only) |
| `tools/call` request (before execution) | `aaep:agent.tool.invoked` |
| `tools/call` request, irreversible flagged | `aaep:agent.awaiting.confirmation` BEFORE the MCP call |
| `tools/call` response success | `aaep:agent.tool.completed` (status=success) |
| `tools/call` response error | `aaep:agent.tool.completed` (status=error) |
| `tools/call` request times out | `aaep:agent.tool.completed` (status=timeout) |
| MCP server disconnects | `aaep:agent.session.errored` (error_category=network) |
| `resources/read` | (optional; emitted as `state.changed` to `reading_resource`) |
| `prompts/get` | (optional; emitted as `state.changed` to `loading_prompt`) |

The bridge also supports the reverse direction:

| AAEP signal | MCP action |
|---|---|
| `confirmation.reply` decision=reject | Cancel pending `tools/call` request, return error to MCP client |
| `confirmation.reply` decision=accept | Allow `tools/call` request to proceed to the MCP server |
| `clarification.reply` response | Forward as additional context to the MCP server (advisory) |

---

## Installation

```bash
cd examples/bridges/mcp-aaep-bridge
pip install -e .
```

Requires Python 3.10 or newer. The bridge depends on:

- `aaep-minimal-producer>=1.0.0` (reuses the emitter)
- `mcp>=1.0.0` (the official MCP Python SDK)
- `aiohttp>=3.9.0` (HTTP/SSE transport for AAEP subscribers)

---

## Quick start

### 1. Configure your MCP server

The bridge connects to an MCP server you've already set up. For example, if you have an MCP filesystem server:

```bash
# In one terminal: an MCP server
npx -y @modelcontextprotocol/server-filesystem /path/to/workspace
```

### 2. Start the bridge

```bash
aaep-mcp-bridge \
    --mcp-server "npx -y @modelcontextprotocol/server-filesystem /path/to/workspace" \
    --aaep-port 8090
```

This starts a bridge that:
- Connects to the MCP filesystem server via stdio JSON-RPC
- Exposes an AAEP `/events` SSE endpoint on `http://localhost:8090`
- Translates every MCP tool call into the appropriate AAEP events

### 3. Connect an AT subscriber

In another terminal:

```bash
aaep-listen --endpoint http://localhost:8090
```

### 4. Drive the agent through the bridge

In a third terminal, send an MCP request through the bridge (or have your agent connect to the bridge as if it were the MCP server directly):

```bash
# Example: list available tools (simple MCP request)
curl -X POST http://localhost:8090/mcp \
    -H "Content-Type: application/json" \
    -d '{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}'

# Example: call a tool
curl -X POST http://localhost:8090/mcp \
    -H "Content-Type: application/json" \
    -d '{
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "read_file",
            "arguments": {"path": "/etc/hostname"}
        }
    }'
```

The AAEP subscriber (terminal with `aaep-listen`) will show:

```
[12:34:56.789] aaep:agent.tool.invoked           Calling read_file via MCP.
                  tool: read_file
                  risk_level: low
                  irreversible: false
                  args_summary: path=/etc/hostname

[12:34:56.823] aaep:agent.tool.completed         myhost.local
                  tool: read_file
                  status: success
```

For tools flagged as irreversible (configurable; see §"Risk Configuration" below), the bridge inserts an `awaiting.confirmation` event before the MCP call and blocks until the AT subscriber replies.

---

## Architecture

```
   AT Subscriber                                              MCP Server
        ↑                                                          ↑
        │ SSE /events                                              │ stdio
        │ POST /messages                                           │ JSON-RPC
        │                                                          │
        ▼                                                          ▼
   ┌────────────────────────────────────────────────────────────────┐
   │                  aaep-mcp-bridge process                       │
   │                                                                │
   │  ┌──────────────┐   translation   ┌──────────────┐            │
   │  │ AAEP         │ ───────────────▶│ MCP Client   │            │
   │  │ Producer     │                  │ (stdio)      │            │
   │  └──────────────┘                  └──────────────┘            │
   │      ▲                                    │                    │
   │      │                                    │                    │
   │      │ confirmation reply                 │ tool/call          │
   │      │ (accept/reject)                    │ response           │
   │      │                                    ▼                    │
   │  ┌──────────────────────────────────────────┐                 │
   │  │  HTTP server: /mcp /events /messages     │                 │
   │  └──────────────────────────────────────────┘                 │
   │      ▲                                                         │
   │      │ JSON-RPC                                                │
   │      │ HTTP                                                    │
   └──────┼─────────────────────────────────────────────────────────┘
          │
          │
   Agent (any LLM with MCP support)
```

The agent talks to the bridge as if it were the MCP server. The MCP server is unchanged. The AT is unchanged. The bridge is the glue.

---

## Risk configuration

By default, the bridge uses heuristics matching the python-minimal example to classify tool risk:

- Tool names containing `send_`, `delete_`, `transfer_`, `write_`, `execute_`, `publish_`, `make_payment` → **high-risk irreversible**
- All other tools → **low-risk**

To override, provide a `--risk-config` JSON file:

```json
{
  "tool_overrides": {
    "read_file": {"risk_level": "low", "irreversible": false},
    "write_file": {"risk_level": "high", "irreversible": true},
    "execute_command": {"risk_level": "high", "irreversible": true}
  },
  "default": {"risk_level": "low", "irreversible": false}
}
```

The bridge consults this map for every `tools/call` before deciding whether to emit `awaiting.confirmation`.

---

## Project layout

```
mcp-aaep-bridge/
├── README.md
├── pyproject.toml
├── aaep_mcp_bridge/
│   ├── __init__.py
│   ├── bridge.py            # MCPToAAEPBridge — the core translator
│   ├── risk.py              # Risk classification + override config
│   └── server.py            # HTTP server combining /mcp + AAEP /events
└── tests/
    └── test_bridge.py
```

---

## Limitations and known issues

This is a **reference bridge**, not production code. Specifically:

- **stdio transport only.** The bridge speaks JSON-RPC over stdio to the MCP server. HTTP/SSE-transported MCP servers will need adaptation. The MCP SDK supports both.
- **One MCP server per bridge instance.** Multi-server MCP setups need to run one bridge per server (or extend this code).
- **No streaming response support yet.** MCP doesn't currently stream `tools/call` responses; if/when it does, this bridge will need updating.
- **Resources and prompts are minimal.** This bridge focuses on `tools/*`. Resources and prompts emit `state.changed` only.
- **No authentication relay.** If your MCP server requires authentication, you'll need to configure it before the bridge starts; this code doesn't proxy credentials.

For production deployments, consider these as starting points to extend, not finished features to rely on.

---

## See also

- [Model Context Protocol specification](https://modelcontextprotocol.io/) — the upstream MCP standard
- [`../opentelemetry-aaep-bridge/`](../opentelemetry-aaep-bridge/) — sister bridge for OpenTelemetry
- [Specification Chapter 11](../../../spec/11-internationalization.md) — bridge patterns
- [Implementer's Guide §5](../../../guides/IMPLEMENTERS_GUIDE.md) — bridge integration patterns
- [`../../subscribers/cli-debug/`](../../subscribers/cli-debug/) — subscriber to test this bridge with
