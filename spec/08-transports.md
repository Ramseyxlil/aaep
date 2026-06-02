# Chapter 8 — Transports

*Status: Normative for §8.1 through §8.4. Informative for §8.5 through §8.10.*

---

This chapter specifies the **transport-agnostic requirements** that any underlying transport carrying AAEP messages MUST satisfy. AAEP is deliberately transport-neutral: the same protocol semantics work over Server-Sent Events, WebSocket, local IPC, gRPC, stdio, or any other channel that satisfies the requirements here.

After the normative section, this chapter provides an informative survey of recommended transport bindings, with selection guidance. Concrete protocol-level details for each binding are in [Appendix B (Transport bindings)](appendix/B-transport-bindings.md).

## 8.1 The transport abstraction principle

AAEP's wire format is JSON. AAEP's exchange model (events flowing from producer to subscriber, reply messages flowing from subscriber to producer) is independent of how those JSON messages are physically transmitted. A producer running in a Python process emitting JSON to stdout, a producer running in a cloud server pushing JSON over Server-Sent Events, and a producer running in a desktop application writing JSON to a Windows named pipe are all equally conforming as long as the messages they emit and accept conform to this specification and the transport they use satisfies the requirements in §8.2.

This abstraction has three important consequences:

1. **Implementers choose the transport that fits their deployment.** A web application uses SSE or WebSocket. A native desktop application uses local IPC. A command-line tool spawned by a subscriber uses stdio. A high-throughput multi-tenant service uses gRPC. None of these choices change anything about the messages.

2. **Producers and subscribers can switch transports.** A subscriber that fails to connect over WebSocket may retry over SSE without renegotiating its capabilities at the AAEP level. Transport selection is below AAEP.

3. **Transports can be added later.** Future transports (QUIC streams, distributed pub-sub, peer-to-peer overlays) can carry AAEP without changes to this specification. Adding a transport is an extension activity (see [Chapter 7 §7.1](07-extensions.md), capability 5).

## 8.2 Normative transport requirements

The following requirements apply to ALL transports used to carry AAEP messages. A transport that does not satisfy these requirements is non-conforming, and producers/subscribers using such a transport cannot claim AAEP conformance.

### 8.2.1 Message integrity

The transport MUST deliver each AAEP message to the receiver byte-identical to the form in which the sender emitted it. Any transport that may corrupt, truncate, or alter messages in transit is non-conforming.

This is typically satisfied automatically by any transport with adequate framing (HTTP, WebSocket frames, IPC message boundaries, JSON-RPC line delimiters). Implementers using raw TCP or other unframed transports MUST add their own framing.

### 8.2.2 Message boundaries

The transport MUST preserve the boundaries between AAEP messages. The receiver MUST be able to identify where one JSON message ends and the next begins, without parsing the JSON content itself.

Approved framing strategies include:

- **HTTP request/response** with `Content-Type: application/json` (one message per request).
- **Server-Sent Events `data:` lines** with `\n\n` termination (one message per event).
- **WebSocket text or binary frames** (one message per frame).
- **Length-prefixed framing** (4-byte big-endian length followed by JSON bytes), suitable for raw TCP or IPC.
- **Newline-delimited JSON (NDJSON)** with `\n` between messages, where messages themselves do not contain embedded newlines. NOT RECOMMENDED for pretty-printed JSON; suitable for compact JSON only.
- **JSON-RPC envelope** with explicit `id` and `method` fields wrapping AAEP payloads.

A transport that relies on the receiver parsing JSON to find message boundaries (no framing) is non-conforming because malformed JSON cannot be recovered from in a stream.

### 8.2.3 Ordered delivery within a session

The transport MUST deliver messages of a single session to a single subscriber in the order the producer emitted them. The transport MAY reorder messages across sessions or across subscribers.

If the transport cannot guarantee ordering (e.g., UDP-based transports), producers MUST emit `sequence_number` on every event, and subscribers MUST detect out-of-order events and either reorder them before processing or signal a protocol error to the producer.

### 8.2.4 At-least-once delivery

The transport MUST deliver each message at least once. Lost messages are non-conforming.

