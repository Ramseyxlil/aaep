# ACP-NNNN: [Short descriptive title]

| Field | Value |
|---|---|
| **ACP Number** | NNNN |
| **Title** | [Short descriptive title] |
| **Author(s)** | [Name <email>, additional names...] |
| **Status** | Draft / Discussion / Last Call / Accepted / Final / Rejected / Withdrawn |
| **Type** | Standards Track / Informational / Process |
| **Category** | Core / Extension / Tooling / Governance |
| **Created** | YYYY-MM-DD |
| **Updated** | YYYY-MM-DD |
| **Requires** | List of ACPs this depends on, or "none" |
| **Replaces** | List of ACPs this supersedes, or "none" |
| **Discussion-URL** | Link to the PR or discussion thread |
| **Implementation** | Link to reference implementation PR (when applicable) |

---

## Abstract

Two-to-four sentence summary of what this proposal does and why. Should be readable without further context. This is what appears in summaries and announcements.

---

## Motivation

Why does this change need to happen? What problem does it solve? What's the cost of not making this change?

This section should be **concrete**. Not "users would benefit from..." but "users with cognitive disabilities currently cannot adjust verbosity per-session; the current spec requires global setting changes that disrupt other users."

If the motivation is theoretical or speculative, the proposal is probably premature. ACPs respond to demonstrated needs.

---

## Specification

The exact, normative change being proposed.

If changing the protocol specification, include:
- Schema additions or modifications (with JSON Schema snippets)
- New event types or fields (with examples)
- Behavioral requirements (using RFC 2119 keywords: MUST, SHOULD, MAY)
- Conformance criteria

If adding tooling, include:
- New CLI commands or API surfaces
- Configuration changes
- Migration paths for existing users

Use concrete code samples and schema snippets liberally. Vague proposals don't pass review.

---

## Backward compatibility

How does this change affect existing implementations?

Required analysis:
- Will producers built against the previous spec still work?
- Will subscribers built against the previous spec still work?
- Will the change require coordinated updates across producers and subscribers?
- Are there silent failure modes for non-compliant implementations?

If breaking changes are required, this section must include a migration path with timeline.

---

## Accessibility implications

**REQUIRED for every ACP.** Proposals without this section are returned to authors without review per [`GOVERNANCE.md`](../GOVERNANCE.md) §4.2.

Required analysis:
- Which AT user groups (screen reader users, AAC users, low-vision users, motor-impaired users, cognitive disability users, etc.) benefit from this change?
- Are any AT user groups disadvantaged by this change?
- Does this introduce new accessibility barriers (even temporarily during migration)?
- How does this interact with existing accessibility standards (ARIA, WCAG, ATAG)?
- Has the AT community been consulted on this change?

---

## Alternatives considered

What other approaches were considered, and why were they rejected?

This section prevents bikeshedding during review and shows the author has thought through the design space. Even if you considered only obvious alternatives, list them.

Minimum: one alternative per significant design decision in the Specification.

---

## Rationale

Why this specific design? Why these specific choices?

This section captures the reasoning that doesn't fit in Specification (which is normative) or Alternatives (which is comparative). Future readers re-evaluating decisions should be able to understand the original logic here.

---

## Reference implementation

Link to the reference implementation PR or branch. ACPs cannot reach Final status without a shipping reference implementation.

If the implementation is in progress, describe its current state and expected timeline.

---

## Security considerations

How does this proposal affect security? Consider:
- Information disclosure risks
- Authentication and authorization implications
- Threat model changes
- Cryptographic dependencies

This section is required even when the answer is "no security implications" — that statement should be made explicitly.

---

## Privacy considerations

How does this proposal affect privacy? Consider:
- PII or sensitive data exposure
- Compliance implications (HIPAA, GDPR, FERPA)
- Audit trail and logging
- User consent flows

This section is required even when the answer is "no privacy implications" — that statement should be made explicitly.

---

## Open questions

What aspects of this proposal need more discussion before it can be Accepted? Listing them here invites focused review.

When all open questions are resolved, this section becomes "(no open questions)" and the proposal moves to Last Call.

---

## References

- Related ACPs
- External specifications referenced
- Research papers or articles informing the design
- Discussion threads or earlier drafts

---

## Acknowledgments

Names of people who substantively contributed to this proposal beyond the listed authors. Include reviewers who provided substantial feedback, even if the proposal wasn't their idea.

---

## Changelog

- **YYYY-MM-DD:** Created as Draft
- **YYYY-MM-DD:** Updated based on review feedback
- ...

Each material change to the proposal gets an entry here. Minor typos and formatting fixes don't need entries; substantive content changes do.
