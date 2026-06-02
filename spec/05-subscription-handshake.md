# Chapter 5 — Subscription handshake

*Status: Normative*

---

This chapter specifies the **subscription handshake**: the protocol by which a subscriber connects to a producer, declares its capabilities, and negotiates the terms under which events will be delivered. The handshake is required at Conformance Level 3 and OPTIONAL at lower levels (where defaults apply).

The handshake exists because subscribers vary enormously. A high-bandwidth web UI can process hundreds of events per second; a refreshable braille display can process roughly one update per second. An English-only screen reader needs events in English; a multilingual braille translator needs language tags. A debugging tool wants every event with maximum verbosity; an end-user screen reader wants terse summaries. A protocol that emits the same stream to all subscribers fails all of them. The handshake lets each subscriber declare what it can handle, lets the producer honor those declarations, and produces a tailored event stream for each subscription without requiring per-subscriber producer code.

The canonical machine-readable definitions are the JSON Schemas in [`schemas/handshake/`](../schemas/handshake/).

## 5.1 Handshake overview

The handshake is a short exchange of two to four messages between subscriber and producer at the start of a subscription:

```text
Subscriber                              Producer
    |                                       |
    |── subscription.request ─────────────► |
    |                                       |── (evaluates capabilities)
    |                                       |
    |◄────────────── subscription.accepted ─|   (or .rejected, or .renegotiate)
    |                                       |
    |── (subscription is active) ──────────►|
    |                                       |
    |◄──────────────────── event.stream ────|   (events flow here)
    |◄──────────────────── event.stream ────|
    |◄──────────────────── event.stream ────|
    |                                       |
    |── confirmation.reply ───────────────► |   (when required by Chapter 6)
    |                                       |
    |── subscription.close ───────────────► |   (or producer-initiated)
    |                                       |
```

Each message in the handshake is a JSON object conforming to its respective schema. The transport for these messages is specified separately in [Chapter 8](08-transports.md); the same handshake message format is used over Server-Sent Events, WebSocket, local IPC, gRPC, and stdio JSON-RPC.

## 5.2 The `subscription.request` message

The subscriber initiates the handshake by sending a `subscription.request` to the producer.

### 5.2.1 Required fields

| Field | Type | Description |
|---|---|---|
| `type` | string | MUST be the literal value `"subscription.request"`. |
| `aaep_version` | string | The AAEP version the subscriber is requesting. |
| `subscriber_id` | string | Stable identifier of the subscriber, like `producer.agent_id` but for the subscriber. |
| `capabilities` | object | The subscriber's capability declaration; see §5.3. |

### 5.2.2 Optional fields

| Field | Type | Description |
|---|---|---|
| `subscriber_name` | string | Human-readable name (e.g., `"Windows Narrator 11.2"`). |
| `subscriber_version` | string | Version of the subscriber software. |
| `subscriber_manifest_uri` | string | URI to the subscriber's published manifest. |
| `correlation_id` | string | Trace identifier for logging. |
| `extensions` | object | Namespaced extension fields. |

### 5.2.3 Example

```json
{
  "type": "subscription.request",
  "aaep_version": "1.0.0",
  "subscriber_id": "windows-narrator",
  "subscriber_name": "Windows Narrator 11.2",
  "subscriber_version": "11.2.5621.0",
  "capabilities": {
    "max_events_per_second": 3,
    "preferred_verbosity": "normal",
    "languages": ["en-US"],
    "supports_confirmation_reply": true,
    "supports_clarification_reply": true,
    "coalesce_boundaries": ["sentence", "completion"],
    "event_filters": {
      "include": ["aaep:agent.*"],
      "exclude": ["aaep:agent.progress.updated"]
    },
    "supported_conformance_levels": [1, 2]
  }
}
```

## 5.3 The capability declaration object

The `capabilities` object describes what the subscriber can handle. The producer uses this object to shape the event stream it will emit on this subscription.

### 5.3.1 Capability fields

The following fields are defined for `capabilities`. Subscribers SHOULD include all fields relevant to their implementation; the empty object `{}` is permitted but produces a stream of default behavior.

#### 5.3.1.1 `max_events_per_second`

**Type:** integer (≥ 1)

**Default if absent:** No rate limit (unlimited).

**Meaning:** The maximum sustained rate at which the subscriber can process incoming events. The producer MUST NOT emit events faster than this rate, except for events with urgency `"critical"`, which are exempt from rate limiting (see §5.5.4).

