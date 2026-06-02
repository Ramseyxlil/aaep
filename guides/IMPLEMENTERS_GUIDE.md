# AAEP Implementer's Guide

**For engineers integrating AAEP into agent frameworks and products.**

This guide is the practical companion to the [specification](../spec/SPEC.md). The spec defines what conforming implementations must do; this guide shows you how to actually do it. Patterns here are battle-tested across a range of agent architectures.

If you have not yet read the [Quickstart](QUICKSTART.md), do that first. This guide assumes you understand the basic shape of an AAEP event and a session lifecycle.

---

## Table of contents

1. [Decision matrix: which pattern fits your framework](#1-decision-matrix-which-pattern-fits-your-framework)
2. [The five integration patterns](#2-the-five-integration-patterns)
3. [Framework-specific guidance](#3-framework-specific-guidance)
4. [Implementing the confirmation flow correctly](#4-implementing-the-confirmation-flow-correctly)
5. [Implementing streaming output and coalescing](#5-implementing-streaming-output-and-coalescing)
6. [Implementing backpressure](#6-implementing-backpressure)
7. [Handling errors and timeouts](#7-handling-errors-and-timeouts)
8. [Common pitfalls](#8-common-pitfalls)
9. [Production deployment checklist](#9-production-deployment-checklist)
10. [Testing your integration](#10-testing-your-integration)

---

## 1. Decision matrix: which pattern fits your framework

The first decision is structural: at what level of your agent's code do you emit AAEP events? There are five common patterns. Pick the one that matches your framework's natural extension point.

| Pattern | Best when your framework offers... | Examples |
|---|---|---|
| **Middleware** | A pipeline where you can register pre/post hooks around the agent loop | Microsoft Agent Framework, Semantic Kernel filters |
| **Callbacks** | Named lifecycle callbacks fired by the framework | LangChain `BaseCallbackHandler`, AutoGen event handlers |
| **Decorators** | The ability to wrap tool/function definitions | OpenAI function calling, Anthropic SDK tool use, custom Python with `@aaep_emit` decorators |
| **Event emitter** | A native event emitter or pub/sub system | Node.js EventEmitter, Python `asyncio.Queue`, frameworks built on observables |
| **Manual loop** | No framework — you control the agent loop directly | Custom reasoning loops, research scripts, embedded agents |

You can mix patterns. A LangChain integration might use callbacks for state events and decorators for tool emission. There is no rule against this; pick what reads cleanly.

---

## 2. The five integration patterns

### 2.1 Middleware pattern

Use when your framework runs the agent through a configurable pipeline.

```python
class AAEPMiddleware:
    """Middleware that emits AAEP events around agent execution."""

    def __init__(self, emitter):
        self.emitter = emitter

    async def __call__(self, request, next_handler):
        session_id = self.emitter.start_session(
            summary_normal=f"Processing: {request.user_message[:80]}",
            request_text=request.user_message,
        )

        try:
            await self.emitter.state_changed("idle", "thinking", session_id)
            response = await next_handler(request)
            await self.emitter.state_changed("writing_output", "idle", session_id)
            self.emitter.complete_session(
                session_id,
                summary_normal="Response generated.",
            )
            return response
        except Exception as e:
            self.emitter.error_session(
                session_id,
                error_category="unknown",
                summary_normal=f"Agent error: {type(e).__name__}",
            )
            raise
```

**Pros:** Clean separation between AAEP and agent logic. No agent code changes.

**Cons:** Tool-level emission requires additional integration; middleware alone doesn't see inside the agent's tool calls.

A detailed walkthrough of this pattern is in [patterns/middleware-based.md](patterns/middleware-based.md).

### 2.2 Callback pattern

Use when your framework fires named lifecycle callbacks.

```python
class AAEPCallbackHandler:
    """Implements the lifecycle callbacks of an agent framework."""

    def __init__(self, emitter):
        self.emitter = emitter
        self.session_id = None
        self.active_tool_calls = {}  # tool_name -> tool_call_id

    def on_agent_start(self, user_message, **kwargs):
        self.session_id = self.emitter.start_session(
            summary_normal=f"Processing: {user_message[:80]}",
            request_text=user_message,
        )

    def on_llm_start(self, **kwargs):
        self.emitter.state_changed("idle", "thinking", self.session_id)

    def on_tool_start(self, tool_name, tool_input, **kwargs):
        tool_call_id = self.emitter.make_id("call")
        self.active_tool_calls[tool_name] = tool_call_id
        self.emitter.tool_invoked(
            self.session_id,
            tool=tool_name,
            tool_call_id=tool_call_id,
            args_summary=self._summarize(tool_input),
            risk_level=self._classify_risk(tool_name),
            irreversible=self._is_irreversible(tool_name),
        )

    def on_tool_end(self, tool_name, output, **kwargs):
        tool_call_id = self.active_tool_calls.pop(tool_name, None)
        self.emitter.tool_completed(
            self.session_id,
            tool=tool_name,
            tool_call_id=tool_call_id,
            status="success",
            summary_normal=self._summarize(output),
        )

    def on_agent_end(self, output, **kwargs):
        self.emitter.complete_session(self.session_id)
```

**Pros:** Natural fit for callback-oriented frameworks. Most of the work is done by the framework's existing event surface.

**Cons:** Requires the framework to actually fire all the relevant callbacks. Many frameworks have gaps (e.g., no callback when LLM reasoning starts vs. when tools are about to be called).

### 2.3 Decorator pattern

Use when you can wrap tool/function definitions at registration time.

```python
def aaep_tool(emitter, risk_level="low", irreversible=False):
    """Decorator that emits agent.tool.invoked/completed around a tool function."""
    def wrapper(tool_fn):
        async def wrapped(*args, session_id=None, **kwargs):
            tool_call_id = emitter.make_id("call")

            # Emit invoked BEFORE the side effect
            emitter.tool_invoked(
                session_id,
                tool=tool_fn.__name__,
                tool_call_id=tool_call_id,
                args_summary=str(kwargs)[:200],
                risk_level=risk_level,
                irreversible=irreversible,
            )

            # If irreversible, require pre-confirmation
            if irreversible:
                reply_token = emitter.await_confirmation(
                    session_id,
                    action=f"Call {tool_fn.__name__}",
                    consequence="This action cannot be undone.",
                    risk_level=risk_level,
                    default_decision="reject",
                )
                if not emitter.wait_for_decision(reply_token) == "accept":
                    emitter.tool_completed(
                        session_id, tool=tool_fn.__name__,
                        tool_call_id=tool_call_id,
                        status="error",
                        error_message="User rejected.",
                    )
                    raise PermissionError("User rejected the action.")

            # Execute and emit completed
            try:
                result = await tool_fn(*args, **kwargs)
                emitter.tool_completed(
                    session_id, tool=tool_fn.__name__,
                    tool_call_id=tool_call_id,
                    status="success",
                )
                return result
            except Exception as e:
                emitter.tool_completed(
                    session_id, tool=tool_fn.__name__,
                    tool_call_id=tool_call_id,
                    status="error",
                    error_message=str(e),
                )
                raise
        return wrapped
    return wrapper


# Usage:
@aaep_tool(emitter, risk_level="high", irreversible=True)
async def transfer_funds(amount, from_account, to_account, session_id=None):
    # Actual implementation
    ...
```

**Pros:** Very localized. Each tool declares its own risk profile. The decorator handles confirmation automatically.

**Cons:** Requires modifying tool definitions. Doesn't help with session-level lifecycle events.

### 2.4 Event emitter pattern

Use when your framework already publishes events you can subscribe to.

```python
import asyncio

class AAEPEventBridge:
    """Bridges a framework's native event stream into AAEP events."""

    def __init__(self, emitter, source_queue: asyncio.Queue):
        self.emitter = emitter
        self.source = source_queue
        self.session_id = None

    async def run(self):
        while True:
            event = await self.source.get()
            await self._translate(event)

    async def _translate(self, source_event):
        kind = source_event.get("kind")

        if kind == "session_started":
            self.session_id = self.emitter.start_session(
                summary_normal=source_event["user_message"]
            )
        elif kind == "llm_streaming_chunk":
            self.emitter.output_streaming(
                self.session_id,
                chunk=source_event["text"],
                position=source_event["offset"],
                complete=source_event["done"],
                coalesce_hint="sentence" if source_event["done"] else "none",
            )
        # ... etc
```

**Pros:** Total decoupling. The agent doesn't know AAEP exists. Add or remove AAEP support by attaching/detaching the bridge.

**Cons:** Two levels of indirection. Debugging requires tracing source events through the bridge.

### 2.5 Manual loop pattern

Use when you control the agent loop directly with no framework abstraction.

This is what the [Quickstart](QUICKSTART.md) demonstrates. The full pattern is:

```python
async def agent_loop(user_message, emitter):
    session_id = emitter.start_session(
        summary_normal=f"Processing: {user_message[:80]}",
        request_text=user_message,
    )

    try:
        emitter.state_changed(session_id, "idle", "thinking")

        # LLM reasoning loop
        messages = [{"role": "user", "content": user_message}]
        while True:
            response = await call_llm(messages)
            messages.append({"role": "assistant", "content": response})

            if not response.has_tool_calls:
                # Stream the final output
                emitter.state_changed(session_id, "thinking", "writing_output")
                position = 0
                for chunk in response.streaming_chunks:
                    emitter.output_streaming(
                        session_id,
                        chunk=chunk.text,
                        position=position,
                        complete=chunk.is_final,
                        coalesce_hint="sentence" if not chunk.is_final else "completion",
                    )
                    position += len(chunk.text)
                break

            # Execute tool calls
            for tool_call in response.tool_calls:
                emitter.state_changed(session_id, "thinking", "calling_tool")
                # ... full tool invoke/complete cycle
                emitter.state_changed(session_id, "calling_tool", "thinking")

        emitter.complete_session(session_id)
    except Exception as e:
        emitter.error_session(session_id, error_category="unknown",
                              summary_normal=str(e))
        raise
```

**Pros:** Full control. Every AAEP event is exactly where you put it.

**Cons:** Every state transition requires explicit code. Easy to forget an emission.

---

## 3. Framework-specific guidance

### 3.1 LangChain

LangChain provides `BaseCallbackHandler`, which is a near-perfect fit for the **callback pattern** above.

Key callbacks to implement:

| LangChain callback | AAEP event to emit |
|---|---|
| `on_chain_start` | `agent.session.started` |
| `on_chain_end` | `agent.session.completed` |
| `on_chain_error` | `agent.session.errored` |
| `on_llm_start` | `agent.state.changed` (→ thinking) |
| `on_tool_start` | `agent.tool.invoked` |
| `on_tool_end` | `agent.tool.completed` |
| `on_tool_error` | `agent.tool.completed` with `status=error` |
| `on_llm_new_token` | `agent.output.streaming` (coalesce at sentence boundaries) |

A complete worked example is in [`../examples/producers/python-langchain/`](../examples/producers/python-langchain/).

**Gotcha:** LangChain does not fire a callback when an irreversible action is about to execute. You must wrap the tool itself (combining the **callback pattern** with the **decorator pattern**) to interpose your confirmation flow before the side-effect.

### 3.2 Microsoft Agent Framework (MAF)

Microsoft Agent Framework supports **middleware** natively. This is the canonical integration:

```csharp
var agent = new ChatCompletionAgent
{
    Instructions = "You are a helpful assistant.",
    Kernel = kernel,
};

agent.Use<AAEPMiddleware>();
```

`AAEPMiddleware` implements the standard MAF middleware interface: it receives the request, emits `agent.session.started`, calls `next(request)`, then emits `agent.session.completed`. Tool emission is handled at the kernel-function level via a separate filter.

A complete worked example is in [`../examples/producers/python-microsoft-agent-framework/`](../examples/producers/python-microsoft-agent-framework/).

### 3.3 AutoGen

AutoGen v0.4+ uses an event-driven model. Use the **event emitter pattern** above.

The `agent.message_published` event in AutoGen maps to multiple AAEP events depending on the message kind:

- `RequestMessage` → `agent.session.started`
- `ToolCallMessage` → `agent.tool.invoked`
- `ToolResultMessage` → `agent.tool.completed`
- `AssistantMessage` (streaming) → `agent.output.streaming`
- `TerminationMessage` → `agent.session.completed` or `agent.session.errored`

### 3.4 Anthropic SDK with tool use

Use the **decorator pattern**. Wrap your tool functions at registration time:

```python
from anthropic import Anthropic
from aaep_helpers import aaep_tool

client = Anthropic()
emitter = AAEPEmitter()

@aaep_tool(emitter, risk_level="low")
def get_weather(location: str):
    return f"Weather in {location}: sunny."

@aaep_tool(emitter, risk_level="high", irreversible=True)
def send_email(to: str, subject: str, body: str):
    # Actual email sending
    ...

# Run the agent loop manually with AAEP wrapping
response = client.messages.create(
    model="claude-opus-4-7",
    max_tokens=1024,
    tools=[...],
    messages=[...],
)
```

A complete worked example is in [`../examples/producers/python-anthropic-sdk/`](../examples/producers/python-anthropic-sdk/).

### 3.5 Semantic Kernel

Semantic Kernel offers function filters, which fit the **middleware pattern**. Register a filter on the kernel:

```csharp
kernel.FunctionFilters.Add(new AAEPFunctionFilter(emitter));
```

The filter sees every kernel function invocation, including LLM calls and tool calls. Each maps cleanly to AAEP events.

### 3.6 OpenAI Assistants API

The Assistants API is server-side. Your client code receives events via the Run streaming endpoint. Use the **event emitter pattern**: subscribe to the stream and translate each event type.

### 3.7 Custom / no framework

Use the **manual loop pattern**. See the [Quickstart](QUICKSTART.md) for the complete shape. The reference example in [`../examples/producers/python-minimal/`](../examples/producers/python-minimal/) is a production-grade version.

---

## 4. Implementing the confirmation flow correctly

The confirmation flow is the most error-prone part of an AAEP integration. Get this wrong and your "AAEP support" claim fails the conformance tests.

### 4.1 The mandatory sequence

For any irreversible action (or any action your product policy treats as confirmation-required):

```
1. Producer emits agent.awaiting.confirmation (with reply_token=X, default_decision="reject")
2. Producer BLOCKS (does not execute the action)
3. One of:
     a. Producer receives confirmation.reply(reply_token=X, decision="accept") → proceed
     b. Producer receives confirmation.reply(reply_token=X, decision="reject") → cancel
     c. timeout_seconds elapses → apply default_decision (which is "reject" for irreversibles)
4. Producer emits agent.tool.invoked (only if decision was accept)
```

### 4.2 What "blocking" means in code

The producer's logic must literally not call the tool until step 3 completes. Concretely:

```python
async def execute_with_confirmation(tool_fn, args, session_id):
    reply_token = emitter.make_id("rpl")

    emitter.await_confirmation(
        session_id,
        action=describe_action(tool_fn, args),
        consequence=describe_consequence(tool_fn, args),
        reply_token=reply_token,
        timeout_seconds=300,
        default_decision="reject",
        risk_level="high",
        irreversible=True,
    )

    # CRITICAL: do NOT call tool_fn before this completes
    decision = await emitter.await_decision(reply_token, timeout=300)

    if decision != "accept":
        emitter.state_changed(session_id, "awaiting_input", "thinking",
                              summary_normal="User declined the action.")
        return None  # Do not execute

    # Now safe to execute
    return await tool_fn(**args)
```

### 4.3 Default decision rules (machine-verified)

The JSON Schema for `agent.awaiting.confirmation` enforces these at validation time:

| Action characteristics | Required `default_decision` |
|---|---|
| `irreversible=true` AND `risk_level=high` | MUST be `reject` |
| `irreversible=true` AND `risk_level=medium` | MUST be `reject` |
| `irreversible=true` AND `risk_level=low` | SHOULD be `reject` (MAY be `accept`) |
| `irreversible=false` AND `risk_level=high` | SHOULD be `reject` |
| Everything else | MAY be either |

If you try to emit a confirmation event with `irreversible=true, risk_level=high, default_decision=accept`, the conformance test suite (and any JSON Schema validator) will reject it as non-conforming. This is intentional: the protocol mechanically prevents the most common safety failure.

### 4.4 What to put in `action` and `consequence`

These fields are announced to the user. Write them as if the user has no visual context.

**Good:** `"Transfer $500.00 from checking-7821 to savings-3344."`
**Bad:** `"Execute pending transaction."`

**Good:** `"Funds move immediately. Reversal requires bank intervention."`
**Bad:** `"Side effects may apply."`

The user is making an informed decision based on these strings. They should be unambiguous, specific, and complete.

---

## 5. Implementing streaming output and coalescing

LLMs produce tokens at 30-100/sec. Screen readers announce at 2-5 events/sec. Without coalescing, you'll either flood the subscriber or your output will arrive in unintelligible fragments.

### 5.1 The recommended pattern

```python
class StreamCoalescer:
    """Buffers tokens and emits at sentence boundaries."""

    SENTENCE_ENDS = ".!?"

    def __init__(self, emitter, session_id, output_id):
        self.emitter = emitter
        self.session_id = session_id
        self.output_id = output_id
        self.buffer = ""
        self.position = 0

    def add_token(self, token):
        self.buffer += token
        # Check for sentence boundary
        for i, ch in enumerate(self.buffer):
            if ch in self.SENTENCE_ENDS and i + 1 < len(self.buffer):
                if self.buffer[i + 1] == " ":
                    self._flush_through(i + 2, "sentence", complete=False)
                    return

    def finish(self):
        if self.buffer:
            self._flush_through(len(self.buffer), "completion", complete=True)

    def _flush_through(self, index, hint, complete):
        chunk = self.buffer[:index]
        self.buffer = self.buffer[index:]
        self.emitter.output_streaming(
            session_id=self.session_id,
            chunk=chunk,
            position=self.position,
            complete=complete,
            coalesce_hint=hint,
            output_id=self.output_id,
        )
        self.position += len(chunk)
```

### 5.2 Adapting to subscriber preferences

The subscriber declares its preferred `coalesce_boundaries` during the handshake. Honor what was negotiated:

```python
if "completion" in honored_coalesce_boundaries and len(honored_coalesce_boundaries) == 1:
    # Subscriber only wants the final result; buffer everything
    coalescer = CompletionOnlyCoalescer(...)
elif "sentence" in honored_coalesce_boundaries:
    coalescer = SentenceCoalescer(...)
elif "paragraph" in honored_coalesce_boundaries:
    coalescer = ParagraphCoalescer(...)
else:
    # No coalescing requested; emit per-token
    coalescer = NoOpCoalescer(...)
```

---

## 6. Implementing backpressure

Backpressure is the mechanism that protects subscribers from event flood.

### 6.1 Token-bucket emission

```python
class TokenBucket:
    """Standard token-bucket rate limiter."""

    def __init__(self, rate_per_second, burst=None):
        self.rate = rate_per_second
        self.capacity = burst or rate_per_second
        self.tokens = self.capacity
        self.last_check = time.monotonic()

    def try_consume(self, n=1):
        now = time.monotonic()
        elapsed = now - self.last_check
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self.last_check = now
        if self.tokens >= n:
            self.tokens -= n
            return True
        return False
```

Emit events through the bucket:

```python
def emit_with_backpressure(event):
    if event.get("urgency") == "critical":
        emit_directly(event)  # Critical events bypass the bucket
        return
    if bucket.try_consume():
        emit_directly(event)
    else:
        coalesce_or_drop(event)
```

### 6.2 Critical events bypass everything

This is a normative requirement. A subscriber that declares `max_events_per_second=3` still receives `agent.awaiting.confirmation` (urgency=critical) at full speed. Otherwise, the user would miss confirmations under load.

---

## 7. Handling errors and timeouts

### 7.1 Tool errors

When a tool fails or times out, you must emit `agent.tool.completed` — never silently abandon a tool:

```python
try:
    result = await tool_fn(**args, timeout=10)
    emit_tool_completed(status="success", ...)
except asyncio.TimeoutError:
    emit_tool_completed(status="timeout", error_message="Tool exceeded 10s.")
except Exception as e:
    emit_tool_completed(status="error", error_message=str(e))
```

### 7.2 Session-level errors

If the agent itself fails (LLM down, infrastructure issue, unhandled exception):

```python
emit_session_errored(
    error_category="transient",  # or "permanent", "requires_user", "unknown"
    summary_normal="The model service is temporarily unavailable.",
    recoverable=True,
    remediation_hint="Try again in a few moments.",
)
```

---

## 8. Common pitfalls

The following mistakes are flagged by the conformance test suite. Avoid them.

| Pitfall | Why it fails | Fix |
|---|---|---|
| Emitting `tool.invoked` AFTER the side effect | Race: user can't intervene | Always emit `tool.invoked` before the function call |
| Setting `default_decision="accept"` on irreversible+high-risk | Schema rejects it | Set `default_decision="reject"` |
| Setting `urgency` other than `"critical"` on `awaiting.confirmation` | Schema rejects it | Always `urgency="critical"` |
| Reusing a `reply_token` after timeout | Token is single-use | Generate a fresh token for each retry |
| Skipping `tool.completed` on timeout | Session looks orphaned | Emit `tool.completed` with `status="timeout"` |
| Emitting events without `summary_normal` | Subscribers have nothing to announce | Always include `summary_normal` on user-facing events |
| Sending PII or secrets in `args_summary` | Privacy violation | Redact secrets; include only user-supplied PII |
| Forgetting to honor `max_events_per_second` | Subscriber overwhelm | Implement token-bucket backpressure |
| Not bypassing rate limits for critical events | User misses confirmations | Critical events always pass through |

---

## 9. Production deployment checklist

Before shipping AAEP support to production:

- [ ] Run the conformance test suite at your target level. Publish the report.
- [ ] Verify every irreversible tool emits `awaiting.confirmation` before executing.
- [ ] Verify `default_decision` follows the rules in §4.3.
- [ ] Verify streaming output coalesces at sentence boundaries by default.
- [ ] Verify your producer manifest is published at `/.well-known/aaep-manifest.json` (Level 3).
- [ ] Verify auth: producer authenticates subscriber on every reply.
- [ ] Verify no secrets/PII in `args_summary` or any human-readable field.
- [ ] Test with a real screen reader (Narrator, NVDA, or VoiceOver) using your subscriber.
- [ ] Test under load: at `max_events_per_second` rate sustained for 60 seconds.
- [ ] Test reconnection: kill and restore the transport mid-session.
- [ ] Register in [governance/ADOPTERS.md](../governance/ADOPTERS.md).

---

## 10. Testing your integration

### 10.1 Use the conformance suite

```bash
pip install aaep-conformance
aaep-conformance producer --endpoint <your-endpoint> --level 2
```

The suite generates a machine-readable report (`conformance-report.json`) and a human-readable HTML report. Publish both alongside your product's accessibility documentation.

### 10.2 Use the CLI debug subscriber

For interactive debugging, run the CLI debug subscriber:

```bash
python ../examples/subscribers/cli-debug/aaep_listen.py --connect <your-endpoint>
```

It prints every event in human-readable form with timing information. Excellent for spotting missing emissions or wrong sequencing.

### 10.3 Use capture and replay

To verify a problematic session:

```bash
aaep-capture --endpoint <your-endpoint> --output session.aaep
aaep-replay --input session.aaep --visualize
```

The visualizer renders a state-machine trace showing exactly where any sequencing violation occurred.

---

## Where to go from here

- For the precise normative rules, return to the [specification](../spec/SPEC.md).
- For domain-specific extensions, read the [Extensions Guide](EXTENSIONS_GUIDE.md).
- For frequently asked questions, see the [FAQ](FAQ.md).
- For pattern-specific deep dives, browse [patterns/](patterns/).
- To register as an adopter once you ship, edit [governance/ADOPTERS.md](../governance/ADOPTERS.md).

Welcome to the AAEP implementer community.
