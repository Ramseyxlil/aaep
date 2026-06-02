# Chapter 4 — Core event types

*Status: Normative*

---

This chapter defines the **twelve core event types** of AAEP. Each type is specified with its purpose, required payload fields, optional payload fields, sequencing rules, semantic constraints, complete examples, and normative requirements.

This is the longest and most frequently-referenced chapter of the specification. Implementers SHOULD treat this chapter as the canonical reference when integrating AAEP into a producer or subscriber.

The twelve core types are grouped into four families:

| Family | Event types | Purpose |
|---|---|---|
| **Lifecycle** | `agent.session.started`, `agent.session.completed`, `agent.session.errored`, `agent.session.cancelled` | Bound the beginning and end of an agent session. |
| **Reasoning state** | `agent.state.changed`, `agent.progress.updated` | Communicate the producer's internal state transitions. |
| **Tool and action** | `agent.tool.invoked`, `agent.tool.completed`, `agent.output.streaming` | Announce side-effecting operations and user-visible output. |
| **Human-in-the-loop** | `agent.awaiting.confirmation`, `agent.awaiting.clarification`, `agent.handoff.requested` | Pause the producer pending human input or escalation. |

Every event in this chapter MUST also carry the envelope fields defined in [Chapter 3](03-event-envelope.md). For brevity, examples in this chapter sometimes omit envelope fields; implementers MUST include them in actual emitted events.

Canonical JSON Schemas for each event type are in [`schemas/core/`](../schemas/core/). The schema filename for an event of type `aaep:agent.session.started` is `agent.session.started.schema.json`, and so on.

---

## 4.1 Lifecycle family

Lifecycle events bound the beginning and end of an agent session. Every session MUST begin with exactly one `agent.session.started` event and MUST end with exactly one of `agent.session.completed`, `agent.session.errored`, or `agent.session.cancelled`. Lifecycle events are required at Conformance Level 1 and above.

### 4.1.1 `aaep:agent.session.started`

**Purpose:** Announces the beginning of an agent session. This is the first event of every session and the anchor for the session's `session_id`.

**Required payload fields:**

| Field | Type | Description |
|---|---|---|
| `summary_normal` | string | Human-readable description of what the session will do at normal verbosity. |

**Optional payload fields:**

| Field | Type | Description |
|---|---|---|
| `summary_terse` | string | Shorter form of `summary_normal` for terse verbosity. |
| `summary_detailed` | string | Longer form with more context, for detailed verbosity. |
| `expected_duration_ms` | integer | Producer's estimate of total session duration in milliseconds. |
| `requested_by` | string | Identifier of the user, system, or process that initiated the session. |
| `request_text` | string | The original natural-language request from the user, if available. |
| `tools_available` | array of strings | List of tool names the agent has access to in this session. |

**Sequencing rules:**

- MUST be the first event of a session.
- A producer MUST NOT emit any event with this `session_id` before the `agent.session.started` event for that session.
- A producer MUST emit exactly one `agent.session.started` per session.

**Example:**

```json
{
  "@context": "https://aaep-protocol.org/context/v1",
  "type": "aaep:agent.session.started",
  "event_id": "evt_8a3f5b22c91e4d7a",
  "session_id": "sess_2c91a7b4d23f1e88",
  "timestamp": "2026-05-24T14:22:11.342Z",
  "producer": {
    "agent_id": "retirement-planner",
    "agent_version": "1.4.2",
    "agent_name": "Retirement Planning Assistant"
  },
  "urgency": "normal",
  "summary_terse": "Started.",
  "summary_normal": "Retirement Planning Assistant is processing your request.",
  "summary_detailed": "Retirement Planning Assistant is processing your request to plan retirement savings strategy. Estimated 30 seconds. The assistant will read your financial profile, calculate projections, and draft a recommendation.",
  "expected_duration_ms": 30000,
  "requested_by": "user:folake",
  "request_text": "Plan my retirement savings strategy.",
  "tools_available": ["fetch_balance", "calculate_projection", "draft_plan"]
}
```

**Subscriber behavior:**

- Subscribers SHOULD announce the start of the session using the verbosity level the user has configured.
- Subscribers MAY use `expected_duration_ms` to set up progress UI or to advise the user of expected wait time.

---

### 4.1.2 `aaep:agent.session.completed`

**Purpose:** Announces successful completion of an agent session.

**Required payload fields:**

| Field | Type | Description |
|---|---|---|
| `summary_normal` | string | Human-readable description of what the session accomplished. |

**Optional payload fields:**

