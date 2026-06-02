# Pattern: Decorator-based AAEP Integration

**Use this pattern when you can wrap tool/function definitions at registration time.**

This is the most precise pattern for tool-level emission. Each tool declares its own risk profile, and the decorator handles the entire `agent.tool.invoked` → confirmation → `agent.tool.completed` cycle. It's also the canonical answer to the "callback gap" problem (callbacks fire after a tool is dispatched and can't interpose confirmation before execution).

---

## When decorators are the right choice

Pick decorators when:

- You have a clear catalog of tool functions
- You want per-tool risk classification declared at the tool definition
- You need to interpose confirmation flow BEFORE a tool runs
- You can change the tool function (or wrap it at registration time)

Pick something else when:

- Your tools are dynamically defined or discovered at runtime (use manual loop or event emitter)
- You can't modify or wrap tool functions (use callbacks + a separate confirmation gate)
- You're emitting at session level only, not tool level (use middleware)

---

## Anatomy of an AAEP tool decorator

A complete `@aaep_tool` decorator does five things:

1. Emits `agent.tool.invoked` with risk metadata
2. If irreversible/high-risk, emits `agent.awaiting.confirmation` and **blocks** for the reply
3. If the user rejects, emits `agent.tool.completed` with `status="error"` and raises a permission error
4. If the user accepts (or no confirmation was needed), executes the wrapped function
5. Emits `agent.tool.completed` with `status="success"` or `status="error"` based on the result

---

## Complete Python implementation

```python
import asyncio
import functools
from typing import Awaitable, Callable

from aaep_helpers import AAEPEmitter, make_id


def aaep_tool(
    emitter: AAEPEmitter,
    *,
    risk_level: str = "low",
    irreversible: bool = False,
    require_confirmation: bool | None = None,
    description: str | None = None,
):
    """
    Decorator that wraps a tool function with AAEP emissions.

    Args:
        emitter: AAEPEmitter instance for this producer
        risk_level: "low", "medium", or "high"
        irreversible: True if the action cannot be undone
        require_confirmation: Force confirmation regardless of risk/irreversibility.
            Defaults to True if irreversible or risk_level == "high".
        description: Optional human-readable description of what the tool does.
    """

    # Default: require confirmation for irreversible OR high-risk actions
    if require_confirmation is None:
        require_confirmation = irreversible or risk_level == "high"

    # Safety enforcement: irreversible + high/medium MUST default to reject
    if irreversible and risk_level in ("high", "medium"):
        default_decision = "reject"
    elif risk_level == "high":
        default_decision = "reject"
    else:
        default_decision = "accept"

    def decorator(tool_fn: Callable[..., Awaitable]):
        @functools.wraps(tool_fn)
        async def wrapped(*args, session_id: str | None = None, **kwargs):
            if session_id is None:
                raise ValueError(
                    f"aaep_tool wrapper for {tool_fn.__name__} requires session_id "
                    "to be passed by the agent loop."
                )

            tool_name = tool_fn.__name__
            tool_call_id = make_id("call")

            # 1. Emit tool.invoked BEFORE any side effect
            emitter.tool_invoked(
                session_id=session_id,
                tool=tool_name,
                tool_call_id=tool_call_id,
                description=description,
                args_summary=_safe_args_summary(kwargs),
                risk_level=risk_level,
                irreversible=irreversible,
                summary_normal=f"Calling {tool_name}.",
            )

            # 2. If confirmation needed, emit awaiting.confirmation and BLOCK
            if require_confirmation:
                action = description or f"Execute {tool_name}"
                consequence = _consequence_text(irreversible, risk_level)

                reply_token = emitter.await_confirmation(
                    session_id=session_id,
                    action=action,
                    consequence=consequence,
                    timeout_seconds=300,
                    default_decision=default_decision,
                    risk_level=risk_level,
                    irreversible=irreversible,
                    summary_normal=f"Confirmation required to call {tool_name}.",
                )

                decision = await emitter.wait_for_decision(
                    reply_token, timeout_seconds=300
                )

                if decision != "accept":
                    # 3. User rejected; emit tool.completed and raise
                    emitter.tool_completed(
                        session_id=session_id,
                        tool=tool_name,
                        tool_call_id=tool_call_id,
                        status="error",
                        error_message="User declined the action.",
                        summary_normal=f"{tool_name} not executed: user declined.",
                    )
                    raise PermissionError(
                        f"User declined confirmation for {tool_name}"
                    )

            # 4. Execute the wrapped tool
            try:
                result = await tool_fn(*args, **kwargs)
                emitter.tool_completed(
                    session_id=session_id,
                    tool=tool_name,
                    tool_call_id=tool_call_id,
                    status="success",
                    summary_normal=_safe_result_summary(result),
                )
                return result

            except asyncio.TimeoutError as exc:
                emitter.tool_completed(
                    session_id=session_id,
                    tool=tool_name,
                    tool_call_id=tool_call_id,
                    status="timeout",
                    error_message=str(exc)[:1000],
                )
                raise

            except Exception as exc:
                emitter.tool_completed(
                    session_id=session_id,
                    tool=tool_name,
                    tool_call_id=tool_call_id,
                    status="error",
                    error_message=str(exc)[:1000],
                )
                raise

        return wrapped

    return decorator


def _safe_args_summary(kwargs: dict) -> str:
    """Build a short summary of args, redacting obvious secrets."""
    parts = []
    for key, value in kwargs.items():
        if any(s in key.lower() for s in ("password", "token", "key", "secret")):
            parts.append(f"{key}=[redacted]")
        elif isinstance(value, (str, int, float, bool)):
            v = str(value)
            parts.append(f"{key}={v[:80]}")
        else:
            parts.append(f"{key}=<{type(value).__name__}>")
    return ", ".join(parts)[:1000]


def _safe_result_summary(result) -> str:
    if isinstance(result, str):
        return result[:200]
    if isinstance(result, (int, float, bool)):
        return str(result)
    return f"<{type(result).__name__}>"


def _consequence_text(irreversible: bool, risk_level: str) -> str:
    if irreversible and risk_level == "high":
        return "This action is irreversible and high-risk. Cannot be undone."
    if irreversible:
        return "This action cannot be easily undone."
    if risk_level == "high":
        return "This is a high-risk action."
    return "This action will be executed."
```

