# Appendix C — Glossary

*Status: Informative*

---

This appendix provides an alphabetical index of terms used throughout the AAEP specification. Each entry includes a brief definition and a cross-reference to the chapter or section where the term is normatively defined (where applicable).

Definitions in this glossary are condensed for quick reference. The normative definitions in the cited locations take precedence over any apparent conflict with this glossary.

---

## A

**AAEP** (Agent Accessibility Event Protocol)
The protocol defined by this specification. An open, vendor-neutral, programming-language-neutral standard for enabling AI agents to communicate their lifecycle, state, tool invocations, and confirmation requests to assistive technology consumers. See [Chapter 1](../01-introduction.md).

**ABNF** (Augmented Backus-Naur Form)
Grammar notation used in this specification to define structural formats for fields such as `event_id` and `session_id`. Specified in [RFC 5234]. See [§2.4.5](../02-terminology.md).

**Action**
A side-effecting operation that an agent performs, typically by invoking a tool. Actions are categorized by risk level (low, medium, high) and reversibility (reversible, reversible-with-effort, irreversible). See [§2.3.5](../02-terminology.md).

**Adopter**
An organization or project that has shipped a product or service incorporating AAEP support. See [governance/ADOPTERS.md](../../governance/ADOPTERS.md) for the public list.

**Agent**
A software system that uses an LLM or comparable model to perform tasks, typically by combining reasoning with tool invocations. See [§2.2.1](../02-terminology.md).

**`agent_id`**
A stable string identifier for a producer, contained in the `producer` field of the event envelope. See [§3.2.6.1](../03-event-envelope.md).

**Announcement**
The presentation of an AAEP event to the user by a subscriber. AAEP does not specify how announcements are rendered; subscribers translate events into speech, braille, haptic, visual, or other modalities appropriate to the user.

**ARIA** (Accessible Rich Internet Applications)
W3C standard defining roles, states, and properties for accessible web content. AAEP complements ARIA: ARIA addresses rendered UI accessibility; AAEP addresses agent state accessibility. See [§1.2](../01-introduction.md).

**Assistive technology (AT)**
Software or hardware that helps users with disabilities interact with computer systems. Examples: screen readers (Narrator, JAWS, NVDA, VoiceOver, TalkBack), voice control software, switch control software, refreshable braille displays. In AAEP, assistive technology typically acts as a subscriber.

**Authentication**
The process by which a party proves its identity to another. AAEP delegates authentication to transport layers (TLS, OAuth, OS-level trust, signed JWS). See [§10.3](../10-security.md).

**Authorization**
The process of determining whether an authenticated party is permitted to perform a specific action. See [§10.3.2](../10-security.md).

**`available_languages`**
A field in `localization_hints` listing the languages a producer could provide for this event if requested. See [§11.1.1](../11-internationalization.md).

## B

**Backpressure**
The protocol mechanism by which a subscriber signals that it cannot process events as fast as the producer is producing them, and the producer responds by slowing, batching, or coalescing events. See [§2.2.21](../02-terminology.md) and [§5.6](../05-subscription-handshake.md).

**BCP 14**
IETF Best Current Practice 14, defining the conformance keywords MUST, SHOULD, MAY, etc. Adopted normatively by AAEP. See [§2.1](../02-terminology.md).

**BCP 47**
IETF Best Current Practice 47, defining language tags. AAEP requires BCP 47 tags in `localization_hints`. See [§11.1.2](../11-internationalization.md).

**Bidirectional text**
Text containing mixed left-to-right and right-to-left content. Subscribers handle bidirectional text per Unicode UAX #9. See [§11.4](../11-internationalization.md).

**Blocking contract**
The normative requirement that a producer MUST NOT proceed with a confirmed action until a valid reply arrives or the timeout expires. The blocking contract is AAEP's central safety guarantee. See [§6.1](../06-confirmation-protocol.md).

**Bridge**
A program that translates between AAEP and another protocol, such as MCP, OpenTelemetry, or platform-specific accessibility APIs. Bridges are a form of producer. Examples are in [`examples/bridges/`](../../examples/bridges/).

## C

