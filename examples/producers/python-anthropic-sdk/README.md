# Python Anthropic SDK Producer Example

AAEP integration with the official Anthropic Python SDK. This example demonstrates how to emit AAEP events from agents built directly on `anthropic.Anthropic()` and `client.messages.stream()`, without any agent framework.

If you're building Claude-powered agents using the Anthropic SDK and want AAEP support, this is the example to copy.

---

## What this example demonstrates

- Direct integration with `client.messages.stream()` and `client.messages.create()`
- Native handling of Anthropic's streaming event format (content_block_delta, content_block_start, etc.)
- Tool use translation: Anthropic's `tool_use` content blocks → AAEP `agent.tool.invoked`
- Multi-turn conversation handling
- Proper Claude model version reporting in `producer.model`
- Streaming output with sentence-boundary coalescing
- All 12 core AAEP event types in realistic Anthropic-API-driven usage

This example **reuses the `AAEPEmitter` from python-minimal** — same machinery, different integration. The Anthropic-specific code is just the adapter between Anthropic's API and the emitter.

---

## When to use this pattern vs others

**Pick this pattern when:**
- You use the Anthropic Python SDK directly
- You want to leverage Anthropic's native tool use, prompt caching, or extended thinking
- You don't need (or don't want) a framework abstraction

**Pick `python-langchain` when:** you already use LangChain (regardless of LLM provider).

**Pick `python-minimal` when:** you're building everything from scratch, including your own LLM client.

---

## Installation

```bash
cd examples/producers/python-anthropic-sdk
pip install -e .
```

You'll need an Anthropic API key in your environment:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

Requires Python 3.10 or newer.

---

## Quick start

```python
import anthropic
from aaep_anthropic_sdk import AnthropicAAEPAdapter

# Step 1: Set up your Anthropic client normally
client = anthropic.Anthropic()

# Step 2: Wrap it with the AAEP adapter
def my_transport(event):
    """Send the event to subscribers (HTTP/SSE, WebSocket, etc.)"""
    print(event)  # in production: serialize and send

adapter = AnthropicAAEPAdapter(send_event=my_transport, model="claude-opus-4-7")

# Step 3: Run a session through the adapter
session_id = await adapter.run_session(
    user_message="Tell me about retirement planning.",
    tools=[
        {
            "name": "fetch_balance",
            "description": "Look up an account balance",
            "input_schema": {
                "type": "object",
                "properties": {"account": {"type": "string"}},
            },
        },
    ],
    tool_handlers={
        "fetch_balance": lambda account: f"Balance for {account}: $3,247.18",
    },
)
```

That's all. The adapter calls Claude, processes the streaming response, executes any tool_use blocks (with confirmation for irreversible tools), and emits AAEP events throughout.

---

## Running the included demo

```bash
python -m aaep_anthropic_sdk.example_agent
```

This runs three example sessions (basic query, tool use, multi-turn) against Claude and prints every emitted AAEP event.

**Note:** the demo requires `ANTHROPIC_API_KEY` to be set. If not set, it falls back to a mock mode that doesn't call the real API.

---

## Running the conformance suite against it

```bash
# Terminal 1: start the server (uses mock mode by default for portability)
python -m aaep_anthropic_sdk.server --port 8082

# Terminal 2: run conformance
aaep-conformance producer --endpoint http://localhost:8082 --level 2
```

The conformance suite drives the adapter with synthetic user prompts and verifies the resulting AAEP event streams.

---

## Project layout

```
python-anthropic-sdk/
├── README.md
├── pyproject.toml
├── aaep_anthropic_sdk/
│   ├── __init__.py
│   ├── adapter.py             # AnthropicAAEPAdapter
│   ├── example_agent.py       # Runnable demo with real Anthropic API
│   └── server.py              # HTTP/SSE wrapper for conformance testing
└── tests/
    ├── __init__.py
    └── test_adapter.py
```

---

## Key design decisions

### 1. The adapter directly consumes Anthropic's streaming events

Anthropic's `client.messages.stream()` returns a structured event stream:
- `message_start` — model begins responding
- `content_block_start` — new content block (text, tool_use, etc.)
- `content_block_delta` — incremental update (text_delta, input_json_delta)
- `content_block_stop` — content block done
- `message_delta` — usage stats, stop_reason
- `message_stop` — full message done

The adapter translates each into the appropriate AAEP event. Text deltas feed the StreamCoalescer; tool_use blocks become `tool.invoked`/`tool.completed` pairs; stop_reason informs the terminal event.

### 2. Tool use safety enforced before execution

When Claude emits a `tool_use` content block, the adapter:
1. Emits `agent.tool.invoked` BEFORE calling the handler
2. For irreversible or high-risk tools: emits `agent.awaiting.confirmation` and blocks on the reply
3. Only executes the tool handler on `decision: "accept"`
4. Emits `agent.tool.completed` with the result

This means an unsafe action (e.g., `send_email`) cannot execute without explicit user consent — regardless of what the model "wants" to do.

### 3. Model version included in producer

The adapter reports the exact Claude model version in `producer.model`, so subscribers know which model is responding (different models may need different verbosity treatment for accessibility). When using `claude-opus-4-7`, you'll see `"model": "claude-opus-4-7"` in every emitted event.

### 4. Same emitter as python-minimal

The adapter imports `AAEPEmitter`, `StreamCoalescer`, and `make_id` from the python-minimal package. Bug fixes propagate; safety guarantees are uniform across all examples.

---

## See also

- [`../python-minimal/`](../python-minimal/) — manual loop pattern with the same emitter
- [`../python-langchain/`](../python-langchain/) — callback pattern with LangChain
- [Implementer's Guide §3.4](../../../guides/IMPLEMENTERS_GUIDE.md) — Anthropic SDK specifics
- [Anthropic SDK documentation](https://docs.anthropic.com/claude/reference/messages-streaming) — upstream reference
