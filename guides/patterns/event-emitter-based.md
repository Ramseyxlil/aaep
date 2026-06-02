# Pattern: Event-emitter-based AAEP Integration

**Use this pattern when your agent framework already publishes events you can subscribe to.**

This pattern provides the cleanest separation between agent code and AAEP code. The agent emits events about itself (often for its own debugging or observability), and a translation bridge converts those into AAEP events. The agent doesn't know AAEP exists.

---

## When the event-emitter pattern is the right choice

Pick event-emitter when:

- Your framework has a native event/pub-sub system (Node.js EventEmitter, AutoGen messages, observable streams)
- You want zero changes to agent code
- You may need to add/remove AAEP support without redeploying the agent
- You're bridging from a framework you don't control (e.g., a vendored library)

Pick something else when:

- Your framework has no event surface (use middleware or manual loop)
- You need to interpose logic synchronously between agent steps (use decorator)
- The translation logic would be more complex than the agent code itself (rethink)

---

## The bridge concept

A bridge is a long-running component that:

1. Subscribes to the framework's native event stream
2. Maintains per-session state (mapping framework session IDs to AAEP session IDs)
3. Translates each framework event into 0, 1, or many AAEP events
4. Manages stream coalescing for streaming output
5. Handles producer-side confirmation flow (if the framework supports awaiting human input)

The bridge is the only component that knows both protocols. The agent stays AAEP-unaware. Subscribers stay framework-unaware.

```
┌──────────┐     framework      ┌────────┐    AAEP     ┌────────────┐
│  Agent   │ ─── events ──────▶ │ Bridge │ ─ events ─▶ │ Subscriber │
└──────────┘                    └────────┘             └────────────┘
   no AAEP                      both sides             no framework
   knowledge                                            knowledge
```

---

## Complete Python (asyncio) implementation

