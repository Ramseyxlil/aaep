# Pattern: Callback-based AAEP Integration

**Use this pattern when your agent framework fires named lifecycle callbacks.**

This is the natural integration for frameworks built around the observer pattern. LangChain's `BaseCallbackHandler` is the canonical example. AutoGen event handlers, Hugging Face transformers callbacks, and many custom frameworks follow the same shape.

---

## When callbacks are the right choice

Pick callbacks when:

- Your framework exposes a hook system with named events (`on_llm_start`, `on_tool_end`, etc.)
- The framework reliably fires these hooks at meaningful points
- You want emission code separated from agent code, but coarser-grained than middleware allows

Pick something else when:

- Your framework's hooks don't fire at all the lifecycle points AAEP needs (combine with decorator or manual emission)
- You can't register multiple callback handlers simultaneously (use a single composite handler)
- You need to interpose logic before a tool executes (callbacks fire after, not before — combine with decorator)

---

## The callback emission model

Each framework callback maps to one or more AAEP events:

| Framework callback | AAEP event to emit | Notes |
|---|---|---|
| `on_chain_start` / `on_agent_start` | `agent.session.started` | The top-level callback only; nested chains don't re-emit |
| `on_chain_end` / `on_agent_end` | `agent.session.completed` | Only on the top-level |
| `on_chain_error` / `on_agent_error` | `agent.session.errored` | Map exception class to `error_category` |
| `on_llm_start` | `agent.state.changed` (to `thinking`) | |
| `on_llm_end` | `agent.state.changed` (from `thinking`) | |
| `on_llm_new_token` | `agent.output.streaming` | Coalesce at sentence boundaries before emitting |
| `on_tool_start` | `agent.tool.invoked` | See gap-handling section below |
| `on_tool_end` | `agent.tool.completed` (status=success) | |
| `on_tool_error` | `agent.tool.completed` (status=error) | |
| `on_text` | `agent.output.streaming` (depending on context) | |
| `on_retry` | informative log only | Not normatively required |

---

## Complete LangChain implementation