The transport MAY deliver messages more than once (duplicate delivery). Subscribers MUST be prepared to deduplicate using `event_id`. Producers MUST emit unique `event_id` values per event (per §3.2.3).

### 8.2.5 Connection lifecycle signals

The transport MUST provide signals to both parties when the connection terminates, whether gracefully (the other party closed) or abruptly (network failure, process crash). Both producers and subscribers MUST handle disconnection by:

- Stopping further message transmission.
- Releasing resources associated with the connection.
- For producers: applying `default_decision` to any pending confirmations whose subscriber-of-record was on the disconnected connection (per [Chapter 6 §6.4](06-confirmation-protocol.md) and Chapter 5 §5.8.2).

### 8.2.6 Bidirectional capability when reply messages are required

Transports used at Conformance Level 2 or higher MUST support reply messages from subscriber to producer. SSE alone does not (SSE is one-way from server to client); SSE deployments at Level 2 MUST pair SSE for producer-to-subscriber events with HTTP POST or a separate channel for subscriber-to-producer replies.

Transports that are intrinsically bidirectional (WebSocket, gRPC bidirectional streams, IPC) MAY carry both directions on the same connection.

### 8.2.7 Authentication hooks

The transport MUST provide a mechanism by which one party can authenticate the other. Acceptable mechanisms include:

- TLS with mutual certificate authentication.
- Authorization headers (Bearer tokens, mutual TLS plus signed JWS).
- Local-IPC trust based on operating-system process identity (Unix socket peer credentials, Windows named-pipe security descriptors).
- Pre-shared keys (with appropriate caution; see [Chapter 10](10-security.md)).

Transports lacking authentication mechanisms (plain HTTP, anonymous TCP, anonymous IPC over public sockets) are non-conforming for production use. They MAY be used for local development if the security implications are understood; conformance testing on such transports is permitted only with explicit warnings.

### 8.2.8 Confidentiality for non-local transports

Transports that traverse a network MUST encrypt traffic in transit. Acceptable mechanisms:

- TLS 1.2 or higher (TLS 1.3 RECOMMENDED) for HTTPS, WSS, and gRPC.
- Application-layer encryption equivalent to TLS for transports not natively supporting TLS.

Transports operating purely within a single host (Unix domain sockets, Windows named pipes, stdio) MAY omit transport encryption since OS-level protections suffice. Implementers running such transports across hosts MUST add encryption.

## 8.3 Maximum message size

The transport MUST support messages up to at least 64 KiB in size (consistent with the AAEP envelope size limit in §3.7). Transports that impose smaller maximums are non-conforming.

The transport SHOULD support messages up to 1 MiB to accommodate large extension payloads. Producers SHOULD nevertheless prefer to split large content across multiple events rather than transmit single large events.

## 8.4 Transport selection in subscription handshake

The transport in use at the time of subscription is implicitly chosen by the subscriber initiating the connection. The subscription handshake (`subscription.request`) does not normally specify the transport, since the handshake messages themselves are travelling over the transport.

However, a producer manifest (§5.10) MAY advertise multiple supported transports. A subscriber that can choose may select based on its capabilities; producers MAY redirect a connection to a different transport (e.g., HTTP 307 redirect, WebSocket upgrade response) if the transport offered does not match the producer's preferences.

The full lifecycle of transport selection, fallback, and reconnection is documented in [Appendix B](appendix/B-transport-bindings.md).

---

## 8.5 Survey of recommended transports

*The remainder of this chapter is informative.*

The following transports are RECOMMENDED bindings. Each has trade-offs that suit different deployment contexts. Implementers SHOULD choose based on their environment rather than uniformity for its own sake.

### 8.5.1 Server-Sent Events (SSE)

**When to use:** Web applications where the agent runs server-side and the subscriber is in a browser. Particularly suited when the subscriber is a screen reader integrated into a web-based UI, a captioning overlay, or a server-rendered accessible interface.

**Pros:**

- Standard HTTP infrastructure (works through corporate proxies and CDNs).
- Automatic reconnection with last-event-ID resumption.
- Simple to implement; well-supported across languages.
- Already in production at most major LLM API providers for streaming completions.