A typical screen reader subscriber declares `max_events_per_second` of 2 to 5. A debugging or logging subscriber may declare 100 or higher. A refreshable braille display may declare 1.

#### 5.3.1.2 `preferred_verbosity`

**Type:** string

**Allowed values:** `"terse"`, `"normal"`, `"detailed"`

**Default if absent:** `"normal"`

**Meaning:** The subscriber's preferred verbosity level. The producer SHOULD emit events whose `verbosity` envelope field matches this preference, and SHOULD include `summary_*` fields appropriate to this level. Subscribers MAY override on a per-event basis.

#### 5.3.1.3 `languages`

**Type:** array of language tags (RFC 5646)

**Default if absent:** `["en-US"]`

**Meaning:** Languages the subscriber can announce, ordered by preference. The producer SHOULD emit events whose human-readable strings are in one of these languages, using the first matching language available to it. Localization details are specified in [Chapter 11](11-internationalization.md).

#### 5.3.1.4 `supports_confirmation_reply`

**Type:** boolean

**Default if absent:** `false`

**Meaning:** Whether the subscriber can deliver confirmation replies back to the producer. If `false`, the producer MUST NOT emit `agent.awaiting.confirmation` events to this subscription (they would block forever); instead, the producer MUST apply each confirmation's `default_decision` immediately and continue.

Subscribers that claim Conformance Level 2 or higher MUST declare `supports_confirmation_reply: true`.

#### 5.3.1.5 `supports_clarification_reply`

**Type:** boolean

**Default if absent:** `false`

**Meaning:** Whether the subscriber can deliver clarification replies. Same semantics as `supports_confirmation_reply` but for `agent.awaiting.clarification` events.

#### 5.3.1.6 `coalesce_boundaries`

**Type:** array of strings

**Allowed values:** any combination of `"none"`, `"word"`, `"sentence"`, `"paragraph"`, `"completion"`

**Default if absent:** `["sentence", "completion"]`

**Meaning:** The boundaries at which the subscriber wishes streaming output to be coalesced. The producer SHOULD emit `agent.output.streaming` events whose `coalesce_hint` falls in this set. Implementation strategies are discussed in §5.6.

A screen-reader subscriber typically declares `["sentence", "completion"]`. A visual UI showing token-by-token streaming typically declares `["none"]` (no coalescing). A summarization subscriber that only needs final outputs typically declares `["completion"]`.

#### 5.3.1.7 `event_filters`

**Type:** object with `include` and `exclude` arrays of event type patterns

**Default if absent:** `{ "include": ["aaep:agent.*"], "exclude": [] }`

**Meaning:** Patterns of event types the subscriber wishes to receive (`include`) or suppress (`exclude`). Patterns use the literal event type or the wildcard `*` at the end:

- `"aaep:agent.*"` matches all core AAEP events.
- `"aaep:agent.tool.*"` matches all tool-family events.
- `"aaep:agent.session.started"` matches only that exact type.

Exclude patterns take precedence over include patterns. The producer MUST NOT emit events whose type matches an exclude pattern but not an include pattern.

Events of urgency `"critical"` MAY still be emitted regardless of filters; see §5.5.4.

#### 5.3.1.8 `supported_conformance_levels`

**Type:** array of integers (subset of `[1, 2, 3]`)

**Default if absent:** `[1]`

**Meaning:** The conformance levels the subscriber implements. The producer SHOULD operate at the highest level the subscriber supports that the producer can also offer. See [Chapter 9](09-conformance.md).

#### 5.3.1.9 `supported_extensions`

**Type:** array of strings (URIs)

**Default if absent:** `[]`

**Meaning:** Extension vocabulary URIs the subscriber implements. The producer MAY include extension data targeting these vocabularies in events emitted on this subscription. Subscribers MUST gracefully ignore extension data they do not understand even when listed; the field is a hint, not a contract.

#### 5.3.1.10 `cognitive_load`

**Type:** string

**Allowed values:** `"low"`, `"medium"`, `"high"`

**Default if absent:** `"medium"`

**Meaning:** The cognitive load mode the user has configured. The producer SHOULD adapt verbosity and event volume accordingly. `"low"` cognitive load means the user wants minimum announcements and shorter sentences; `"high"` means the user wants comprehensive announcements and full context. This is distinct from `preferred_verbosity` because it affects whether to emit events at all, not just their length.

#### 5.3.1.11 `pace_wpm`

**Type:** integer (≥ 50, ≤ 1000)