| Field | Type | Description |
|---|---|---|
| `summary_terse` | string | Shorter form for terse verbosity. |
| `summary_detailed` | string | Longer form with more context. |
| `duration_ms` | integer | Actual session duration in milliseconds. |
| `tool_invocations_count` | integer | Number of tools the agent invoked during this session. |
| `output_summary` | string | Brief summary of the final output produced. |
| `result_uri` | string | URI to a richer representation of the result, if applicable. |

**Sequencing rules:**

- MUST be the last event of a session if the session completed successfully.
- MUST NOT be emitted if any of `agent.session.errored` or `agent.session.cancelled` has been emitted for the same session.
- A producer MUST emit exactly one terminal lifecycle event per session.

**Example:**

```json
{
  "@context": "https://aaep-protocol.org/context/v1",
  "type": "aaep:agent.session.completed",
  "event_id": "evt_4f7d9c12ab8e3f5a",
  "session_id": "sess_2c91a7b4d23f1e88",
  "timestamp": "2026-05-24T14:22:38.921Z",
  "producer": {
    "agent_id": "retirement-planner",
    "agent_version": "1.4.2"
  },
  "urgency": "normal",
  "summary_terse": "Done.",
  "summary_normal": "Retirement plan complete. Ready to review.",
  "summary_detailed": "Retirement plan generation complete in 27 seconds. Plan covers projected savings, recommended monthly contributions, and tax-advantaged account allocations for the next 30 years.",
  "duration_ms": 27579,
  "tool_invocations_count": 4,
  "output_summary": "Generated a 5-section retirement plan with projections and recommendations."
}
```

**Subscriber behavior:**

- Subscribers SHOULD announce successful completion with appropriate finality (for example, a short audio cue or a clear verbal "Done").
- Subscribers SHOULD release any UI elements that were waiting for the session to complete (progress indicators, busy states).

---

### 4.1.3 `aaep:agent.session.errored`

**Purpose:** Announces that the session ended due to an error.

**Required payload fields:**

| Field | Type | Description |
|---|---|---|
| `error_category` | string | One of: `"transient"`, `"permanent"`, `"requires_user"`, `"unknown"`. |
| `summary_normal` | string | Human-readable description of the error. |

**Optional payload fields:**

| Field | Type | Description |
|---|---|---|
| `summary_terse` | string | Shorter form. |
| `summary_detailed` | string | Longer form with technical context. |
| `error_code` | string | Producer-defined short error code (e.g., `"AUTH_FAILED"`, `"TOOL_TIMEOUT"`). |
| `error_uri` | string | URI to documentation or remediation guidance for this error. |
| `recoverable` | boolean | Whether the session could plausibly succeed if retried. |
| `remediation_hint` | string | Plain-language suggestion of how the user might address the issue. |

**Error categories (normative):**

| Category | Meaning |
|---|---|
| `"transient"` | A temporary failure (network timeout, rate limit, temporary unavailability). Retry is likely to succeed. |
| `"permanent"` | A failure that retry will not resolve (invalid configuration, missing permissions, deprecated tool). |
| `"requires_user"` | The session cannot continue without user action (re-authenticate, grant permission, clarify intent). |
| `"unknown"` | The producer cannot categorize the error. |

**Sequencing rules:**

- MUST be the last event of a session if the session ended in error.
- MUST be emitted with urgency `"critical"`.

**Example:**

```json
{
  "@context": "https://aaep-protocol.org/context/v1",
  "type": "aaep:agent.session.errored",
  "event_id": "evt_3a8f9b21c5e7d4f2",
  "session_id": "sess_2c91a7b4d23f1e88",
  "timestamp": "2026-05-24T14:22:25.115Z",
  "producer": {
    "agent_id": "retirement-planner",
    "agent_version": "1.4.2"
  },
  "urgency": "critical",
  "error_category": "transient",
  "error_code": "TOOL_TIMEOUT",
  "summary_terse": "Tool timed out.",
  "summary_normal": "The financial data service did not respond in time. Please try again.",
  "summary_detailed": "The fetch_balance tool timed out after 10 seconds connecting to the financial data service. This is usually a temporary issue.",
  "recoverable": true,
  "remediation_hint": "Try the request again in a few moments."
}
```

**Subscriber behavior:**

- Subscribers MUST announce errored sessions promptly and with appropriate urgency.
- Subscribers SHOULD include the `remediation_hint` in the announcement when present.
- Subscribers MUST NOT suppress errored events even under aggressive backpressure (these events have urgency `"critical"`).

---