**Cancellation**
Termination of a session, pending confirmation, or other in-progress operation before its natural completion. See [§4.1.4](../04-core-event-types.md) for session cancellation and [§6.8](../06-confirmation-protocol.md) for confirmation cancellation.

**Capability declaration**
A structured object in a subscription request describing what the subscriber can handle (rate, languages, verbosity, etc.). See [§2.2.13](../02-terminology.md) and [§5.3](../05-subscription-handshake.md).

**Chunk**
A segment of streaming output emitted in a single `agent.output.streaming` event. See [§4.3.3](../04-core-event-types.md).

**Clarification**
A free-form question from a producer to a subscriber requesting additional information from the user. See [§4.4.2](../04-core-event-types.md) and [Chapter 6](../06-confirmation-protocol.md).

**`clarification.reply`**
The reply message a subscriber sends in response to an `agent.awaiting.clarification` event. See [§6.5](../06-confirmation-protocol.md).

**Coalescing**
The process of merging multiple events into a smaller number of events or announcements, typically at natural boundaries (word, sentence, paragraph, completion). See [§2.2.20](../02-terminology.md) and [§5.6](../05-subscription-handshake.md).

**`coalesce_hint`**
A field on streaming output events indicating the boundary the producer has emitted at. Values: `"none"`, `"word"`, `"sentence"`, `"paragraph"`, `"completion"`. See [§4.3.3](../04-core-event-types.md).

**Cognitive load**
The amount of mental effort required to process information. AAEP allows subscribers to declare a `cognitive_load` capability so producers can adapt verbosity. See [§5.3.1.10](../05-subscription-handshake.md).

**Conformance**
The state of an implementation satisfying the requirements of a given AAEP level. Conformance is verified by the open-source test suite. See [Chapter 9](../09-conformance.md).

**Conformance level**
One of three graded requirement sets: Level 1 (Notification), Level 2 (Interactive), Level 3 (Negotiated). See [§2.2.11](../02-terminology.md) and [Chapter 9](../09-conformance.md).

**Confirmation**
A structured request from a producer requesting explicit user consent before an irreversible action. See [§2.2.14](../02-terminology.md) and [§4.4.1](../04-core-event-types.md).

**`confirmation.reply`**
The reply message a subscriber sends in response to an `agent.awaiting.confirmation` event. See [§6.3](../06-confirmation-protocol.md).

**`@context`**
A required envelope field specifying the JSON-LD context for the event. Identifies which vocabularies are in use. See [§3.2.1](../03-event-envelope.md).

**`correlation_id`**
An optional envelope field carrying trace identifiers from observability systems. Useful for cross-system tracing. See [§3.4.2](../03-event-envelope.md).

## D

**`default_decision`**
A field on confirmation events specifying what the producer applies if no reply arrives before timeout. For irreversible high-risk actions, MUST be `"reject"`. See [§6.4.1](../06-confirmation-protocol.md).

**Deprecation**
The process of marking a feature for eventual removal in a future major version. See [§12.4](../12-versioning.md).

## E

**Encoding**
AAEP requires UTF-8 encoding throughout. See [§3.8](../03-event-envelope.md) and [§11.3](../11-internationalization.md).

**End-of-life (EOL)**
The point at which a major version of AAEP no longer receives updates. See [§12.9](../12-versioning.md).

**Envelope**
The fixed structure of fields every AAEP event carries, including `@context`, `type`, `event_id`, `session_id`, `timestamp`, and `producer`. See [§2.2.6](../02-terminology.md) and [Chapter 3](../03-event-envelope.md).

**Errata**
PATCH-level corrections to a published specification version. See [§12.8](../12-versioning.md).

**Event**
A single AAEP message emitted by a producer. See [§2.2.4](../02-terminology.md).

**`event_filters`**
A capability field declaring which event types the subscriber wishes to receive. Critical events bypass filters. See [§5.3.1.7](../05-subscription-handshake.md).

**`event_id`**
A unique identifier for a single event, formatted as `evt_` plus alphanumeric characters. See [§3.2.3](../03-event-envelope.md).

**Event type**
A URI identifying the semantic category of an event. Core event types are in the `aaep:` namespace. See [§2.2.7](../02-terminology.md) and [Chapter 4](../04-core-event-types.md).

