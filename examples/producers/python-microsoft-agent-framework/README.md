# Python Microsoft Agent Framework Producer Example

AAEP integration with **Microsoft Agent Framework** (MAF), Microsoft's official agent framework that succeeded Semantic Kernel as the recommended path for building production agents on Azure and beyond.

If you're building agents with Microsoft's stack and want AAEP support — especially with Narrator integration in view — this is the example to copy.

---

## What this example demonstrates

- Direct integration with `microsoft.agents` and the MAF agent lifecycle
- Native handling of MAF's tool/function calling system
- MAF middleware pattern for intercepting agent steps
- Streaming output via MAF's async response iterators
- Tool invocation with safety-gated confirmation for irreversible operations
- All 12 core AAEP event types emitted from MAF-driven agents
- Compatible with Azure OpenAI, Azure AI Foundry, and OpenAI-compatible models

This example **reuses the `AAEPEmitter` from python-minimal** — same machinery, MAF-specific adapter. Everything follows the same safety contract.

---

## When to use this pattern

**Pick this pattern when:**
- You build agents with Microsoft Agent Framework
- You target Azure AI Foundry, Azure OpenAI, or any MAF-compatible model
- You need Narrator/Microsoft Accessibility compatibility in the long term
- You want AAEP support that aligns with Microsoft's official agent stack

**Pick `python-anthropic-sdk` when:** you call Anthropic models directly without MAF.  
**Pick `python-langchain` when:** you use LangChain rather than MAF.  
**Pick `python-minimal` when:** you build agents from scratch without framework.

---

## Installation

```bash
cd examples/producers/python-microsoft-agent-framework
pip install -e .
```

You'll need Microsoft Agent Framework installed (the `microsoft-agents` package or compatible). For Azure model access:

```bash
export AZURE_OPENAI_ENDPOINT="https://your-resource.openai.azure.com"
export AZURE_OPENAI_API_KEY="..."
```

The example also runs in mock mode without any credentials, so the conformance suite can verify it in CI.

Requires Python 3.10 or newer.

---

## Quick start

```python
from microsoft.agents import Agent, AgentBuilder
from aaep_maf import MAFAAEPMiddleware

# Step 1: build your MAF agent normally
agent = (AgentBuilder()
    .with_model("gpt-4o")
    .with_tools(your_tools)
    .build())

# Step 2: create the AAEP middleware
def my_transport(event):
    """Send AAEP events to subscribers (HTTP/SSE, WebSocket, etc.)"""
    print(event)  # in production: serialize and send

middleware = MAFAAEPMiddleware(send_event=my_transport)

# Step 3: attach the middleware to your agent
agent.add_middleware(middleware)

# Step 4: run sessions normally — AAEP events emit automatically
result = await agent.invoke("What's my Azure budget status?")
```

The middleware observes agent execution and emits AAEP events without modifying the agent's behavior. Pure addition, no friction.

---

## Running the included demo

```bash
python -m aaep_maf.example_agent
```

Drives a MAF-style agent through three scenarios: a basic query, a tool call, and a high-risk tool that triggers confirmation. Uses mock mode if MAF or Azure credentials aren't installed/configured.

---

## Running the conformance suite against it

```bash
# Terminal 1: start the server (port 8083)
python -m aaep_maf.server --port 8083

# Terminal 2: run conformance
aaep-conformance producer --endpoint http://localhost:8083 --level 2
```

The server uses mock MAF mode by default for CI portability.

---

## Project layout

```
python-microsoft-agent-framework/
├── README.md
├── pyproject.toml
├── aaep_maf/
│   ├── __init__.py
│   ├── middleware.py           # MAFAAEPMiddleware (the core integration)
│   ├── example_agent.py        # Runnable demo
│   └── server.py               # HTTP/SSE wrapper for conformance testing
└── tests/
    ├── __init__.py
    └── test_middleware.py
```

---

## Key design decisions

### 1. Middleware pattern, not callback handler

MAF uses a middleware pattern (similar to ASP.NET Core or Express.js) where steps in the agent loop pass through a chain of middleware. Our `MAFAAEPMiddleware` slots into this chain, observing each step and emitting the appropriate AAEP event.

This is different from python-langchain's callback handler — MAF didn't choose the callback pattern, so we follow MAF's pattern instead. Both produce identical AAEP events; the integration shape differs.

### 2. Safety gates for tools fire BEFORE execution

When MAF prepares to invoke a tool, our middleware:
1. Inspects the tool's metadata (name, irreversibility, risk)
2. If irreversible or high-risk: emits `agent.awaiting.confirmation` (urgency=critical, default_decision=reject)
3. Blocks the middleware chain until reply arrives (or timeout default)
4. Only allows MAF to proceed on `accept`

MAF doesn't natively block on user input mid-execution. We achieve it via `asyncio.Future` synchronization, the same pattern used in the python-anthropic-sdk adapter.

### 3. Azure AI Foundry compatible

The example respects MAF's content-filter and grounding annotations. When MAF reports a content filter blocked output, our middleware emits a `session.errored` with `error_category: "policy"` and proper remediation hints — preserving the safety signal for AT.

### 4. Same emitter as python-minimal

Imports `AAEPEmitter` from the python-minimal package. Bug fixes propagate. Safety guarantees are uniform.

---

## Microsoft Narrator forward compatibility

This example is positioned for eventual Narrator integration. Key alignments:

- **UIA-friendly summaries** — `summary_normal` fields are written for screen reader announcement, not for visual display
- **Speech rate compliance** — events respect the subscriber's negotiated `pace_wpm` and `cognitive_load` capabilities
- **NaviSync-ready** — the streaming output format works with Narrator's natural-pause heuristics

When AAEP eventually integrates with Narrator (whether via direct adoption or a community bridge), this example will be the canonical Python reference.

---

## See also

- [`../python-minimal/`](../python-minimal/) — manual loop pattern with the same emitter
- [`../python-anthropic-sdk/`](../python-anthropic-sdk/) — Anthropic SDK direct integration
- [Implementer's Guide §3.5](../../../guides/IMPLEMENTERS_GUIDE.md) — Microsoft Agent Framework specifics
- [Microsoft Agent Framework documentation](https://learn.microsoft.com/en-us/azure/ai-foundry/) — upstream reference