### 4.1.4 `aaep:agent.session.cancelled`

**Purpose:** Announces that the session was cancelled before completion, either by the user, by the producer itself, or by a controlling system.

**Required payload fields:**

| Field | Type | Description |
|---|---|---|
| `cancelled_by` | string | One of: `"user"`, `"producer"`, `"timeout"`, `"system"`. |
| `summary_normal` | string | Human-readable description of why the cancellation occurred. |

**Optional payload fields:**

| Field | Type | Description |
|---|---|---|
| `summary_terse` | string | Shorter form. |
| `summary_detailed` | string | Longer form. |
| `cancellation_reason` | string | Producer-specific reason code (e.g., `"user_pressed_escape"`, `"timeout_exceeded"`). |
| `partial_result` | string | Brief description of any partial work produced before cancellation. |

**Sequencing rules:**

- MUST be the last event of a session if the session was cancelled.
- MAY be triggered by a transport-level cancellation signal or a user action propagated through the subscriber.

**Example:**

```json
{
  "@context": "https://aaep-protocol.org/context/v1",
  "type": "aaep:agent.session.cancelled",
  "event_id": "evt_6c2e8a1f4d7b3a9c",
  "session_id": "sess_2c91a7b4d23f1e88",
  "timestamp": "2026-05-24T14:22:18.450Z",
  "producer": {
    "agent_id": "retirement-planner",
    "agent_version": "1.4.2"
  },
  "urgency": "normal",
  "cancelled_by": "user",
  "cancellation_reason": "user_pressed_escape",
  "summary_terse": "Cancelled.",
  "summary_normal": "Retirement plan generation cancelled at your request.",
  "partial_result": "Initial projection was drafted but no recommendations were generated."
}
```

---

## 4.2 Reasoning state family

Reasoning state events describe the producer's internal state and progress through a session. They are essential for accessibility because the producer's internal state is invisible to users who cannot see visual indicators.

### 4.2.1 `aaep:agent.state.changed`

**Purpose:** Announces that the producer has transitioned from one internal state to another.

**Required payload fields:**

| Field | Type | Description |
|---|---|---|
| `from_state` | string | The state being exited. |
| `to_state` | string | The state being entered. |

**Optional payload fields:**

| Field | Type | Description |
|---|---|---|
| `summary_terse` | string | Brief description of the new state. |
| `summary_normal` | string | Standard description. |
| `summary_detailed` | string | Detailed description with rationale for the transition. |
| `expected_duration_ms` | integer | How long the new state is expected to last. |

**Standard state values (informative):**

The following state strings are recommended for interoperability:

| State | Description |
|---|---|
| `"idle"` | Producer is not actively working. |
| `"thinking"` | Producer is consuming compute on reasoning (LLM call, internal planning). |
| `"calling_tool"` | Producer is invoking an external tool. |
| `"writing_output"` | Producer is generating user-facing output. |
| `"awaiting_input"` | Producer is blocked awaiting user input (confirmation or clarification). |
| `"deciding"` | Producer is selecting next action between tool calls. |
| `"handing_off"` | Producer is preparing to hand off to another agent or human. |

Producers MAY use other state strings as long as they are consistently meaningful. Subscribers MUST NOT reject events with unrecognized state strings; they SHOULD fall back to generic announcements.

**Sequencing rules:**

- The first `agent.state.changed` event in a session MUST have `from_state` of `"idle"`.
- Subsequent `agent.state.changed` events MUST have `from_state` matching the `to_state` of the prior `agent.state.changed` event (or be consistent with the implicit state derived from other emitted events).

**Example:**

```json
{
  "@context": "https://aaep-protocol.org/context/v1",
  "type": "aaep:agent.state.changed",
  "event_id": "evt_7d2a8c1f5e3b6a9d",
  "session_id": "sess_2c91a7b4d23f1e88",
  "timestamp": "2026-05-24T14:22:13.108Z",
  "producer": {
    "agent_id": "retirement-planner",
    "agent_version": "1.4.2"
  },
  "urgency": "background",
  "from_state": "idle",
  "to_state": "thinking",
  "summary_terse": "Thinking.",
  "summary_normal": "Analyzing your retirement planning question.",
  "expected_duration_ms": 4000
}
```

**Subscriber behavior:**

- Subscribers SHOULD announce state changes at the user's preferred verbosity.
- Subscribers MAY suppress state changes that are deemed redundant under user-configured filters (for example, suppress `idle → thinking → deciding → thinking` cycles that are too short to be informative).
- Subscribers MUST NOT permanently silence all `agent.state.changed` events; the user retains the right to receive them.

