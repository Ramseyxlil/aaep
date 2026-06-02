# Chapter 3 — Event envelope

*Status: Normative*

---

This chapter specifies the **envelope**: the fixed structure of fields that every AAEP event MUST carry, independent of event type. The envelope is the rigid foundation on which all other events are built. Event-type-specific fields (defined in [Chapter 4](04-core-event-types.md)) and extension fields (defined in [Chapter 7](07-extensions.md)) sit on top of, but never replace, the envelope.

The canonical machine-readable definition is the JSON Schema at [`schemas/envelope.schema.json`](../schemas/envelope.schema.json). This chapter is the canonical human-readable definition. In the event of irresolvable conflict between this chapter and the schema, this chapter takes precedence and the schema MUST be corrected in a subsequent patch release.

## 3.1 Overview

Every AAEP event is a JSON object that conforms to the envelope structure defined in this chapter, extended with event-type-specific fields defined elsewhere in the specification or in published extensions.

The minimal envelope of a valid AAEP event looks like this:

```json
{
  "@context": "https://aaep-protocol.org/context/v1",
  "type": "aaep:agent.session.started",
  "event_id": "evt_8a3f5b22c91e4d7a",
  "session_id": "sess_2c91a7b4d23f1e88",
  "timestamp": "2026-05-24T14:22:11.342Z",
  "producer": {
    "agent_id": "retirement-planner",
    "agent_version": "1.4.2"
  }
}
```

This envelope contains the six **required** envelope fields. The complete envelope, with all optional fields populated, is shown in §3.10.

## 3.2 Required fields

The following fields are required in every AAEP event. A JSON object that omits any required field is **not** a valid AAEP event and MUST NOT be claimed as conforming.

### 3.2.1 `@context`

The `@context` field is a JSON-LD context that identifies the vocabularies used in the event. It MUST be present in every event.

**Type:** string or array of strings

**Required:** Yes

**Format:**

The value MUST be either:

- The string `"https://aaep-protocol.org/context/v1"` (when the event uses only core AAEP vocabulary), OR
- An array of strings whose first element is `"https://aaep-protocol.org/context/v1"` (when the event also references extension vocabularies).

**Examples:**

Minimal context (core only):

```json
{ "@context": "https://aaep-protocol.org/context/v1" }
```

Extended context (core plus an extension):

```json
{
  "@context": [
    "https://aaep-protocol.org/context/v1",
    "https://example.org/medai/context/v1"
  ]
}
```

**Normative requirements:**

- Producers MUST include `@context` in every event.
- The AAEP core context MUST be the first element when `@context` is an array.
- Subscribers MUST verify that `@context` is present and well-formed before processing an event.
- Subscribers MAY use `@context` to determine which extension vocabularies are required to fully interpret the event.

**Rationale (informative):**

JSON-LD's `@context` model is the established standard for extensible JSON vocabularies, used by ActivityStreams 2.0, ActivityPub, Schema.org, W3C Verifiable Credentials, and the broader Linked Data ecosystem. Adopting this model gives AAEP a well-understood extension mechanism without inventing a new pattern.

### 3.2.2 `type`

The `type` field identifies the semantic category of the event. It MUST be present in every event.

**Type:** string (URI or compact prefixed identifier)

**Required:** Yes

**Format:**

The value MUST be one of:

- A compact prefixed identifier of the form `<prefix>:<local-name>`, where the prefix is defined in the `@context` (for example, `aaep:agent.session.started`), OR
- A fully-qualified URI (for example, `https://aaep-protocol.org/types/agent.session.started`).

Implementations MAY choose either form; the two forms are equivalent. Implementations SHOULD use the compact form for readability and bandwidth.

**Allowed local names for the `aaep:` namespace:**

The complete list of core event types is enumerated in [Chapter 4](04-core-event-types.md). Producers MUST NOT emit events with a `type` value in the `aaep:` namespace that is not in this list. Producers MAY emit events with `type` values in their own namespaces (see [Chapter 7](07-extensions.md)).

**Examples:**

```json
{ "type": "aaep:agent.session.started" }
```

```json
{ "type": "aaep:agent.tool.invoked" }
```

```json
{ "type": "https://example.org/medai/agent.patient.consulted" }
```

**Normative requirements:**

