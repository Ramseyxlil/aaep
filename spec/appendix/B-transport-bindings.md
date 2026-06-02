# Appendix B — Transport bindings

*Status: Informative*

---

This appendix provides **concrete code-level details** for each of the recommended transport bindings surveyed in [Chapter 8 §8.5](../08-transports.md). Each binding section includes URL or path conventions, framing rules, header values, authentication patterns, reconnection behavior, and minimal working examples.

The bindings here are non-normative: any transport satisfying the requirements in Chapter 8 §8.2-§8.4 is conforming. The bindings in this appendix represent the recommended deployment patterns, established to encourage interoperability across implementations that choose the same transport.

## B.1 Server-Sent Events (SSE)

### B.1.1 Producer endpoint conventions

A producer offering SSE exposes two HTTP endpoints:

- **Event stream endpoint:** `GET /aaep/v1/events` — the server-sent events stream.
- **Reply endpoint:** `POST /aaep/v1/replies` — for `confirmation.reply`, `clarification.reply`, `subscription.renegotiate`, and `subscription.close` messages.

Both endpoints SHOULD be served from the same origin (host:port). The path prefix `/aaep/v1` MAY be different per deployment but SHOULD be discoverable from the producer manifest.

### B.1.2 Establishing the subscription

The subscriber initiates by POSTing a `subscription.request`:

```http
POST /aaep/v1/subscriptions HTTP/1.1
Host: producer.example.com
Authorization: Bearer eyJhbGciOi...
Content-Type: application/json

{
  "type": "subscription.request",
  "aaep_version": "1.0.0",
  "subscriber_id": "windows-narrator",
  "capabilities": {
    "max_events_per_second": 3,
    "preferred_verbosity": "normal",
    "languages": ["en-US"],
    "supports_confirmation_reply": true,
    "coalesce_boundaries": ["sentence", "completion"]
  }
}
```

The producer responds with either `subscription.accepted` or `subscription.rejected`:

```http
HTTP/1.1 201 Created
Content-Type: application/json
Location: /aaep/v1/events?subscription_id=sub_8a4f2c9d

{
  "type": "subscription.accepted",
  "subscription_id": "sub_8a4f2c9d",
  "aaep_version": "1.0.0",
  "producer": { "agent_id": "retirement-planner" },
  "honored_capabilities": { ... }
}
```

The subscriber then opens an SSE stream against the URL in the `Location` header.

### B.1.3 SSE stream format

The event stream uses standard SSE syntax. Each AAEP event is sent as a single SSE event:

```text
event: aaep.event
id: evt_8a3f5b22c91e4d7a
data: {"@context":"https://aaep-protocol.org/context/v1","type":"aaep:agent.session.started","event_id":"evt_8a3f5b22c91e4d7a","session_id":"sess_2c91a7","timestamp":"2026-05-24T14:22:11.342Z","producer":{"agent_id":"retirement-planner"},"summary_normal":"Session started."}

event: aaep.event
id: evt_1b7a4f2c9e3d6a8f
data: {"@context":"https://aaep-protocol.org/context/v1","type":"aaep:agent.state.changed","event_id":"evt_1b7a4f2c9e3d6a8f","session_id":"sess_2c91a7","timestamp":"2026-05-24T14:22:11.421Z","producer":{"agent_id":"retirement-planner"},"from_state":"idle","to_state":"thinking"}
```

**Notes:**

- The `event:` field is always `aaep.event` for core AAEP events. Extensions MAY use other event names.
- The `id:` field is the AAEP `event_id`, enabling SSE's native `Last-Event-ID` resumption.
- The `data:` field contains the complete AAEP JSON on a single line. Multi-line JSON SHOULD use multiple `data:` lines per SSE convention.

### B.1.4 Reply messages

Replies are sent as HTTP POST to the reply endpoint:

```http
POST /aaep/v1/replies HTTP/1.1
Host: producer.example.com
Authorization: Bearer eyJhbGciOi...
Content-Type: application/json

{
  "type": "confirmation.reply",
  "reply_token": "rpl_4f8a2e7d9c1b6a3f",
  "decision": "accept",
  "subscription_id": "sub_8a4f2c9d",
  "timestamp": "2026-05-24T14:22:24.812Z"
}
```

The producer responds with `204 No Content` on successful acceptance:

