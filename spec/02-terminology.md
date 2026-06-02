# Chapter 2 — Terminology and conventions

*Status: Normative*

---

This chapter defines the terminology used throughout the AAEP specification and the conventions that govern its normative language. Readers SHOULD consult this chapter before reading other normative chapters, because terms used colloquially elsewhere in software engineering may carry specific, narrower meanings under this specification.

## 2.1 Conformance keywords

The key words **MUST**, **MUST NOT**, **REQUIRED**, **SHALL**, **SHALL NOT**, **SHOULD**, **SHOULD NOT**, **RECOMMENDED**, **NOT RECOMMENDED**, **MAY**, and **OPTIONAL** in this document are to be interpreted as described in [BCP 14] when, and only when, they appear in all capitals, as shown here.

[BCP 14]: https://www.rfc-editor.org/info/bcp14

### 2.1.1 Plain-language summary of the keywords

The following summary is informative; the normative definitions are in [BCP 14] ([RFC 2119] and [RFC 8174]).

| Keyword | Meaning |
|---|---|
| **MUST** / **REQUIRED** / **SHALL** | Absolute requirement. An implementation that does not satisfy this requirement is non-conforming. |
| **MUST NOT** / **SHALL NOT** | Absolute prohibition. An implementation that violates this prohibition is non-conforming. |
| **SHOULD** / **RECOMMENDED** | Strong recommendation. Implementations may deviate only after weighing consequences. Deviations should be documented in the implementation's public materials. |
| **SHOULD NOT** / **NOT RECOMMENDED** | Strong recommendation against. Implementations may proceed with this behavior only after weighing consequences. |
| **MAY** / **OPTIONAL** | Truly optional. An implementer may include or omit this feature with no impact on conformance. |

[RFC 2119]: https://www.rfc-editor.org/rfc/rfc2119
[RFC 8174]: https://www.rfc-editor.org/rfc/rfc8174

### 2.1.2 Lowercase usage

When the words *must*, *should*, or *may* appear in this document in lowercase, they carry their ordinary English meaning and do **not** invoke conformance language. Only the all-capitals forms are normative.

### 2.1.3 Negative requirements

The phrase "MUST NOT do X" is normatively equivalent to "is REQUIRED to not do X." Implementations that perform action X are non-conforming.

### 2.1.4 Conditional requirements

Conformance requirements that depend on context are written explicitly. For example: "A producer MUST emit `agent.tool.invoked` immediately before calling a tool **when** at least one subscriber has indicated interest in tool events during the subscription handshake." Both halves of such a statement are normative; an implementation that satisfies the antecedent but not the consequent is non-conforming.

## 2.2 Core terminology

The following terms are used with specific meaning throughout this specification. Definitions are normative.

### 2.2.1 Agent

An **agent** is a software system that uses a Large Language Model (LLM) or comparable model to perform tasks autonomously or semi-autonomously, typically by combining reasoning with tool invocations and producing output for or on behalf of a user. The internal architecture of the agent (single-loop, multi-agent, hierarchical, graph-based) is outside the scope of this specification.

An agent that emits AAEP events is referred to as a **producer**. The same software system may or may not act as a producer at any given moment, depending on whether AAEP support has been activated for that session.

### 2.2.2 Producer

A **producer** is an entity that emits AAEP events. In typical use, a producer is an AI agent, but other systems may also serve as producers if they implement the protocol correctly, such as:

- Agent framework runtime libraries that emit AAEP events on behalf of agents they execute.
- Bridges that translate other event streams (Model Context Protocol, OpenTelemetry traces, internal telemetry) into AAEP events.
- Test fixtures and replay tools that emit pre-recorded event sequences.

A producer is normatively defined by its behavior: it emits AAEP events conforming to this specification, it implements the subscription handshake, and it honors negotiated capabilities. A producer that does not satisfy these requirements is non-conforming, regardless of what software system it is implemented in.

### 2.2.3 Subscriber

A **subscriber** is an entity that receives AAEP events from a producer. Typical subscribers include:

- Screen readers (Narrator, JAWS, NVDA, VoiceOver, TalkBack, Orca)
- Voice control software
- Switch control software
- Refreshable braille displays
- Accessible user interface components
- Captioning and translation systems
- Multi-modal output systems (haptic, audio-spatial, sensory substitution)
- Debugging tools and event captures (e.g., the AAEP debug CLI in `tools/aaep-capture/`)
- Logging and observability backends

