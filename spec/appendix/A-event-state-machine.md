# Appendix A — Event state machine

*Status: Informative*

---

This appendix provides a **non-normative reference** for the legal orderings of AAEP events within a session. The state machine illustrated here captures the constraints stated normatively in [Chapter 4 §4.5](../04-core-event-types.md) and is intended as an implementer aid, not an authoritative source.

In any conflict between this appendix and the normative text in Chapter 4, the normative text takes precedence.

## A.1 Top-level session lifecycle

Every AAEP session traces a path through this top-level state diagram:

```text
                    ┌────────────────────────┐
                    │       (no session)     │
                    └─────────────┬──────────┘
                                  │ session.started
                                  ▼
                    ┌────────────────────────┐
                    │     ACTIVE SESSION     │
                    │ (substantive events    │
                    │  may flow here)        │
                    └──┬─────────┬──────────┘
                       │         │         │
       session.completed│        │         │session.errored
                       │         │         │
                       │         │ session.cancelled
                       ▼         ▼         ▼
                    ┌────────────────────────┐
                    │       (terminated)     │
                    └────────────────────────┘
```

**Invariants:**

- A session has exactly one `agent.session.started` event and exactly one terminal lifecycle event (`agent.session.completed`, `agent.session.errored`, or `agent.session.cancelled`).
- All other events with the same `session_id` occur in the ACTIVE SESSION state.

**Conformance test reference:** [`conformance/checks/lifecycle.py`](../../conformance/src/aaep_conformance/checks/lifecycle.py).

## A.2 Internal state transitions during ACTIVE SESSION

The substantive activity within ACTIVE SESSION is described by `agent.state.changed` events. The state machine traces these transitions:

```text
                              ┌───────┐
                              │ idle  │  (initial state)
                              └───┬───┘
                                  │
                                  ▼
                              ┌───────────┐
                       ┌──────│ thinking  │──────┐
                       │      └────┬──────┘      │
                       │           │             │
                       ▼           ▼             ▼
                ┌──────────────┐ ┌────────┐ ┌──────────────┐
                │ calling_tool │ │deciding│ │writing_output│
                └──────┬───────┘ └────┬───┘ └──────┬───────┘
                       │              │             │
                       └──────────────┴─────────────┘
                                  │
                                  ▼
                              ┌───────────────┐
                              │awaiting_input │
                              │(blocking)     │
                              └──────┬────────┘
                                  │
                                  ▼ (reply received or timeout)
                              ┌───────┐
                              │thinking│ (or other)
                              └────┬──┘
                                  │
                                  ▼
                              ┌──────────────┐
                              │ handing_off  │ (terminal-equivalent)
                              └──────────────┘
```

**Notes:**

- The transition graph above shows the typical flow. Producers MAY use additional states (any string is permitted) as long as transitions are documented in the producer's manifest.
- `awaiting_input` is the state during which the producer is blocked awaiting a confirmation or clarification reply (Chapter 6 §6.1).
- `handing_off` typically precedes session termination via `agent.session.completed` (when handoff is acknowledged) or `agent.session.cancelled` (when handoff is rejected).

## A.3 Tool invocation state machine

Each tool invocation traces this sub-state machine:

```text
              (state: thinking or deciding)
                        │
                        │   (decision to call tool)
                        ▼
              ┌─────────────────────────┐
              │  agent.tool.invoked     │
              │  (event emitted)        │
              └──────────┬──────────────┘
                         │
                         │   (tool execution begins)
                         ▼
              ┌─────────────────────────┐
              │  (tool executing)       │
              │  state: calling_tool    │
              └──────────┬──────────────┘
                         │
                         │   (tool returns or times out)
                         ▼
              ┌─────────────────────────┐
              │  agent.tool.completed   │
              │  (event emitted)        │
              │  status: success/error/timeout  │
              └──────────┬──────────────┘
                         │
                         │
                         ▼
              (state: thinking or writing_output)
```

**Invariants:**

- Every `agent.tool.invoked` MUST be followed by exactly one `agent.tool.completed` with matching `tool_call_id` or matching `tool` name.
- `agent.tool.completed` MUST NOT be emitted without a preceding `agent.tool.invoked`.
- The state during tool execution SHOULD be `calling_tool`.

**Concurrent tool calls:** If the producer supports parallel tool invocations, multiple `agent.tool.invoked` events MAY be in-flight simultaneously, each awaiting its own `agent.tool.completed`. The pairing is established by `tool_call_id`.

## A.4 Confirmation state machine

The confirmation flow involves multiple state changes:

```text
              (state: thinking)
                        │
                        │   (irreversible action detected)
                        ▼
              ┌──────────────────────────────────┐
              │  agent.awaiting.confirmation     │
              │  (event emitted)                 │
              │  state changes to awaiting_input │
              └────────────────┬─────────────────┘
                               │
                               │
                ┌──────────────┼──────────────┐
                │              │              │
                │ confirmation │              │
                │ .reply       │              │
                │ (accept)     │ (reject)     │ (timeout)
                │              │              │
                ▼              ▼              ▼
        ┌───────────┐  ┌───────────┐  ┌─────────────────────┐
        │perform    │  │cancel     │  │apply default_decision│
        │action     │  │action     │  │(per §6.4.1)         │
        └──────┬────┘  └─────┬─────┘  └──────┬──────────────┘
               │             │                │
               │             │                │
               └─────────────┴────────────────┘
                             │
                             ▼
                 ┌──────────────────────┐
                 │  agent.state.changed │
                 │  (resumes thinking   │
                 │   or proceeds)       │
                 └──────────────────────┘
```

**Invariants:**

- The producer MUST emit `agent.state.changed` to `awaiting_input` at or before `agent.awaiting.confirmation`.
- The producer MUST emit `agent.state.changed` away from `awaiting_input` after resolution (reply or timeout).
- If `accept`, the producer MUST emit `agent.tool.invoked` for the confirmed action.
- If `reject`, the producer MUST NOT emit `agent.tool.invoked` for the rejected action.

## A.5 Clarification state machine

Clarification is structurally similar to confirmation but does not involve a side-effecting action:

```text
              (state: thinking or deciding)
                        │
                        │   (need clarification)
                        ▼
              ┌────────────────────────────────────┐
              │  agent.awaiting.clarification      │
              │  (event emitted)                   │
              │  state changes to awaiting_input   │
              └────────────────┬───────────────────┘
                               │
                ┌──────────────┴──────────────┐
                │                             │
                │  clarification.reply        │
                │  (response received)        │  (timeout)
                ▼                             ▼
        ┌───────────────────┐      ┌─────────────────────┐
        │  process response │      │  apply default_     │
        │                   │      │  response (if set)  │
        └─────────┬─────────┘      └───────┬─────────────┘
                  │                        │
                  └────────────┬───────────┘
                               │
                               ▼
                 ┌──────────────────────┐
                 │  agent.state.changed │
                 │  (resumes thinking)  │
                 └──────────────────────┘
```

## A.6 Streaming output state machine

Output streaming involves multiple chunks terminated by a final chunk:

```text
              (state: writing_output)
                        │
                        │   (first chunk ready)
                        ▼
              ┌─────────────────────────────────┐
              │  agent.output.streaming         │
              │  (chunk N, complete: false)     │
              └────────────────┬────────────────┘
                               │
                               │  (more chunks)
                               ▼
              ┌─────────────────────────────────┐
              │  agent.output.streaming         │
              │  (chunk N+1, complete: false)   │
              └────────────────┬────────────────┘
                               │
                               │  (...continues...)
                               │
                               ▼
              ┌─────────────────────────────────┐
              │  agent.output.streaming         │
              │  (final chunk, complete: true)  │
              └────────────────┬────────────────┘
                               │
                               ▼
              (state: writing_output → thinking or session terminating)
```

**Invariants:**

- For each `output_id`, exactly one event with `complete: true` MUST be emitted.
- The `position` field MUST increase monotonically across chunks of the same `output_id`.
- After emitting `complete: true`, no further chunks with the same `output_id` MAY be emitted.

## A.7 Per-event legal predecessor/successor tables

The following tables list, for each core event type, which events may legally precede or follow it within a session.

### A.7.1 `agent.session.started`

| Position in session | Legal predecessors |
|---|---|
| First event | (none — must be the first event of the session) |

| Legal successors |
|---|
| Any non-terminal lifecycle event |
| `agent.state.changed` |
| `agent.progress.updated` |
| `agent.tool.invoked` |
| `agent.output.streaming` |
| `agent.awaiting.confirmation` |
| `agent.awaiting.clarification` |
| `agent.handoff.requested` |
| Terminal: `agent.session.completed` / `errored` / `cancelled` |

### A.7.2 `agent.session.completed` / `errored` / `cancelled`

| Legal predecessors |
|---|
| `agent.session.started` (immediately or after intervening events) |
| Any non-terminal session event |

| Legal successors |
|---|
| (none — these are terminal events for the session) |

### A.7.3 `agent.state.changed`

| Legal predecessors |
|---|
| `agent.session.started` |
| Another `agent.state.changed` (transitions chain) |
| `agent.tool.completed` (returning to thinking after tool) |
| `confirmation.reply` or timeout resolution |
| Any other intra-session event |

| Legal successors |
|---|
| Any intra-session event |
| Terminal events |

### A.7.4 `agent.tool.invoked`