---

### 4.2.2 `aaep:agent.progress.updated`

**Purpose:** Reports incremental progress through a long-running task. Use sparingly to avoid event flood.

**Required payload fields:**

| Field | Type | Description |
|---|---|---|
| `progress` | object | Progress information; see below. |

The `progress` object MUST contain at least one of:

| Field | Type | Description |
|---|---|---|
| `percent` | number (0-100) | Completion percentage. |
| `step` | integer | Current step number. |
| `total_steps` | integer | Total number of steps, if known. |
| `description` | string | Brief description of the current step. |

**Optional payload fields (on the top-level event):**

| Field | Type | Description |
|---|---|---|
| `summary_terse` | string | Terse progress announcement. |
| `summary_normal` | string | Normal progress announcement. |
| `eta_ms` | integer | Estimated milliseconds to completion. |

**Sequencing rules:**

- MUST NOT be emitted at a rate exceeding what the subscription handshake's negotiated rate permits.
- Producers SHOULD coalesce rapid successive progress updates into less frequent emissions (e.g., emit every 5% rather than every 1%).
- Subscribers MAY suppress progress events entirely if the user has configured low cognitive load mode.

**Example:**

```json
{
  "@context": "https://aaep-protocol.org/context/v1",
  "type": "aaep:agent.progress.updated",
  "event_id": "evt_2e6c9a3f1d8b4e7a",
  "session_id": "sess_2c91a7b4d23f1e88",
  "timestamp": "2026-05-24T14:22:18.701Z",
  "producer": {
    "agent_id": "retirement-planner",
    "agent_version": "1.4.2"
  },
  "urgency": "background",
  "progress": {
    "percent": 60,
    "step": 3,
    "total_steps": 5,
    "description": "Calculating retirement projections"
  },
  "summary_terse": "60 percent.",
  "summary_normal": "Calculating retirement projections, 60 percent complete.",
  "eta_ms": 12000
}
```

---

## 4.3 Tool and action family

Tool and action events make agent side-effects audible. Without these events, users cannot know what an agent is doing on their behalf.

### 4.3.1 `aaep:agent.tool.invoked`

**Purpose:** Announces that the producer is about to invoke a tool. MUST be emitted before the tool's side-effecting operation begins.

**Required payload fields:**

| Field | Type | Description |
|---|---|---|
| `tool` | string | The tool's identifier (typically its function name). |
| `summary_normal` | string | Human-readable description of what the producer is doing. |

**Optional payload fields:**

| Field | Type | Description |
|---|---|---|
| `summary_terse` | string | Shorter form. |
| `summary_detailed` | string | Longer form with argument context. |
| `description` | string | The tool's static description. |
| `args_summary` | string | Summarized arguments suitable for announcement. |
| `expected_duration_ms` | integer | How long the producer expects the tool to take. |
| `risk_level` | string | One of `"low"`, `"medium"`, `"high"`. Default `"low"`. |
| `irreversible` | boolean | Whether the action is irreversible. Default `false`. |
| `tool_call_id` | string | Identifier correlating with the matching `agent.tool.completed`. |

**Normative requirements:**

- `aaep:agent.tool.invoked` MUST be emitted BEFORE the tool's side-effect occurs, not after.
- If `irreversible` is `true`, the producer MUST have first emitted an `aaep:agent.awaiting.confirmation` event for this tool invocation and received an accept reply. Emitting `tool.invoked` with `irreversible: true` without prior confirmation is a protocol violation.
- `tool_call_id`, when present, MUST be unique within the session and MUST match the `tool_call_id` of the subsequent `agent.tool.completed` event.
- Producers MUST NOT include sensitive secrets in `args_summary` (API keys, passwords, PII beyond what the user already supplied).

**Example:**

```json
{
  "@context": "https://aaep-protocol.org/context/v1",
  "type": "aaep:agent.tool.invoked",
  "event_id": "evt_9f3c2a8b5d1e7f4a",
  "session_id": "sess_2c91a7b4d23f1e88",
  "timestamp": "2026-05-24T14:22:14.527Z",
  "producer": {
    "agent_id": "retirement-planner",
    "agent_version": "1.4.2"
  },
  "urgency": "normal",
  "tool": "fetch_balance",
  "tool_call_id": "call_7a2b9c4e",
  "description": "Retrieve account balance from financial data service",
  "args_summary": "account_id: checking-7821",
  "summary_terse": "Checking balance.",
  "summary_normal": "Retrieving your checking account balance.",
  "expected_duration_ms": 2000,
  "risk_level": "low",
  "irreversible": false
}
```