A subscriber is normatively defined by its behavior: it initiates the subscription handshake, it processes received events, and it sends valid reply messages when required by the protocol (such as confirmation replies). A subscriber MAY perform any presentation or routing of received events that is appropriate to its purpose; the specification does not constrain how subscribers render events to end users.

### 2.2.4 Event

An **event** is a single AAEP message emitted by a producer and received by zero or more subscribers. An event is a JSON object that conforms to the envelope defined in [Chapter 3](03-event-envelope.md) and, if it carries an event-type-specific payload, to the schema for that type as defined in [Chapter 4](04-core-event-types.md) or in a published extension.

Every event is atomic. Subscribers MUST process events as complete units and MUST NOT attempt to interpret partial event content.

### 2.2.5 Session

A **session** is a logical unit of agent activity, beginning with a single `agent.session.started` event and ending with exactly one of `agent.session.completed`, `agent.session.errored`, or `agent.session.cancelled`. All events emitted by a producer between these terminal markers belong to the same session and share the same `session_id`.

A session corresponds, conceptually, to a single user-initiated agent request. A session MAY involve multiple LLM calls, multiple tool invocations, and multiple confirmation requests, all under the same `session_id`. A session MUST NOT span multiple user requests; each user request begins a new session.

Multi-agent systems in which several agents collaborate to fulfill a single user request MAY model the collaboration as a single session (with each sub-agent's activity emitted under the same `session_id` and distinguished by the `producer` field) or as multiple linked sessions (with `session_id` differing per sub-agent and a parent/child relationship encoded via extension). Both patterns are conformant; the choice is left to the implementer and SHOULD be documented in the producer's adopter notes.

### 2.2.6 Envelope

The **envelope** is the fixed structure of fields that every AAEP event carries, independent of event type. The envelope is specified in [Chapter 3](03-event-envelope.md) and includes fields such as `@context`, `type`, `event_id`, `session_id`, `timestamp`, `producer`, `verbosity`, `urgency`, `localization_hints`, and `extensions`.

The envelope is rigidly specified. Producers MUST NOT add fields to the envelope; extensions MUST go in the `extensions` sub-object.

### 2.2.7 Event type

An **event type** is a URI that identifies the semantic category of an event. Event types defined by this specification are prefixed with the `aaep:` namespace, which resolves to `https://aaep-protocol.org/types/`. Event types defined by extensions use their own namespaces; see [Chapter 7 (Extensions)](07-extensions.md) for details.

The complete list of core event types is specified in [Chapter 4](04-core-event-types.md). The twelve core event types are:

| Family | Event type | Brief purpose |
|---|---|---|
| Lifecycle | `aaep:agent.session.started` | Session begins. |
| Lifecycle | `aaep:agent.session.completed` | Session ends successfully. |
| Lifecycle | `aaep:agent.session.errored` | Session ends with an error. |
| Lifecycle | `aaep:agent.session.cancelled` | Session ends by cancellation. |
| Reasoning state | `aaep:agent.state.changed` | Producer transitions between internal states. |
| Reasoning state | `aaep:agent.progress.updated` | Long-running task reports progress. |
| Tool and action | `aaep:agent.tool.invoked` | Producer is about to call a tool. |
| Tool and action | `aaep:agent.tool.completed` | A tool call has returned. |
| Tool and action | `aaep:agent.output.streaming` | Producer is emitting output to the user. |
| Human-in-the-loop | `aaep:agent.awaiting.confirmation` | Producer is blocked awaiting user consent. |
| Human-in-the-loop | `aaep:agent.awaiting.clarification` | Producer is blocked awaiting user clarification. |
| Human-in-the-loop | `aaep:agent.handoff.requested` | Producer requests handoff to a human or another agent. |

### 2.2.8 Verbosity

**Verbosity** is the level of detail at which information about an event is communicated to the end user. AAEP defines three normative verbosity levels:

| Level | Identifier | Description |
|---|---|---|
| Terse | `"terse"` | Minimal essential information. Suitable for users who want rapid notification without detail, or who are operating under high cognitive load. Typically a few words. |
| Normal | `"normal"` | Default level. Conveys what the agent is doing and any user-relevant outcome. Typically a sentence or short paragraph. |
| Detailed | `"detailed"` | Full context including reasoning, parameters, and rationale where relevant. Suitable for users who want comprehensive information or are debugging the agent's behavior. |

Producers SHOULD provide event summaries at all three verbosity levels for events likely to be announced to users (state changes, tool invocations, confirmations). Subscribers indicate their preferred verbosity during the subscription handshake and MAY allow the end user to switch verbosity at runtime.

Verbosity is a presentation hint, not a content filter. A producer MUST NOT omit events based on verbosity; verbosity only affects which summary string the subscriber prefers from a given event.

### 2.2.9 Urgency

**Urgency** is the priority a producer assigns to an event for delivery and announcement. AAEP defines three normative urgency levels:

| Level | Identifier | Description |
|---|---|---|
| Background | `"background"` | Low priority. Subscribers MAY defer announcement, batch with other background events, or omit if user preferences indicate suppression. |
| Normal | `"normal"` | Default priority. Subscribers SHOULD announce in turn without significant delay. |
| Critical | `"critical"` | High priority. Subscribers MUST announce immediately upon receipt, interrupting lower-priority announcements if necessary. Reserved for confirmation requests, errors, and other events the user must act on. |

Urgency is determined by the producer based on the semantic significance of the event. Subscribers MUST respect the urgency hint when scheduling announcements but MAY apply additional user preferences (for example, a user-configured "do not interrupt" mode).

### 2.2.10 Localization hint

A **localization hint** is a structured object accompanying an event that indicates the language, locale, and text-direction characteristics of human-readable strings in the event payload. The structure of localization hints is specified in [Chapter 11 (Internationalization)](11-internationalization.md).

Producers SHOULD provide localization hints on every event whose payload contains human-readable text. Subscribers MAY use localization hints to select appropriate text-to-speech voices, braille translation tables, or display fonts.

### 2.2.11 Conformance level

A **conformance level** is one of three graded requirement sets that producers and subscribers may claim to satisfy. Levels are specified in [Chapter 9 (Conformance)](09-conformance.md):

| Level | Name | Summary |
|---|---|---|
| 1 | Notification | Emit and consume lifecycle and state events. |
| 2 | Interactive | Adds confirmation, clarification, and handoff with working reply channel. |
| 3 | Negotiated | Adds subscription handshake, backpressure, and coalescing negotiation. |

Conformance is verified through the AAEP conformance test suite (see [`conformance/`](../conformance/)). Implementations may claim a conformance level only after passing the corresponding tests.

### 2.2.12 Subscription

A **subscription** is a logical channel between a single subscriber and a single producer over which events flow. A subscription is established by the subscription handshake (see [Chapter 5](05-subscription-handshake.md)), persists for the duration of the agreed terms, and is terminated by either party.

A single producer MAY have multiple concurrent subscriptions with different subscribers. A single subscriber MAY have multiple concurrent subscriptions to different producers. Each subscription has independent capability negotiation and event delivery.

### 2.2.13 Capability declaration

A **capability declaration** is a structured object included in a subscription request that describes what the subscriber can handle: maximum event rate, preferred verbosity, supported languages, supported event types, reply capability, and any extension capabilities. The full structure is specified in [Chapter 5](05-subscription-handshake.md).

Capability declarations are advisory until accepted by the producer. The producer's acceptance message (or a renegotiation message) establishes the binding terms of the subscription.

### 2.2.14 Confirmation

A **confirmation** is a structured request from a producer to a subscriber asking for explicit user consent before the producer performs an irreversible or sensitive action. A confirmation is conveyed by an `aaep:agent.awaiting.confirmation` event and is matched to a **reply** message containing a `reply_token` that links the user's decision back to the originating confirmation.

The confirmation protocol is specified in detail in [Chapter 6](06-confirmation-protocol.md). When a producer emits a confirmation event, it MUST block its own progress (specifically, it MUST NOT execute the action being confirmed) until either a valid reply is received or the timeout expires, at which point the producer MUST apply the default decision specified in the confirmation event.

### 2.2.15 Reply token

A **reply token** is an opaque string included in events that require a response (currently confirmation events and clarification events). When a subscriber sends a reply, the reply message MUST include the same reply token. Producers MUST validate that received replies carry valid, unexpired reply tokens before acting on them.

Reply tokens are not security credentials and MUST NOT be relied upon as such. They are correlation identifiers. Authentication and authorization of replies are the responsibility of the transport layer and the producer's own security policies (see [Chapter 10](10-security.md)).

### 2.2.16 Extension

An **extension** is a published set of additional event types, additional fields on existing events, additional capabilities, or additional transport bindings that supplements but does not modify the core specification. Extensions are identified by a namespace URI distinct from `aaep:` and are documented separately from the core specification.

The extension mechanism is specified in detail in [Chapter 7](07-extensions.md). The AAEP project maintains an [Extensions Registry](../governance/EXTENSIONS_REGISTRY.md) listing known extensions, but registration is not required; anyone may publish an extension under their own namespace.

### 2.2.17 Profile

A **profile** is a published specification that selects a subset or combination of AAEP features (core event types, extensions, conformance level) appropriate to a particular domain. A profile does not introduce new technical features; it specifies which existing features must be supported by implementations claiming conformance to the profile.

For example, a hypothetical "Medical AAEP Profile" might require: Level 2 conformance, the HIPAA extension, the Multilingual extension restricted to specified languages, and additional verbosity provisions for clinical workflows. An agent compliant with the profile is automatically compliant with AAEP at the specified level; the profile adds requirements but does not subtract any.

Profiles are documented in the same way as extensions: by URI, with a published specification document. Anyone may publish a profile.

### 2.2.18 Transport

A **transport** is the underlying mechanism by which AAEP events and messages travel between producers and subscribers. Transports include Server-Sent Events, WebSocket, local IPC mechanisms, gRPC streams, and stdio JSON-RPC. Requirements that transports MUST satisfy are specified in [Chapter 8](08-transports.md). Recommended bindings are documented in [Appendix B](appendix/B-transport-bindings.md).

A subscription has exactly one transport at any given time. A subscriber MAY re-establish a subscription over a different transport if a transport fails or becomes unavailable.

### 2.2.19 Manifest

A **manifest** is a producer-published declaration of its capabilities, including supported event types, supported conformance level, supported transports, supported languages, and any extensions. Manifests are exchanged during the subscription handshake (see [Chapter 5](05-subscription-handshake.md)).

For Level 3 conformance, manifests MAY be cryptographically signed; see [Chapter 10 (Security)](10-security.md) for the requirements.

### 2.2.20 Coalescing

**Coalescing** is the process by which a producer or subscriber merges multiple events into a smaller number of events or announcements, typically to respect rate limits, reduce cognitive load on the user, or align with natural boundaries in the content (sentence breaks, tool completions, paragraph breaks).

Coalescing is negotiated during the subscription handshake. Subscribers indicate preferred coalescing boundaries; producers honor the negotiated boundaries when emitting events that are eligible for coalescing (notably `aaep:agent.output.streaming`). Details are specified in [Chapter 5 (Subscription handshake)](05-subscription-handshake.md), [Chapter 4 (Core event types)](04-core-event-types.md), and [Chapter 8 (Transports)](08-transports.md).

### 2.2.21 Backpressure

**Backpressure** is the protocol mechanism by which a subscriber signals that it cannot process events as fast as the producer is producing them, and the producer responds by slowing, batching, dropping, or coalescing events. Backpressure is essential to prevent overwhelm of slower subscribers (notably screen readers, which announce content at human speech rates) by faster producers (notably LLMs, which can stream tokens at fifty to one hundred per second).

The backpressure mechanism is part of the negotiated subscription model and is specified in [Chapter 5](05-subscription-handshake.md).

## 2.3 Auxiliary terminology

The following terms are also used in this specification, with the meanings indicated.

### 2.3.1 User

The **user** is the human at whom the agent's activity is directed and on whose behalf the subscriber operates. The user is not directly addressed by the protocol; AAEP's contract is between producers and subscribers. The user's experience is the ultimate purpose of the protocol but the user is not an addressable party in any message exchange.

### 2.3.2 Implementer

An **implementer** is an individual or organization that builds software conforming to the AAEP specification, whether as a producer, a subscriber, an extension publisher, or a tool author.

### 2.3.3 Adopter

An **adopter** is an organization or project that has shipped a product or service incorporating AAEP support. Adopters may register themselves in [governance/ADOPTERS.md](../governance/ADOPTERS.md).

### 2.3.4 Tool (in the agent sense)

A **tool**, in the context of agentic AI, is a function or external service that an agent may invoke to perform an action or retrieve information. Tools include file operations, web search, database queries, API calls, mathematical computation, code execution, and any other capability exposed to the agent. AAEP uses the term "tool" with this agentic-AI meaning throughout.

This is distinct from the AAEP project's own utility programs (in [`tools/`](../tools/)), which are command-line tools for working with the protocol itself.

### 2.3.5 Action

An **action** is a side-effecting operation that an agent performs, typically by invoking a tool. Actions are categorized in AAEP by **risk level** (low, medium, high) and **reversibility** (reversible, irreversible). Both are declared by the agent author as metadata on the relevant event. Actions deemed high-risk or irreversible MUST be preceded by a confirmation event.

### 2.3.6 Producer identity

A **producer identity** is a structured value that identifies the producer emitting an event. It includes at minimum a stable string identifier (`agent_id`) and may include version, model name, and other metadata. Producer identity is required in every event envelope (see [Chapter 3](03-event-envelope.md)).

## 2.4 Document conventions

This section specifies the conventions used to present technical material throughout the specification.

### 2.4.1 Chapter and section numbering

Chapters are numbered with Arabic numerals (1, 2, 3, ...). Sections within a chapter use dotted notation (2.1, 2.2, 2.2.1, ...). Cross-references within the specification use this notation; for example, "see §3.2.4" refers to chapter 3, section 2, subsection 4.

Chapter numbers are stable within a major version of the specification. Section numbers may be renumbered in minor releases when material is added or removed; mappings between old and new numbers are documented in [CHANGELOG.md](../CHANGELOG.md) for affected sections.

### 2.4.2 JSON examples

JSON examples in this specification are presented in fenced code blocks with `json` syntax highlighting:

```json
{
  "@context": "https://aaep-protocol.org/context/v1",
  "type": "aaep:agent.session.started",
  "event_id": "evt_8a3f5b22",
  "session_id": "sess_2c91a7"
}
```

JSON examples are illustrative unless explicitly marked as normative. The canonical machine-readable definition of any event is its JSON Schema, located in [`schemas/`](../schemas/).

### 2.4.3 Code examples

Code examples in programming languages (Python, TypeScript, C#, Go, Rust) are presented in fenced code blocks with the appropriate syntax highlighting. Code examples are always informative. They illustrate possible implementations but do not constrain implementations to follow the illustrated pattern.

### 2.4.4 Schema references

References to JSON Schema files appear as relative paths, for example:

> The envelope MUST conform to [`schemas/envelope.schema.json`](../schemas/envelope.schema.json).

The canonical URL for any schema is the file at the indicated path in the AAEP repository. Schemas hosted at `https://aaep-protocol.org/schemas/v1/...` (once the project website is established) are mirrors of the repository files and are byte-identical to the canonical versions.

### 2.4.5 ABNF grammar

Where structural grammars are specified (for example, for `event_id` formats, transport URIs, or namespace patterns), Augmented Backus-Naur Form ([RFC 5234]) is used. ABNF productions appear in fenced code blocks marked `abnf`:

```abnf
event-id     = "evt_" 1*hexdig
hexdig       = DIGIT / "a" / "b" / "c" / "d" / "e" / "f"
```

[RFC 5234]: https://www.rfc-editor.org/rfc/rfc5234

### 2.4.6 Normative vs. informative

Each chapter, section, and appendix is labeled at its head as either **Normative** or **Informative**.

- **Normative** material defines conformance requirements. Implementations claiming AAEP conformance MUST satisfy normative requirements.
- **Informative** material provides context, examples, rationale, and recommendations. Informative material may guide implementations but does not constrain them.

Examples within a normative chapter are informative unless explicitly marked as normative. The walkthrough scenarios and worked examples throughout the specification are informative.

### 2.4.7 Tables

Tables in this specification are presented in standard Markdown table syntax. Tables are normative when they appear in normative sections and informative when they appear in informative sections. The header row of a normative table is part of the normative content; cell ordering is significant.

### 2.4.8 Diagrams

Diagrams appear as ASCII art, Mermaid diagrams, or referenced image files. Diagrams are informative unless explicitly marked otherwise. The textual specification accompanying any diagram is normative; the diagram serves to aid understanding.

## 2.5 Versioning of terms

The terminology defined in this chapter is stable within a major version of the specification. Minor versions MAY add new terms but MUST NOT change the meaning of existing terms. If the meaning of a term must change in a way that affects normative requirements, the change requires a major version bump and a clear notice in [CHANGELOG.md](../CHANGELOG.md).

Implementers and reviewers may rely on the meanings defined here remaining stable for the life of the major version.

## 2.6 Where to go next

Readers should now proceed to [Chapter 3 (Event envelope)](03-event-envelope.md), which specifies the structure of the envelope that every AAEP event carries.
