# Chapter 6 — Confirmation protocol

*Status: Normative*

---

This chapter specifies the **confirmation protocol**: the blocking flow by which a producer asks for and receives user consent or clarification before proceeding with sensitive actions. The protocol is required at Conformance Level 2 and above.

The confirmation protocol is AAEP's safety contract. Without it, an agent could perform irreversible actions silently while a screen reader user is unable to perceive the visual modal asking for permission. With it, the agent is **mechanically prevented** from performing such actions until the user (through the subscriber) has explicitly authorized them. The blocking contract specified in this chapter is what makes "AI suddenly stopped being broken" a reality rather than a marketing claim.

Two reply message types are specified in this chapter:

- `confirmation.reply` — the response to an `agent.awaiting.confirmation` event (§4.4.1).
- `clarification.reply` — the response to an `agent.awaiting.clarification` event (§4.4.2).

The canonical machine-readable definitions are the JSON Schemas in [`schemas/handshake/`](../schemas/handshake/).

## 6.1 The blocking contract

When a producer emits an `agent.awaiting.confirmation` event, the producer enters a blocked state with respect to the action being confirmed. The blocking contract is normative:

1. The producer MUST NOT perform the action being confirmed until one of:
   - A valid `confirmation.reply` arrives with matching `reply_token` indicating decision `"accept"`, OR
   - The `timeout_seconds` specified in the confirmation event elapses, AND the `default_decision` is `"accept"`.

2. The producer MUST NOT silently drop or skip the action upon rejection. If the decision (replied or defaulted) is `"reject"`, the producer MUST emit a follow-up event reflecting the cancelled action. This is typically an `agent.state.changed` returning to `"thinking"` or `"deciding"`, optionally followed by an `agent.output.streaming` event explaining the cancellation.

3. The producer MAY continue with non-blocked work (work that does not depend on the confirmation) during the blocked period, but MUST NOT emit any event whose semantics imply the confirmed action has been performed.

4. The producer MUST NOT emit a subsequent `agent.awaiting.confirmation` for the same action without first releasing the prior block (via reply or timeout).

The same contract applies to `agent.awaiting.clarification`: the producer is blocked with respect to actions that depend on the clarification, MUST honor the reply or timeout, and MUST NOT proceed before resolution.

## 6.2 Reply tokens

Every blocking event (confirmation, clarification) carries a `reply_token`. The reply token is the binding identifier that ties a reply back to the originating event.

### 6.2.1 Reply token format

**Type:** string

**ABNF:**

```abnf
reply-token  = "rpl_" 1*64( ALPHA / DIGIT )
ALPHA        = %x41-5A / %x61-7A
DIGIT        = %x30-39
```

That is, the literal prefix `rpl_` followed by one to sixty-four alphanumeric characters. The recommended generation method is a 128-bit cryptographically random value rendered as 32 hexadecimal characters.

### 6.2.2 Reply token uniqueness

- Reply tokens MUST be unique within a producer for at least the duration of the issuing session plus 24 hours.
- Global uniqueness across all producers and all time is RECOMMENDED but not required.
- A producer MUST NOT reuse a reply token from a prior confirmation, even after the original confirmation has been resolved.

### 6.2.3 Reply tokens are opaque

Reply tokens are opaque to subscribers. Subscribers MUST NOT:

- Parse, interpret, or modify reply tokens.
- Generate reply tokens themselves.
- Use reply tokens for any purpose other than echoing them back in reply messages.

The format described in §6.2.1 is for producer convenience and diagnostic readability; it does not encode any meaning the subscriber should depend on.

### 6.2.4 Reply tokens are not security credentials

Reply tokens establish correlation, not authentication. A producer that receives a reply with a valid reply token MUST still authenticate the sender of the reply through transport-level mechanisms (TLS client certs, OAuth tokens, signed messages, or local-IPC trust) before acting on the reply.

A reply token alone is NOT proof that the user authorized the decision. The reply token proves only that the sender of the reply knew the token. See [Chapter 10 (Security)](10-security.md) for the threat model and mitigations.

## 6.3 The `confirmation.reply` message

A subscriber sends `confirmation.reply` to convey the user's decision on a confirmation request.

### 6.3.1 Required fields

| Field | Type | Description |
|---|---|---|
| `type` | string | MUST be `"confirmation.reply"`. |
| `reply_token` | string | The exact `reply_token` from the originating `agent.awaiting.confirmation` event. |
| `decision` | string | One of `"accept"`, `"reject"`. |
| `subscription_id` | string | The subscription on which this reply is sent. |
| `timestamp` | string | RFC 3339 timestamp of when the user made the decision. |