```http
HTTP/1.1 204 No Content
```

Or `400 Bad Request` for invalid replies (with body):

```http
HTTP/1.1 400 Bad Request
Content-Type: application/json

{
  "error": "invalid_token",
  "message": "Reply token does not match any outstanding confirmation."
}
```

### B.1.5 Reconnection with Last-Event-ID

If the SSE stream disconnects, the subscriber MAY reconnect using the SSE-standard `Last-Event-ID` header:

```http
GET /aaep/v1/events?subscription_id=sub_8a4f2c9d HTTP/1.1
Host: producer.example.com
Authorization: Bearer eyJhbGciOi...
Accept: text/event-stream
Last-Event-ID: evt_1b7a4f2c9e3d6a8f
```

The producer SHOULD resume the stream from the event after the specified `event_id`. If the producer cannot resume (event was already aged out), it MUST emit an `agent.state.changed` event summarizing the current state of the session, then continue normally.

### B.1.6 Required HTTP headers

For SSE event stream:

- `Accept: text/event-stream`
- `Cache-Control: no-cache`
- `Authorization: <auth scheme>` (e.g., Bearer token)

For reply POSTs:

- `Content-Type: application/json`
- `Authorization: <auth scheme>`

### B.1.7 Browser compatibility

Modern browsers' EventSource API supports the SSE pattern. Implementers building browser subscribers can use:

```javascript
const stream = new EventSource(
  `/aaep/v1/events?subscription_id=${subscriptionId}`,
  { withCredentials: true }
);

stream.addEventListener('aaep.event', (event) => {
  const aaepEvent = JSON.parse(event.data);
  // handle event...
});
```

EventSource handles reconnection automatically using `Last-Event-ID`.

## B.2 WebSocket

### B.2.1 Endpoint conventions

A WebSocket producer exposes a single endpoint:

- **WebSocket endpoint:** `wss://producer.example.com/aaep/v1/ws`

The subprotocol identifier `aaep.v1` MUST be negotiated during the WebSocket handshake:

```http
GET /aaep/v1/ws HTTP/1.1
Host: producer.example.com
Upgrade: websocket
Connection: Upgrade
Sec-WebSocket-Version: 13
Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==
Sec-WebSocket-Protocol: aaep.v1
Authorization: Bearer eyJhbGciOi...
```

The producer responds with `101 Switching Protocols`:

```http
HTTP/1.1 101 Switching Protocols
Upgrade: websocket
Connection: Upgrade
Sec-WebSocket-Accept: s3pPLMBiTxaQ9kYGzzhZRbK+xOo=
Sec-WebSocket-Protocol: aaep.v1
```

### B.2.2 Frame format

Each AAEP message (event or handshake message or reply) is sent as a single WebSocket text frame containing the JSON object:

```text
[Text frame] {"@context":"https://aaep-protocol.org/context/v1","type":"aaep:agent.session.started",...}
[Text frame] {"@context":"https://aaep-protocol.org/context/v1","type":"aaep:agent.state.changed",...}
```

Each frame contains exactly one message. Binary frames SHOULD NOT be used for AAEP messages.

### B.2.3 Handshake over WebSocket

After the WebSocket connection is established, the subscriber sends the first AAEP message — typically `subscription.request`:

```json
{
  "type": "subscription.request",
  "aaep_version": "1.0.0",
  "subscriber_id": "narrator-web",
  "capabilities": { ... }
}
```

The producer responds with `subscription.accepted` or `subscription.rejected` in the next text frame.

### B.2.4 Reply messages

Reply messages flow on the same WebSocket connection, as text frames in the subscriber-to-producer direction:

```json
{
  "type": "confirmation.reply",
  "reply_token": "rpl_4f8a2e7d9c1b6a3f",
  "decision": "accept",
  "subscription_id": "sub_8a4f2c9d",
  "timestamp": "2026-05-24T14:22:24.812Z"
}
```

The producer does not send an explicit acknowledgment; the next state change event implicitly confirms reply receipt.

### B.2.5 Reconnection

WebSocket does not have native resumption. After disconnection, the subscriber MUST reissue a fresh `subscription.request`. The producer MAY recognize a `subscriber_id` that was recently connected (within, say, 60 seconds) and may skip the full handshake response if capabilities are unchanged.

### B.2.6 Close codes