```python
import asyncio
from dataclasses import dataclass
from typing import Any

from aaep_helpers import AAEPEmitter, StreamCoalescer, make_id


@dataclass
class FrameworkEvent:
    """Generic framework event shape; adapt to your framework."""
    kind: str
    framework_session_id: str
    payload: dict[str, Any]


class AAEPEventBridge:
    """
    Bridges a framework's native event stream into AAEP events.

    The framework emits FrameworkEvent objects to source_queue;
    the bridge translates each into appropriate AAEP emissions.
    """

    def __init__(
        self,
        emitter: AAEPEmitter,
        source_queue: asyncio.Queue,
    ):
        self.emitter = emitter
        self.source = source_queue

        # Per-framework-session state
        self.session_map: dict[str, str] = {}        # framework_id -> aaep session_id
        self.coalescers: dict[str, StreamCoalescer] = {}  # session_id -> coalescer
        self.active_tools: dict[str, str] = {}       # framework_tool_id -> aaep tool_call_id
        self.last_states: dict[str, str] = {}        # session_id -> last state

    async def run(self):
        """Main loop. Run as a background task."""
        while True:
            event = await self.source.get()
            try:
                await self._translate(event)
            except Exception as exc:
                # Bridge errors must not crash the agent or block its queue
                print(f"[bridge] error translating {event.kind}: {exc}")

    async def _translate(self, event: FrameworkEvent):
        translator = self.TRANSLATORS.get(event.kind)
        if translator is None:
            return  # unknown event kind; ignore safely
        await translator(self, event)

    # === Translators (one per framework event kind) ===

    async def _on_session_started(self, event: FrameworkEvent):
        aaep_session_id = self.emitter.start_session(
            summary_normal=event.payload.get("description", "Session started."),
            request_text=event.payload.get("user_message"),
        )
        self.session_map[event.framework_session_id] = aaep_session_id
        self.last_states[aaep_session_id] = "idle"

    async def _on_thinking_started(self, event: FrameworkEvent):
        session_id = self._aaep_session(event)
        self.emitter.state_changed(
            session_id=session_id,
            from_state=self.last_states.get(session_id, "idle"),
            to_state="thinking",
            summary_normal="Considering.",
        )
        self.last_states[session_id] = "thinking"

    async def _on_streaming_chunk(self, event: FrameworkEvent):
        session_id = self._aaep_session(event)
        if session_id not in self.coalescers:
            self.coalescers[session_id] = StreamCoalescer(
                emitter=self.emitter,
                session_id=session_id,
                output_id=make_id("out"),
            )
        coalescer = self.coalescers[session_id]
        chunk = event.payload["text"]
        is_final = event.payload.get("is_final", False)
        coalescer.add_token(chunk)
        if is_final:
            coalescer.finish()
            del self.coalescers[session_id]

    async def _on_tool_called(self, event: FrameworkEvent):
        session_id = self._aaep_session(event)
        tool_name = event.payload["tool_name"]
        framework_tool_id = event.payload["tool_id"]
        aaep_tool_call_id = make_id("call")
        self.active_tools[framework_tool_id] = aaep_tool_call_id

        self.emitter.tool_invoked(
            session_id=session_id,
            tool=tool_name,
            tool_call_id=aaep_tool_call_id,
            args_summary=self._safe_summary(event.payload.get("args")),
            risk_level=self._classify_risk(tool_name),
            irreversible=self._is_irreversible(tool_name),
            summary_normal=f"Calling {tool_name}.",
        )

    async def _on_tool_returned(self, event: FrameworkEvent):
        session_id = self._aaep_session(event)
        framework_tool_id = event.payload["tool_id"]
        aaep_tool_call_id = self.active_tools.pop(framework_tool_id, None)

        self.emitter.tool_completed(
            session_id=session_id,
            tool_call_id=aaep_tool_call_id,
            status="success" if not event.payload.get("error") else "error",
            error_message=event.payload.get("error"),
            summary_normal=self._safe_summary(event.payload.get("result")),
        )

    async def _on_session_completed(self, event: FrameworkEvent):
        session_id = self._aaep_session(event)
        # Flush any pending streaming output
        if session_id in self.coalescers:
            self.coalescers[session_id].finish()
            del self.coalescers[session_id]
        self.emitter.complete_session(
            session_id=session_id,
            summary_normal=event.payload.get("summary", "Done."),
        )
        del self.session_map[event.framework_session_id]
        self.last_states.pop(session_id, None)

    async def _on_session_errored(self, event: FrameworkEvent):
        session_id = self._aaep_session(event)
        self.emitter.error_session(
            session_id=session_id,
            error_category="unknown",
            summary_normal=f"Error: {event.payload.get('error')}",
        )
        del self.session_map[event.framework_session_id]

    # === Helpers ===

    def _aaep_session(self, event: FrameworkEvent) -> str:
        session_id = self.session_map.get(event.framework_session_id)
        if session_id is None:
            raise KeyError(
                f"Received {event.kind} for unknown framework session "
                f"{event.framework_session_id}"
            )
        return session_id

    @staticmethod
    def _safe_summary(obj) -> str:
        if obj is None:
            return ""
        return str(obj)[:200]

    @staticmethod
    def _classify_risk(tool_name: str) -> str:
        high_risk = {"send_email", "transfer_funds", "delete_record"}
        if tool_name in high_risk:
            return "high"
        return "low"

    @staticmethod
    def _is_irreversible(tool_name: str) -> bool:
        return tool_name in {"send_email", "transfer_funds", "delete_record"}

    # Dispatch table; populated below class definition
    TRANSLATORS = {}


# Wire up the translators
AAEPEventBridge.TRANSLATORS = {
    "session_started": AAEPEventBridge._on_session_started,
    "thinking_started": AAEPEventBridge._on_thinking_started,
    "streaming_chunk": AAEPEventBridge._on_streaming_chunk,
    "tool_called": AAEPEventBridge._on_tool_called,
    "tool_returned": AAEPEventBridge._on_tool_returned,
    "session_completed": AAEPEventBridge._on_session_completed,
    "session_errored": AAEPEventBridge._on_session_errored,
}
```

Usage:

```python
emitter = AAEPEmitter()
framework_event_queue: asyncio.Queue = asyncio.Queue()
bridge = AAEPEventBridge(emitter, framework_event_queue)

# Start the bridge as a background task
asyncio.create_task(bridge.run())

# Configure your agent to push events to framework_event_queue
agent.event_callback = lambda evt: framework_event_queue.put_nowait(evt)
```

---

## Node.js EventEmitter implementation

