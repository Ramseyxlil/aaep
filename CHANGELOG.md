# Changelog

All notable changes to the AAEP specification, schemas, conformance test suite, and reference materials are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and AAEP versioning adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html) with the following protocol-specific conventions:

- **Major version (X.0.0)** — Breaking changes to the wire format, event semantics, or subscription handshake. Implementations conforming to a prior major version may no longer conform.
- **Minor version (0.X.0)** — Backward-compatible additions: new event types, new optional fields, new conformance levels, new transport bindings, or new extension mechanisms.
- **Patch version (0.0.X)** — Clarifications, typo fixes, schema corrections that do not change semantics, and editorial improvements.

Conformance claims should reference the major version (e.g., "AAEP v1 Level 2 conformant"). Implementations may also claim conformance to a specific minor version when relying on features introduced in that minor version.

The process for proposing changes is documented in [governance/CONTRIBUTING.md](governance/CONTRIBUTING.md). Substantial changes follow the AAEP Change Proposal (ACP) workflow described in [governance/proposals/README.md](governance/proposals/README.md).

---

## [Unreleased]

Changes prepared for the next release will be listed here. When a release is cut, this section is renamed to the new version number and a fresh `[Unreleased]` block is created above it.

### Added
- *Nothing yet.*

### Changed
- *Nothing yet.*

### Deprecated
- *Nothing yet.*

### Removed
- *Nothing yet.*

### Fixed
- *Nothing yet.*

### Security
- *Nothing yet.*

---

## [0.1.0-draft] — 2026-05-24

Initial public draft of the AAEP specification.

This release is marked `draft` because it has not yet undergone formative review with disabled developers, has not been submitted to a standards body, and may change substantially in response to early implementer feedback. Implementations against `0.1.0-draft` should not yet be considered stable.

### Added

#### Specification (`spec/`)
- Initial specification document covering twelve core event types organized into four families (Lifecycle, Reasoning State, Tool and Action, Human-in-the-Loop).
- Event envelope definition with required fields: `@context`, `type`, `event_id`, `session_id`, `timestamp`, `producer`, `verbosity`, `urgency`, `localization_hints`.
- Subscription handshake protocol with capability negotiation.
- Confirmation reply protocol with reply tokens and timeout semantics.
- Extension mechanism via JSON-LD `@context` arrays and namespaced `type` URIs.
- Conformance levels 1 (Notification), 2 (Interactive), and 3 (Negotiated).
- Transport requirements abstraction; non-normative appendix listing SSE, WebSocket, local IPC (Windows named pipes, Unix domain sockets), and stdio JSON-RPC as conforming transports.
- Security and threat-model section addressing producer dishonesty, information disclosure, and denial-of-service via event flood.
- Internationalization guidance covering language declaration, locale negotiation, and Unicode handling.

#### Schemas (`schemas/`)
- JSON Schema definitions for the envelope and each of the twelve core event types.
- JSON Schema definitions for subscription request, subscription accepted, subscription rejected, and confirmation reply messages.
- Canonical JSON-LD context document at `schemas/context/aaep-v1.jsonld`.

#### Guides (`guides/`)
- Implementer's Guide covering integration patterns for middleware-based, callback-based, decorator-based, event-emitter-based, and manual-loop agent frameworks.
- Subscribers' Guide for assistive technology vendors.
- Extensions Guide explaining how to design and publish AAEP extensions.
- Quickstart tutorial demonstrating a minimal AAEP integration in under ten minutes.
- FAQ addressing common misconceptions about AAEP being a library, service, or vendor-specific tool.

#### Conformance test suite (`conformance/`)
- Installable Python package `aaep-conformance`.
- Test batteries for envelope validation, event schema validation, subscription handshake, confirmation flow, backpressure, and extension handling.
- Level-1, Level-2, and Level-3 test suites with selectable execution.
- Machine-readable conformance reports.

#### Reference examples (`examples/`)
- Minimal Python producer with no framework dependency.
- Python LangChain integration via `BaseCallbackHandler`.
- Python Anthropic SDK wrapper demonstrating Claude integration.
- Python Microsoft Agent Framework integration via middleware.
- Minimal TypeScript producer.
- Minimal C# producer.
- Minimal Go producer.
- Minimal Rust producer.
- CLI debug subscriber.
- NVDA add-on prototype subscriber.
- React component subscriber for accessible web UIs.
- Narrator bridge prototype.
- Model Context Protocol (MCP) to AAEP bridge.
- OpenTelemetry to AAEP bridge.
- Multilingual African languages extension example (Yoruba, Hausa, Igbo).
- Medical HIPAA extension example.

#### Tools (`tools/`)
- `aaep-validate`: validates a single event against its schema.
- `aaep-capture`: captures a live AAEP event stream for debugging.
- `aaep-replay`: replays captured event streams for testing subscribers.

#### Governance (`governance/`)
- Governance document defining decision-making process, maintainer roles, and W3C Community Group transition plan.
- Contribution guide with AAEP Change Proposal (ACP) workflow.
- Code of conduct based on Contributor Covenant 2.1.
- Security disclosure policy.
- Maintainers list.
- Extensions registry.
- Initial adopters list (empty at first publication; populated as adopters self-register).
- Roadmap document covering 18-month plan to W3C Community Group submission.
- Initial AAEP Change Proposals:
  - ACP-0001: Initial specification (this release).
  - ACP-0002: Multilingual extension framework.

#### Repository infrastructure
- README.md, LICENSE (split-license notice), LICENSE-CC-BY-4.0, LICENSE-MIT, NOTICE.
- CITATION.cff for academic citation.
- `.gitignore` and `.editorconfig`.
- GitHub Actions workflows for conformance tests, schema validation, spec build, examples build, and website publication.
- Issue templates for bug reports, spec clarifications, extension proposals, and adopter registration.
- Pull request template.
- CODEOWNERS file routing reviews to appropriate maintainers.
- Dependabot configuration.

### Known limitations of `0.1.0-draft`

The following are acknowledged gaps that will be addressed before `1.0.0`:

- Formative review with disabled developers has not yet been conducted. Findings from that review will inform the `0.2.0` revision.
- Signed manifest support (required for Level 3 conformance) is specified but not yet implemented in reference examples.
- No assistive technology vendor has shipped production AAEP support at the time of this release. NVDA, JAWS, Narrator, VoiceOver, and TalkBack integration is planned but unvalidated.
- The W3C Community Group proposal has not yet been submitted.
- Cross-language conformance has been verified for Python and TypeScript examples but not yet for C#, Go, or Rust examples.

These items appear on the public roadmap in [governance/ROADMAP.md](governance/ROADMAP.md).

---

## Version history summary

| Version | Date | Status |
|---|---|---|
| 0.1.0-draft | 2026-05-24 | Initial public draft |

---

[Unreleased]: https://github.com/Ramseyxlil/aaep/compare/v0.1.0-draft...HEAD
[0.1.0-draft]: https://github.com/Ramseyxlil/aaep/releases/tag/v0.1.0-draft