**Extension**
A published set of additional event types, fields, capabilities, or transport bindings that supplements but does not modify the core specification. See [§2.2.16](../02-terminology.md) and [Chapter 7](../07-extensions.md).

**Extensions Registry**
The public list of known AAEP extensions, maintained at [governance/EXTENSIONS_REGISTRY.md](../../governance/EXTENSIONS_REGISTRY.md). Registration is not required to publish an extension.

## F

**Fallback chain**
An ordered list of languages the subscriber prefers to receive if its primary language is unavailable. See [§11.1.1](../11-internationalization.md).

**`from_state`**
A field on `agent.state.changed` events identifying the state being exited. See [§4.2.1](../04-core-event-types.md).

**Forward compatibility**
The property that an older subscriber can gracefully consume events from a newer producer. See [§12.6.1](../12-versioning.md).

**Framing**
The mechanism a transport uses to separate one AAEP message from the next on the wire. See [§8.2.2](../08-transports.md).

## G

**Glossary**
This appendix.

**Grapheme cluster**
A sequence of one or more code points that combine to form a single user-perceived character (e.g., a base character plus combining marks). Subscribers handle grapheme clusters correctly per Unicode. See [§11.3.3](../11-internationalization.md).

## H

**Handoff**
The transfer of session control from one agent to another, or to a human. Indicated by `agent.handoff.requested`. See [§4.4.3](../04-core-event-types.md).

**Handshake**
The exchange of `subscription.request`, `subscription.accepted` (or `subscription.rejected`) at the start of a subscription. See [Chapter 5](../05-subscription-handshake.md).

**`honored_capabilities`**
The capabilities the producer commits to in `subscription.accepted`, which MUST NOT be more permissive than the subscriber's request. See [§5.4.4](../05-subscription-handshake.md).

## I

**Idempotency**
The property of an operation being safe to repeat. Reply messages are idempotent in that only the first valid reply is honored; subsequent replies to the same `reply_token` are ignored. See [§6.3.5](../06-confirmation-protocol.md).

**Implementer**
An individual or organization that builds software conforming to AAEP. See [§2.3.2](../02-terminology.md).

**Informative**
Material in the specification that provides context, examples, or recommendations but does not impose conformance requirements. See [§2.4.6](../02-terminology.md).

**Internationalization (i18n)**
The handling of language, locale, character encoding, text direction, and culturally-sensitive content. AAEP treats i18n as a first-class concern. See [Chapter 11](../11-internationalization.md).

**Irreversible**
A flag on action events indicating the action cannot be cleanly undone after execution. Irreversible high-risk actions MUST have `default_decision: "reject"`. See [§4.3.1](../04-core-event-types.md) and [§6.4.1](../06-confirmation-protocol.md).

**ISO 8601**
International standard for date and time format. AAEP timestamps use ISO 8601 / RFC 3339. See [§3.2.5](../03-event-envelope.md).

## J

**JSON**
JavaScript Object Notation. The wire format for AAEP messages. See [RFC 8259].

**JSON-LD**
JSON for Linking Data. AAEP events are JSON-LD documents; the `@context` mechanism enables extensions. See [§3.2.1](../03-event-envelope.md).

**JSON-RPC**
A remote procedure call protocol using JSON. AAEP messages may be carried over JSON-RPC 2.0 envelopes, particularly for stdio transports. See [§B.6](B-transport-bindings.md).

**JWS** (JSON Web Signature)
[RFC 7515]. Used at Conformance Level 3 to sign producer manifests cryptographically. See [§10.4](../10-security.md).

## L

**Language tag**
A BCP 47-formatted string identifying a language, region, script, and optional variant. See [§11.1.2](../11-internationalization.md).

**`languages`**
A capability field listing languages the subscriber can accept, in preference order. See [§5.3.1.3](../05-subscription-handshake.md).

**Last-Event-ID**
The SSE-standard mechanism for resuming a stream after disconnection. See [§B.1.5](B-transport-bindings.md).

**Level 1 (Notification)**
The lowest AAEP conformance level. Producers emit events; subscribers consume them. No reply channel required. See [§9.3](../09-conformance.md).

**Level 2 (Interactive)**
Adds the confirmation/clarification protocol with reply channel. See [§9.4](../09-conformance.md).