```javascript
const EventEmitter = require('events');

class AAEPEventBridge {
  constructor(emitter, sourceEmitter) {
    this.emitter = emitter;
    this.sessionMap = new Map();    // framework session id -> aaep session id
    this.coalescers = new Map();
    this.activeTools = new Map();
    this.lastStates = new Map();

    // Subscribe to framework events
    sourceEmitter.on('session_started', (e) => this.onSessionStarted(e));
    sourceEmitter.on('streaming_chunk', (e) => this.onStreamingChunk(e));
    sourceEmitter.on('tool_called', (e) => this.onToolCalled(e));
    sourceEmitter.on('tool_returned', (e) => this.onToolReturned(e));
    sourceEmitter.on('session_completed', (e) => this.onSessionCompleted(e));
    sourceEmitter.on('session_errored', (e) => this.onSessionErrored(e));
  }

  onSessionStarted(e) {
    const aaepSessionId = this.emitter.startSession({
      summaryNormal: e.description || 'Session started.',
      requestText: e.userMessage,
    });
    this.sessionMap.set(e.frameworkSessionId, aaepSessionId);
    this.lastStates.set(aaepSessionId, 'idle');
  }

  // ... other handlers
}
```

---

## AutoGen v0.4+ integration

AutoGen v0.4+ uses message-passing natively. Subscribe to the agent's message bus:

```python
from autogen_core.base import MessageContext
from autogen_core.components import RoutedAgent, message_handler

class AAEPObservingAgent(RoutedAgent):
    def __init__(self, emitter: AAEPEmitter):
        super().__init__(description="AAEP observer")
        self.bridge = AAEPEventBridge(emitter, asyncio.Queue())

    @message_handler
    async def on_user_message(self, message: UserMessage, ctx: MessageContext):
        await self.bridge.source.put(FrameworkEvent(
            kind="session_started",
            framework_session_id=str(ctx.message_id),
            payload={"user_message": message.content}
        ))

    @message_handler
    async def on_tool_call(self, message: ToolCallMessage, ctx: MessageContext):
        await self.bridge.source.put(FrameworkEvent(
            kind="tool_called",
            framework_session_id=str(ctx.parent_id or ctx.message_id),
            payload={
                "tool_name": message.tool_name,
                "tool_id": message.tool_call_id,
                "args": message.arguments,
            }
        ))

    # ... etc
```

---

## Bridging from a message bus (Kafka, RabbitMQ)

If your framework emits to a message bus rather than an in-process queue:

```python
from aiokafka import AIOKafkaConsumer

async def kafka_to_aaep_bridge(emitter: AAEPEmitter, topic: str, brokers: str):
    consumer = AIOKafkaConsumer(topic, bootstrap_servers=brokers)
    await consumer.start()

    bridge_queue: asyncio.Queue = asyncio.Queue()
    bridge = AAEPEventBridge(emitter, bridge_queue)
    asyncio.create_task(bridge.run())

    try:
        async for msg in consumer:
            framework_event = parse_kafka_message(msg.value)
            await bridge_queue.put(framework_event)
    finally:
        await consumer.stop()
```

---

## Common pitfalls

| Mistake | Consequence | Fix |
|---|---|---|
| Not handling unknown event kinds | Bridge crashes on framework upgrades | Default-case: log and ignore |
| Bridge dies and queue fills indefinitely | Memory leak; agent eventually blocks | Run bridge as supervised task with restart |
| Lost session_id mapping after restart | Orphan AAEP events | Persist session_map or accept session resets on restart |
| Translating one framework event into too many AAEP events | Subscriber flood | Batch or coalesce on the bridge side |
| Bridge blocks on a slow subscriber | Framework events queue up | Use buffered/dropping queue for non-critical events |

---

## Testing

```bash
aaep-conformance producer \
    --endpoint <your-bridge-endpoint> \
    --bridge-mode \
    --level 1
```

The conformance suite synthesizes framework events, pushes them to your bridge, and verifies the AAEP output. Useful for confirming the bridge's translation is faithful before deploying.

---

## See also

- [Implementer's Guide §2.4](../IMPLEMENTERS_GUIDE.md) — overview of the event-emitter pattern
- [Implementer's Guide §3.3](../IMPLEMENTERS_GUIDE.md) — AutoGen specifics
- [Implementer's Guide §3.6](../IMPLEMENTERS_GUIDE.md) — OpenAI Assistants API specifics
- [`../../examples/bridges/`](../../examples/bridges/) — complete bridge implementations including MCP and OpenTelemetry
