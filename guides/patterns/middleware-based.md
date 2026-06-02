# Pattern: Middleware-based AAEP Integration

**Use this pattern when your agent framework runs requests through a pipeline of pre/post hooks.**

This is the cleanest integration when available because AAEP code stays out of your agent's reasoning logic. Examples include Microsoft Agent Framework, Semantic Kernel filters, FastAPI middleware around an agent endpoint, and ASP.NET Core middleware.

---

## When middleware is the right choice

Pick middleware when:

- Your framework has a clear request → agent → response pipeline
- You can register hooks that run before and after the agent's main work
- You want zero modifications to your agent's core reasoning code
- Tool-level emission is handled separately (or not required at your conformance level)

Pick something else when:

- You need fine-grained per-tool emission (combine middleware with the decorator pattern)
- Your framework doesn't expose a pipeline (use callbacks or manual loop)
- You need to observe LLM token-by-token streaming (combine with event emitter)

---

## Anatomy of an AAEP middleware

A complete middleware does five things:

1. Emits `agent.session.started` when a request arrives
2. Passes the request to the next handler (the actual agent)
3. Emits `agent.state.changed` events at meaningful transitions (if visible from middleware)
4. Emits `agent.session.completed` on success or `agent.session.errored` on failure
5. Surfaces any exception cleanly while still emitting the terminal event

---

## Complete Python implementation

```python
import asyncio
import time
from typing import Awaitable, Callable

from aaep_helpers import AAEPEmitter, make_id


class AAEPMiddleware:
    """
    Middleware that wraps an agent's request handler with AAEP emissions.
    
    Designed for frameworks that follow the `async def handler(request)` shape.
    """

    def __init__(self, emitter: AAEPEmitter, *, classify_request=None):
        self.emitter = emitter
        # Optional callable that takes a request and returns a summary string
        self.classify_request = classify_request or self._default_summary

    @staticmethod
    def _default_summary(request) -> str:
        text = getattr(request, "user_message", None) or str(request)
        return text[:80] if isinstance(text, str) else "Processing request."

    async def __call__(
        self,
        request,
        next_handler: Callable[[object], Awaitable[object]],
    ):
        session_id = self.emitter.start_session(
            summary_normal=self.classify_request(request),
            request_text=getattr(request, "user_message", None),
            requested_by=getattr(request, "user_id", None),
        )

        start_time = time.monotonic()

        try:
            self.emitter.state_changed(
                session_id=session_id,
                from_state="idle",
                to_state="thinking",
                summary_normal="Agent is processing the request.",
            )

            response = await next_handler(request)

            self.emitter.state_changed(
                session_id=session_id,
                from_state="writing_output",
                to_state="idle",
                summary_normal="Response generated.",
            )

            duration_ms = int((time.monotonic() - start_time) * 1000)
            self.emitter.complete_session(
                session_id=session_id,
                summary_normal=self._summary_for_response(response),
                duration_ms=duration_ms,
            )

            return response

        except asyncio.CancelledError:
            self.emitter.cancelled_session(
                session_id=session_id,
                cancelled_by="system",
                summary_normal="Request was cancelled.",
            )
            raise

        except Exception as exc:
            self.emitter.error_session(
                session_id=session_id,
                error_category=self._classify_error(exc),
                summary_normal=f"Error: {type(exc).__name__}",
                summary_detailed=str(exc)[:1000],
                recoverable=self._is_recoverable(exc),
            )
            raise

    @staticmethod
    def _summary_for_response(response) -> str:
        text = getattr(response, "text", None) or str(response)
        return text[:200] if isinstance(text, str) else "Done."

    @staticmethod
    def _classify_error(exc: Exception) -> str:
        if isinstance(exc, (TimeoutError, asyncio.TimeoutError)):
            return "transient"
        if isinstance(exc, (PermissionError, ValueError)):
            return "requires_user"
        return "unknown"

    @staticmethod
    def _is_recoverable(exc: Exception) -> bool:
        return isinstance(exc, (TimeoutError, asyncio.TimeoutError, ConnectionError))
```

---

## Composing with framework middleware

The pattern composes naturally with your framework's existing middleware. For ASP.NET Core:

```csharp
public class AAEPMiddleware
{
    private readonly RequestDelegate _next;
    private readonly IAAEPEmitter _emitter;

    public AAEPMiddleware(RequestDelegate next, IAAEPEmitter emitter)
    {
        _next = next;
        _emitter = emitter;
    }

    public async Task InvokeAsync(HttpContext context)
    {
        var request = await context.Request.ReadFromJsonAsync<AgentRequest>();
        var sessionId = _emitter.StartSession(
            summaryNormal: Summarize(request),
            requestText: request?.UserMessage
        );

        try
        {
            await _next(context);
            _emitter.CompleteSession(sessionId, summaryNormal: "Done.");
        }
        catch (Exception ex)
        {
            _emitter.ErrorSession(
                sessionId,
                errorCategory: "unknown",
                summaryNormal: $"Error: {ex.GetType().Name}"
            );
            throw;
        }
    }
}

// Register:
app.UseMiddleware<AAEPMiddleware>();
```

The position in the pipeline matters. Register AAEP middleware **inside** your authentication middleware (so we know who's making the request) but **outside** your routing middleware (so we wrap the entire request lifecycle).

---

## The tool emission problem

Middleware sees the request and the response. It does NOT see what happens between — particularly, individual tool invocations. If you need tool-level emission (which you do for Conformance Level 2), combine middleware with one of the other patterns.

The cleanest combination is **middleware + decorator**:

- Middleware handles session lifecycle (started, completed, errored, cancelled)
- Decorator handles tool lifecycle (invoked, completed) and confirmation flow

```python
# Tool decorator handles tool-level events
@aaep_tool(emitter, risk_level="high", irreversible=True)
async def transfer_funds(amount, from_account, to_account):
    ...

# Middleware handles session-level events
agent.use(AAEPMiddleware(emitter))
```

The two patterns don't interfere; they emit at different scopes.

---

## Handling streaming output through middleware

If your framework returns a streaming response (token-by-token output), middleware needs to wrap the stream:

```python
class AAEPMiddleware:
    async def __call__(self, request, next_handler):
        session_id = self.emitter.start_session(...)
        
        try:
            response_stream = await next_handler(request)
            
            # Wrap the stream to emit AAEP output events
            async def aaep_stream():
                position = 0
                output_id = make_id("out")
                async for chunk in response_stream:
                    self.emitter.output_streaming(
                        session_id=session_id,
                        chunk=chunk.text,
                        position=position,
                        complete=chunk.is_final,
                        coalesce_hint=self._coalesce_for(chunk),
                        output_id=output_id,
                    )
                    position += len(chunk.text)
                    yield chunk
            
            return aaep_stream()
        except Exception as exc:
            self.emitter.error_session(...)
            raise
```

---

## Common pitfalls

| Mistake | Consequence | Fix |
|---|---|---|
| Emitting `session.started` AFTER processing begins | Subscribers miss the start of work | Emit immediately on request arrival |
| Catching and swallowing exceptions inside middleware | Session looks orphaned | Always emit terminal event before re-raising |
| Using request-scoped session_id but agent makes nested requests | Nested events lost or misattributed | Generate fresh session_id per top-level request |
| Forgetting to emit `state.changed` to mark transitions | Subscribers don't know what the agent is doing | Emit at clear lifecycle boundaries: thinking, calling_tool, writing_output |
| Putting AAEP middleware BEFORE authentication middleware | Anonymous events emitted | Position AAEP middleware after auth in the pipeline |

---

## Testing your middleware

The conformance suite has a middleware-specific test track:

```bash
aaep-conformance producer \
    --endpoint http://localhost:8000/agent \
    --middleware-mode \
    --level 1
```

The suite exercises your middleware with synthetic requests covering: successful sessions, sessions that error, sessions cancelled mid-execution, sessions that emit no streaming output, sessions that emit lots of streaming output, and concurrent sessions. Pass rate ≥ 95% to claim middleware-based Level 1.

---

## See also

- [Implementer's Guide §2.1](../IMPLEMENTERS_GUIDE.md) — overview of the middleware pattern in context
- [Implementer's Guide §3.2](../IMPLEMENTERS_GUIDE.md) — Microsoft Agent Framework specifics
- [Implementer's Guide §3.5](../IMPLEMENTERS_GUIDE.md) — Semantic Kernel filter integration (same pattern, different name)
- [`../patterns/decorator-based.md`](decorator-based.md) — the natural pairing partner for tool-level emission
- [`../../examples/producers/python-microsoft-agent-framework/`](../../examples/producers/python-microsoft-agent-framework/) — complete working example