**Default if absent:** Subscriber-defined (typically 150-300 for speech, higher for braille).

**Meaning:** The pace at which the subscriber announces content, in words per minute. The producer uses this hint to estimate how long announcements will take and SHOULD coalesce more aggressively for subscribers with lower pace.

#### 5.3.1.12 `accept_signed_manifests_only`

**Type:** boolean

**Default if absent:** `false`

**Meaning:** Whether the subscriber requires the producer's manifest to be cryptographically signed (Level 3 conformance). If `true` and the producer has no signed manifest, the producer MUST reject the subscription with reason `"manifest_signature_required"`.

### 5.3.2 Extension capabilities

Subscribers MAY include extension-specific capability declarations under a namespaced key inside `capabilities`. For example, a haptic subscriber might declare:

```json
{
  "capabilities": {
    "max_events_per_second": 5,
    "preferred_verbosity": "normal",
    "haptic": {
      "patterns_supported": ["pulse", "directional", "intensity_scale"],
      "body_locations": ["wrist", "ankle"]
    }
  }
}
```

The producer evaluates extension capabilities against its own supported extensions. Unknown extension capabilities MUST be ignored (not cause rejection); they remain inert.

## 5.4 The `subscription.accepted` message

The producer responds to a `subscription.request` with `subscription.accepted` when it can serve the subscription on terms compatible with the request.

### 5.4.1 Required fields

| Field | Type | Description |
|---|---|---|
| `type` | string | MUST be `"subscription.accepted"`. |
| `subscription_id` | string | Producer-generated identifier for this subscription. |
| `aaep_version` | string | The version the producer will use. |
| `producer` | object | Producer identity (same structure as the envelope `producer` field). |
| `honored_capabilities` | object | The negotiated capabilities the producer commits to. |

### 5.4.2 Optional fields

| Field | Type | Description |
|---|---|---|
| `manifest_uri` | string | URI to producer's full manifest. |
| `signed_manifest` | string | Inline signed manifest (JWS or equivalent), for Level 3. |
| `negotiation_notes` | string | Human-readable description of any deviations from the request. |

### 5.4.3 Example

```json
{
  "type": "subscription.accepted",
  "subscription_id": "sub_8a4f2c9d1e7b5f3a",
  "aaep_version": "1.0.0",
  "producer": {
    "agent_id": "retirement-planner",
    "agent_version": "1.4.2",
    "agent_name": "Retirement Planning Assistant"
  },
  "honored_capabilities": {
    "max_events_per_second": 3,
    "preferred_verbosity": "normal",
    "languages": ["en-US"],
    "supports_confirmation_reply": true,
    "supports_clarification_reply": true,
    "coalesce_boundaries": ["sentence", "completion"],
    "supported_conformance_levels": [1, 2]
  },
  "manifest_uri": "https://example.com/.well-known/aaep-manifest.json"
}
```

### 5.4.4 Honored vs. requested capabilities

The producer's `honored_capabilities` MUST NOT be more permissive than the subscriber's request:

- `max_events_per_second` in `honored_capabilities` MUST be ≤ the requested value.
- `languages` in `honored_capabilities` MUST be a subset of (or intersection with) the requested set.
- `coalesce_boundaries` in `honored_capabilities` MUST be a subset of (or intersection with) the requested set.
- `event_filters` in `honored_capabilities` MUST be at least as restrictive as the requested filters.

The producer MAY honor less than requested (e.g., honor a 2 events-per-second rate when 3 was requested) but MUST NOT emit events that violate the honored terms after acceptance.

## 5.5 The `subscription.rejected` message

The producer responds with `subscription.rejected` when it cannot serve the subscription.

### 5.5.1 Required fields

| Field | Type | Description |
|---|---|---|
| `type` | string | MUST be `"subscription.rejected"`. |
| `reason_code` | string | Machine-readable reason; see §5.5.3. |
| `reason_message` | string | Human-readable description of the rejection. |

### 5.5.2 Optional fields

| Field | Type | Description |
|---|---|---|
| `retry_after_seconds` | integer | If the subscriber should try again, after how many seconds. |
| `alternative_manifest_uri` | string | URI to a manifest describing what the producer can offer. |

### 5.5.3 Reason codes (normative)

