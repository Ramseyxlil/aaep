# AAEP Frequently Asked Questions

Answers to the questions developers, AT vendors, and standards reviewers ask most often. Use Ctrl+F to find your question quickly.

---

## About AAEP

### What is AAEP?

AAEP (Agent Accessibility Event Protocol) is an open, vendor-neutral standard that lets AI agents communicate their lifecycle, state, tool invocations, and confirmation requests to assistive technology in a structured, machine-readable way. The goal: every screen reader, voice control system, and other AT can work with every AI agent, without bespoke integrations.

### Who is AAEP for?

Three audiences:

1. **Agent and framework developers** who want their AI products to be usable by people with disabilities.
2. **Assistive technology vendors** (Narrator, NVDA, JAWS, VoiceOver, TalkBack, voice control, switch input, braille) who want a standard way to consume AI agent state.
3. **End users with disabilities** who benefit when AAEP-conforming agents and AT interoperate without integration work.

### Why does AAEP exist?

AI agents are everywhere — in IDEs, browsers, customer support, productivity software. None of them work consistently with assistive technology because there is no standard way for an agent to say "I'm about to do something irreversible — please ask the user to confirm." Each AT vendor would have to write custom integration for each agent vendor. The combinatorial explosion is unmanageable. AAEP solves this with one protocol everyone can implement.

### Is AAEP free to use?

Yes. The specification is licensed under Creative Commons Attribution 4.0; the reference code is MIT. Anyone can implement, ship, or extend AAEP without paying license fees.

---

## Relationship to other protocols and standards

### How does AAEP relate to MCP (Model Context Protocol)?

AAEP and MCP solve different problems and are complementary, not competitive.

- **MCP** lets agents discover and call tools. It's about agent-to-tool communication.
- **AAEP** lets agents tell users (via AT) what they're doing. It's about agent-to-user communication.

A production agent typically uses both: MCP to invoke tools, AAEP to announce what it's doing to a screen reader. The [`examples/bridges/mcp-aaep-bridge/`](../examples/bridges/mcp-aaep-bridge/) directory shows a working integration.

### How does AAEP relate to WAI-ARIA?

ARIA addresses the accessibility of *rendered UI* (semantic roles, states, properties on visible elements). AAEP addresses the accessibility of *agent state* (what the agent is thinking, doing, and about to do).

A web page can be ARIA-conformant. An AI agent's reasoning loop cannot be — ARIA has no concept of "the model is about to call a tool." AAEP fills that gap.

### How does AAEP relate to UIA, AT-SPI, and other platform accessibility APIs?

Platform APIs (Microsoft UI Automation, Linux AT-SPI, macOS Accessibility API, Android Accessibility) tell AT about UI elements. AAEP tells AT about agent behavior. They operate at different layers; a complete accessible agent product implements both.

The recommended pattern: your agent's UI is exposed via the platform API, and your agent's reasoning/tool/output events are emitted via AAEP. The AT consumes both streams.

### How does AAEP relate to LangChain callbacks?

LangChain's `BaseCallbackHandler` is a framework-internal mechanism. AAEP is a cross-framework, cross-vendor protocol. A LangChain `BaseCallbackHandler` that emits AAEP events lets a LangChain agent be consumed by any AAEP-aware AT. See the [Implementer's Guide §3.1](IMPLEMENTERS_GUIDE.md) for the mapping.

### How does AAEP relate to OpenTelemetry?

OpenTelemetry is for observability (metrics, traces, logs) targeted at developers and SREs. AAEP is for accessibility, targeted at end users via assistive technology. The protocols can share `correlation_id` so observability traces and accessibility events can be cross-referenced. The bridge example at [`examples/bridges/opentelemetry-aaep-bridge/`](../examples/bridges/opentelemetry-aaep-bridge/) demonstrates this.

---

## Practical adoption

### Do I need W3C approval before using AAEP?

No. AAEP is an open standard published under CC-BY-4.0. Anyone can implement and ship it today. The W3C Community Group path (see [governance/ROADMAP.md](../governance/ROADMAP.md)) is for additional credibility and ecosystem coordination, not for permission.

### Can I use AAEP with closed-source models like GPT-5 or Claude?

Yes. AAEP doesn't care what model is producing tokens. You wrap your agent loop (which calls the model) with AAEP emissions. The model itself doesn't need to know about AAEP.

### How much work is it to add AAEP to my existing agent?