- Producers MUST set `type` to one of the values defined in this specification or in a published extension.
- Subscribers MUST treat events with an unknown `type` according to their policy: ignore the event, fall back to a generic announcement, or surface a diagnostic. Subscribers MUST NOT reject the entire subscription due to a single unknown `type`.

### 3.2.3 `event_id`

The `event_id` field is a unique identifier for the event itself.

**Type:** string

**Required:** Yes

**Format:**

The value MUST be a string conforming to the following ABNF grammar:

```abnf
event-id   = "evt_" 1*64( ALPHA / DIGIT )
ALPHA      = %x41-5A / %x61-7A   ; A-Z, a-z
DIGIT      = %x30-39             ; 0-9
```

That is, the literal prefix `evt_` followed by one to sixty-four alphanumeric characters. The recommended generation method is a 128-bit random value rendered as 32 hexadecimal characters (yielding `event_id` strings of length 36).

**Normative requirements:**

- Producers MUST generate a unique `event_id` for each event. Uniqueness is required within the producer's emission stream for at least the lifetime of the producer process; global uniqueness across all AAEP traffic everywhere is RECOMMENDED.
- `event_id` values are case-sensitive.
- Subscribers MAY use `event_id` for deduplication when transport semantics permit duplicate delivery.

**Rationale (informative):**

The `evt_` prefix makes `event_id` values self-identifying in logs and traces. The length range accommodates common identifier generation strategies (UUIDs, ULIDs, KSUIDs) while bounding the field for storage and parsing efficiency.

### 3.2.4 `session_id`

The `session_id` field links the event to its enclosing session.

**Type:** string

**Required:** Yes

**Format:**

The value MUST conform to the following ABNF grammar:

```abnf
session-id = "sess_" 1*64( ALPHA / DIGIT )
```

That is, the literal prefix `sess_` followed by one to sixty-four alphanumeric characters.

**Normative requirements:**

- Every event emitted by a producer between the `agent.session.started` event and the terminal session event (`agent.session.completed`, `agent.session.errored`, or `agent.session.cancelled`) MUST carry the same `session_id`.
- The `session_id` of the `agent.session.started` event itself MUST appear in all subsequent events of the session.
- Across sessions, `session_id` values MUST be unique within a producer.
- Subscribers MAY use `session_id` to correlate events into the originating session for presentation purposes (for example, to group events from a multi-agent collaboration into separate visual or auditory channels).

### 3.2.5 `timestamp`

The `timestamp` field indicates when the producer emitted the event.

**Type:** string

**Required:** Yes

**Format:**

The value MUST be a string conforming to [ISO 8601] / [RFC 3339] with the following constraints:

- The format MUST be `YYYY-MM-DDTHH:MM:SS.sssZ` (date, T separator, time, optional fractional seconds, Z indicating UTC) or `YYYY-MM-DDTHH:MM:SS.sss±HH:MM` (with explicit offset).
- The fractional seconds component is RECOMMENDED at millisecond precision (three digits after the decimal point). Microsecond precision (six digits) is permitted. Other precisions MUST NOT be used.
- The timestamp MUST reference an actual point in time, not a placeholder.

[ISO 8601]: https://www.iso.org/iso-8601-date-and-time-format.html
[RFC 3339]: https://www.rfc-editor.org/rfc/rfc3339

**Examples:**

```json
{ "timestamp": "2026-05-24T14:22:11.342Z" }
```

```json
{ "timestamp": "2026-05-24T15:22:11.342+01:00" }
```

**Normative requirements:**

- Producers MUST set `timestamp` to the moment of event creation, as close to the actual emission time as practical.
- Producers MUST NOT backdate or future-date timestamps.
- Producers MUST use a monotonic clock or otherwise guarantee that successive events within a session have non-decreasing timestamps. Where transports do not guarantee in-order delivery, the timestamp combined with the producer's emission order is normative for reconstructing the original sequence.
- Subscribers MAY use timestamps for ordering, for measuring elapsed time between events, and for filtering events outside a window of interest.

**Rationale (informative):**

RFC 3339 / ISO 8601 with UTC is the de facto standard timestamp format for JSON-based protocols (used by ActivityStreams, OpenAPI, JSON Schema, OAuth, OpenID Connect). Mandating it eliminates a class of cross-implementation bugs that occur when producers and subscribers disagree on date format.