```python
from typing import Any
from uuid import UUID

from langchain.callbacks.base import BaseCallbackHandler
from langchain.schema import LLMResult, AgentAction, AgentFinish

from aaep_helpers import AAEPEmitter, StreamCoalescer, make_id


class AAEPCallbackHandler(BaseCallbackHandler):
    """
    LangChain callback handler that emits AAEP events for each lifecycle event.
    Combine with @aaep_tool decorators for pre-execution confirmation flow.
    """

    def __init__(self, emitter: AAEPEmitter):
        self.emitter = emitter
        self.session_id: str | None = None
        self.active_tools: dict[str, str] = {}  # run_id -> tool_call_id
        self.coalescer: StreamCoalescer | None = None
        self.last_state = "idle"

    # === Chain lifecycle (top-level only) ===

    def on_chain_start(
        self, serialized: dict[str, Any], inputs: dict[str, Any],
        run_id: UUID, parent_run_id: UUID | None = None, **kwargs
    ):
        if parent_run_id is not None:
            return  # nested chain, ignore
        user_message = inputs.get("input") or inputs.get("query") or ""
        self.session_id = self.emitter.start_session(
            summary_normal=f"Processing: {str(user_message)[:80]}",
            request_text=str(user_message),
        )

    def on_chain_end(
        self, outputs: dict[str, Any], run_id: UUID,
        parent_run_id: UUID | None = None, **kwargs
    ):
        if parent_run_id is not None or not self.session_id:
            return
        output_text = outputs.get("output") or outputs.get("answer") or ""
        self.emitter.complete_session(
            session_id=self.session_id,
            summary_normal="Response ready.",
            output_summary=str(output_text)[:200],
        )

    def on_chain_error(
        self, error: BaseException, run_id: UUID,
        parent_run_id: UUID | None = None, **kwargs
    ):
        if parent_run_id is not None or not self.session_id:
            return
        self.emitter.error_session(
            session_id=self.session_id,
            error_category=self._classify_error(error),
            summary_normal=f"Error: {type(error).__name__}",
            error_message=str(error)[:1000],
            recoverable=self._is_recoverable(error),
        )

    # === LLM lifecycle ===

    def on_llm_start(self, serialized: dict[str, Any], prompts: list[str], **kwargs):
        if not self.session_id:
            return
        if self.last_state != "thinking":
            self.emitter.state_changed(
                session_id=self.session_id,
                from_state=self.last_state,
                to_state="thinking",
                summary_normal="Considering the request.",
            )
            self.last_state = "thinking"

    def on_llm_end(self, response: LLMResult, **kwargs):
        # No state change needed here; next callback will emit transition
        pass

    def on_llm_new_token(self, token: str, **kwargs):
        if not self.session_id:
            return
        if self.coalescer is None:
            self.coalescer = StreamCoalescer(
                emitter=self.emitter,
                session_id=self.session_id,
                output_id=make_id("out"),
            )
        self.coalescer.add_token(token)

    # === Tool lifecycle ===

    def on_tool_start(
        self, serialized: dict[str, Any], input_str: str,
        run_id: UUID, **kwargs
    ):
        if not self.session_id:
            return

        if self.last_state != "calling_tool":
            self.emitter.state_changed(
                session_id=self.session_id,
                from_state=self.last_state,
                to_state="calling_tool",
                summary_normal="Calling a tool.",
            )
            self.last_state = "calling_tool"

        tool_name = serialized.get("name", "unknown_tool")
        tool_call_id = make_id("call")
        self.active_tools[str(run_id)] = tool_call_id

        self.emitter.tool_invoked(
            session_id=self.session_id,
            tool=tool_name,
            tool_call_id=tool_call_id,
            args_summary=self._safe_summary(input_str),
            risk_level=self._classify_risk(tool_name),
            irreversible=self._is_irreversible(tool_name),
        )

    def on_tool_end(self, output: str, run_id: UUID, **kwargs):
        if not self.session_id:
            return
        tool_call_id = self.active_tools.pop(str(run_id), None)
        self.emitter.tool_completed(
            session_id=self.session_id,
            tool_call_id=tool_call_id,
            status="success",
            summary_normal=self._safe_summary(output),
        )

    def on_tool_error(self, error: BaseException, run_id: UUID, **kwargs):
        if not self.session_id:
            return
        tool_call_id = self.active_tools.pop(str(run_id), None)
        self.emitter.tool_completed(
            session_id=self.session_id,
            tool_call_id=tool_call_id,
            status="error",
            error_message=str(error)[:1000],
        )

    # === Agent actions ===

    def on_agent_action(self, action: AgentAction, **kwargs):
        # LangChain agents emit this when picking a tool to use; useful for state transitions
        pass

    def on_agent_finish(self, finish: AgentFinish, **kwargs):
        if not self.session_id:
            return
        # Finish coalescer so any buffered output flushes
        if self.coalescer is not None:
            self.coalescer.finish()
            self.coalescer = None

        if self.last_state != "idle":
            self.emitter.state_changed(
                session_id=self.session_id,
                from_state=self.last_state,
                to_state="idle",
                summary_normal="Final response generated.",
            )
            self.last_state = "idle"

    # === Helpers ===

    @staticmethod
    def _classify_error(error: BaseException) -> str:
        if isinstance(error, TimeoutError):
            return "transient"
        if isinstance(error, (PermissionError, ValueError)):
            return "requires_user"
        return "unknown"

    @staticmethod
    def _is_recoverable(error: BaseException) -> bool:
        return isinstance(error, (TimeoutError, ConnectionError))

    @staticmethod
    def _safe_summary(text: str, limit: int = 200) -> str:
        """Truncate and redact obvious secrets."""
        if not isinstance(text, str):
            text = str(text)
        # Naive secret redaction (real implementation should be more thorough)
        for keyword in ("api_key", "password", "token", "secret"):
            if keyword in text.lower():
                text = "[redacted: contains sensitive keyword]"
                break
        return text[:limit]

    @staticmethod
    def _classify_risk(tool_name: str) -> str:
        # Customize per your tool registry
        high_risk = {"send_email", "transfer_funds", "delete_record", "execute_code"}
        medium_risk = {"create_record", "update_record", "publish_post"}
        if tool_name in high_risk:
            return "high"
        if tool_name in medium_risk:
            return "medium"
        return "low"

    @staticmethod
    def _is_irreversible(tool_name: str) -> bool:
        irreversible = {"send_email", "transfer_funds", "delete_record", "publish_post"}
        return tool_name in irreversible
```