**Level 3 (Negotiated)**
Adds the full subscription handshake, backpressure, coalescing negotiation, and optional signed manifests. See [§9.5](../09-conformance.md).

**Localization hint**
A structured object describing language, locale, and text characteristics of an event's human-readable strings. See [§2.2.10](../02-terminology.md) and [§3.3.3](../03-event-envelope.md).

**LTS** (Long-Term Support)
A designation given to selected MAJOR versions, indicating extended support periods. See [§12.9.1](../12-versioning.md).

## M

**Manifest**
A producer-published declaration of capabilities, supported event types, transports, languages, and extensions. Discoverable at `/.well-known/aaep-manifest.json`. See [§2.2.19](../02-terminology.md) and [§5.10](../05-subscription-handshake.md).

**`max_events_per_second`**
A capability field declaring the maximum rate at which the subscriber can process events. Critical events are exempt. See [§5.3.1.1](../05-subscription-handshake.md).

**MCP** (Model Context Protocol)
An open protocol from Anthropic standardizing how LLM applications connect to tools and resources. AAEP is complementary to MCP, not competitive. See [§1.4](../01-introduction.md).

**mTLS** (Mutual TLS)
A TLS-based authentication mechanism in which both parties present X.509 certificates. The strongest authentication for cross-host AAEP. See [§10.3.1](../10-security.md).

**Multi-subscriber**
A configuration in which a single producer serves multiple concurrent subscribers, each with independent capability negotiation. See [§5.9](../05-subscription-handshake.md).

**MUST / MUST NOT / SHOULD / MAY**
Conformance keywords per BCP 14. See [§2.1](../02-terminology.md).

## N

**Namespace**
A URI under which extensions publish their event types, fields, and capabilities. The `aaep:` namespace is reserved for the core specification. See [§7.3](../07-extensions.md).

**NFC / NFD / NFKC / NFKD**
Unicode normalization forms. Producers SHOULD use NFC. Subscribers MUST accept any form. See [§11.3.2](../11-internationalization.md).

**Non-conforming**
An implementation that fails to satisfy normative requirements for a claimed conformance level. See [Chapter 9](../09-conformance.md).

**Normative**
Material in the specification that defines conformance requirements. See [§2.4.6](../02-terminology.md).

## O

**OAuth 2.0**
An authorization framework, often used to issue bearer tokens for subscriber authentication. See [§10.3.1](../10-security.md).

**Output streaming**
The emission of agent output in chunks, typically as the LLM produces tokens. See [§4.3.3](../04-core-event-types.md).

## P

**`pace_wpm`**
A capability field indicating the subscriber's announcement pace in words per minute. Helps the producer estimate timing for coalescing. See [§5.3.1.11](../05-subscription-handshake.md).

**Payload**
The portion of an AAEP event beyond the envelope, containing event-type-specific fields.

**Prefix**
A short identifier (e.g., `medai`, `azlearn`) used to compactly reference an extension's namespace in JSON. See [§7.3](../07-extensions.md).

**PHI** (Protected Health Information)
Sensitive health-related data subject to regulation (HIPAA in the US). AAEP's privacy considerations apply. See [§10.5](../10-security.md).

**Producer**
The party that emits AAEP events. Typically an AI agent. See [§2.2.2](../02-terminology.md).

**Producer identity**
A structured value identifying a producer, carried in the `producer` envelope field. Includes `agent_id` and optional other fields. See [§3.2.6](../03-event-envelope.md).

**Profile**
A published specification combining a conformance level with required extensions and additional constraints for a domain. See [§2.2.17](../02-terminology.md) and [§7.10](../07-extensions.md).

**Progress**
Incremental progress toward task completion, reported via `agent.progress.updated`. See [§4.2.2](../04-core-event-types.md).

## R

**Rate limit**
A maximum events-per-second cap negotiated during subscription. See [§5.3.1.1](../05-subscription-handshake.md).

**Reconnection**
Re-establishing a transport connection after failure. Behavior is transport-specific. See [§8.7](../08-transports.md).

**Renegotiation**
A subscriber's update of capabilities mid-subscription via `subscription.renegotiate`. See [§5.7](../05-subscription-handshake.md).