**Cons:**

- One-way only (server → client). Replies require a separate HTTP POST endpoint.
- Higher per-message overhead than WebSocket due to HTTP framing.
- Some legacy proxies buffer SSE poorly.

**Reference binding details:** [Appendix B §B.1](appendix/B-transport-bindings.md#b1-server-sent-events).

### 8.5.2 WebSocket

**When to use:** Web applications requiring full bidirectional flow, where replies, renegotiation, or push notifications need lowest latency.

**Pros:**

- Fully bidirectional in a single connection.
- Low per-message overhead.
- Frame boundaries provided natively.
- Wide language and runtime support.

**Cons:**

- Some corporate proxies block or buffer WebSocket traffic.
- Reconnection logic must be implemented by the application (no native resume).
- Slightly more complex client code than SSE.

**Reference binding details:** [Appendix B §B.2](appendix/B-transport-bindings.md#b2-websocket).

### 8.5.3 Local IPC: Windows named pipes

**When to use:** Desktop integration where the AAEP producer runs as a desktop application or service and the subscriber is a screen reader, voice control software, or other AT installed locally on Windows.

**Path convention:** `\\.\pipe\aaep\<producer-id>`

**Pros:**

- High performance (no network stack overhead).
- Native OS-level authentication via security descriptors and process identity.
- Works without network configuration.
- Standard mechanism on Windows for AT-to-application communication.

**Cons:**

- Platform-specific (Windows only).
- Requires named pipe permissions to be set correctly.
- Cross-process debugging is harder than network transports.

**Reference binding details:** [Appendix B §B.3](appendix/B-transport-bindings.md#b3-windows-named-pipes).

### 8.5.4 Local IPC: Unix domain sockets

**When to use:** Desktop integration on macOS, Linux, BSD where producer and subscriber share a host.

**Path convention:** `$XDG_RUNTIME_DIR/aaep/<producer-id>.sock` (Linux/BSD) or `~/Library/Application Support/AAEP/<producer-id>.sock` (macOS).

**Pros:**

- High performance.
- Native authentication via peer credentials (UID/GID, process identity).
- Standard mechanism for desktop service integration.

**Cons:**

- Platform-specific (Unix-like only).
- Cross-platform code requires both this and Windows named pipes.

**Reference binding details:** [Appendix B §B.4](appendix/B-transport-bindings.md#b4-unix-domain-sockets).

### 8.5.5 gRPC bidirectional streams

**When to use:** Multi-tenant or enterprise deployments where strong typing, low latency, and binary efficiency matter more than universality.

**Pros:**

- High performance, efficient binary encoding.
- Strong typing via Protocol Buffers (AAEP JSON wrapped in a `Bytes` field, or expressed via a Protocol Buffers IDL provided as a non-normative companion).
- First-class bidirectional streaming.
- Standard observability through OpenTelemetry, mTLS authentication.

**Cons:**

- Larger client-side library footprint than SSE/WebSocket.
- Harder to debug than text-based transports.
- gRPC-Web is required for browser clients (additional layer).

**Reference binding details:** [Appendix B §B.5](appendix/B-transport-bindings.md#b5-grpc).

### 8.5.6 stdio JSON-RPC

**When to use:** When a subscriber spawns a producer as a child process and communicates over stdin/stdout (or vice versa). This pattern is common for desktop assistive technology launching agent processes, and for the Model Context Protocol's local server pattern.

**Format:** JSON-RPC 2.0 messages framed by newline (one JSON object per line). AAEP messages are wrapped in JSON-RPC request/response envelopes.

**Pros:**

- Trivial to implement; no networking required.
- Works in sandboxed environments (mobile, browsers via WebAssembly, restricted enterprise machines).
- Native to the patterns established by Language Server Protocol and Model Context Protocol.
- Direct OS-level trust between parent and child.

**Cons:**

- Single producer per subscriber per process.
- Process lifecycle becomes the connection lifecycle.

**Reference binding details:** [Appendix B §B.6](appendix/B-transport-bindings.md#b6-stdio-json-rpc).

## 8.6 Transport selection guidance

The following table summarizes recommended transport selection for common deployments. The advice is informative; many other combinations work.

| Deployment | Recommended primary transport | Alternative |
|---|---|---|
| Browser-based subscriber, agent in cloud | SSE + HTTP POST for replies | WebSocket |
| Browser-based subscriber, agent in browser | WebSocket (in-page) | postMessage with framing |
| Desktop AT (Narrator, NVDA), local agent | Windows named pipes (Windows); Unix domain sockets (macOS/Linux) | stdio JSON-RPC |
| Desktop AT, agent in cloud | WebSocket | SSE + HTTP POST |
| Mobile screen reader, mobile agent | Platform IPC (UIAccessibility on iOS, AccessibilityService on Android, AAEP transport binding TBD) | stdio JSON-RPC for prototypes |
| Multi-tenant enterprise | gRPC | WebSocket with mTLS |
| Sandbox or browser extension subscriber | postMessage with framing, WebSocket via tunnel, or HTTP+SSE | stdio JSON-RPC if subprocess permissions exist |
| CLI debug tool | stdio JSON-RPC | SSE or WebSocket if debugging cloud agents |
| OS-level voice control | Windows named pipes or Unix domain sockets | Platform-specific IPC |
| Tests, replays, captures | Newline-delimited JSON on filesystem | stdio JSON-RPC |

## 8.7 Reconnection semantics

When a transport connection fails, the subscriber MAY reconnect. The semantics of reconnection depend on the transport:

- **SSE** supports `Last-Event-ID` headers, and the producer SHOULD honor them to resume from the last event the subscriber received.
- **WebSocket** has no native resumption; the subscriber must reissue `subscription.request` after reconnect. The producer SHOULD recognize a `subscriber_id` that was recently connected and skip restating the manifest if capabilities are unchanged.
- **Local IPC** typically has no resumption; reconnect requires a fresh handshake.
- **gRPC** streams support resumption via deadline extension and client retries; the producer SHOULD recognize resumed streams within a short window.

In all cases, if a subscriber reconnects while the producer is mid-session, the producer SHOULD send the subscriber an `agent.state.changed` event summarizing the current state to bring the subscriber up to speed.

## 8.8 Backpressure at the transport layer

Backpressure (Chapter 5 §5.6) is primarily a producer-level concern: the producer holds events and coalesces based on the subscriber's declared rate. However, transports also have their own buffering and flow control:

- **TCP-based transports** (HTTP, WebSocket, TCP socket) provide kernel-level flow control via TCP window updates.
- **Local IPC** has finite OS-level buffers; writes block when buffers are full.
- **HTTP/SSE** is one-way; backpressure is limited to closing the SSE connection.

Producers SHOULD treat transport-layer write blocking as a signal to slow event emission to that subscriber, even if the negotiated rate is technically not yet reached. Subscribers SHOULD read promptly to prevent transport-layer backpressure from masking AAEP-layer rate negotiation.

## 8.9 Diagnostics and observability

All transports SHOULD support diagnostic mechanisms compatible with standard tooling:

- **HTTP transports** integrate with browser DevTools, curl, and standard reverse proxies.
- **WebSocket** is inspectable in browser DevTools and via `wscat`-style tools.
- **Local IPC** is inspectable via OS-specific tools (`netstat`, `lsof`, `Get-Process`, `Process Monitor`).
- **gRPC** integrates with grpcurl and gRPC Web tools.
- **stdio JSON-RPC** is trivially inspectable via piping or log capture.

The AAEP project's `aaep-capture` tool (in [`tools/aaep-capture/`](../tools/aaep-capture/)) provides cross-transport capture and replay for debugging.

## 8.10 Where to go next

Readers should now proceed to [Chapter 9 (Conformance)](09-conformance.md), which specifies the three conformance levels (Notification, Interactive, Negotiated) and their normative requirements.

Implementers selecting a specific transport should consult [Appendix B (Transport bindings)](appendix/B-transport-bindings.md) for concrete code-level details of each binding, including header values, URL paths, error codes, and reference examples.