| Legal predecessors |
|---|
| `agent.state.changed` (to `calling_tool` or `thinking`) |
| `confirmation.reply` (with decision: accept) — required if this `agent.tool.invoked` has `irreversible: true` |

| Required successor |
|---|
| `agent.tool.completed` with matching `tool_call_id` |

### A.7.5 `agent.tool.completed`

| Legal predecessors |
|---|
| `agent.tool.invoked` with matching `tool_call_id` |

| Legal successors |
|---|
| `agent.state.changed` (often to `thinking` or `writing_output`) |
| Any subsequent intra-session event |

### A.7.6 `agent.awaiting.confirmation`

| Legal predecessors |
|---|
| `agent.state.changed` (to `awaiting_input`) |
| `agent.session.started` (rare; for sessions that start by asking permission) |

| Required successor |
|---|
| Either: `confirmation.reply` with matching `reply_token` |
| Or: (no reply within `timeout_seconds`) → producer applies `default_decision` |

| Then |
|---|
| `agent.state.changed` away from `awaiting_input` |
| If accepted: `agent.tool.invoked` for the confirmed action |

### A.7.7 `agent.output.streaming`

| Legal predecessors |
|---|
| `agent.state.changed` (to `writing_output`) |
| `agent.tool.completed` (the tool's output is being relayed) |
| Another `agent.output.streaming` event with same `output_id` and `complete: false` |

| Legal successors |
|---|
| Another `agent.output.streaming` event with same `output_id`, until `complete: true` |
| After `complete: true`: any intra-session event |

## A.8 Invalid sequences (informative)

The following are examples of invalid event sequences that conformance tests detect. Producers MUST NOT emit such sequences.

### A.8.1 Tool completion without invocation

```text
INVALID:
1. agent.session.started
2. agent.tool.completed  ← no preceding tool.invoked
3. agent.session.completed
```

### A.8.2 Multiple terminal events

```text
INVALID:
1. agent.session.started
2. agent.session.completed
3. agent.session.errored  ← session already terminated
```

### A.8.3 Events after terminal event

```text
INVALID:
1. agent.session.started
2. agent.session.completed
3. agent.tool.invoked  ← session already terminated
```

### A.8.4 Irreversible action without confirmation

```text
INVALID:
1. agent.session.started
2. agent.state.changed (thinking)
3. agent.tool.invoked (transfer_funds, irreversible: true)  ← no preceding confirmation
4. agent.tool.completed
5. agent.session.completed
```

### A.8.5 Action performed after rejection

```text
INVALID:
1. agent.session.started
2. agent.awaiting.confirmation (reply_token: rpl_xyz)
3. confirmation.reply (decision: reject, reply_token: rpl_xyz)
4. agent.tool.invoked (the rejected action)  ← MUST NOT proceed after reject
```

### A.8.6 Streaming output after completion

```text
INVALID:
1. agent.output.streaming (output_id: out_1, complete: true)
2. agent.output.streaming (output_id: out_1, complete: false)  ← cannot continue after complete
```

### A.8.7 Out-of-order streaming positions

```text
INVALID:
1. agent.output.streaming (output_id: out_1, position: 0, complete: false)
2. agent.output.streaming (output_id: out_1, position: 50, complete: false)
3. agent.output.streaming (output_id: out_1, position: 30, complete: false)  ← position decreased
```

## A.9 Multi-agent sessions

When a session involves multiple sub-agents collaborating, the state machine extends in one of two patterns described in [Chapter 2 §2.2.5](../02-terminology.md):

**Pattern 1 — Single session, multiple producers:** All sub-agents emit events under the same `session_id`. The `producer` field distinguishes which agent emitted each event. The top-level state machine in §A.1 still applies; multiple sub-agents may be in different states simultaneously.

**Pattern 2 — Linked sessions:** Each sub-agent has its own `session_id`. Parent/child relationships are encoded via an extension (often `extensions.parent_session_id`). Each session's state machine is independent.

Implementers SHOULD document which pattern their producers use in their manifest.

## A.10 Visualizing your own producer

The AAEP project provides a debugging tool, `aaep-capture`, that records event streams to a file. The capture file can be inspected with `aaep-replay --visualize` to render a state-machine trace of a recorded session.

This is useful for verifying that a producer's emission order conforms to the state machine in this appendix. See [`tools/aaep-capture/`](../../tools/aaep-capture/) and [`tools/aaep-replay/`](../../tools/aaep-replay/).

## A.11 Where to go next

For concrete transport-level details (URL paths, headers, framing rules), continue to [Appendix B (Transport bindings)](B-transport-bindings.md).

For an alphabetical index of terms used in the specification, see [Appendix C (Glossary)](C-glossary.md).