---

### 4.3.2 `aaep:agent.tool.completed`

**Purpose:** Announces that a previously-invoked tool has returned (successfully or with an error).

**Required payload fields:**

| Field | Type | Description |
|---|---|---|
| `tool` | string | The tool that completed. MUST match the prior `agent.tool.invoked`. |
| `status` | string | One of `"success"`, `"error"`, `"timeout"`. |

**Optional payload fields:**

| Field | Type | Description |
|---|---|---|
| `summary_terse` | string | Terse description of the result. |
| `summary_normal` | string | Normal description of the result. |
| `summary_detailed` | string | Detailed description, possibly including key result values. |
| `tool_call_id` | string | Correlator matching `agent.tool.invoked`. |
| `duration_ms` | integer | Actual elapsed time of the tool call. |
| `error_message` | string | Brief error description if `status` is `"error"` or `"timeout"`. |

**Normative requirements:**

- MUST be emitted after the matching `agent.tool.invoked` and before any subsequent `agent.state.changed` that reflects the post-tool state.
- If a tool fails to return at all and is abandoned, the producer MUST emit `agent.tool.completed` with `status: "timeout"` rather than silently moving on.
- Subscribers MAY use `duration_ms` to detect tools that consistently take longer than `expected_duration_ms` and surface this to the user.

**Example:**

```json
{
  "@context": "https://aaep-protocol.org/context/v1",
  "type": "aaep:agent.tool.completed",
  "event_id": "evt_1b7a4f2c9e3d6a8f",
  "session_id": "sess_2c91a7b4d23f1e88",
  "timestamp": "2026-05-24T14:22:16.412Z",
  "producer": {
    "agent_id": "retirement-planner",
    "agent_version": "1.4.2"
  },
  "urgency": "normal",
  "tool": "fetch_balance",
  "tool_call_id": "call_7a2b9c4e",
  "status": "success",
  "duration_ms": 1885,
  "summary_terse": "Got balance.",
  "summary_normal": "Balance: $12,500.00.",
  "summary_detailed": "Retrieved checking account balance of $12,500.00 as of 2026-05-24 14:22:16."
}
```

---

### 4.3.3 `aaep:agent.output.streaming`

**Purpose:** Carries a chunk of user-facing output produced by the agent. This is the most-emitted event type and the one most subject to backpressure rules.

**Required payload fields:**

| Field | Type | Description |
|---|---|---|
| `chunk` | string | The current chunk of output content. |
| `position` | integer | Zero-based character offset within the session's total output. |
| `complete` | boolean | `true` if this is the final chunk of this output; `false` otherwise. |

**Optional payload fields:**

| Field | Type | Description |
|---|---|---|
| `coalesce_hint` | string | One of `"none"`, `"word"`, `"sentence"`, `"paragraph"`, `"completion"`. Tells subscribers when this chunk should be announced. |
| `output_id` | string | Identifier grouping chunks of the same logical output (useful for multiple outputs within one session). |
| `content_type` | string | MIME type of the chunk content. Default `"text/plain"`. |
| `language` | string | Language code (e.g., `"en-US"`) overriding `localization_hints` for this chunk. |

**Normative requirements:**

- `position` MUST be the total character offset since the start of the current `output_id` (or the start of the session if no `output_id` is provided).
- The final chunk of an output MUST have `complete: true`.
- Producers MUST honor the subscriber's negotiated coalescing preference: if the subscriber requested `"sentence"` coalescing, the producer MAY batch tokens internally and emit one event per sentence boundary, OR it MAY emit at the token level and rely on the subscriber to coalesce. Either is conforming.
- Subscribers MUST NOT announce events with `coalesce_hint: "none"` directly; they MUST wait for the next event with a more meaningful boundary or buffer until completion.

**Example (mid-stream, sentence-coalesced):**

```json
{
  "@context": "https://aaep-protocol.org/context/v1",
  "type": "aaep:agent.output.streaming",
  "event_id": "evt_5d9c2a7f1b4e8a3c",
  "session_id": "sess_2c91a7b4d23f1e88",
  "timestamp": "2026-05-24T14:22:23.140Z",
  "producer": {
    "agent_id": "retirement-planner",
    "agent_version": "1.4.2"
  },
  "urgency": "normal",
  "chunk": "Your retirement plan should target a monthly contribution of $1,200 to maximize your tax-advantaged accounts.",
  "position": 348,
  "complete": false,
  "coalesce_hint": "sentence",
  "output_id": "out_3a8c2",
  "content_type": "text/plain"
}
```