Depends on your framework:

- **If your framework has callbacks/middleware** (LangChain, Microsoft Agent Framework, Semantic Kernel): 200-400 lines of glue code, plus configuration.
- **If you control your agent loop directly**: 100-300 lines to wrap the loop with AAEP emissions.
- **If you're building from scratch**: integrate at the start; 50-150 lines woven into your agent structure.

Most teams report 2-5 days of work to reach Conformance Level 1, plus an additional 1-2 weeks to reach Level 2 with the confirmation flow.

### What's the performance impact?

Negligible in normal operation. Each event is a small JSON object emitted via your existing transport. At sustained 5 events/sec (a busy agent), the overhead is under 0.1% CPU on typical hardware.

The exception: signed manifest verification at Level 3 adds ~5ms per subscription handshake. This is one-time per subscription, not per event.

### Does AAEP work in browser-only environments?

Yes. AAEP events are just JSON. A browser-based agent can emit them via SSE (Server-Sent Events) or WebSocket. The Quickstart's pattern adapts to fetch streaming or any web transport.

### Does AAEP work on mobile?

Yes. iOS apps emit AAEP events to a VoiceOver-bridge subscriber. Android apps emit to a TalkBack-bridge subscriber. Both are reference-implemented; see [`examples/subscribers/`](../examples/subscribers/).

---

## Conformance and testing

### What are the three conformance levels?

- **Level 1 (Notification)**: producer emits events, subscriber consumes. No reply channel.
- **Level 2 (Interactive)**: adds the confirmation/clarification reply protocol.
- **Level 3 (Negotiated)**: adds the full subscription handshake, backpressure, coalescing negotiation, and optional signed manifests.

A product can claim Level 1, Level 2, or Level 3. Most commercial products eventually target Level 2.

### How do I claim conformance?

Run the conformance test suite at your target level and publish the report. There is no central certifier; AAEP uses self-certification with public reports.

### Can I be "partially" conformant?

No. You're either conformant at a level or you're not. Partial implementations should claim only the highest level they fully pass.

### What if I disagree with a conformance test result?

Open an issue. Either your implementation has a bug, or the test has a bug, or the spec is ambiguous. All three happen and the project welcomes the reports.

---

## Specific concerns

### How do I handle PHI / HIPAA?

AAEP has no built-in PHI handling, but the protocol is designed to make HIPAA compliance practical:

- The `summary_*` fields are user-facing strings; never put raw PHI here unless the user has explicitly consented to AT access to that data.
- The `extensions` envelope object can carry audit-trail IDs (see the medical extension example).
- Conformance Level 3's signed manifest mechanism provides cryptographic chain-of-custody for compliance audits.

A dedicated HIPAA extension is in development; see the registry.

### What about multilingual content?