**Reply**
A subscriber's response to a blocking event (confirmation or clarification). See [Chapter 6](../06-confirmation-protocol.md).

**Reply forwarding**
A pattern where one subscriber forwards a confirmation to another subscriber that has reply capability. See [§6.6](../06-confirmation-protocol.md).

**`reply_token`**
An opaque correlation identifier binding a reply to its originating event. Single-use; not a security credential. See [§2.2.15](../02-terminology.md) and [§6.2](../06-confirmation-protocol.md).

**Reversibility**
The property of an action being undoable. Values: `"reversible"`, `"reversible_with_effort"`, `"irreversible"`. See [§4.4.1](../04-core-event-types.md).

**RFC 2119 / RFC 8174**
IETF standards defining conformance keywords. Together they form BCP 14. See [§2.1](../02-terminology.md).

**RFC 3339**
IETF standard for timestamps. AAEP timestamps follow RFC 3339. See [§3.2.5](../03-event-envelope.md).

**RFC 5646**
IETF standard for language tags. Together with [RFC 5646bis], forms BCP 47. See [§11.1.2](../11-internationalization.md).

**RFC 8259**
IETF standard for JSON. AAEP messages are valid JSON per RFC 8259. See [§3.8](../03-event-envelope.md).

**RFC 9110**
IETF standard for HTTP semantics. Cited as inspiration for AAEP's versioning approach. See [NOTICE](../../NOTICE).

**Risk level**
A classification of an action's potential impact: `"low"`, `"medium"`, `"high"`. Affects required `default_decision`. See [§4.3.1](../04-core-event-types.md) and [§6.4.1](../06-confirmation-protocol.md).

**RTL** (Right-to-left)
Text direction for languages like Arabic, Hebrew, Persian. AAEP supports RTL via `text_direction` in `localization_hints`. See [§11.4](../11-internationalization.md).

## S

**Schema**
A JSON Schema document defining the structure of an AAEP event, message, or capability. Located in [`schemas/`](../../schemas/).

**SemVer** (Semantic Versioning)
The versioning scheme AAEP follows: MAJOR.MINOR.PATCH. See [§12.1](../12-versioning.md).

**`sequence_number`**
An optional envelope field providing per-session event ordering. See [§3.4.1](../03-event-envelope.md).

**Session**
A logical unit of agent activity, bracketed by `agent.session.started` and a terminal lifecycle event. See [§2.2.5](../02-terminology.md).

**`session_id`**
The identifier linking all events of a session, formatted as `sess_` plus alphanumeric characters. See [§3.2.4](../03-event-envelope.md).

**Signed manifest**
A producer manifest cryptographically signed using JWS, used at Conformance Level 3. See [§10.4](../10-security.md).

**SSE** (Server-Sent Events)
A web standard for server-to-client streaming over HTTP. A recommended AAEP transport. See [§8.5.1](../08-transports.md) and [§B.1](B-transport-bindings.md).

**State**
The producer's internal status (idle, thinking, calling_tool, writing_output, awaiting_input, deciding, handing_off). Communicated via `agent.state.changed`. See [§4.2.1](../04-core-event-types.md).

**stdio JSON-RPC**
A transport pattern where producer and subscriber communicate via stdin/stdout using JSON-RPC 2.0. See [§B.6](B-transport-bindings.md).

**Streaming**
The continuous emission of output chunks, typically tokens from an LLM. See [§4.3.3](../04-core-event-types.md).

**`subscriber_id`**
A stable string identifier for a subscriber, declared in `subscription.request`. See [§5.2.1](../05-subscription-handshake.md).

**Subscription**
A logical channel between a single subscriber and a single producer over which events flow. See [§2.2.12](../02-terminology.md).

**`subscription_id`**
A producer-generated identifier for an established subscription. See [§5.4.1](../05-subscription-handshake.md).

**Summary fields**
The `summary_terse`, `summary_normal`, and `summary_detailed` fields providing event content at three verbosity levels. See [§2.2.8](../02-terminology.md).

## T

**Terminal lifecycle event**
One of `agent.session.completed`, `agent.session.errored`, or `agent.session.cancelled`. Exactly one terminates every session. See [§4.1](../04-core-event-types.md).