**Example (final chunk):**

```json
{
  "@context": "https://aaep-protocol.org/context/v1",
  "type": "aaep:agent.output.streaming",
  "event_id": "evt_8a4f2c9d1e7b5f3a",
  "session_id": "sess_2c91a7b4d23f1e88",
  "timestamp": "2026-05-24T14:22:25.812Z",
  "producer": {
    "agent_id": "retirement-planner",
    "agent_version": "1.4.2"
  },
  "urgency": "normal",
  "chunk": "Please review and let me know if you would like adjustments.",
  "position": 587,
  "complete": true,
  "coalesce_hint": "completion",
  "output_id": "out_3a8c2",
  "content_type": "text/plain"
}
```

---

## 4.4 Human-in-the-loop family

Human-in-the-loop events pause the producer pending input from the user or escalation to another agent or human. These events are critical for safety and for accessibility, because they ensure irreversible actions cannot occur without user awareness.

### 4.4.1 `aaep:agent.awaiting.confirmation`

**Purpose:** Pauses the producer pending explicit user consent for a specific action. MUST be emitted before any irreversible action.

**Required payload fields:**

| Field | Type | Description |
|---|---|---|
| `action` | string | Human-readable description of the action awaiting confirmation. |
| `consequence` | string | Human-readable description of what happens if the action proceeds. |
| `reply_token` | string | Opaque token identifying this confirmation; subscriber MUST include in reply. |
| `timeout_seconds` | integer | Seconds after which the producer applies the default decision. |
| `default_decision` | string | One of `"accept"`, `"reject"`. Applied if no reply arrives before timeout. |

**Optional payload fields:**

| Field | Type | Description |
|---|---|---|
| `summary_terse` | string | Short form for terse verbosity. |
| `summary_normal` | string | Standard form (equivalent to `action` + `consequence`). |
| `summary_detailed` | string | Detailed form, e.g., listing affected resources. |
| `risk_level` | string | `"low"`, `"medium"`, `"high"`. Influences urgency. |
| `reversibility` | string | `"reversible"`, `"reversible_with_effort"`, `"irreversible"`. |
| `allowed_replies` | array of strings | Allowed reply decisions. Default `["accept", "reject"]`. |
| `extra_context` | object | Additional structured context the subscriber may surface. |

**Normative requirements:**

- The producer MUST block its own progress (i.e., MUST NOT proceed with the action being confirmed) until a valid reply is received or `timeout_seconds` elapses.
- `reply_token` MUST be opaque to the subscriber. Subscribers MUST NOT parse, interpret, or modify reply tokens.
- `default_decision` for irreversible high-risk actions MUST be `"reject"`. Setting `default_decision: "accept"` for an irreversible high-risk action is a protocol violation.
- This event MUST be emitted with urgency `"critical"`.
- The reply mechanism is specified in [Chapter 6 (Confirmation protocol)](06-confirmation-protocol.md).

**Example:**

```json
{
  "@context": "https://aaep-protocol.org/context/v1",
  "type": "aaep:agent.awaiting.confirmation",
  "event_id": "evt_b7c4e9a2f5d1a8c3",
  "session_id": "sess_2c91a7b4d23f1e88",
  "timestamp": "2026-05-24T14:22:20.014Z",
  "producer": {
    "agent_id": "retirement-planner",
    "agent_version": "1.4.2"
  },
  "urgency": "critical",
  "action": "Transfer $500.00 from checking-7821 to savings-3344.",
  "consequence": "Funds move immediately. Reversal requires bank intervention and takes 3 to 5 business days.",
  "reply_token": "rpl_4f8a2e7d9c1b6a3f",
  "timeout_seconds": 300,
  "default_decision": "reject",
  "summary_terse": "Confirm transfer?",
  "summary_normal": "Confirmation required. Transfer $500 from checking to savings. Cannot be easily reversed.",
  "risk_level": "high",
  "reversibility": "reversible_with_effort"
}
```

**Subscriber behavior:**

- Subscribers MUST announce confirmation events with high prominence and provide a clear input method for the user to reply.
- Subscribers MUST NOT auto-respond on the user's behalf except as explicitly configured by the user.
- The reply message format is specified in [Chapter 6](06-confirmation-protocol.md).

---

### 4.4.2 `aaep:agent.awaiting.clarification`

**Purpose:** Pauses the producer pending free-form clarification from the user.

**Required payload fields:**