AAEP treats multilingual content as first-class. Every event can carry `localization_hints.primary_language` (BCP 47 tag) and per-chunk `language` overrides on streaming events. The multilingual African languages extension is the canonical worked example. See the [Subscribers' Guide §8](SUBSCRIBERS_GUIDE.md) for details.

### What about privacy?

Three layers:

1. **At the protocol level:** Producers MUST NOT include secrets in `args_summary` or `summary_*` fields. The spec says so normatively.
2. **At the transport level:** Use TLS for cross-host transports. Local transports (stdio, Unix sockets) inherit OS-level isolation.
3. **At the subscriber level:** Subscribers SHOULD log envelopes only (type, IDs, timestamps), not full payloads.

See [Chapter 10 of the spec](../spec/10-security.md) for the threat model.

### What about security?

AAEP defines a threat model with 8 categories (impersonation, replay, MITM, etc.) and mitigations for each. Level 3 mandates cryptographically signed manifests. Authentication is delegated to the transport (TLS, OAuth, mTLS, OS trust).

### How does backpressure work?

The subscriber declares `max_events_per_second` in the handshake. The producer implements a token bucket. When the bucket is empty, non-critical events are coalesced or dropped. **Critical events bypass the bucket** — they always get through. See [Implementer's Guide §6](IMPLEMENTERS_GUIDE.md) for the implementation.

### How does coalescing work for streaming output?

Producers emit chunks with a `coalesce_hint` indicating natural boundaries (`word`, `sentence`, `paragraph`, `completion`). Subscribers buffer based on their preferred boundary and the user's cognitive-load setting. The default for screen readers is sentence-level coalescing.

---

## Building extensions

### Can I make a domain-specific extension?

Yes. See the [Extensions Guide](EXTENSIONS_GUIDE.md) for the complete process. Extensions add new event types, capabilities, and fields without touching the core.

### Do I need permission to publish an extension?

No. AAEP has no central authority that approves extensions. You can publish independently. Registration in the official registry is optional and provides visibility, not endorsement.

### Can my extension override safety rules?

No. The core's safety rules (especially the `default_decision: "reject"` requirement for irreversible+high-risk actions) cannot be weakened by extensions. An extension that tried to override them would fail conformance.

### Can I make my extension proprietary?

Yes. Extensions can have any license you choose. However, an extension under a proprietary license excludes adopters who require open standards. Most successful extensions use CC-BY-4.0 or similar.

---

## Project status and governance

### Is AAEP a real standard?

It's an open specification with public governance, conformance tests, and reference implementations. It's not yet a W3C Recommendation (that path takes 3-5 years for any protocol). It IS already a deployable protocol with real implementations.

### Who maintains AAEP?

The project was founded by Abdulrafiu Izuafa and is maintained by a community of contributors. Governance is documented in [governance/GOVERNANCE.md](../governance/GOVERNANCE.md). Contributors come from agent framework vendors, AT vendors, accessibility researchers, and end-user communities.

### What's the path to W3C?

1. **Year 1 (2026-2027)**: Build community and reach 10+ implementations.
2. **Year 2**: Form a W3C Community Group.
3. **Year 3-4**: Move to W3C Working Group with vendor sponsorship.
4. **Year 5+**: W3C Recommendation status.

This is the standard path for new accessibility protocols. See [governance/ROADMAP.md](../governance/ROADMAP.md).

### How do I contribute?

See [governance/CONTRIBUTING.md](../governance/CONTRIBUTING.md). Common contributions: improving the spec, adding examples, building reference implementations, writing extensions, running conformance tests on your product, joining discussions.

### Is there a paid commercial version?

No. AAEP is open. Commercial entities can build paid products that implement AAEP, but the protocol itself is free.

---

## Hard questions

### What happens if Microsoft never adopts AAEP?

The protocol still works for everyone who does adopt it. Adoption is incremental; even one vendor adopting AAEP makes AT integration meaningfully easier for that vendor's users. The protocol's value compounds with each adopter but doesn't depend on any one of them.

### What happens if AAEP fails to gain traction?

The work that produced it isn't lost. A well-designed protocol that didn't reach mass adoption still:

- Documented a problem and a feasible solution
- Provided reference implementations and code patterns others can borrow
- Pushed adjacent protocols (MCP, OpenTelemetry, ARIA) to address agent accessibility
- Provided a baseline for the next attempt

Open standards work this way: many protocols fail to reach Recommendation status, but their architectural ideas often live on in successors.

### Why should I trust a young protocol?

You shouldn't trust it on faith. You should:

1. Read the spec and confirm the design is sound.
2. Run the conformance suite against your test implementation.
3. Talk to other adopters about their experience.
4. Verify the safety rules are mechanically enforced (the JSON Schema for `agent.awaiting.confirmation` does this).

A protocol earns trust by being honest about its limitations, transparent about its decisions, and verifiable in its claims. AAEP is designed to support all three.

### Why "Accessibility" in the name?

Because the protocol's reason for existing is to make AI agents work with assistive technology for users with disabilities. That's the core problem. Some events in AAEP are useful beyond accessibility (the same blocking-confirmation flow is good for sighted users too), but the protocol's design priorities — what it normatively requires, what it enforces, what it refuses to compromise on — are set by accessibility needs.

### Could AAEP's design also help users without disabilities?

Yes, and it does. The confirmation flow protects every user from accidental irreversible actions. The streaming-with-coalescing pattern improves output quality for any consumer. The capability handshake makes integration cleaner for any subscriber. Accessibility-driven design tends to benefit everyone — that's been the story of curb cuts, captions, and ARIA. AAEP follows the same pattern.

---

## Still have a question?

- File an issue on the AAEP repository
- Search past discussions
- Read the [specification](../spec/SPEC.md) for normative details
- Email questions to the maintainer (see [governance/MAINTAINERS.md](../governance/MAINTAINERS.md))

The FAQ grows from real questions. If you ask something that isn't here, your question is worth adding.
