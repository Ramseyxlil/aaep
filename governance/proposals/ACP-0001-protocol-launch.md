# ACP-0001: AAEP v1.0.0 Protocol Launch

| Field | Value |
|---|---|
| **ACP Number** | 0001 |
| **Title** | AAEP v1.0.0 Protocol Launch |
| **Author(s)** | Abdulrafiu Izuafa <Abdulrafiu@izusoft.tech> |
| **Status** | Final |
| **Type** | Standards Track |
| **Category** | Core |
| **Created** | 2026-06-30 |
| **Updated** | 2026-06-30 |
| **Requires** | none |
| **Replaces** | none |
| **Discussion-URL** | https://github.com/Ramseyxlil/aaep/pull/1 |
| **Implementation** | https://github.com/Ramseyxlil/aaep (entire repository at v1.0.0 tag) |

---

## Abstract

This ACP formally establishes AAEP version 1.0.0 as the initial published version of the Agent Accessibility Event Protocol. It serves as the foundational record for the protocol launch, capturing the scope, included components, governance structure, and stability commitments that apply from the launch date forward.

This is a self-referential ACP — the protocol it describes is the protocol that defines the ACP process. As such, it is automatically Final upon publication of v1.0.0.

---

## Motivation

AAEP has been developed iteratively over the months leading to June 30, 2026. The launch needs a formal anchor:

- A single document recording what shipped at v1.0.0
- A baseline against which future changes are measured
- A statement of stability commitments that adopters can rely on
- The first entry in the ACP series so that subsequent proposals have a precedent

Without this anchor, future debates about "what was always in AAEP" versus "what changed later" would lack a reference point.

---

## Specification

### Components shipped at v1.0.0

The launch comprises:

**Specification** (17 chapters + 4 appendices):
1. Introduction and goals
2. Conformance and terminology
3. Core architecture
4. Event types (12 core event types)
5. Capability negotiation and handshake
6. Transport bindings
7. Extensions mechanism
8. Privacy and security
9. Internationalization
10. Versioning and stability
11. Bridge patterns
12. Conformance levels
13. Glossary
14-17. Appendices: schema reference, transport bindings detail, conformance level criteria, cross-references

**Schemas** (21 JSON Schemas):
- Envelope schema
- 12 core event schemas
- 4 handshake schemas
- 4 context schemas

**Conformance suite:**
- Levels 1, 2, and 3 implemented
- `aaep-conformance` package with CLI

**Tooling:**
- `aaep-validate`, `aaep-capture`, `aaep-replay` commands

**Reference implementations:**
- 5 producers (python-minimal, python-langchain, python-anthropic-sdk, python-microsoft-agent-framework, typescript-minimal)
- 4 subscribers (cli-debug, nvda-addon-prototype, web-subscriber-react, narrator-bridge-prototype)
- 2 bridges (mcp-aaep-bridge, opentelemetry-aaep-bridge)
- 2 canonical extensions (multilingual-african-languages, medical-hipaa)

**Guides:**
- Implementer's Guide, Quickstart, Subscribers Guide, Extensions Guide
- 5 pattern deep-dive documents

**Governance:**
- GOVERNANCE, CONTRIBUTING, CODE_OF_CONDUCT, SECURITY, MAINTAINERS, ROADMAP, EXTENSIONS_REGISTRY, ADOPTERS, TRADEMARK

### Stability commitments

The following are guaranteed for the lifetime of the v1.x.y series:

1. **Schema stability:** existing required fields will not be removed or have their types changed in any v1.x.y release
2. **Behavioral stability:** any normative MUST or SHALL requirement in v1.0.0 remains in effect through v1.x.y
3. **Conformance stability:** an implementation passing Level N at v1.0.0 will continue to pass Level N at any v1.x.y release without changes
4. **Support window:** v1.x.y receives security patches for at least 5 years from v1.0.0 release (June 2026 to June 2031), then 2 years of security-only maintenance (through June 2033)

These commitments are normative parts of the v1.0.0 specification and cannot be weakened by future v1.x.y releases.

---

## Backward compatibility

This is the initial version. There is nothing to be backward compatible with.