---

## Usage examples

### Simple low-risk tool (no confirmation)

```python
@aaep_tool(emitter, risk_level="low")
async def fetch_weather(location: str, session_id: str = None):
    return await weather_api.get(location)
```

### High-risk irreversible tool (confirmation required)

```python
@aaep_tool(
    emitter,
    risk_level="high",
    irreversible=True,
    description="Transfer funds between accounts",
)
async def transfer_funds(amount: float, from_account: str, to_account: str,
                        session_id: str = None):
    return await banking_api.transfer(amount, from_account, to_account)
```

When the agent calls this, the user (via their AT) sees a confirmation prompt: *"This action is irreversible and high-risk. Cannot be undone. Execute Transfer funds between accounts?"* and must accept before the actual API call happens.

### Custom confirmation override

```python
@aaep_tool(
    emitter,
    risk_level="low",
    require_confirmation=True,  # force confirmation even for low-risk
    description="Subscribe user to newsletter",
)
async def subscribe(email: str, session_id: str = None):
    return await newsletter.subscribe(email)
```

Useful when business policy mandates confirmation even for technically low-risk actions.

---

## Anthropic SDK integration

The Anthropic SDK supports function calling via the `tools` parameter. Combine decorators with manual agent loop:

```python
from anthropic import AsyncAnthropic

client = AsyncAnthropic()
emitter = AAEPEmitter()

@aaep_tool(emitter, risk_level="high", irreversible=True)
async def send_email(to: str, subject: str, body: str, session_id: str = None):
    return await email_service.send(to, subject, body)

@aaep_tool(emitter, risk_level="low")
async def get_calendar_events(date: str, session_id: str = None):
    return await calendar.get_events(date)

tool_registry = {
    "send_email": send_email,
    "get_calendar_events": get_calendar_events,
}

async def run_agent(user_message: str):
    session_id = emitter.start_session(summary_normal="Processing user request.")

    try:
        messages = [{"role": "user", "content": user_message}]

        while True:
            response = await client.messages.create(
                model="claude-opus-4-7",
                max_tokens=1024,
                tools=[...],  # tool schemas
                messages=messages,
            )

            if response.stop_reason == "tool_use":
                # Execute tool with AAEP wrapping
                for block in response.content:
                    if block.type == "tool_use":
                        tool_fn = tool_registry[block.name]
                        result = await tool_fn(**block.input, session_id=session_id)
                        messages.append({"role": "user", "content": [
                            {"type": "tool_result", "tool_use_id": block.id,
                             "content": str(result)}
                        ]})
            else:
                break

        emitter.complete_session(session_id=session_id, summary_normal="Done.")
        return response

    except Exception as exc:
        emitter.error_session(
            session_id=session_id,
            error_category="unknown",
            summary_normal=str(exc),
        )
        raise
```