**`text_direction`**
A field in `localization_hints` indicating writing direction. Values: `"ltr"`, `"rtl"`, `"auto"`. See [§11.4.1](../11-internationalization.md).

**Timeout**
The duration after which a producer applies `default_decision` to an unanswered confirmation or clarification. Specified per-event by `timeout_seconds`. See [§6.4](../06-confirmation-protocol.md).

**Timestamp**
A required envelope field indicating when the event was emitted, in RFC 3339 format. See [§3.2.5](../03-event-envelope.md).

**TLS** (Transport Layer Security)
Cryptographic protocol providing transport-layer authentication, integrity, and confidentiality. AAEP requires TLS 1.2+ for cross-host transports. See [§10.1.2](../10-security.md).

**Token bucket**
A rate-limiting algorithm in which the budget for events is replenished smoothly over time. Producers implement backpressure via token bucket or equivalent. See [§5.6.1](../05-subscription-handshake.md).

**Tool**
A function or external service that an agent invokes to perform an action or retrieve information. See [§2.3.4](../02-terminology.md).

**`tool_call_id`**
A correlator linking an `agent.tool.invoked` to its matching `agent.tool.completed`. See [§4.3.1](../04-core-event-types.md).

**Transport**
The underlying mechanism by which AAEP messages travel between parties. Examples: SSE, WebSocket, named pipes, Unix sockets, gRPC, stdio. See [§2.2.18](../02-terminology.md) and [Chapter 8](../08-transports.md).

**Type**
A required envelope field identifying the event's semantic category. See [§3.2.2](../03-event-envelope.md).

## U

**UAX #9** (Unicode Annex 9)
The Unicode Bidirectional Algorithm. Subscribers use UAX #9 to render bidirectional text correctly. See [§11.4](../11-internationalization.md).

**UIA** (UI Automation)
Microsoft Windows accessibility API. AAEP complements UIA. See [§1.2](../01-introduction.md).

**Unicode**
The character encoding standard underlying UTF-8. AAEP uses Unicode throughout. See [§11.3](../11-internationalization.md).

**Unix domain socket**
A local-host IPC mechanism on Unix-like systems. A recommended AAEP transport. See [§B.4](B-transport-bindings.md).

**Urgency**
The producer's recommended priority for an event. Values: `"background"`, `"normal"`, `"critical"`. See [§2.2.9](../02-terminology.md) and [§3.3.2](../03-event-envelope.md).

**User**
The human at whom the agent's activity is directed. Not an addressable party in the protocol; AAEP's contract is between producers and subscribers. See [§2.3.1](../02-terminology.md).

**UTF-8**
The character encoding required for AAEP messages. See [§3.8](../03-event-envelope.md).

## V

**Verbosity**
The level of detail at which information is communicated. Values: `"terse"`, `"normal"`, `"detailed"`. Verbosity is a presentation hint, not a content filter. See [§2.2.8](../02-terminology.md).

**Version**
The protocol's specification version, following SemVer. See [Chapter 12](../12-versioning.md).

## W

**WAI-ARIA**
W3C Accessible Rich Internet Applications. The mature standard for web UI accessibility. AAEP complements WAI-ARIA. See [§1.2](../01-introduction.md).

**Web of trust**
A decentralized model where trust is established by chains of cryptographic signatures rather than central authorities. One of several keys-distribution mechanisms supported by AAEP. See [§10.4.3](../10-security.md).

**WebSocket**
A bidirectional web protocol over a single TCP connection. A recommended AAEP transport. See [§8.5.2](../08-transports.md) and [§B.2](B-transport-bindings.md).

**Windows named pipe**
A Microsoft IPC mechanism. A recommended AAEP transport. See [§B.3](B-transport-bindings.md).

## Where to go next

For the complete list of normative and informative references cited throughout this specification, see [Appendix D (References)](D-references.md).

For the body of the specification itself, return to [SPEC.md](../SPEC.md) and navigate from there.

[RFC 5234]: https://www.rfc-editor.org/rfc/rfc5234
[RFC 8259]: https://www.rfc-editor.org/rfc/rfc8259
[RFC 7515]: https://www.rfc-editor.org/rfc/rfc7515
[RFC 5646bis]: https://www.rfc-editor.org/rfc/rfc5646