Forward compatibility (how v1.0.0 implementations will fare against future v1.x.y releases) is guaranteed by the stability commitments above.

---

## Accessibility implications

AAEP exists specifically to improve accessibility of AI agents. Every component shipped in v1.0.0 was designed with AT user needs as a primary consideration:

- **Screen reader users** benefit from structured event semantics, language-aware summaries, and explicit confirmation flows
- **AAC users** benefit from the structured options in clarification events and predictable safety-by-default behavior
- **Low-vision users** benefit from the streamed output pattern that AT can re-format
- **Motor-impaired users** benefit from the confirmation timeout mechanisms that don't require fast input
- **Cognitive disability users** benefit from verbosity controls (terse/normal/detailed summary levels) and progress disclosure

No AT user group is disadvantaged by v1.0.0. The protocol is opt-in: agents that don't emit AAEP work the same as before; agents that do emit gain accessibility capability.

The AT community has been consulted through the design phase via informal channels. Formal consultation will continue post-launch via the announcement channel and structured feedback through the conformance suite.

---

## Alternatives considered

**1. Defer launch until X.** Several "must-have" features were proposed and deferred to v1.x.y minor releases: braille extension, voice fingerprinting, additional language extensions beyond the canonical three. We chose to ship v1.0.0 with a smaller scope rather than defer indefinitely.

**2. Launch as v0.x.** A beta-numbered launch would have signaled less stability. We chose v1.0.0 because the protocol has been internally stable for months and we want adopters to rely on the stability commitments above.

**3. Launch under W3C or IETF process.** Standards body process would have provided external legitimacy but added 12-24 months of process overhead. We chose to ship as an independent protocol now with the foundation transition path described in `GOVERNANCE.md` §9 leading toward future standards-body submission.

---

## Rationale

The June 30, 2026 launch date was chosen because:

- The reference implementations had reached the working-end-to-end milestone
- The conformance suite had stabilized at three levels with comprehensive tests
- The governance documents had matured through internal review
- Delaying further would not have improved quality measurably and would have delayed real-world adopter feedback

The 5-year + 2-year support commitment was chosen to match the planning horizons of major AT vendors (NVDA, JAWS, VoiceOver). AT software has long release cycles; protocols they integrate with must have correspondingly long stability commitments.

The dual canonical extensions (multilingual + medical) were chosen to demonstrate the extension mechanism with two different patterns (content vs profile) rather than ship only one shape of extension. This establishes the extension mechanism as general.

---

## Reference implementation

This entire repository at the v1.0.0 tag is the reference implementation. See the tag at https://github.com/Ramseyxlil/aaep/releases/tag/v1.0.0.

---

## Security considerations

The launch includes the SECURITY.md disclosure policy. Initial security review was conducted internally; external security audit is planned for Q3 2026 (per ROADMAP). No known vulnerabilities at launch.

The "safety by default" contract — irreversible high-risk actions get `default_decision: "reject"` — is the central security property of the protocol. This contract is testable via Level 2 conformance tests.

---

## Privacy considerations

The launch includes structural privacy considerations (request_text hashing in OTEL bridge, args_summary redaction) and the medical-hipaa extension demonstrates HIPAA-aware redaction patterns. The base specification does NOT mandate redaction; that is left to deployments.

---

## Open questions

(no open questions)

This ACP is Final.

---

## References

- [AAEP Specification v1.0.0](../../spec/)
- [AAEP Conformance Suite](../../conformance/)
- [Reference implementations](../../examples/)
- [Governance documents](../)

---

## Acknowledgments

The protocol's development drew on the work of many communities:

- The disability rights community for decades of advocacy that shaped what accessibility means
- The W3C WAI for the ARIA and WCAG foundations
- NV Access, Freedom Scientific, Apple Accessibility, GNOME Orca team, and Microsoft Accessibility for their AT systems that make this protocol meaningful
- Anthropic for MCP (the inspiration for our extension mechanism) and for general agent ecosystem progress
- The Python, TypeScript, and JSON Schema communities for the tooling that made the reference implementations possible

This is not an exhaustive list, but it captures the most direct intellectual debts.

---

## Changelog

- **2026-06-30:** Created and immediately Final as the launch anchor
