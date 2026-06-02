# Python LangChain Producer Example

AAEP integration with LangChain via the callback handler pattern. This example demonstrates the **callback-based pattern** from the [Implementer's Guide §2.2](../../../guides/IMPLEMENTERS_GUIDE.md) using LangChain's native `BaseCallbackHandler` infrastructure.

If you have an existing LangChain agent and want to add AAEP support without rewriting your agent code, this is the example to copy.

---

## What this example demonstrates

- **Zero changes to existing LangChain agent code** — just register `LangChainAAEPHandler` as a callback
- LangChain owns the agent loop; our handler translates its callbacks into AAEP events
- All 12 core AAEP event types emitted from a real LangChain agent
- Streaming support via `on_llm_new_token`
- Tool invocation pairing via `on_tool_start` / `on_tool_end`
- Multi-turn conversations as separate AAEP sessions
- Safety enforcement at the handler boundary (refuses to emit unsafe confirmations)

This example uses **the same `AAEPEmitter` from the python-minimal example.** That's deliberate: the emitter is reusable across integration patterns. What differs is how the emissions are triggered.

---

## When to use this pattern vs others

**Pick this pattern when:** you have a LangChain agent already running in production and want to add AAEP without refactoring.

**Pick `python-minimal` instead when:** you're starting from scratch and want full control over the agent loop.

**Pick `python-anthropic-sdk` instead when:** you're using the Anthropic SDK directly without LangChain.

See [Implementer's Guide §2](../../../guides/IMPLEMENTERS_GUIDE.md) for the full pattern comparison.

---

## Installation

```bash
cd examples/producers/python-langchain
pip install -e .
```

This installs LangChain and LangChain Core alongside the AAEP minimal emitter package.

Requires Python 3.10 or newer.

---

## Quick start

```python
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_openai import ChatOpenAI

from aaep_langchain import LangChainAAEPHandler, make_aaep_handler


# Step 1: create your LangChain agent normally
llm = ChatOpenAI(model="gpt-4")
agent_executor = AgentExecutor(agent=create_openai_tools_agent(llm, tools, prompt),
                                tools=tools)

# Step 2: create the AAEP handler with your transport callback
def my_transport(event):
    """Send the event to subscribers (HTTP/SSE, WebSocket, etc.)"""
    print(event)  # in production: serialize and send

handler = make_aaep_handler(send_event=my_transport)

# Step 3: run with the handler attached
result = agent_executor.invoke(
    {"input": "What's the weather in Lagos?"},
    config={"callbacks": [handler]}
)
```

That's all. The handler emits AAEP events as the agent runs.

---

## Running the included demo

```bash
python -m aaep_langchain.example_agent
```

This runs a complete LangChain agent through a few example interactions and prints every emitted AAEP event. Useful for seeing what an agent's emissions look like in real time.

---

## Running the conformance suite against it

Start a server wrapping the LangChain example:

```bash
python -m aaep_langchain.server --port 8081
```

In another terminal:

```bash
aaep-conformance producer \
    --endpoint http://localhost:8081 \
    --level 2 \
    --profile langchain-mode
```

The `--profile langchain-mode` flag tells the conformance suite to use test scenarios optimized for callback-based integrations (some checks behave slightly differently — e.g., LangChain handlers receive nested chain events that this profile knows to flatten).

---

## Project layout

```
python-langchain/
├── README.md
├── pyproject.toml
├── aaep_langchain/
│   ├── __init__.py
│   ├── callback_handler.py    # LangChainAAEPHandler
│   ├── example_agent.py        # Runnable demo with a real LangChain agent
│   └── server.py               # HTTP/SSE wrapper for conformance testing
└── tests/
    ├── __init__.py
    └── test_callback_handler.py
```

---

## Key design decisions

### 1. The handler does NOT modify LangChain's behavior

`LangChainAAEPHandler` is a pure observer. It receives LangChain's callbacks and emits AAEP events. It never intercepts, alters, or vetoes anything LangChain does.

This means LangChain agents work identically whether or not the handler is attached. AAEP support is **additive**, not invasive.

### 2. Confirmation flow requires a small extension

LangChain's callbacks don't natively support pausing the agent loop for user confirmation. To support Level 2 conformance, you'd need to either:

(a) Use a LangChain tool that internally calls `ask_for_confirmation()`, OR  
(b) Implement an interrupt mechanism via LangChain's `RunnableConfig` interruption support.

This example demonstrates option (a) — the simpler path. See `example_agent.py`.

### 3. The handler maintains per-run session state

LangChain runs are not the same as AAEP sessions. The handler maps each top-level `on_chain_start` (the outermost chain) to a new AAEP session, and uses the `run_id` from LangChain as a correlation key for nested events.

### 4. Same emitter as python-minimal

The handler imports `AAEPEmitter`, `StreamCoalescer`, and `make_id` from the python-minimal package. This proves the emitter design is reusable across integration patterns — there's nothing LangChain-specific in the AAEP machinery itself.

---

## See also

- [`../python-minimal/`](../python-minimal/) — the same machinery, manual loop pattern
- [Implementer's Guide §3.1](../../../guides/IMPLEMENTERS_GUIDE.md) — LangChain integration specifics
- [`guides/patterns/callback-based.md`](../../../guides/patterns/callback-based.md) — the callback pattern theory
- [LangChain callback documentation](https://python.langchain.com/docs/modules/callbacks/) — upstream reference