| Code | Meaning |
|---|---|
| `"version_unsupported"` | The producer does not support the requested `aaep_version`. |
| `"manifest_signature_required"` | The subscriber requires a signed manifest the producer does not provide. |
| `"capabilities_incompatible"` | The producer cannot offer any subset of requested capabilities. |
| `"rate_limit"` | The producer has too many active subscriptions to accept another. |
| `"authentication_required"` | Authentication credentials are required and were not provided. |
| `"authorization_denied"` | Credentials provided are not authorized for this subscription. |
| `"transport_unavailable"` | The producer cannot serve this subscriber over the current transport. |
| `"unknown"` | The producer cannot categorize the rejection. |

### 5.5.4 Critical events are exempt from filtering and rate limits

Regardless of the subscriber's declared capabilities, the producer MUST always emit events with urgency `"critical"` to all subscriptions, even if those events would otherwise be filtered or rate-limited. Critical events include `agent.session.errored`, `agent.awaiting.confirmation`, `agent.awaiting.clarification`, and `agent.handoff.requested`.

This rule exists for safety: a subscriber that filters out critical events would silently miss confirmations and errors, causing the protocol's safety contract to fail.

Subscribers MUST be prepared to handle critical events at any time, even when their capabilities suggest they would not receive them.

## 5.6 Backpressure and coalescing

The combination of `max_events_per_second` and `coalesce_boundaries` produces backpressure. This section specifies normative behavior.

### 5.6.1 Producer responsibilities

When emitting events that may be subject to coalescing (primarily `agent.output.streaming`, `agent.progress.updated`, and `agent.state.changed`), the producer MUST:

1. Maintain a per-subscription emission budget tied to `max_events_per_second`. The budget is replenished smoothly over time (token bucket or equivalent), not at fixed intervals.

2. For each event eligible for coalescing, evaluate whether emitting now would exceed the budget. If yes, the producer MUST:
   - For events with `coalesce_hint` matching one of the subscriber's `coalesce_boundaries`: hold the event, accumulate subsequent events into a coalesced summary, and emit at the next legal boundary.
   - For events with `coalesce_hint` not matching any boundary: hold and emit as soon as budget allows.

3. Never delay critical events. Critical events are emitted immediately upon production.

### 5.6.2 Subscriber responsibilities

Subscribers MUST be prepared to receive bursts of events up to the negotiated `max_events_per_second`. Subscribers that cannot sustain their declared rate are non-conforming and SHOULD declare a lower rate.

If a subscriber detects that incoming events are arriving faster than declared, the subscriber MAY:

- Buffer events locally and announce them at the user's pace.
- Drop background-urgency events.
- Send a renegotiation message (see §5.7) requesting a lower rate.

The subscriber MUST NOT drop critical events.

### 5.6.3 Coalescing for streaming output

The `agent.output.streaming` event is the primary case where coalescing matters. The recommended pattern:

- Subscriber declares `coalesce_boundaries: ["sentence", "completion"]`.
- Producer streams LLM tokens internally at the LLM's native rate.
- Producer buffers tokens until a sentence boundary (period, exclamation, question mark followed by whitespace) or completion.
- Producer emits one `agent.output.streaming` event per sentence with `coalesce_hint: "sentence"`, OR a final event with `coalesce_hint: "completion"` and `complete: true`.

This pattern produces approximately one event per second for typical LLM outputs, comfortably within a screen reader's processing rate.

## 5.7 Renegotiation

A subscriber MAY send a `subscription.renegotiate` message at any point during an active subscription to update its capabilities. The producer MUST respond with `subscription.accepted` (with updated `honored_capabilities`) or `subscription.rejected` (terminating the subscription).

### 5.7.1 Renegotiation message

```json
{
  "type": "subscription.renegotiate",
  "subscription_id": "sub_8a4f2c9d1e7b5f3a",
  "capabilities": {
    "max_events_per_second": 1,
    "cognitive_load": "low"
  }
}
```

Only fields included in the renegotiate message are changed; fields omitted retain their prior negotiated values.

### 5.7.2 Renegotiation timing

The producer MUST apply renegotiated capabilities to all events emitted after the `subscription.accepted` response to the renegotiation. Events already in flight at the time of renegotiation MAY arrive under the prior terms; the subscriber MUST handle this gracefully.

## 5.8 Subscription closure

Either party MAY close a subscription at any time. The closing party SHOULD send a `subscription.close` message before disconnecting; the receiving party MUST handle abrupt disconnection without `subscription.close` gracefully.

### 5.8.1 `subscription.close` message

```json
{
  "type": "subscription.close",
  "subscription_id": "sub_8a4f2c9d1e7b5f3a",
  "reason_code": "subscriber_shutdown",
  "reason_message": "Narrator is closing."
}
```

