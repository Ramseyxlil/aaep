# AAEP Roadmap

This document describes the planned evolution of the Agent Accessibility Event Protocol. It covers the next 18 months in detail and outlines longer-term goals more loosely.

**Roadmap status:** This roadmap is informational, not contractual. Items can be added, reordered, or removed via the ACP process described in [`GOVERNANCE.md`](./GOVERNANCE.md). The version policy in `GOVERNANCE.md` §5 is binding regardless of what this document says.

**Last updated:** June 30, 2026 (v1.0.0 launch)

---

## Where we are: v1.0.0 (June 2026)

Released contents:

- The AAEP v1.0.0 specification (17 chapters + 4 appendices)
- 21 JSON Schemas (envelope + 12 core events + 4 handshake + 4 context)
- Conformance suite covering Levels 1-3
- 5 reference producer implementations (Python: minimal, LangChain, Anthropic SDK, Microsoft Agent Framework; TypeScript: minimal)
- CLI tools: `aaep-validate`, `aaep-capture`, `aaep-replay`
- Implementer's Guide, Quickstart Guide, 5 pattern deep dives

**Current adoption status:** Pre-launch. The protocol exists; production implementations are forthcoming.

---

## Q3 2026 (June – August 2026): v1.0.x stability

**Focus:** Production-hardening through feedback from initial implementers.

Planned in this period:

- **Bug fixes** as discovered by early adopters
- **Documentation improvements** based on real-world implementation experience
- **Conformance suite refinements** — additional edge case tests, clearer failure messages
- **First subscriber reference implementation** — a Python CLI debug subscriber that prints captured AAEP streams in a screen-reader-friendly format
- **Translation initiatives** — Quickstart Guide translated into Yoruba, Hausa, Igbo, Spanish, Portuguese, French (volunteer-driven; we facilitate, don't gate)

Patch releases (1.0.1, 1.0.2, etc.) ship as needed. We aim for at most one patch release per month.

**Will not ship in this period:** New events, new conformance levels, schema changes. We need real implementation experience before evolving the protocol.

---

## Q4 2026 (September – November 2026): v1.1.0 — Subscribers and bridges

**Focus:** Demonstrate AAEP works end-to-end by shipping subscriber examples and the first bridges.

Planned for v1.1.0:

- **NVDA add-on prototype** — open-source NVDA add-on that subscribes to AAEP producers and routes events to NVDA's speech engine. This is the first reference subscriber for a major screen reader.
- **Web subscriber (React)** — a browser-based subscriber suitable for embedding in agent UIs, with ARIA-live region integration.
- **MCP bridge** — bidirectional bridge between AAEP and the Model Context Protocol. Allows MCP-aware tools to participate in AAEP sessions.
- **OpenTelemetry bridge** — convert AAEP events to OpenTelemetry spans for unified observability with existing telemetry stacks.
- **First minor release** — v1.1.0 with any new optional fields needed for subscribers (`pace_wpm` for TTS throttling, `cognitive_load` for verbosity hints, all backward-compatible).

This is the period when AAEP demonstrably becomes a working end-to-end protocol, not just a producer specification.

**Stretch goals (will happen if capacity allows):**

- VoiceOver subscriber prototype (macOS)
- Orca subscriber prototype (Linux GNOME)

---

## Q1 2027 (December 2026 – February 2027): v1.2.0 — Extensions ecosystem

**Focus:** Show that AAEP's extension mechanism (`extensions` namespace) works in practice.

Planned for v1.2.0:

- **Multilingual extension (1.0)** — first-class support for non-English languages in event content. Includes:
  - Yoruba, Hausa, Igbo summary translations as canonical examples
  - Right-to-left language support (Arabic, Hebrew)
  - Language detection hints
  - Multi-language fallback chains
- **Medical extension (1.0)** — AAEP profile for healthcare agents with HIPAA-aware redaction, BAA-friendly capability negotiation, audit log integration.
- **Conformance suite update** — Levels 1-3 unchanged. New optional conformance dimensions: "multilingual conformance" and "medical-profile conformance" as orthogonal labels.

This release proves AAEP's extension model is real and not just aspirational.

---

## Q2 2027 (March – May 2027): v1.3.0 — Adoption and foundation transition begins

**Focus:** Initiate the foundation transition described in [`GOVERNANCE.md`](./GOVERNANCE.md) §9.

By this point we expect:

- At least 5 production implementations across at least 3 distinct organizations
- Active translation in at least 5 languages
- First major AT vendor in adoption discussions (NVDA, JAWS, VoiceOver, Narrator, or Orca)
- Steering Committee expanded from 1 person (Protocol Architect) to 5 people per the bootstrap-exit rules

Foundation transition activities:

- **Foundation candidate selection** — Steering Committee evaluates Linux Foundation, OpenSSF, W3C, GNOME Foundation
- **Trademark transfer preparation** — documentation, legal review
- **Pre-transition audit** — security audit, governance audit, license compliance audit

v1.3.0 itself contains minor improvements; the strategic work this quarter is governance, not code.

---

## H2 2027 (June – December 2027): v1.4 and v1.5

By this point AAEP should have:

- Multiple AT vendors with at least preview/beta support
- 10+ production implementations
- An active extensions ecosystem with at least one third-party extension
- A funded foundation with full-time staff capacity (legal, infrastructure, communications)

Planned releases:

- **v1.4.0 (Q3 2027)** — Education extension, financial services extension, third-party extension support polish
- **v1.5.0 (Q4 2027)** — Performance optimizations based on production scale data; new conformance Level 4 (high-throughput compliance)

---

## 2028 and beyond: long-term goals

These are vision items, not commitments. They will only materialize if community interest and resources align.

### Production maturity

- Wide adoption across major AT vendors (Narrator, NVDA, JAWS, VoiceOver, Orca all have native AAEP support)
- AAEP as default expected interface for AI agents shipped by Microsoft, Anthropic, Google, Apple, and Mozilla
- Reference implementations maintained for at least 5 languages by community contributors

### Standards body publication

- AAEP submitted to W3C or IETF as a proposed standard
- Process for handling standards-body feedback while preserving protocol integrity
- Translation of the spec into language understood by standards body reviewers

### Adjacent protocols

- AAEP-compatible profile for IoT accessibility (Matter, BLE)
- AAEP-compatible profile for in-game accessibility (working with the Accessibility Game Awards community)
- AAEP-compatible profile for educational and AAC use cases

### Long-term technical evolution

- v2.0.0 — only after at least 4 years of v1.x stability. v2.0.0 will be backward-incompatible only if v1.x cannot support real user needs. The bar for breaking compatibility is deliberately high.

Earliest plausible v2.0.0 release: 2030.

---

## What we're explicitly NOT doing

Setting expectations matters. These are things AAEP will not become:

### We will not become a transport protocol

AAEP defines event schemas and semantics. It does not define a wire transport. Producers may serve AAEP over HTTP/SSE, WebSocket, gRPC, IPC, or any other transport. We provide examples and recommendations, but the transport is the implementer's choice.

We will not introduce mandatory transport bindings.

### We will not become a model alignment specification

AAEP is about how agents communicate with AT users. It does not specify how agents should behave at the model level — what should be aligned, what should be filtered, how RLHF should be tuned. Those are separate questions; AAEP only addresses what agents must surface to AT once they decide to act.

We will not introduce AAEP-mandated alignment requirements.

### We will not duplicate existing accessibility specs

ARIA, WCAG, ATAG, EPUB Accessibility, and other established specs cover their domains. AAEP focuses on a specific gap (live agent-AT communication) that those specs don't address. Where they overlap (e.g., screen reader announcement semantics), we defer to them and provide bridges.

We will not redefine ARIA-live, alt text, or heading semantics.

### We will not gate participation

AAEP's specification is freely usable. Conformance levels are objective and verifiable. No certification body. No paid memberships. No required licenses for implementations (the spec is CC-BY-4.0; reference code is MIT).

We will not introduce paid certifications or required memberships.

### We will not chase fashion

LLM ecosystem evolution is dramatic. New frameworks emerge monthly. AAEP will support major patterns through bridges and adapters but will not restructure the protocol around any specific framework. AAEP must outlive the current AI hype cycle.

We will not bake LangChain, AutoGen, MCP, or any single framework into the protocol's core.

---

## Priorities can change

This roadmap reflects current intentions. It can be revised by:

- An ACP at significant or constitutional decision tier (per [`GOVERNANCE.md`](./GOVERNANCE.md) §4)
- A Steering Committee vote on quarterly priorities
- Community-driven shifts (if a working group identifies a higher-priority item)

When this roadmap changes materially, the changes appear here with a date and ACP reference. The previous version is preserved in git history.

---

## How to influence the roadmap

If you want to:

- **Speed up an item:** Volunteer to implement it. Many roadmap items are scoped to land in a quarter only because someone has committed to do them. Adding capacity moves the date.
- **Add an item:** File an ACP. Roadmap items come from accepted ACPs.
- **Remove an item:** Argue for de-prioritization in a Steering Committee discussion. We periodically review whether listed items still warrant priority.
- **Question the priority order:** Open a Discussion. The roadmap reflects current judgment, not an unmovable plan.

Community involvement shapes the roadmap. The Steering Committee makes the final call, but they listen.

---

## Acknowledgments

This roadmap is informed by:

- The Python Steering Council's annual priorities documents
- The Rust roadmap process
- The W3C Accessible Platform Architectures Working Group charters
- The Open Source Initiative's standards evolution guidance

We thank these communities for showing how to evolve specifications openly and predictably over multi-year horizons.