The WebSocket close frame carries a numeric code and optional reason string. AAEP-specific close codes are in the WebSocket private-use range:

| Code | Meaning |
|---|---|
| 4000 | Subscription closed cleanly (informational). |
| 4001 | Subscription rejected during handshake. |
| 4002 | Authentication failed. |
| 4003 | Authorization denied. |
| 4004 | Subscription terminated by producer due to violation. |
| 4005 | Subscription terminated by subscriber. |

Standard WebSocket close codes (1000, 1001, etc.) apply when the close is due to transport-level reasons unrelated to AAEP.

## B.3 Windows named pipes

### B.3.1 Pipe path convention

A producer offering Windows named pipes opens a pipe at:

```text
\\.\pipe\aaep\<producer-id>
```

The path components are case-insensitive but SHOULD use the casing the producer publishes in its manifest. For example, a producer with `agent_id: "retirement-planner"` opens:

```text
\\.\pipe\aaep\retirement-planner
```

### B.3.2 Pipe creation parameters

The producer creates the pipe with `CreateNamedPipe` using parameters that enable:

- `PIPE_ACCESS_DUPLEX` — bidirectional access.
- `PIPE_TYPE_MESSAGE | PIPE_READMODE_MESSAGE | PIPE_WAIT` — message-mode I/O.
- A security descriptor restricting access to the current user account (and optionally the SYSTEM account).
- An output buffer of at least 1 MiB to accommodate large AAEP messages.

```c
HANDLE hPipe = CreateNamedPipeA(
    "\\\\.\\pipe\\aaep\\retirement-planner",
    PIPE_ACCESS_DUPLEX,
    PIPE_TYPE_MESSAGE | PIPE_READMODE_MESSAGE | PIPE_WAIT,
    PIPE_UNLIMITED_INSTANCES,
    65536,    // out buffer size
    65536,    // in buffer size
    0,
    &securityAttributes  // ACL restricting to current user
);
```

### B.3.3 Subscriber connection

The subscriber connects with `CreateFile`:

```c
HANDLE hPipe = CreateFileA(
    "\\\\.\\pipe\\aaep\\retirement-planner",
    GENERIC_READ | GENERIC_WRITE,
    0,
    NULL,
    OPEN_EXISTING,
    0,
    NULL
);
```

### B.3.4 Message framing

Each AAEP message is sent as a single Windows named-pipe message. Because the pipe is in message mode, message boundaries are preserved automatically. A single `WriteFile` / `ReadFile` call carries exactly one AAEP JSON document.

For pipes opened in byte mode (less common), implementers MUST add explicit framing such as length-prefixed framing:

```text
[4-byte big-endian length] [JSON bytes]
```

### B.3.5 Handshake and event flow

After the pipe is established, the subscriber writes a `subscription.request` message. The producer reads it, validates, and responds with `subscription.accepted` or `subscription.rejected`. Events then flow from producer to subscriber, and reply messages flow from subscriber to producer, on the same pipe.

### B.3.6 Authentication

Authentication is handled by the OS: the named pipe's security descriptor restricts which user accounts can connect. The producer SHOULD also validate the connecting process via `GetNamedPipeClientProcessId` if process-level isolation is needed.

## B.4 Unix domain sockets

### B.4.1 Socket path convention

A producer offering Unix domain socket transport opens a socket at:

- On Linux/BSD: `$XDG_RUNTIME_DIR/aaep/<producer-id>.sock` (typically `/run/user/<uid>/aaep/<producer-id>.sock`).
- On macOS: `~/Library/Application Support/AAEP/<producer-id>.sock`.
- Fallback: `/tmp/aaep-<uid>/<producer-id>.sock` if neither of the above is writable.

### B.4.2 Socket creation

```c
int sock = socket(AF_UNIX, SOCK_STREAM, 0);

struct sockaddr_un addr = {0};
addr.sun_family = AF_UNIX;
strncpy(addr.sun_path, "/run/user/1000/aaep/retirement-planner.sock", sizeof(addr.sun_path) - 1);

bind(sock, (struct sockaddr *)&addr, sizeof(addr));
chmod(addr.sun_path, 0600);  // owner-only access
listen(sock, 8);
```

### B.4.3 Subscriber connection

