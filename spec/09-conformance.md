# Chapter 9 — Conformance

*Status: Normative*

---

This chapter specifies the **three conformance levels** of AAEP and the normative requirements an implementation MUST satisfy to claim each level. It also specifies how conformance is verified, what claims may be made publicly, and how disputes are resolved.

Conformance in AAEP is graded rather than binary. A small Level 1 implementation is more valuable than no implementation at all and may itself be the appropriate target for many products. A full Level 3 implementation is required for safety-critical and high-assurance deployments but is not required of every adopter. The grading lets the protocol meet implementers where they are while preserving a clear path to higher rigor.

## 9.1 Conformance principles

Conformance in AAEP rests on four principles:

1. **Conformance is verifiable.** Every conformance claim corresponds to a defined set of tests in the open-source conformance suite at [`conformance/`](../conformance/). An implementation that cannot pass the tests cannot claim conformance.

2. **Conformance is graded.** Three levels exist (Level 1, Level 2, Level 3). Each higher level adds requirements to the prior level. An implementation conforming at Level N automatically conforms at all levels less than N.

3. **Conformance is bidirectional.** Producers and subscribers each have their own conformance requirements at each level. A producer-only and a subscriber-only implementation may both claim conformance.

4. **Conformance is honest.** Conformance claims include the conformance level, the test suite version against which conformance was verified, and the date of verification. Stale or unverifiable claims are non-conforming.

## 9.2 Conformance levels overview

| Level | Name | Producer requirements | Subscriber requirements |
|---|---|---|---|
| **1** | Notification | Emit lifecycle, reasoning state, and tool/action events. | Receive and announce events. |
| **2** | Interactive | All of Level 1 + emit confirmation/clarification events, honor blocking contract. | All of Level 1 + provide reply channel, send replies. |
| **3** | Negotiated | All of Level 2 + full subscription handshake, backpressure, coalescing, optional signed manifest. | All of Level 2 + initiate handshake, declare capabilities, respect honored capabilities. |

The three levels correspond to three increasingly capable implementations. Level 1 makes agents audible. Level 2 makes them interactive. Level 3 makes them adaptable.

## 9.3 Level 1 — Notification

### 9.3.1 Producer requirements

A producer claiming Level 1 conformance MUST:

1. Emit `agent.session.started` at the start of every session it serves.
2. Emit exactly one terminal lifecycle event (`agent.session.completed`, `agent.session.errored`, or `agent.session.cancelled`) at the end of every session.
3. Emit `agent.state.changed` for substantive internal state transitions (at minimum: transitions to and from `"thinking"`, `"calling_tool"`, and `"writing_output"`).
4. Emit `agent.tool.invoked` immediately before invoking any tool that has user-visible side effects.
5. Emit `agent.tool.completed` after every `agent.tool.invoked` (with appropriate status), including on timeout and error.
6. Emit `agent.output.streaming` for user-facing output, with `coalesce_hint` set when emitting at granular boundaries.
7. Include all required envelope fields (per [Chapter 3 §3.2](03-event-envelope.md)) on every emitted event.
8. Produce events that conform to the JSON Schemas in [`schemas/core/`](../schemas/core/).
9. Include `summary_normal` on every event likely to be announced to users.

A producer claiming Level 1 conformance MAY (and is encouraged to):

- Include `summary_terse` and `summary_detailed` for verbosity flexibility.
- Include `urgency`, `verbosity`, and `localization_hints` on relevant events.
- Emit `agent.progress.updated` for long-running operations.

### 9.3.2 Subscriber requirements

A subscriber claiming Level 1 conformance MUST:

1. Receive AAEP events over a conforming transport (per [Chapter 8](08-transports.md)).
2. Validate envelope structure of incoming events.
3. Announce or render `agent.session.started`, terminal lifecycle events, and `agent.tool.invoked` events to the user using the verbosity preference the user has configured.
4. Distinguish between `agent.session.completed`, `agent.session.errored`, and `agent.session.cancelled` in user-facing announcements.
5. Gracefully handle events with unknown `type` values (announce generically rather than crash).
6. Gracefully handle events containing `extensions` sub-objects the subscriber does not recognize.
7. Honor `urgency: "critical"` events with appropriate prominence; never suppress them.