| Field | Type | Description |
|---|---|---|
| `question` | string | The clarification question. |
| `reply_token` | string | Opaque token for the reply. |
| `timeout_seconds` | integer | Seconds after which the producer treats clarification as unavailable. |

**Optional payload fields:**

| Field | Type | Description |
|---|---|---|
| `summary_terse` | string | Brief form. |
| `summary_normal` | string | Standard form. |
| `accepted_response_kinds` | array of strings | One or more of `"freetext"`, `"yes_no"`, `"multiple_choice"`, `"numeric"`. |
| `choices` | array of objects | For multiple-choice: list of `{ value, label }` options. |
| `context` | string | Why the producer needs this clarification. |
| `default_response` | string | Producer's fallback if no clarification arrives in time. |

**Sequencing rules:**

- MUST block the producer's progress until a reply arrives or timeout expires.
- MUST be emitted with urgency `"critical"`.

**Example:**

```json
{
  "@context": "https://aaep-protocol.org/context/v1",
  "type": "aaep:agent.awaiting.clarification",
  "event_id": "evt_a3c9f2e7b1d8a4c6",
  "session_id": "sess_2c91a7b4d23f1e88",
  "timestamp": "2026-05-24T14:22:12.890Z",
  "producer": {
    "agent_id": "retirement-planner",
    "agent_version": "1.4.2"
  },
  "urgency": "critical",
  "question": "Which retirement age should I plan for?",
  "reply_token": "rpl_2c8e4a9f7b1d3a6e",
  "timeout_seconds": 300,
  "accepted_response_kinds": ["multiple_choice", "numeric"],
  "choices": [
    { "value": "60", "label": "Age 60" },
    { "value": "65", "label": "Age 65 (standard)" },
    { "value": "67", "label": "Age 67 (full Social Security)" },
    { "value": "70", "label": "Age 70 (maximum benefits)" }
  ],
  "context": "Different retirement ages substantially change required savings.",
  "default_response": "65",
  "summary_normal": "Which retirement age should I plan for?"
}
```

---

### 4.4.3 `aaep:agent.handoff.requested`

**Purpose:** Indicates that the producer is unable to complete the session and is requesting handoff to a human or another agent.

**Required payload fields:**

| Field | Type | Description |
|---|---|---|
| `reason` | string | Why the handoff is being requested. |
| `target_kind` | string | One of `"human"`, `"specialist_agent"`, `"escalation_queue"`. |

**Optional payload fields:**