### 5.8.2 Producer behavior on subscription closure

When a subscription closes:

- The producer MUST stop emitting events to that subscription.
- If the producer is in the middle of a session and was awaiting a confirmation reply from the closed subscription, the producer MUST apply the `default_decision` of the pending confirmation as if a timeout had occurred.
- The producer MAY continue serving other subscriptions normally.

## 5.9 Multi-subscriber semantics

A single producer MAY have multiple concurrent subscriptions. Each subscription has independent capability negotiation. The same event may be emitted to multiple subscriptions in different shapes (different `summary_*` fields selected, different languages, different verbosity levels).

The producer MUST treat each subscription independently and MUST NOT degrade one subscription's behavior because of another's.

For confirmations and clarifications, when multiple subscribers can reply: the producer MUST accept the first valid reply with the matching `reply_token` and ignore subsequent replies to the same token. The producer SHOULD send a notification to all other subscriptions indicating the confirmation has been resolved.

## 5.10 The producer manifest

A producer SHOULD publish a manifest describing its capabilities. Manifests are advertisements, not subscriptions: they are static documents subscribers fetch to know what to expect.

### 5.10.1 Manifest structure

```json
{
  "@context": "https://aaep-protocol.org/context/v1",
  "type": "aaep:producer.manifest",
  "agent_id": "retirement-planner",
  "agent_version": "1.4.2",
  "agent_name": "Retirement Planning Assistant",
  "aaep_versions_supported": ["1.0.0"],
  "conformance_levels_supported": [1, 2],
  "transports_supported": ["sse", "websocket", "stdio-jsonrpc"],
  "languages_supported": ["en-US", "es-419", "yo-NG"],
  "event_types_emitted": [
    "aaep:agent.session.*",
    "aaep:agent.state.changed",
    "aaep:agent.tool.*",
    "aaep:agent.output.streaming",
    "aaep:agent.awaiting.confirmation"
  ],
  "extensions_supported": [
    "https://example.org/finance/context/v1"
  ],
  "default_verbosity": "normal",
  "max_concurrent_subscriptions": 16,
  "contact": "accessibility@example.com"
}
```

### 5.10.2 Manifest discovery

Subscribers MAY discover producer manifests by:

- Following the `manifest_uri` returned in a `subscription.accepted` message.
- Fetching `/.well-known/aaep-manifest.json` at the producer's HTTP origin.
- Consulting a directory or registry (out of scope of this specification).

### 5.10.3 Signed manifests (Level 3)

At Conformance Level 3, manifests MAY be signed with JSON Web Signature (JWS). Signed manifests give subscribers cryptographic proof of producer identity. The signing key and verification procedure are specified in [Chapter 10 (Security)](10-security.md).

## 5.11 Example: complete subscription lifecycle

The following non-normative example shows a complete subscription lifecycle.

```text
Time   Direction   Message
─────  ──────────  ────────────────────────────────────────────────
14:22:10  S → P    subscription.request (Narrator, max 3 eps, English, level 2)
14:22:10  P → S    subscription.accepted (sub_1234, honored as requested)
14:22:11  P → S    agent.session.started
14:22:11  P → S    agent.state.changed (idle → thinking)
14:22:14  P → S    agent.tool.invoked (fetch_balance)
14:22:16  P → S    agent.tool.completed (success)
14:22:20  P → S    agent.awaiting.confirmation (transfer $500, reply_token=rpl_xyz)
14:22:25  S → P    confirmation.reply (decision: accept, reply_token=rpl_xyz)
14:22:26  P → S    agent.tool.invoked (transfer_funds)
14:22:28  P → S    agent.tool.completed (success)
14:22:30  P → S    agent.output.streaming (chunk, coalesce: sentence)
14:22:33  P → S    agent.output.streaming (chunk, complete=true, coalesce: completion)
14:22:34  P → S    agent.session.completed
14:22:35  S → P    subscription.close (subscriber_shutdown)
                   (transport disconnects)
```

This trace represents a single session within one subscription. The same producer could simultaneously serve another subscription with different capabilities, receiving events tailored to that subscriber's terms.

## 5.12 Where to go next

Readers should now proceed to [Chapter 6 (Confirmation protocol)](06-confirmation-protocol.md), which specifies the blocking flow for confirmations and clarifications and the format of reply messages.

Implementers building subscribers should refer to this chapter and Chapter 6 together, since the handshake and the confirmation protocol jointly govern the interactive Level 2 contract.