---

## OpenAI function calling integration

The same pattern works with OpenAI's function calling:

```python
from openai import AsyncOpenAI

client = AsyncOpenAI()
emitter = AAEPEmitter()

@aaep_tool(emitter, risk_level="high", irreversible=True)
async def book_flight(origin: str, destination: str, date: str, session_id: str = None):
    return await booking_api.book(origin, destination, date)

# Tool registry maps OpenAI function names to decorated implementations
tool_registry = {"book_flight": book_flight}

async def run_agent(user_message: str):
    session_id = emitter.start_session(summary_normal="Processing.")

    messages = [{"role": "user", "content": user_message}]

    while True:
        response = await client.chat.completions.create(
            model="gpt-5",
            messages=messages,
            tools=[...],  # tool schemas
        )

        msg = response.choices[0].message
        if msg.tool_calls:
            for call in msg.tool_calls:
                fn = tool_registry[call.function.name]
                args = json.loads(call.function.arguments)
                result = await fn(**args, session_id=session_id)
                messages.append({"role": "tool", "tool_call_id": call.id,
                                "content": str(result)})
        else:
            break

    emitter.complete_session(session_id=session_id, summary_normal="Done.")
```

---

## Common pitfalls

| Mistake | Consequence | Fix |
|---|---|---|
| Forgetting to pass `session_id` to the wrapped tool | Decorator raises ValueError | Always thread session_id through the agent loop |
| Setting `irreversible=True, default_decision="accept"` (manually) | Schema rejects the confirmation event | Let the decorator compute default_decision automatically |
| Catching `PermissionError` from rejected tools and silently continuing | Agent appears to ignore user's reject | Re-raise or handle explicitly with user-visible response |
| Adding `@aaep_tool` to a sync function | Wrapped function is async; calling site must await | Make tools async or use a sync variant of the decorator |
| Using the decorator without an active session | session_id is None; raises | Wrap calls in start/complete_session boundaries |

---

## Testing

Use the conformance suite to verify decorator-wrapped tools emit correct events:

```bash
aaep-conformance producer \
    --endpoint <your-endpoint> \
    --tool-mode \
    --level 2
```

The suite invokes your decorated tools with synthetic inputs and verifies:

- `agent.tool.invoked` arrives before any tool result
- `agent.awaiting.confirmation` is emitted for irreversible/high-risk tools
- The producer correctly blocks until reply
- `agent.tool.completed` is emitted exactly once, with correct status
- Schema rules are honored (`default_decision` reflects risk profile)

---

## See also

- [Implementer's Guide §2.3](../IMPLEMENTERS_GUIDE.md) — overview of the decorator pattern
- [Implementer's Guide §3.4](../IMPLEMENTERS_GUIDE.md) — Anthropic SDK specifics
- [`callback-based.md`](callback-based.md) — natural pairing partner for framework-level emission
- [`../../examples/producers/python-anthropic-sdk/`](../../examples/producers/python-anthropic-sdk/) — complete worked example
