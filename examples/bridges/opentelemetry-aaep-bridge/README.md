# OpenTelemetry ↔ AAEP Bridge

A bridge that converts AAEP event streams into [OpenTelemetry](https://opentelemetry.io/) traces and spans, so AAEP-producing agents become observable in any OTEL-compatible backend (Jaeger, Tempo, Datadog, Honeycomb, Grafana, New Relic, and many others).

If you operate AAEP producers in production and want unified observability with the rest of your stack, this bridge is the integration path.

---

## Why this bridge exists

AAEP and OpenTelemetry address different but adjacent concerns:

| Standard | Optimized for | Audience |
|---|---|---|
| **AAEP** | Real-time agent ↔ AT communication with safety semantics | Assistive technology, accessibility consumers |
| **OpenTelemetry** | Post-hoc service observability with rich context | SRE, platform, compliance, security |

An agent emitting AAEP for AT subscribers can simultaneously feed OTEL collectors for observability. This bridge makes that happen without changing either side: AAEP producers stay AAEP, OTEL backends stay OTEL.

---

## What the bridge does

The bridge is a subscriber that connects to any AAEP producer's `/events` SSE endpoint and translates each event into the appropriate OTEL span or span event, then forwards it to a configured OTEL collector.

### AAEP → OTEL translation

| AAEP event | OTEL representation |
|---|---|
| `agent.session.started` | New `span` opens (trace=session_id, span_kind=internal) |
| `agent.session.completed` | The session span closes with `Ok` status |
| `agent.session.errored` | The session span closes with `Error` status + exception event |
| `agent.session.cancelled` | The session span closes with `Cancelled` status |
| `agent.state.changed` | Span event: `state.changed` with from/to attributes |
| `agent.progress.updated` | Span event: `progress` with percent attribute |
| `agent.tool.invoked` | Child span opens (tool name, args_summary, risk attrs) |
| `agent.tool.completed` | Child span closes with corresponding status |
| `agent.output.streaming` | Span event: `output.chunk` (counted, not text-content) |
| `agent.awaiting.confirmation` | Span event: `confirmation.requested` (CRITICAL severity) |
| `agent.awaiting.clarification` | Span event: `clarification.requested` (CRITICAL severity) |
| `agent.handoff.requested` | Span event: `handoff.requested` (CRITICAL severity) |

### Privacy-preserving translation

OTEL backends are often shared infrastructure. We do not forward potentially-sensitive content:

- **Text content** is replaced with counts (e.g., `"output.chunk_size_bytes"` not the chunk text itself)
- **Tool arguments** use the already-redacted `args_summary` field (passwords/tokens redacted by the producer)
- **User messages** are forwarded only as length/hash, not the literal text
- **Reply tokens** are NOT forwarded (they're internal to the AAEP transport)

The result: an OTEL backend sees the shape and timing of agent activity, including critical safety events, without seeing the actual user data.

### Critical event signaling

Critical-urgency AAEP events (`session.errored`, `awaiting.confirmation`, `awaiting.clarification`, `handoff.requested`) get extra OTEL treatment:

- Marked with `severity_text="CRITICAL"` and `severity_number=21`
- Emitted as `Span.add_event()` so they appear inline in traces
- Tagged with `aaep.urgency=critical` for filter queries

OTEL backends can route these to alert channels for real-time visibility into agent safety-relevant events.

---

## Installation

```bash
cd examples/bridges/opentelemetry-aaep-bridge
pip install -e .
```

This installs the bridge with OTEL SDK dependencies. Real OTEL collectors are external (Jaeger, OTLP-compatible exporter, etc.).

Requires Python 3.10 or newer.

---

## Quick start

### 1. Start any AAEP producer

In one terminal:

```bash
python -m aaep_minimal_producer.server --port 8080
```

### 2. Configure OTEL export target

Set environment variables for your OTEL collector. For an OTLP-compatible endpoint:

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT="http://localhost:4317"
export OTEL_SERVICE_NAME="aaep-bridge"
export OTEL_RESOURCE_ATTRIBUTES="aaep.bridge.version=1.0.0"
```

For local development you can use the console exporter (no collector needed):

```bash
export OTEL_TRACES_EXPORTER=console
```

### 3. Start the bridge

```bash
aaep-otel-bridge --endpoint http://localhost:8080
```

The bridge connects to the AAEP producer, consumes events, and exports them to OTEL.

### 4. Drive an AAEP session

In a third terminal, trigger a session:

```bash
curl -X POST http://localhost:8080/sessions \
    -H "Content-Type: application/json" \
    -d '{"user_message": "Send an email to alice@example.com"}'
```

You'll see OTEL traces appear in your collector. The session becomes a trace; each tool call becomes a span; each critical event becomes a flagged span event.

---

## Example trace shape (in Jaeger)

```
[trace 8f3a2b1c...]  session_id=sess_a1b2c3
├─ [span] aaep.session                  duration: 1.8s   status: Ok
│   │   attrs: aaep.session_id=sess_a1b2c3
│   │           aaep.agent_id=demo-agent
│   │           aaep.duration_ms=1812
│   │           aaep.tool_invocations_count=1
│   │
│   ├─ [event] state.changed             from=idle, to=thinking
│   ├─ [event] state.changed             from=thinking, to=calling_tool
│   │
│   ├─ [span] aaep.tool.send_email       duration: 800ms  status: Ok
│   │   │   attrs: aaep.tool=send_email
│   │   │           aaep.risk_level=high
│   │   │           aaep.irreversible=true
│   │   │           aaep.args_summary="to=alice@example.com"
│   │   │
│   │   ├─ [event] confirmation.requested  severity=CRITICAL
│   │   │       attrs: aaep.action="Call send_email"
│   │   │               aaep.consequence="This action cannot be easily undone."
│   │   │               aaep.default_decision=reject
│   │   │
│   │   └─ [event] confirmation.received   decision=accept
│   │
│   ├─ [event] state.changed             from=calling_tool, to=writing_output
│   ├─ [event] output.chunk               chunk_size_bytes=42
│   ├─ [event] output.chunk               chunk_size_bytes=18  complete=true
│   │
│   └─ [span end] status=Ok
```

The trace lets SREs verify:
- How long sessions take (full session span duration)
- Which tools are called and how often (child spans)
- Where critical events occur in the timeline (CRITICAL-severity span events)
- Whether confirmations are typically accepted or rejected (event attributes)

---

## Compliance and audit use cases

For organizations subject to compliance audits (HIPAA, SOX, GDPR, etc.), this bridge provides:

- **Audit trail of all AAEP-emitting agent activity** in your existing OTEL store
- **Critical event flagging** for security/compliance review
- **Privacy-preserving traces** that don't include the content but document the shape and decisions
- **Standard OTLP format** that works with whatever compliance backend you already have

The bridge does NOT replace AAEP. AT subscribers should still connect directly to the AAEP `/events` endpoint for real-time accessibility delivery. The OTEL bridge is parallel infrastructure for SRE/compliance observation.

---

## Configuration

| Environment variable | Purpose |
|---|---|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OTLP gRPC endpoint (e.g., http://collector:4317) |
| `OTEL_EXPORTER_OTLP_PROTOCOL` | "grpc" or "http/protobuf" (default: grpc) |
| `OTEL_SERVICE_NAME` | Service name in OTEL backend (default: "aaep-bridge") |
| `OTEL_RESOURCE_ATTRIBUTES` | Comma-separated key=value pairs |
| `OTEL_TRACES_EXPORTER` | "otlp" (default) or "console" (for local dev) |

CLI flags override env vars where applicable.

---

## Project layout

```
opentelemetry-aaep-bridge/
├── README.md
├── pyproject.toml
├── aaep_otel_bridge/
│   ├── __init__.py
│   ├── translator.py        # AAEP → OTEL event translator
│   └── bridge.py            # Subscriber loop + CLI entry
└── tests/
    └── test_translator.py
```

---

## Limitations

- **Subscriber-only.** This bridge consumes AAEP events; it does not emit AAEP from OTEL traces (that direction has no clear use case yet).
- **No back-pressure handling.** If your OTEL collector can't keep up with a high-volume AAEP producer, the bridge will buffer in memory. Configure a real collector with batching for production use.
- **Privacy-aware by default.** Text content is not forwarded. If you need richer attributes for debugging, edit `translator.py` (and add appropriate consent banners).

---

## See also

- [`../mcp-aaep-bridge/`](../mcp-aaep-bridge/) — sister bridge for MCP
- [OpenTelemetry specification](https://opentelemetry.io/docs/specs/) — upstream OTEL standard
- [Specification appendix D](../../../spec/appendix/D-references.md) — AAEP cross-references
- [Implementer's Guide §5](../../../guides/IMPLEMENTERS_GUIDE.md) — bridge integration patterns