```c
int sock = socket(AF_UNIX, SOCK_STREAM, 0);

struct sockaddr_un addr = {0};
addr.sun_family = AF_UNIX;
strncpy(addr.sun_path, "/run/user/1000/aaep/retirement-planner.sock", sizeof(addr.sun_path) - 1);

connect(sock, (struct sockaddr *)&addr, sizeof(addr));
```

### B.4.4 Message framing

Unix domain sockets are byte streams; AAEP messages MUST be framed. The recommended framing is length-prefixed:

```text
[4-byte big-endian length] [JSON bytes]
```

An alternative is newline-delimited JSON (NDJSON):

```text
{"@context":"https://aaep-protocol.org/context/v1","type":"aaep:agent.session.started",...}\n
{"@context":"https://aaep-protocol.org/context/v1","type":"aaep:agent.state.changed",...}\n
```

Implementers MUST pick one framing and use it consistently. The producer manifest SHOULD declare which framing is used.

### B.4.5 Peer credentials

For authentication, the producer uses platform-specific calls to retrieve the connecting process's credentials:

- Linux/BSD: `SO_PEERCRED` socket option, returning UID, GID, PID.
- macOS: `LOCAL_PEERCRED` socket option.

The producer SHOULD verify that the connecting process belongs to the expected user account (typically the same UID as the producer).

## B.5 gRPC

### B.5.1 Service definition

The recommended gRPC service definition uses Protocol Buffers wrapping AAEP JSON:

```protobuf
syntax = "proto3";

package aaep.v1;

service AaepService {
  // Bidirectional streaming: subscriber initiates, producer streams events,
  // subscriber sends reply messages on the same stream.
  rpc Subscribe(stream AaepMessage) returns (stream AaepMessage);

  // Fetch the producer manifest.
  rpc GetManifest(GetManifestRequest) returns (Manifest);
}

message AaepMessage {
  // The AAEP message as JSON. Wrapping JSON in bytes preserves the
  // canonical JSON representation and allows extensions without
  // requiring updates to the .proto file.
  bytes json = 1;

  // Optional: pre-parsed message type for routing.
  string message_type = 2;
}

message GetManifestRequest {}

message Manifest {
  bytes json = 1;
}
```

### B.5.2 Subscription flow

The subscriber opens a bidirectional stream and sends `subscription.request` as the first message. The producer responds with `subscription.accepted` and then streams events. The subscriber sends reply messages on the same stream.

```python
# Pseudocode for a Python gRPC subscriber
async def subscribe():
    request_stream = make_subscription_requests()
    async for message in stub.Subscribe(request_stream):
        event = json.loads(message.json)
        handle_event(event)

async def make_subscription_requests():
    # First message: subscription request
    yield AaepMessage(json=json.dumps({
        "type": "subscription.request",
        "aaep_version": "1.0.0",
        "capabilities": { ... }
    }).encode())

    # Subsequent messages: replies as they're produced
    while True:
        reply = await get_next_reply()
        yield AaepMessage(json=json.dumps(reply).encode())
```

### B.5.3 Authentication

gRPC supports mutual TLS via channel credentials. Implementers SHOULD configure:

- TLS 1.2 or higher.
- Mutual certificate authentication.
- Optional JWT or OAuth tokens via the `Authorization` metadata key.

### B.5.4 Reconnection

gRPC streams have deadlines; the subscriber SHOULD configure long deadlines (hours) for AAEP. On disconnect, the subscriber retries with backoff and re-sends `subscription.request`. The producer SHOULD recognize recent subscriber identities and resume efficiently.

## B.6 stdio JSON-RPC

### B.6.1 Framing

JSON-RPC 2.0 messages are framed by newline, one JSON object per line. Each line MUST be valid UTF-8 JSON terminated by `\n` (LF). Embedded newlines in JSON values are escaped per RFC 8259.

### B.6.2 JSON-RPC envelope

AAEP messages are wrapped in JSON-RPC 2.0 envelopes:

**Notification (event from producer to subscriber):**

```json
{
  "jsonrpc": "2.0",
  "method": "aaep.event",
  "params": {
    "@context": "https://aaep-protocol.org/context/v1",
    "type": "aaep:agent.session.started",
    "event_id": "evt_8a3f5b22",
    "session_id": "sess_2c91a7",
    "timestamp": "2026-05-24T14:22:11.342Z",
    "producer": { "agent_id": "retirement-planner" },
    "summary_normal": "Session started."
  }
}
```