### 3.2.6 `producer`

The `producer` field identifies the entity emitting the event.

**Type:** object

**Required:** Yes

**Structure:**

```json
{
  "producer": {
    "agent_id": "<stable identifier>",
    "agent_version": "<version string>",
    "agent_name": "<human-readable name>",
    "model": "<model identifier>",
    "manifest_uri": "<uri>"
  }
}
```

The `producer` object MUST contain at least the field `agent_id`. The remaining fields are OPTIONAL but RECOMMENDED.

#### 3.2.6.1 `producer.agent_id`

A stable string identifying the producer. MUST be present.

**Type:** string

**Format:** Any non-empty UTF-8 string. The recommended convention is a reverse-DNS-style identifier (`com.example.product.agent-name`) or a short stable slug (`retirement-planner`).

**Normative requirements:**

- `agent_id` MUST be stable across versions of the same producer (do not encode the version in the `agent_id`).
- `agent_id` MUST be unique within the producer's deployment context. Global uniqueness is RECOMMENDED but not required.

#### 3.2.6.2 `producer.agent_version`

The producer's version, typically a semantic version string. OPTIONAL.

**Type:** string

**Format:** Any non-empty UTF-8 string. Semantic versioning (`MAJOR.MINOR.PATCH`) is RECOMMENDED.

#### 3.2.6.3 `producer.agent_name`

A human-readable name for the producer, suitable for announcing to the user. OPTIONAL.

**Type:** string

**Format:** Any non-empty UTF-8 string.

#### 3.2.6.4 `producer.model`

An identifier for the underlying model the agent uses. OPTIONAL.

**Type:** string

**Format:** Any non-empty UTF-8 string. Recommended values are vendor model identifiers such as `"claude-opus-4-7"`, `"gpt-5-turbo"`, `"gemini-2-pro"`, or open-model identifiers such as `"meta-llama/Llama-3-70B-Instruct"`.

#### 3.2.6.5 `producer.manifest_uri`

A URI pointing to the producer's published manifest. OPTIONAL.

**Type:** string (URI)

**Format:** Any RFC 3986 URI. The dereferenced document MUST be a valid producer manifest (see [Chapter 5 §5.6](05-subscription-handshake.md)) if the URI is dereferenceable.

**Examples:**

Minimal `producer`:

```json
{
  "producer": {
    "agent_id": "retirement-planner"
  }
}
```

Recommended `producer`:

```json
{
  "producer": {
    "agent_id": "retirement-planner",
    "agent_version": "1.4.2",
    "agent_name": "Retirement Planning Assistant",
    "model": "claude-opus-4-7"
  }
}
```

Fully populated `producer` with manifest reference:

```json
{
  "producer": {
    "agent_id": "retirement-planner",
    "agent_version": "1.4.2",
    "agent_name": "Retirement Planning Assistant",
    "model": "claude-opus-4-7",
    "manifest_uri": "https://example.com/.well-known/aaep-manifest.json"
  }
}
```

## 3.3 Optional but recommended envelope fields

The following fields are not required but are RECOMMENDED for events that benefit from their inclusion. Producers SHOULD set these fields when the relevant information is known.

### 3.3.1 `verbosity`

The `verbosity` field is a hint indicating the verbosity level of any human-readable strings carried in the event's payload. See §2.2.8 for the normative definitions of verbosity levels.

**Type:** string

**Required:** No (but RECOMMENDED on events with human-readable payload)

**Allowed values:** `"terse"`, `"normal"`, `"detailed"`

**Default:** `"normal"`, if absent

**Example:**

```json
{ "verbosity": "normal" }
```

When a producer wishes to provide multiple verbosity levels for the same event, the producer SHOULD include explicit `summary_terse`, `summary_normal`, and `summary_detailed` fields in the event's payload rather than using `verbosity` at the envelope level. The envelope-level `verbosity` indicates the "default" level the producer recommends; payload fields enable subscribers to render at their preferred level.

### 3.3.2 `urgency`

The `urgency` field indicates the producer's recommended priority for the event. See §2.2.9 for the normative definitions of urgency levels.

**Type:** string

**Required:** No (but RECOMMENDED on all events)

**Allowed values:** `"background"`, `"normal"`, `"critical"`

**Default:** `"normal"`, if absent

**Example:**