Usage:

```python
from langchain.agents import AgentExecutor

emitter = AAEPEmitter()
handler = AAEPCallbackHandler(emitter)

agent_executor = AgentExecutor(
    agent=my_agent,
    tools=my_tools,
    callbacks=[handler],
)

result = await agent_executor.arun("plan my retirement")
```

---

## The callback gap problem

LangChain's `on_tool_start` fires **after** the tool function has been called (more accurately, after the framework decided to call it). By the time your callback runs, you can emit `agent.tool.invoked`, but the tool is already executing in another stack frame.

For Conformance Level 1 (notification only), this is fine.

For Conformance Level 2 with irreversible actions, this is broken: you need to emit `agent.awaiting.confirmation` **before** the tool runs, and you need to **block** until the user replies. Callbacks fire after-the-fact and cannot block the framework's flow.

**Solution:** Combine the callback pattern with the decorator pattern. Wrap each irreversible tool with `@aaep_tool` so confirmation happens inside the tool function before any side effect. The callback handler still emits the standard tool lifecycle events; the decorator handles the confirmation interposition.

```python
@aaep_tool(emitter, risk_level="high", irreversible=True)
async def send_email(to: str, subject: str, body: str):
    # Decorator emits agent.awaiting.confirmation here, BLOCKS for reply,
    # only then executes the real function
    await actual_send_email(to, subject, body)

# Pass the decorated tool to LangChain
tools = [Tool(name="send_email", func=send_email, ...)]

# Callback handler emits the standard tool lifecycle events
agent_executor = AgentExecutor(
    agent=my_agent,
    tools=tools,
    callbacks=[AAEPCallbackHandler(emitter)],
)
```

This is the combination most production LangChain deployments use.

---

## AutoGen variant

AutoGen v0.4+ uses message-passing rather than named callbacks. The pattern is similar but you subscribe to a message stream:

```python
from autogen_core.base import MessageContext

class AAEPMessageObserver:
    async def on_message(self, message, context: MessageContext):
        if isinstance(message, UserMessage):
            self.session_id = self.emitter.start_session(...)
        elif isinstance(message, ToolCall):
            self.emitter.tool_invoked(...)
        elif isinstance(message, ToolResult):
            self.emitter.tool_completed(...)
        # ... etc
```

---

## Common pitfalls

| Mistake | Consequence | Fix |
|---|---|---|
| Treating every `on_chain_start` as session start | Nested chains create duplicate sessions | Only emit when `parent_run_id is None` |
| Emitting `on_llm_new_token` without coalescing | Subscribers flooded | Use `StreamCoalescer` to buffer to sentence boundaries |
| Not tracking `run_id` for tool pairing | `tool.completed` can't be matched to `tool.invoked` | Use `run_id → tool_call_id` mapping |
| Catching errors in callbacks and swallowing them | LangChain expects exceptions to propagate | Never swallow; let LangChain handle them |
| Forgetting to flush coalescer on `on_agent_finish` | Last fragment of output never emitted | Always call `coalescer.finish()` |

---

## Testing

```bash
aaep-conformance producer \
    --endpoint <your-endpoint> \
    --langchain-mode \
    --level 1
```

The conformance suite has a LangChain-specific test profile that exercises typical agent flows (single-turn, multi-turn, tool-heavy, streaming-heavy) and checks AAEP emission at each phase.

---

## See also

- [Implementer's Guide §2.2](../IMPLEMENTERS_GUIDE.md) — overview of the callback pattern
- [Implementer's Guide §3.1](../IMPLEMENTERS_GUIDE.md) — LangChain specifics
- [Implementer's Guide §3.3](../IMPLEMENTERS_GUIDE.md) — AutoGen specifics
- [`decorator-based.md`](decorator-based.md) — the natural pairing partner for confirmation flow
- [`../../examples/producers/python-langchain/`](../../examples/producers/python-langchain/) — complete working example
