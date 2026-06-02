# Changelog

All notable changes to the AAEP specification, schemas, conformance test suite, and reference materials are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and AAEP versioning adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html) with the following protocol-specific conventions:

- **Major version (X.0.0)** — Breaking changes to the wire format, event semantics, or subscription handshake. Implementations conforming to a prior major version may no longer conform.
- **Minor version (0.X.0)** — Backward-compatible additions: new event types, new optional fields, new conformance levels, new transport bindings, or new extension mechanisms.
- **Patch version (0.0.X)** — Clarifications, typo fixes, schema corrections that do not change semantics, and editorial improvements.

Conformance claims should reference the major version (e.g., "AAEP v1 Level 2 conformant"). Implementations may also claim conformance to a specific minor version when relying on features introduced in that minor version.

The process for proposing changes is documented in [governance/CONTRIBUTING.md](governance/CONTRIBUTING.md). Substantial changes follow the AAEP Change Proposal (ACP) workflow described in [governance/proposals/template.md](governance/proposals/template.md).

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

## [1.0.0] — 2026-06-30

First public release of the Agent Accessibility Event Protocol.

### Added

#### Specification (`spec/`)
- Twelve core event types organized into four families: Lifecycle, Reasoning State, Tool and Action, and Human-in-the-Loop.
- Event envelope with required fields: `@context`, `type`, `event_id`, `session_id`, `timestamp`, `producer`, `verbosity`, `urgency`, `localization_hints`.
- Subscription handshake protocol with capability negotiation.
- Confirmation reply protocol with reply tokens and timeout semantics.
- Extension mechanism via JSON-LD `@context` arrays and namespaced `type` URIs.
- Three conformance levels: Level 1 (Notification), Level 2 (Interactive), Level 3 (Negotiated).
- Transport-agnostic core with non-normative appendix covering SSE, WebSocket, local IPC, and stdio JSON-RPC.
- Security threat model addressing producer dishonesty, information disclosure, and event flooding.
- Internationalization guidance covering language declaration, locale negotiation, and Unicode handling.

#### Schemas (`schemas/`)
- JSON Schemas for the envelope and all twelve core event types.
- JSON Schemas for subscription request, subscription accepted, subscription rejected, confirmation reply, and clarification reply messages.
- Canonical JSON-LD context document at `schemas/context/aaep-v1.jsonld`.

#### Conformance suite (`conformance/`)
- Installable Python package `aaep-conformance`.
- Level 1, Level 2, and Level 3 test suites.
- 29 self-tests covering envelope, lifecycle, tools, streaming, confirmation, handshake, safety, and reporter logic.
- Machine-readable conformance reports in JSON and HTML formats.

#### Reference implementations (`examples/`)
- **Producers:** Python minimal, Python LangChain integration, Python Anthropic SDK integration, Python Microsoft Agent Framework integration, TypeScript minimal.
- **Subscribers:** CLI debug, NVDA add-on prototype, web subscriber (React), Narrator bridge prototype.
- **Bridges:** Model Context Protocol (MCP) to AAEP, OpenTelemetry to AAEP.
- **Extensions:** Multilingual African languages (Yoruba, Hausa, Igbo), Medical HIPAA-aware extension.

#### Tools (`tools/`)
- `aaep-validate`: validates a single event against its schema.
- `aaep-capture`: captures a live AAEP event stream.
- `aaep-replay`: replays captured streams against subscribers.

#### Guides (`guides/`)
- Implementer's Guide with five integration patterns: middleware-based, callback-based, decorator-based, event-emitter-based, and manual-loop.
- Subscribers' Guide for assistive technology vendors.
- Extensions Guide for designing and publishing AAEP extensions.
- Quickstart tutorial.
- FAQ.

#### Governance (`governance/`)
- Governance document defining decision-making process, maintainer roles, and foundation transition criteria.
- Contribution guide with AAEP Change Proposal (ACP) workflow.
- Code of Conduct based on Contributor Covenant 2.1.
- Security disclosure policy with 90-day coordinated disclosure timeline.
- Maintainers list, extensions registry, adopters list, roadmap, trademark policy.
- ACP-0001 (Protocol Launch) and ACP-0002 (Multilingual Extension), plus the ACP template.

#### Repository infrastructure
- `README.md`, `LICENSE` (split-license notice), `LICENSE-MIT`, `LICENSE-CC-BY-4.0`, `NOTICE`.
- `CITATION.cff` for academic citation.
- `.gitignore` and `.editorconfig`.
- GitHub Actions workflows: conformance tests, schema validation, spec build, website publication.
- Issue templates for bug reports, feature requests, and spec clarifications.
- Pull request template with mandatory accessibility implications section.
- `CODEOWNERS`, `dependabot.yml`, `FUNDING.yml`.

#### Website (`website/`)
- Source for `https://aaep-protocol.org`.
- Landing page, 404 page, accessibility-first stylesheet.
- Build script that renders spec, guides, and governance from markdown to HTML.
- Canonical schema URLs hosted at `https://aaep-protocol.org/schemas/v1/`.

### Stability commitments

- Backward-compatible schema and behavioral stability throughout the v1.x series.
- Full support window: June 2026 through June 2031 (5 years).
- Security-only maintenance: through June 2033 (2 additional years).

### Known limitations of v1.0.0

- No production assistive technology integration ships with this release. NVDA, JAWS, Narrator, VoiceOver, and TalkBack support is on the v1.x roadmap.
- No external organizations are listed as production adopters at launch (per the empty-by-design `ADOPTERS.md`).
- The foundation transition has not yet begun; the protocol is governed during a bootstrap period per `GOVERNANCE.md`.

---

## Version history summary

| Version | Date       | Status                |
|---------|------------|-----------------------|
| 1.0.0   | 2026-06-30 | Initial public release |

---

[1.0.0]: https://github.com/Ramseyxlil/aaep/releases/tag/v1.0.0