```json
{ "urgency": "critical" }
```

**Normative usage by event type (informative cross-reference):**

| Event type | RECOMMENDED urgency |
|---|---|
| `aaep:agent.session.started` | `normal` |
| `aaep:agent.session.completed` | `normal` |
| `aaep:agent.session.errored` | `critical` |
| `aaep:agent.session.cancelled` | `normal` |
| `aaep:agent.state.changed` | `background` or `normal` |
| `aaep:agent.progress.updated` | `background` |
| `aaep:agent.tool.invoked` | `normal` |
| `aaep:agent.tool.completed` | `normal` |
| `aaep:agent.output.streaming` | `normal` |
| `aaep:agent.awaiting.confirmation` | `critical` |
| `aaep:agent.awaiting.clarification` | `critical` |
| `aaep:agent.handoff.requested` | `critical` |

Producers MAY deviate from these recommended urgencies when context warrants, but SHOULD document non-default usage.

### 3.3.3 `localization_hints`

The `localization_hints` field is a structured object describing the language, locale, and text characteristics of any human-readable strings in the event payload. See [Chapter 11](11-internationalization.md) for the full structure and normative requirements.

**Type:** object

**Required:** No (but RECOMMENDED on events with human-readable payload)

**Example:**

```json
{
  "localization_hints": {
    "primary_language": "en-US",
    "text_direction": "ltr",
    "available_languages": ["en-US", "es-419", "yo-NG"]
  }
}
```

## 3.4 Optional envelope fields

The following fields are optional. Producers MAY include them; subscribers MUST gracefully handle their absence and SHOULD make use of them when present.

### 3.4.1 `sequence_number`

A monotonically increasing integer indicating the position of this event within its session.

**Type:** integer (≥ 0)

**Required:** No

**Normative requirements:**

- If present, `sequence_number` MUST be 0 for the `agent.session.started` event and MUST increment by exactly 1 for each subsequent event in the same session.
- Producers MUST either include `sequence_number` on every event of a session or omit it on every event of that session; mixed usage within a single session is non-conforming.
- Subscribers MAY use `sequence_number` to detect missing or out-of-order events, particularly over transports that do not guarantee ordering.

### 3.4.2 `correlation_id`

A string that correlates this event with related events outside of AAEP, such as trace identifiers from observability systems.

**Type:** string

**Required:** No

**Format:** Any UTF-8 string. Recommended formats include W3C Trace Context identifiers, OpenTelemetry trace IDs, or vendor-specific request identifiers.

**Example:**

```json
{ "correlation_id": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01" }
```

### 3.4.3 `extensions`

A namespace-prefixed object carrying extension fields. See [Chapter 7](07-extensions.md) for the extension mechanism.

**Type:** object

**Required:** No

**Format:**

The `extensions` object is keyed by namespace prefix. Each value is an object containing the extension's own fields.

**Example:**

```json
{
  "extensions": {
    "medai": {
      "patient_data_accessed": true,
      "phi_categories": ["medical_history", "medications"]
    },
    "azlearn": {
      "ui_language": "yo-NG",
      "fallback_languages": ["en-US"]
    }
  }
}
```

**Normative requirements:**

- The prefix used in `extensions` keys MUST also appear in the event's `@context`, either directly or via the resolution rules of JSON-LD.
- Subscribers MUST gracefully ignore extension namespaces they do not recognize.
- Subscribers MAY surface unrecognized extensions in a diagnostic mode but MUST NOT reject events solely because they contain unknown extensions.

### 3.4.4 `aaep_version`

A string indicating the version of the AAEP specification that the producer claims to conform to.

**Type:** string

**Required:** No (but RECOMMENDED)

**Format:** Semantic version string of the AAEP specification, for example `"1.0.0"` or `"0.1.0-draft"`.

**Example:**

```json
{ "aaep_version": "1.0.0" }
```

**Normative requirements:**

- If present, `aaep_version` MUST match a published version of this specification.
- Subscribers MAY use `aaep_version` to enable or disable version-specific handling.

## 3.5 Forbidden envelope fields

The following field names are reserved and MUST NOT be used at the envelope level for purposes other than those specified in this chapter or future versions of the AAEP specification:

- Any field name beginning with `aaep_`
- Any field name listed in §3.2, §3.3, or §3.4
- The reserved JSON-LD field names `@id`, `@graph`, `@base`, `@vocab`