A subscriber claiming Level 1 conformance MAY (and is encouraged to):

- Announce `agent.state.changed` and `agent.progress.updated` events.
- Provide user controls for verbosity, suppression of background events, and other preferences.
- Render events to multiple output modalities (speech, braille, haptic).

### 9.3.3 What Level 1 does NOT require

Explicitly NOT required at Level 1:

- The subscription handshake. A Level 1 producer MAY emit events without ever receiving a `subscription.request`; a Level 1 subscriber MAY receive events without ever sending one. (Default behavior applies in both directions.)
- Reply messages. Level 1 does not include the confirmation protocol.
- Backpressure negotiation.
- Coalescing negotiation.
- Signed manifests.

### 9.3.4 Conformance test summary for Level 1

The Level 1 test suite (in [`conformance/src/aaep_conformance/levels/level_1.py`](../conformance/src/aaep_conformance/levels/level_1.py)) verifies:

- Envelope conformance on all received events.
- Schema conformance for each event type.
- Correct sequencing of session events (lifecycle bracketing, tool invocation/completion pairing).
- Presence of `summary_normal` on appropriate events.
- Graceful handling of unknown event types in subscriber.
- Graceful handling of unknown extensions in subscriber.

## 9.4 Level 2 — Interactive

### 9.4.1 Producer requirements

A producer claiming Level 2 conformance MUST:

1. Satisfy all Level 1 producer requirements.
2. Emit `agent.awaiting.confirmation` before any irreversible action.
3. Apply the blocking contract (Chapter 6 §6.1): do not perform the confirmed action until a valid reply arrives or timeout expires, and apply `default_decision` on timeout.
4. Apply the correct `default_decision` per Chapter 6 §6.4.1. Setting `default_decision: "accept"` on an irreversible high-risk action is non-conforming.
5. Validate received `confirmation.reply` messages per Chapter 6 §6.3.4 (token validity, expiration, signature/authentication).
6. Treat replies as idempotent: honor first valid reply, ignore subsequent ones for the same `reply_token`.
7. Emit `agent.awaiting.clarification` when clarification is genuinely needed, with `accepted_response_kinds` accurately reflecting what kinds of answers the producer can use.
8. Validate received `clarification.reply` messages and reject those that fail type validation.
9. Emit follow-up events (typically `agent.state.changed`) after each confirmation or clarification resolves, so subscribers stay synchronized.
10. Surface `agent.handoff.requested` when the producer cannot complete the session and intends to escalate to a human or another agent.

### 9.4.2 Subscriber requirements

A subscriber claiming Level 2 conformance MUST:

1. Satisfy all Level 1 subscriber requirements.
2. Declare `supports_confirmation_reply: true` in any capability declarations it sends.
3. Send `confirmation.reply` messages in response to `agent.awaiting.confirmation` events, when the user provides a decision.
4. Echo the `reply_token` exactly as received in `confirmation.reply` and `clarification.reply` messages.
5. Provide a clear user-facing mechanism for the user to issue the reply, with appropriate prominence given the event's `urgency` and `risk_level`.
6. NOT auto-respond on the user's behalf except as explicitly configured by the user.
7. Implement the same requirements for `agent.awaiting.clarification` and `clarification.reply`.
8. Handle reply forwarding correctly if implemented (Chapter 6 §6.6).
9. Detect cancellation of pending confirmations (Chapter 6 §6.8) and update UI accordingly.

### 9.4.3 What Level 2 adds beyond Level 1

Level 2 adds the interactive contract: confirmations, clarifications, and handoffs become first-class with binding semantics. The producer can ASK the user something and rely on the user's answer; the subscriber can SPEAK FOR the user reliably. This contract is what makes accessible irreversible-action workflows possible.

### 9.4.4 Conformance test summary for Level 2

The Level 2 test suite (in [`conformance/src/aaep_conformance/levels/level_2.py`](../conformance/src/aaep_conformance/levels/level_2.py)) verifies, in addition to Level 1 requirements:

- Producer correctly emits `agent.awaiting.confirmation` before irreversible actions.
- Producer honors `timeout_seconds` and applies the correct `default_decision`.
- Producer rejects forged or replayed reply tokens.
- Producer correctly applies first-reply-wins semantics for duplicate replies.
- Producer applies the correct default decision rules (e.g., irreversible high-risk MUST default to reject).
- Subscriber sends valid `confirmation.reply` and `clarification.reply` messages.
- Subscriber correctly echoes `reply_token` values.
- Both parties handle cancellation of pending confirmations.

## 9.5 Level 3 — Negotiated

### 9.5.1 Producer requirements

A producer claiming Level 3 conformance MUST:

1. Satisfy all Level 2 producer requirements.
2. Accept `subscription.request` messages over its transport(s).
3. Respond with `subscription.accepted` or `subscription.rejected`, never silently.
4. In `subscription.accepted`, declare `honored_capabilities` that are no more permissive than the requested capabilities (Chapter 5 §5.4.4).
5. Honor all negotiated capabilities for the duration of the subscription, including:
   - `max_events_per_second` rate limiting (excluding critical events per §5.5.4).
   - `event_filters` include/exclude patterns (excluding critical events).
   - `coalesce_boundaries` for output streaming.
   - `languages` preferences (selecting language for `summary_*` fields).
6. Accept `subscription.renegotiate` and apply renegotiated terms to subsequent events.
7. Accept `subscription.close` cleanly; release resources; apply default decisions for any pending confirmations on the closed subscription.
8. Publish a producer manifest (Chapter 5 §5.10), discoverable at `/.well-known/aaep-manifest.json` or via `manifest_uri` in `subscription.accepted`.
9. OPTIONALLY support signed manifests via JWS (Chapter 10). Producers serving subscribers that require signed manifests MUST sign their manifests.
10. Apply backpressure correctly: token-bucket budget for rate, coalesce events to the negotiated boundary, never delay critical events.

### 9.5.2 Subscriber requirements

A subscriber claiming Level 3 conformance MUST:

1. Satisfy all Level 2 subscriber requirements.
2. Initiate every subscription with a `subscription.request` message that includes a `capabilities` object.
3. Honor the producer's `honored_capabilities` (i.e., if the producer accepted a lower rate than requested, the subscriber must accept the lower rate).
4. Send `subscription.renegotiate` when capabilities need updating; not simply ignore the negotiated terms.
5. Detect and handle out-of-order events (using `sequence_number` if the producer provides them).
6. Detect and deduplicate duplicate events (using `event_id`).
7. Send `subscription.close` cleanly on shutdown.
8. Verify signed manifests (if subscriber declared `accept_signed_manifests_only: true`).
9. Continue to honor critical events even under backpressure.

### 9.5.3 What Level 3 adds beyond Level 2

Level 3 adds the negotiated contract: producers and subscribers explicitly agree on rate, languages, verbosity, and coalescing for each subscription. This is what enables a slow braille display and a fast logging tool to subscribe to the same producer simultaneously, each receiving an event stream tailored to its declared capabilities.

Level 3 also enables higher assurance via signed manifests, which is essential for safety-critical deployments and zero-trust environments.

### 9.5.4 Conformance test summary for Level 3

The Level 3 test suite (in [`conformance/src/aaep_conformance/levels/level_3.py`](../conformance/src/aaep_conformance/levels/level_3.py)) verifies, in addition to Level 2 requirements:

- Subscription handshake conformance (request, accepted, rejected formats).
- `honored_capabilities` are subset of requested capabilities.
- Backpressure correctness (events do not exceed negotiated rate).
- Coalescing correctness (streaming output respects negotiated boundaries).
- Critical events bypass filters and rate limits.
- Renegotiation applies correctly.
- Subscription closure handles in-flight confirmations.
- Signed manifest validation (if signed manifest support is claimed).

## 9.6 Profile conformance

Beyond the three core conformance levels, an implementation MAY also claim conformance to a published profile (Chapter 7 §7.10).

To claim profile conformance, the implementation MUST:

1. Pass all core conformance tests at the profile's required level.
2. Pass all profile-specific conformance fixtures published by the profile.
3. State the profile URI and version in its conformance claim.

Profile conformance is additive: an implementation conforming to a profile is automatically conforming at the profile's required core level. Profile conformance is verified independently of core conformance.

## 9.7 Conformance verification procedure

To verify conformance, an implementer MUST:

1. **Install the conformance test suite.** Clone or install from [`conformance/`](../conformance/). The Python package is `aaep-conformance`.

2. **Run the appropriate test suite against the implementation.**

   For a producer:
   ```bash
   aaep-conformance producer \
     --endpoint <transport-endpoint> \
     --level <1|2|3> \
     --extensions <comma-separated-extension-uris>
   ```

   For a subscriber:
   ```bash
   aaep-conformance subscriber \
     --endpoint <transport-endpoint> \
     --level <1|2|3> \
     --extensions <comma-separated-extension-uris>
   ```

3. **Collect the conformance report.** The test suite emits a machine-readable JSON report (`conformance-report.json`) and a human-readable HTML report (`conformance-report.html`).

4. **Review and address any failures.** Failures MUST be addressed before claiming conformance at the tested level.

5. **Record the report.** Implementations claiming conformance SHOULD make their conformance report available publicly (e.g., on the project's documentation site).

The test suite is open source; results are reproducible by any party. An implementation that passes the test suite at a given level is conforming at that level for the test suite version used.

## 9.8 Conformance claims

Implementations claiming AAEP conformance SHOULD use the following format in public materials:

> "Implementation \[name\] is AAEP \[level\] conformant, verified by AAEP Conformance Suite version \[suite-version\] on \[date\]."

Examples:

- "Windows Narrator 11.4 is AAEP Level 2 conformant, verified by AAEP Conformance Suite version 0.1.0 on 2026-08-15."
- "Acme Customer Service Agent v2.3 is AAEP Level 3 conformant with the Medical AAEP Profile v1, verified by AAEP Conformance Suite version 1.0.0 on 2026-12-01."

Implementations SHOULD NOT claim:

- "AAEP compliant" (without level) — too vague; reviewers cannot evaluate.
- "AAEP certified" — the AAEP project does not certify; it verifies. Verification can be self-administered.
- A higher level than the implementation passes — straightforward misrepresentation.

## 9.9 Self-certification vs third-party verification

AAEP supports both self-certification and third-party verification:

- **Self-certification:** The implementer runs the conformance suite, addresses failures, and publishes the resulting report. This is the primary mode and is sufficient for honest claims.

- **Third-party verification:** An independent entity (auditor, certification body, customer requiring verification) runs the conformance suite against the implementation. This is required by some regulators and procurement processes; the AAEP project itself does not act as a third-party verifier.

Both modes use the same test suite. The integrity of conformance claims rests on the openness of the suite and the verifiability of the report, not on who runs the tests.

## 9.10 Conformance disputes

If a party disputes another's conformance claim, the resolution process is:

1. **Reproduce the failure.** The disputing party SHOULD reproduce the conformance failure using the published suite version.

2. **Open an issue.** The disputing party files an issue on the AAEP repository with the reproduction evidence.

3. **Implementer response.** The claiming implementer MUST address the failure within a reasonable time, either by fixing the implementation, by withdrawing the claim, or by demonstrating the failure was not actually present.

4. **Maintainer review.** If the parties do not resolve the dispute, AAEP maintainers review the evidence and issue an advisory note in the dispute thread. The maintainers do not have authority to revoke conformance claims (since AAEP does not issue them), but their advisory note is influential in the broader ecosystem.

5. **Public disclosure.** Disputes and their resolution are recorded publicly so future implementers can learn from them.

## 9.11 Maintaining conformance across versions

When the AAEP specification publishes a new version, implementations claiming conformance to the prior version remain valid claims; the conformance level is anchored to the test suite version listed in the claim. To claim conformance to a new specification version, the implementation re-runs the corresponding test suite and updates its claim.

Implementations SHOULD note in their claim which spec versions they conform to. For example:

> "Acme Agent v2.3 is AAEP Level 2 conformant against AAEP v1.0.0 and v1.1.0."

This format communicates that the implementation passes both the v1.0.0 and v1.1.0 test suites at Level 2.

## 9.12 Where to go next

Readers should now proceed to [Chapter 10 (Security)](10-security.md), which specifies the threat model and security boundary of AAEP.

Implementers preparing to run the conformance test suite should consult the [`conformance/README.md`](../conformance/README.md) for installation and operation guidance.
