# Python Minimal Producer Example

A minimal but complete AAEP producer implementation in Python. This example demonstrates the **manual loop pattern** from the [Implementer's Guide §2.5](../../../guides/IMPLEMENTERS_GUIDE.md) at production quality.

**This is the reference example.** If you're building an AAEP producer from scratch in Python without using a framework like LangChain, copy this code and adapt it. Every other example in this repository follows patterns established here.

---

## What this example demonstrates

- A complete agent loop emitting valid AAEP events
- All 12 core AAEP event types in realistic usage
- The confirmation flow for irreversible actions
- Streaming output with proper coalescing
- Tool invocation with arguments redaction
- Session lifecycle management with terminal events on success, cancellation, and error
- HTTP/SSE transport binding for subscribers
- Conformance Level 2 ready (passes the full `aaep-conformance producer --level 2` test suite)

This example does NOT include:
- LangChain or any other framework integration (see [`../python-langchain/`](../python-langchain/))
- Real LLM integration (uses a mock LLM client for portability)
- Production-grade authentication or rate limiting (those belong at a higher layer)

---

## Installation

```bash
cd examples/producers/python-minimal
pip install -e .
```

Requires Python 3.10 or newer.

---

## Quick start

Start the producer server:

```bash
python -m aaep_minimal_producer.server --port 8080
```

In another terminal, run a session:

```bash
curl -X POST http://localhost:8080/sessions \
    -H "Content-Type: application/json" \
    -d '{"user_message": "Tell me about retirement planning."}'
```

Subscribe to events via SSE:

```bash
curl -N http://localhost:8080/events
```

You'll see properly-formatted AAEP events stream in real time.

---

## Running the conformance suite against it

Verify the example passes AAEP Conformance Level 2:

```bash
# Terminal 1: start the producer
python -m aaep_minimal_producer.server --port 8080

# Terminal 2: run conformance tests
aaep-conformance producer --endpoint http://localhost:8080 --level 2
```

Expected output: `VERDICT: PASS`. If you see anything else, please file a bug — this is the reference; it must pass.

---

## Project layout

```
python-minimal/
├── README.md
├── pyproject.toml
├── aaep_minimal_producer/
│   ├── __init__.py
│   ├── emitter.py         # AAEPEmitter, StreamCoalescer, make_id
│   ├── agent.py           # AgentLoop with full lifecycle
│   └── server.py          # HTTP/SSE server
└── tests/
    ├── __init__.py
    └── test_agent.py
```

The intent: someone reading this code top-to-bottom in an hour can understand exactly how AAEP is emitted. No magic, no framework wrappers, no implicit machinery.

---

## Key design decisions

### 1. The emitter is a thin wrapper, not a framework

`AAEPEmitter` is ~200 lines. It exposes one method per event type. You can read the whole thing in fifteen minutes.

There's no plugin system, no middleware chain, no decorator magic. If you want those, see the other examples — they each demonstrate one pattern. This one shows the underlying machinery directly.

### 2. The agent loop is explicit

`AgentLoop.run()` shows every state transition, every tool call cycle, every output emission. It's verbose by design — verbosity is the price of transparency.

If your agent has different needs (concurrent tools, recovery from failures, multi-turn within one session), you'll edit this loop. That's the point: it's a starting template, not a black box.

### 3. Errors are emitted as terminal events, never swallowed

Every exception path in the loop emits `agent.session.errored` with the appropriate `error_category` and re-raises. A session that started MUST end with one of the three terminal event types. The conformance suite verifies this.

### 4. The HTTP/SSE transport is replaceable

`server.py` is a working HTTP/SSE transport, but the agent logic doesn't depend on HTTP. If you need WebSockets, gRPC, or stdio JSON-RPC, replace `server.py` and the agent code works unchanged.

---

## See also

- [`../python-langchain/`](../python-langchain/) — same agent, LangChain callback pattern
- [`../python-anthropic-sdk/`](../python-anthropic-sdk/) — direct Anthropic SDK integration
- [`../typescript-minimal/`](../typescript-minimal/) — equivalent in TypeScript
- [Implementer's Guide §2.5](../../../guides/IMPLEMENTERS_GUIDE.md) — the manual loop pattern theory
- [Quickstart](../../../guides/QUICKSTART.md) — the 50-line version of this example