Producers MUST place all extension or custom fields inside the `extensions` object (§3.4.3), namespaced appropriately.

## 3.6 Field ordering

The order of fields within a JSON object is not significant under [RFC 8259]. Producers MAY emit envelope fields in any order. Subscribers MUST NOT depend on field order for correctness.

For readability, the RECOMMENDED order is:

1. `@context`
2. `aaep_version` (if present)
3. `type`
4. `event_id`
5. `session_id`
6. `sequence_number` (if present)
7. `timestamp`
8. `producer`
9. `verbosity` (if present)
10. `urgency` (if present)
11. `localization_hints` (if present)
12. `correlation_id` (if present)
13. Event-type-specific payload fields
14. `extensions` (if present)

[RFC 8259]: https://www.rfc-editor.org/rfc/rfc8259

## 3.7 Size and complexity limits

Producers and subscribers SHOULD respect the following soft limits to maintain interoperability. Implementations MAY exceed them but MUST handle gracefully receiving events that exceed them.

| Limit | Value | Notes |
|---|---|---|
| Maximum total event size (serialized JSON) | 64 KiB | Larger events SHOULD use external references (links) rather than embedded data. |
| Maximum number of fields at envelope level | 32 | Includes extension-prefix entries inside `extensions`. |
| Maximum nesting depth of payload | 8 levels | Excludes embedded literal strings. |
| Maximum length of any string field | 16 KiB | Long content SHOULD be split across multiple events or referenced by URI. |
| Maximum number of `available_languages` entries | 32 | Inside `localization_hints`. |

Subscribers MAY drop or truncate events exceeding these limits; they MUST log the reason for the drop in a way the operator can inspect.

## 3.8 Encoding

AAEP events MUST be encoded as UTF-8 JSON conforming to [RFC 8259]. Producers and subscribers MUST NOT use other character encodings or JSON dialects (such as JSON5, HJSON, or JSONC).

JSON whitespace and indentation are insignificant. Producers MAY emit compact or pretty-printed JSON. Subscribers MUST accept both forms.

Numbers MUST conform to JSON's IEEE 754 double-precision floating-point semantics. Integers outside the range `-2^53` to `2^53` MUST be represented as strings to avoid precision loss.

## 3.9 Validation procedure

To determine whether a candidate JSON object is a valid AAEP envelope, an implementation MUST perform the following steps in order:

1. Verify that the value is a JSON object (not a string, number, array, boolean, or null).
2. Verify that all required fields listed in §3.2 are present.
3. Verify that each required field has the correct type and format as specified in §3.2.
4. Verify that the `@context` field references the AAEP core context.
5. Verify that the `type` field references a known event type (either a core type or an extension type whose vocabulary is declared in `@context`).
6. Verify that `event_id`, `session_id`, and `timestamp` conform to their respective formats.
7. Validate the event-type-specific payload against the appropriate schema (see [Chapter 4](04-core-event-types.md) or the relevant extension schema).
8. If `extensions` is present, validate each extension sub-object against its declared schema.
9. Verify that the event does not exceed the size and complexity limits in §3.7 (or, if it does, route to fallback handling).

An implementation that performs all these steps and finds no violations MAY treat the event as valid. An implementation that does NOT perform all these steps MUST NOT claim Level 1 or higher conformance.

The reference implementation of this validation procedure is in the [`conformance/`](../conformance/) test suite.

## 3.10 Complete envelope example

The following example shows a complete `agent.tool.invoked` event with all envelope fields populated, plus event-type-specific payload fields (which are specified in [Chapter 4](04-core-event-types.md)) and an extension.