**Request (e.g., subscription.request from subscriber to producer):**

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "aaep.subscribe",
  "params": {
    "type": "subscription.request",
    "aaep_version": "1.0.0",
    "capabilities": { ... }
  }
}
```

**Response (e.g., subscription.accepted):**

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "type": "subscription.accepted",
    "subscription_id": "sub_8a4f2c9d",
    "honored_capabilities": { ... }
  }
}
```

**Reply (confirmation.reply from subscriber):**

```json
{
  "jsonrpc": "2.0",
  "method": "aaep.reply",
  "params": {
    "type": "confirmation.reply",
    "reply_token": "rpl_xyz",
    "decision": "accept",
    "subscription_id": "sub_8a4f2c9d",
    "timestamp": "2026-05-24T14:22:24.812Z"
  }
}
```

### B.6.3 Method namespace

| Method | Direction | Purpose |
|---|---|---|
| `aaep.event` | Producer → Subscriber (notification) | An AAEP event. |
| `aaep.subscribe` | Subscriber → Producer (request) | Subscription request; produces accepted/rejected. |
| `aaep.renegotiate` | Subscriber → Producer (request) | Renegotiation request. |
| `aaep.reply` | Subscriber → Producer (notification) | Confirmation or clarification reply. |
| `aaep.close` | Either → Either (notification) | Subscription close. |
| `aaep.ping` | Either → Either (request) | Liveness check (optional). |

### B.6.4 Process lifecycle

The subscriber typically spawns the producer as a child process:

```python
import subprocess
import json

proc = subprocess.Popen(
    ["./retirement-planner-agent"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True
)

# Send subscription.request
proc.stdin.write(json.dumps({
    "jsonrpc": "2.0",
    "id": 1,
    "method": "aaep.subscribe",
    "params": {
        "type": "subscription.request",
        "aaep_version": "1.0.0",
        "capabilities": { "max_events_per_second": 3, "languages": ["en-US"] }
    }
}) + "\n")
proc.stdin.flush()

# Read responses and events
while True:
    line = proc.stdout.readline()
    if not line:
        break
    msg = json.loads(line)
    if "method" in msg and msg["method"] == "aaep.event":
        handle_event(msg["params"])
    elif "result" in msg:
        handle_response(msg["result"])
```

### B.6.5 Standard error stream

The producer's `stderr` is reserved for human-readable diagnostic output (logs, error messages, debug traces). Subscribers SHOULD NOT parse `stderr` as AAEP messages; it is for operator visibility only.

## B.7 Cross-transport considerations

### B.7.1 Manifest discovery

Regardless of transport, a producer SHOULD publish its manifest at `/.well-known/aaep-manifest.json` for HTTP-based transports, or at a documented filesystem path for local transports. The manifest declares which transports the producer supports, allowing subscribers to choose.

### B.7.2 Transport fallback

If a subscriber's preferred transport fails (e.g., WebSocket blocked by a proxy), the subscriber MAY fall back to an alternative listed in the manifest (e.g., SSE). The fallback is at the subscriber's discretion and does not require renegotiating AAEP capabilities — the subscription handshake re-occurs naturally on the new transport.

### B.7.3 Multi-transport producers

A single producer MAY simultaneously serve subscriptions over multiple transports. Each subscription is independent; the producer maintains separate state per subscription regardless of transport.

## B.8 Reference implementations

Reference implementations of each transport binding are in the AAEP repository:

- SSE: [`examples/producers/python-langchain/`](../../examples/producers/python-langchain/)
- WebSocket: [`examples/subscribers/web-subscriber-react/`](../../examples/subscribers/web-subscriber-react/)
- Windows named pipes: [`examples/subscribers/narrator-bridge-prototype/`](../../examples/subscribers/narrator-bridge-prototype/)
- Unix domain sockets: [`examples/producers/python-minimal/`](../../examples/producers/python-minimal/)
- gRPC: (planned for 1.1.0)
- stdio JSON-RPC: [`examples/bridges/mcp-aaep-bridge/`](../../examples/bridges/mcp-aaep-bridge/)

## B.9 Where to go next

For an alphabetical index of all terms used in the specification, see [Appendix C (Glossary)](C-glossary.md).

For the complete list of normative and informative references, see [Appendix D (References)](D-references.md).