| Field | Type | Description |
|---|---|---|
| `summary_terse` | string | Brief form. |
| `summary_normal` | string | Standard form. |
| `target_uri` | string | URI identifying the specific handoff destination. |
| `packaged_context` | object | Structured summary of the session for the handoff target. |
| `urgency_for_handoff` | string | `"low"`, `"medium"`, `"high"` (separate from the event's transport urgency). |

**Sequencing rules:**

- Typically appears near the end of a session; the producer often follows up with `agent.session.completed` or `agent.session.cancelled` once the handoff is acknowledged.
- MUST be emitted with urgency `"critical"`.

**Example:**

```json
{
  "@context": "https://aaep-protocol.org/context/v1",
  "type": "aaep:agent.handoff.requested",
  "event_id": "evt_4d8a1c7f3e9b2a5d",
  "session_id": "sess_2c91a7b4d23f1e88",
  "timestamp": "2026-05-24T14:22:35.211Z",
  "producer": {
    "agent_id": "retirement-planner",
    "agent_version": "1.4.2"
  },
  "urgency": "critical",
  "reason": "Customer's tax situation is unusual and requires human financial advisor review.",
  "target_kind": "human",
  "target_uri": "queue://customer-service/financial-advisor",
  "urgency_for_handoff": "medium",
  "packaged_context": {
    "user_request_summary": "Retirement planning for self-employed customer with multiple LLCs.",
    "tools_invoked": ["fetch_balance", "calculate_projection"],
    "outstanding_question": "Optimal Solo 401k contribution given pass-through income from three LLCs."
  },
  "summary_terse": "Handing off to a human.",
  "summary_normal": "Your situation needs review by a human financial advisor. I am handing this off to one of our specialists."
}
```

---

## 4.5 Cross-event sequencing rules

The following sequencing rules apply across event types and MUST be honored by all conforming producers.

### 4.5.1 Session bracketing

Every session MUST begin with exactly one `agent.session.started` and end with exactly one terminal lifecycle event (`agent.session.completed`, `agent.session.errored`, or `agent.session.cancelled`). All other events with the same `session_id` MUST be emitted between these two markers.

### 4.5.2 Tool call pairing

Every `agent.tool.completed` event MUST be preceded by an `agent.tool.invoked` event with the same `tool_call_id` (when `tool_call_id` is used) or the same `tool` value (when no `tool_call_id` is used).

Producers SHOULD use `tool_call_id` for unambiguous pairing, especially when multiple concurrent tools may be invoked.

### 4.5.3 Confirmation pairing

A producer that emits `agent.awaiting.confirmation` MUST NOT proceed with the associated action until either:

- A valid confirmation reply matching the `reply_token` arrives indicating `"accept"`, OR
- The `timeout_seconds` elapses and the `default_decision` is `"accept"`.

If the producer proceeds (in either case), the producer MUST emit `agent.tool.invoked` for the action. If the producer does not proceed (reply was `"reject"` or default was `"reject"`), the producer MUST emit a follow-up event reflecting the cancelled action, typically `agent.state.changed` returning to `"thinking"` or `"deciding"`.

### 4.5.4 Streaming output completion

For each distinct `output_id` (or for the session as a whole if `output_id` is not used), exactly one `agent.output.streaming` event with `complete: true` MUST be emitted. Subsequent streaming chunks with the same `output_id` after `complete: true` are non-conforming.

---

## 4.6 Sequencing example: a complete session

This non-normative example shows a complete valid event sequence for a banking session. Envelope fields are abbreviated for readability; in actual emission, full envelopes MUST be present.

```text
1.  agent.session.started        (session opens)
2.  agent.state.changed          (idle → thinking)
3.  agent.tool.invoked           (fetch_balance, low risk)
4.  agent.tool.completed         (fetch_balance, success)
5.  agent.state.changed          (thinking → deciding)
6.  agent.state.changed          (deciding → thinking)
7.  agent.awaiting.confirmation  (transfer funds, high risk, reply_token = rpl_xyz)
    ⋯ (producer blocked, awaiting reply)
    ← confirmation.reply         (decision: accept, reply_token = rpl_xyz)
8.  agent.tool.invoked           (transfer_funds, irreversible, high risk)
9.  agent.tool.completed         (transfer_funds, success)
10. agent.state.changed          (calling_tool → writing_output)
11. agent.output.streaming       (chunk: "Transferred $500 successfully.", complete=false)
12. agent.output.streaming       (chunk: " New balance: $12,000.", complete=true)
13. agent.session.completed      (session closes)
```

The sequence is legal under the rules of §4.5. A subscriber receiving this sequence can synthesize a coherent announcement for the user: the agent started, checked balance, asked for confirmation, transferred funds, announced the result, and finished.

---

## 4.7 Reference schemas

Each core event type has a corresponding JSON Schema in [`schemas/core/`](../schemas/core/). The schemas are normative for machine validation; this chapter is normative for human interpretation. In any conflict, the prose of this chapter takes precedence (per §3.0).

| Event type | Schema file |
|---|---|
| `aaep:agent.session.started` | `schemas/core/agent.session.started.schema.json` |
| `aaep:agent.session.completed` | `schemas/core/agent.session.completed.schema.json` |
| `aaep:agent.session.errored` | `schemas/core/agent.session.errored.schema.json` |
| `aaep:agent.session.cancelled` | `schemas/core/agent.session.cancelled.schema.json` |
| `aaep:agent.state.changed` | `schemas/core/agent.state.changed.schema.json` |
| `aaep:agent.progress.updated` | `schemas/core/agent.progress.updated.schema.json` |
| `aaep:agent.tool.invoked` | `schemas/core/agent.tool.invoked.schema.json` |
| `aaep:agent.tool.completed` | `schemas/core/agent.tool.completed.schema.json` |
| `aaep:agent.output.streaming` | `schemas/core/agent.output.streaming.schema.json` |
| `aaep:agent.awaiting.confirmation` | `schemas/core/agent.awaiting.confirmation.schema.json` |
| `aaep:agent.awaiting.clarification` | `schemas/core/agent.awaiting.clarification.schema.json` |
| `aaep:agent.handoff.requested` | `schemas/core/agent.handoff.requested.schema.json` |

## 4.8 Where to go next

Readers should now proceed to [Chapter 5 (Subscription handshake)](05-subscription-handshake.md), which specifies how subscribers connect to producers, declare their capabilities, and negotiate event delivery.

Implementers building producers should refer back to this chapter frequently while reading the [Implementer's Guide](../guides/IMPLEMENTERS_GUIDE.md).