```json
{
  "@context": [
    "https://aaep-protocol.org/context/v1",
    "https://example.org/medai/context/v1"
  ],
  "aaep_version": "1.0.0",
  "type": "aaep:agent.tool.invoked",
  "event_id": "evt_8a3f5b22c91e4d7a3f5b22c91e4d7a3f",
  "session_id": "sess_2c91a7b4d23f1e88a7b4d23f1e88a7b4",
  "sequence_number": 7,
  "timestamp": "2026-05-24T14:22:11.342Z",
  "producer": {
    "agent_id": "clinical-assistant",
    "agent_version": "2.1.0",
    "agent_name": "Clinical Decision Support Assistant",
    "model": "claude-opus-4-7",
    "manifest_uri": "https://hospital.example/.well-known/aaep-manifest.json"
  },
  "verbosity": "normal",
  "urgency": "normal",
  "localization_hints": {
    "primary_language": "en-US",
    "text_direction": "ltr",
    "available_languages": ["en-US", "es-419"]
  },
  "correlation_id": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
  "tool": "fetch_patient_record",
  "description": "Retrieve patient medical history for clinical review",
  "args_summary": "patient_id: 78921, scope: medications_and_history",
  "risk_level": "medium",
  "irreversible": false,
  "expected_duration_ms": 2000,
  "summary_terse": "Fetching record",
  "summary_normal": "Retrieving Patient 78921's medication history",
  "summary_detailed": "Retrieving complete medication history and clinical notes for Patient 78921 (scope: medications, history) from clinical records system",
  "extensions": {
    "medai": {
      "patient_data_accessed": true,
      "phi_categories": ["medications", "medical_history"],
      "audit_trail_id": "audit_9c4a2b1e7d3f"
    }
  }
}
```

This event is a fully-specified, valid AAEP event. A subscriber implementing Level 2 conformance with knowledge of the `medai` extension can interpret every field. A subscriber implementing Level 1 conformance without `medai` knowledge can still interpret the core fields, will gracefully ignore the `extensions.medai` sub-object, and will produce a useful announcement using `summary_normal`.

## 3.11 Envelope validation example: invalid events

The following examples illustrate invalid envelopes. Producers MUST NOT emit events with these defects; subscribers SHOULD detect and log them as protocol violations.

### 3.11.1 Missing required field

```json
{
  "@context": "https://aaep-protocol.org/context/v1",
  "type": "aaep:agent.session.started",
  "session_id": "sess_2c91a7b4d23f1e88",
  "timestamp": "2026-05-24T14:22:11.342Z",
  "producer": { "agent_id": "test" }
}
```

**Defect:** Missing `event_id`.

### 3.11.2 Malformed timestamp

```json
{
  "@context": "https://aaep-protocol.org/context/v1",
  "type": "aaep:agent.session.started",
  "event_id": "evt_abc123",
  "session_id": "sess_def456",
  "timestamp": "May 24, 2026 14:22:11",
  "producer": { "agent_id": "test" }
}
```

**Defect:** `timestamp` is not in RFC 3339 / ISO 8601 format.

### 3.11.3 Unknown core type

```json
{
  "@context": "https://aaep-protocol.org/context/v1",
  "type": "aaep:agent.purple.flamingo",
  "event_id": "evt_abc123",
  "session_id": "sess_def456",
  "timestamp": "2026-05-24T14:22:11.342Z",
  "producer": { "agent_id": "test" }
}
```

**Defect:** `type` is in the `aaep:` namespace but is not a defined core event type.

### 3.11.4 Extension prefix not declared in `@context`

```json
{
  "@context": "https://aaep-protocol.org/context/v1",
  "type": "aaep:agent.session.started",
  "event_id": "evt_abc123",
  "session_id": "sess_def456",
  "timestamp": "2026-05-24T14:22:11.342Z",
  "producer": { "agent_id": "test" },
  "extensions": {
    "medai": {
      "patient_data_accessed": true
    }
  }
}
```

**Defect:** The `medai` extension prefix is used in `extensions` but the `medai` vocabulary is not declared in `@context`.

### 3.11.5 Forbidden field at envelope level

```json
{
  "@context": "https://aaep-protocol.org/context/v1",
  "type": "aaep:agent.session.started",
  "event_id": "evt_abc123",
  "session_id": "sess_def456",
  "timestamp": "2026-05-24T14:22:11.342Z",
  "producer": { "agent_id": "test" },
  "custom_field": "value"
}
```

**Defect:** Custom envelope-level field `custom_field` is forbidden; extensions must use the `extensions` object.

## 3.12 Where to go next

Readers should now proceed to [Chapter 4 (Core event types)](04-core-event-types.md), which specifies the twelve normative event types and their payloads in detail.

Implementers integrating AAEP into a producer should also consult the [Implementer's Guide](../guides/IMPLEMENTERS_GUIDE.md), which provides framework-specific integration patterns and complete worked examples.