### 6.3.2 Optional fields

| Field | Type | Description |
|---|---|---|
| `decided_by` | string | Identifier of the user or system that made the decision (e.g., `"user:folake"`, `"auto:configured_policy"`). |
| `decision_rationale` | string | Optional free-form text explaining the decision, if the user provided one. |
| `modified_action` | object | If the subscriber permits negotiated decisions (e.g., "accept but with modified parameters"), this object describes the modification. Producer support for this field is OPTIONAL; if the producer does not support modified actions, it MUST treat such a reply as `"reject"`. |
| `correlation_id` | string | Trace identifier. |

### 6.3.3 Example

Simple accept:

```json
{
  "type": "confirmation.reply",
  "reply_token": "rpl_4f8a2e7d9c1b6a3f",
  "decision": "accept",
  "subscription_id": "sub_8a4f2c9d1e7b5f3a",
  "timestamp": "2026-05-24T14:22:24.812Z",
  "decided_by": "user:folake"
}
```

Reject with rationale:

```json
{
  "type": "confirmation.reply",
  "reply_token": "rpl_4f8a2e7d9c1b6a3f",
  "decision": "reject",
  "subscription_id": "sub_8a4f2c9d1e7b5f3a",
  "timestamp": "2026-05-24T14:22:24.812Z",
  "decided_by": "user:folake",
  "decision_rationale": "User wants to reduce transfer amount first."
}
```

### 6.3.4 Producer validation of replies

Upon receiving a `confirmation.reply`, the producer MUST:

1. Verify the message is well-formed JSON conforming to the schema in [`schemas/handshake/confirmation.reply.schema.json`](../schemas/handshake/confirmation.reply.schema.json).
2. Verify the `reply_token` matches an outstanding confirmation issued by this producer.
3. Verify the `reply_token` has not already been used (replies are idempotent only with respect to the matching action; once consumed, the token is invalid for any further use).
4. Verify the `reply_token` has not expired (`timestamp` of reply must precede the originating event's `timestamp` + `timeout_seconds`).
5. Authenticate the sender at the transport level. The mechanism is transport-specific; see [Chapter 10](10-security.md).
6. Verify the `decision` value is one of the values listed in the originating confirmation's `allowed_replies` (default `["accept", "reject"]`).

A reply that fails any check MUST be ignored. The producer MAY log the failure for diagnostic purposes. The producer MUST NOT inform the sender of the specific failure reason (this would aid attackers in token discovery).

### 6.3.5 Idempotency of replies

If the same valid `reply_token` arrives in multiple `confirmation.reply` messages, the producer MUST honor only the first reply received and ignore subsequent ones. The producer MAY send a courtesy notification on the subscription that submitted a late duplicate, indicating the confirmation was already resolved.

This rule prevents race conditions in multi-subscriber scenarios where two subscribers might attempt to reply to the same confirmation.

## 6.4 Timeout semantics

If no valid reply arrives before `timeout_seconds` elapses (measured from the `timestamp` of the originating event), the producer MUST apply the `default_decision` specified in the originating event.

### 6.4.1 Default decision rules

The `default_decision` field of an `agent.awaiting.confirmation` event determines what happens on timeout. The following normative rules apply:

| Action characteristics | Required `default_decision` |
|---|---|
| `irreversible: true` AND `risk_level: "high"` | MUST be `"reject"` |
| `irreversible: true` AND `risk_level: "medium"` | MUST be `"reject"` |
| `irreversible: true` AND `risk_level: "low"` | SHOULD be `"reject"`, MAY be `"accept"` |
| `irreversible: false` AND `risk_level: "high"` | SHOULD be `"reject"` |
| `irreversible: false` AND `risk_level: "medium"` | MAY be either |
| `irreversible: false` AND `risk_level: "low"` | MAY be either |

A producer that emits a confirmation event with `default_decision: "accept"` for an irreversible high-risk action is non-conforming. Conformance test suites MUST detect this and flag it as a violation.

### 6.4.2 Timeout duration recommendations

The following are informative recommendations for `timeout_seconds`:

| Action type | Recommended timeout |
|---|---|
| High-risk irreversible (financial transfer, account changes) | 180 to 600 seconds |
| Medium-risk irreversible (sending email, posting message) | 60 to 180 seconds |
| Low-risk reversible (saving draft, modifying file) | 30 to 90 seconds |
| Clarification (no action involved) | 60 to 300 seconds |

Subscribers MAY request longer timeouts through extension capabilities (e.g., users with motor disabilities may need more time to respond). Producers SHOULD honor reasonable timeout extension requests.

### 6.4.3 Timeout countdown visibility

Producers SHOULD emit periodic `agent.progress.updated` events during long timeouts to keep the user aware of remaining time, especially for timeouts exceeding 60 seconds. The recommended cadence is one update at 50% of timeout remaining and one at 10% remaining.

Subscribers MAY surface this countdown visually or audibly. Subscribers MUST NOT depend on countdown events; the producer's `timeout_seconds` value is authoritative.

## 6.5 The `clarification.reply` message

A subscriber sends `clarification.reply` to convey the user's clarification on an `agent.awaiting.clarification` event.

### 6.5.1 Required fields

| Field | Type | Description |
|---|---|---|
| `type` | string | MUST be `"clarification.reply"`. |
| `reply_token` | string | Echoed from the originating event. |
| `response` | varies | The user's clarification response. Type depends on `accepted_response_kinds`. |
| `subscription_id` | string | The subscription on which this reply is sent. |
| `timestamp` | string | RFC 3339 timestamp. |

### 6.5.2 `response` field shape

The `response` field is typed according to the `accepted_response_kinds` of the originating clarification event:

| Response kind | `response` type | Example |
|---|---|---|
| `"freetext"` | string | `"I want to retire at 67."` |
| `"yes_no"` | boolean | `true` |
| `"multiple_choice"` | string (value from `choices`) | `"67"` |
| `"numeric"` | number | `67` |

For events with multiple `accepted_response_kinds`, the subscriber chooses one and the producer accepts any of the listed kinds.

### 6.5.3 Optional fields

| Field | Type | Description |
|---|---|---|
| `decided_by` | string | Identifier of the user who provided the clarification. |
| `confidence` | number (0-1) | Subscriber-reported confidence in the clarification (e.g., voice-input confidence). |
| `correlation_id` | string | Trace identifier. |

### 6.5.4 Example

```json
{
  "type": "clarification.reply",
  "reply_token": "rpl_2c8e4a9f7b1d3a6e",
  "response": "67",
  "subscription_id": "sub_8a4f2c9d1e7b5f3a",
  "timestamp": "2026-05-24T14:22:18.121Z",
  "decided_by": "user:folake"
}
```

### 6.5.5 Validation by producer

The producer applies the same validation as for confirmation replies (§6.3.4), plus:

- Verify the `response` value's type matches one of the `accepted_response_kinds` of the originating event.
- For `multiple_choice`, verify the response is one of the values listed in `choices`.

A reply that fails type validation MUST be treated as if no reply arrived; the producer continues waiting for a valid reply or for timeout.

## 6.6 Reply forwarding across subscribers

Some subscribers do not have direct user input capability and instead forward confirmations to another subscriber (for example, a server-side bridge forwarding confirmations to a phone-based reply channel). The forwarding pattern is permitted as long as the following rules are observed:

1. The forwarding subscriber receives the confirmation event with `supports_confirmation_reply: false` in its capability declaration, signaling it cannot reply directly.
2. The forwarding subscriber transports the event payload to another reply-capable subscriber through its own out-of-band mechanism.
3. The reply-capable subscriber sends the actual `confirmation.reply` message on its own subscription back to the producer.
4. The producer treats the reply normally: matching `reply_token`, applying decision.

Reply forwarding is opaque to the producer. The producer does not know (and does not need to know) which subscriber the reply originated from. As long as the `reply_token` is valid, the reply is honored.

## 6.7 Multi-subscriber confirmation handling

When a producer has multiple concurrent subscriptions and emits an `agent.awaiting.confirmation` event, the event is delivered to all subscriptions whose capabilities permit (i.e., all subscriptions where the event is not filtered, and critical events are never filtered per §5.5.4).

### 6.7.1 First reply wins

When multiple subscribers can reply, the producer MUST honor the first valid `confirmation.reply` received and MUST ignore subsequent replies to the same `reply_token`. Late replies MAY trigger a courtesy notification (see §6.3.5).

### 6.7.2 Notification of resolution

After resolving a confirmation, the producer SHOULD emit an informational event indicating the outcome to all subscriptions that received the original confirmation. This ensures subscribers that did not contribute the reply still know the action's status. The recommended pattern is an `agent.state.changed` event with payload describing the resolution:

```json
{
  "type": "aaep:agent.state.changed",
  "from_state": "awaiting_input",
  "to_state": "calling_tool",
  "summary_normal": "User accepted the transfer; proceeding."
}
```

Or, for rejection:

```json
{
  "type": "aaep:agent.state.changed",
  "from_state": "awaiting_input",
  "to_state": "thinking",
  "summary_normal": "User rejected the transfer; reconsidering."
}
```

## 6.8 Cancellation of pending confirmations

A producer MAY cancel a pending confirmation before its timeout if external conditions change (the user navigated away, the session was cancelled, the agent decided the action is no longer needed). To cancel, the producer emits an event that supersedes the confirmation:

- If the entire session is cancelled, `agent.session.cancelled` cancels all pending confirmations.
- If only the specific action is no longer needed, the producer emits an `agent.state.changed` returning to `"thinking"` or `"deciding"` with payload explaining the change. The cancelled confirmation's `reply_token` becomes invalid; subsequent replies to it MUST be ignored.

Subscribers SHOULD detect cancellation and update their UI to remove the no-longer-relevant confirmation prompt. Subscribers MAY emit a follow-up notification to the user explaining the cancellation.

## 6.9 Security considerations summary

The detailed threat model and mitigations for the confirmation protocol are in [Chapter 10 (Security)](10-security.md). The key concerns are:

1. **Forged replies.** A reply containing a valid `reply_token` but from an unauthorized sender. Mitigation: transport-level authentication; signed manifests at Level 3; never treat the reply token alone as authorization.

2. **Replay attacks.** Replaying a captured reply to cause the producer to repeat a confirmed action. Mitigation: reply tokens are single-use (§6.3.5); session-bound (`session_id` validation); time-bound (`timestamp` validation in §6.3.4 step 4).

3. **Confirmation phishing.** A malicious producer emits a confirmation that misrepresents the action being confirmed. Mitigation: subscribers SHOULD verify producer identity via signed manifests at Level 3; users SHOULD configure trust policies for unknown producers.

4. **Denial via flooding.** An attacker producer floods a subscriber with confirmation events to exhaust attention. Mitigation: subscriber capability declarations include rate limits; subscribers MAY drop excessive non-critical events (but MUST handle critical events even when overwhelmed; users retain control through subscription closure).

5. **Timing attacks via default_decision.** An attacker subscriber stalls to force a `default_decision: "accept"` to fire. Mitigation: the normative rule in §6.4.1 prevents `default_decision: "accept"` for high-risk irreversible actions.

## 6.10 Complete confirmation sequence example

The following non-normative trace shows a complete confirmation interaction:

```text
Time         Direction   Message
─────────    ──────────  ─────────────────────────────────────────────
14:22:20.014 P → S       agent.awaiting.confirmation
                         (reply_token=rpl_xyz, action="Transfer $500",
                          timeout=300, default_decision="reject",
                          risk_level="high", irreversible=true,
                          urgency="critical")
14:22:20.020 S (announces to user via TTS)
                         "Confirmation required. Transfer five hundred
                          dollars from checking to savings. Cannot be
                          easily reversed. Press space to confirm,
                          escape to reject."
14:22:24.812 S (user presses space)
14:22:24.813 S → P       confirmation.reply
                         (reply_token=rpl_xyz, decision="accept",
                          decided_by="user:folake")
14:22:24.815 P (validates token, marks used)
14:22:24.820 P → S       agent.state.changed
                         (awaiting_input → calling_tool,
                          summary: "User accepted; proceeding.")
14:22:24.821 P → S       agent.tool.invoked
                         (transfer_funds, irreversible=true)
14:22:25.901 P → S       agent.tool.completed (success)
```

The exchange completes in approximately 5 seconds. The user perceives only the confirmation request, the time to consider, and the result. The blocking, token validation, and state transitions happen invisibly. The protocol's role is to make this sequence reliable across producers, subscribers, and transports.

## 6.11 Where to go next

Readers should now proceed to [Chapter 7 (Extensions)](07-extensions.md), which specifies how third parties extend AAEP with new event types, fields, and capabilities without breaking interoperability.

Implementers building producers should next consult the [Implementer's Guide §3 (Confirmation patterns)](../guides/IMPLEMENTERS_GUIDE.md#3-confirmation-patterns) for framework-specific integration.
