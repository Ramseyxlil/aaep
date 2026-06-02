# AAEP Governance

This document describes how the Agent Accessibility Event Protocol (AAEP) is governed: who has authority over what, how changes are proposed and adopted, how versions are released, and how conflicts are resolved.

AAEP is governed openly. Every change to the specification, schemas, or core tooling passes through a defined public process. No single person — including the original author — can unilaterally change the protocol once it reaches version 1.0.0 stable.

This document is itself governed: changes to the governance process require an AAEP Change Proposal (ACP) and a two-thirds supermajority of the Steering Committee.

---

## 1. Principles

The governance process is designed around five principles, in priority order:

1. **Accessibility users come first.** Every change is evaluated against its impact on screen reader users, AAC users, alternative input device users, and other AT users. When in doubt, the change that best serves users wins, even if it inconveniences implementers.

2. **Stability over novelty.** Once a feature is stable, it stays stable. The protocol gains new features through extensions, not by reshaping its core. Implementers who pass conformance Level N MUST continue to pass conformance Level N on the same version forever.

3. **Open by default.** Discussions happen in public. Decisions get recorded with rationale. Working group meetings have public notes. The only exceptions are coordinated security disclosure embargoes and personal matters under the Code of Conduct.

4. **Distributed authority.** No single organization, vendor, or country dominates. As adoption grows, governance broadens. The goal is to remove the original author from the critical path as quickly as adoption justifies, not as slowly as politics allows.

5. **Pragmatic over perfect.** A working protocol with engaged users beats a perfect specification with no implementers. We err on the side of shipping, then iterating, then standardizing what works.

---

## 2. Roles

AAEP recognizes the following roles. Roles are cumulative: a Maintainer is also a Contributor.

### 2.1 Contributors

Anyone who submits an issue, pull request, ACP, documentation change, translation, or implementation. Contributors do not need to be approved or invited. By contributing, you agree to the terms of `CONTRIBUTING.md` and the Code of Conduct.

### 2.2 Reviewers

Contributors who have demonstrated sustained, high-quality engagement and who are explicitly invited by Maintainers to review pull requests in specific areas. Reviewers do not have merge authority but their reviews carry weight in approval decisions.

Reviewers are listed in `MAINTAINERS.md` with the area they review. A Maintainer may invite a Reviewer at any time. A Reviewer can step down at any time without explanation.

### 2.3 Maintainers

Contributors with merge authority on the repository. Maintainers can:

- Merge pull requests once they meet the approval requirements in §4
- Triage issues
- Cut releases per the version policy in §5
- Invite Reviewers
- Propose new Maintainers (subject to Steering Committee approval)

Maintainers are listed in `MAINTAINERS.md` with their areas of responsibility. A Maintainer becomes inactive automatically after 6 months without a substantive contribution; they may resume active status at any time.

### 2.4 Steering Committee

The Steering Committee is the final authority for the protocol. It consists of 3 to 9 members. Steering Committee members:

- Approve ACPs that the working groups cannot resolve
- Approve new Maintainers (simple majority)
- Approve governance changes (two-thirds supermajority)
- Approve major version releases (simple majority)
- Resolve Code of Conduct escalations per `CODE_OF_CONDUCT.md`
- Appoint the Protocol Architect (see §2.5)

Steering Committee members serve two-year staggered terms. Terms can be renewed without limit. Members may resign at any time; replacements are appointed by the remaining members from the active Maintainer pool.

**Initial Steering Committee (v1.0.0–v1.0.x bootstrap period):**

During the bootstrap period (until AAEP has at least 5 production implementations from 3 or more distinct organizations), the Steering Committee consists of the Protocol Architect alone, with an Advisory Committee providing non-binding counsel. The bootstrap period ends automatically when the adoption threshold is met; at that point, the Protocol Architect appoints 4 additional Steering Committee members from the active Maintainer pool, prioritizing organizational and geographic diversity.

This bootstrap structure is honest about the protocol's launch state — one author with strong intent — while committing to broader governance the moment broader adoption justifies it. The criteria for ending the bootstrap are objective and not subject to manipulation by the Protocol Architect.

### 2.5 Protocol Architect

A single individual responsible for the technical coherence of the protocol. The Protocol Architect:

- Has tiebreaker authority on technical questions within the Steering Committee
- Reviews every accepted ACP for technical consistency before merge
- May propose ACPs and participate in their discussion
- Cannot single-handedly approve or reject ACPs after the bootstrap period

The first Protocol Architect is **Abdulrafiu Izuafa**. Future appointments require a two-thirds supermajority of the Steering Committee.

### 2.6 Working Groups

Working groups are time-bounded teams focused on specific aspects of the protocol: e.g., the Multilingual Extension Working Group, the Conformance Working Group, the Web Subscriber Working Group. Working groups:

- Are chartered by the Steering Committee with a defined scope and lifespan (typically 6–18 months)
- Have a designated chair who reports to the Steering Committee
- Produce ACPs within their scope
- Dissolve automatically at the end of their chartered period unless renewed

Working group membership is open to any Contributor who attends two consecutive meetings.

---

## 3. Decisions

AAEP uses a tiered decision model. Decisions are categorized by impact, and each tier has its own approval requirements.

### 3.1 Trivial decisions

Typo fixes, formatting changes, broken link repair, documentation clarifications that don't change meaning, dependency version bumps in tooling that don't affect the protocol surface.

**Approval:** Any single Maintainer.

### 3.2 Standard decisions

Non-trivial documentation changes, new conformance tests for already-specified behavior, new reference examples, schema clarifications that don't change behavior, additions to the implementer's guide.

**Approval:** Two Maintainers (one author, one reviewer who is not the author).

### 3.3 Significant decisions

Changes to schemas, addition or removal of optional fields, new conformance levels, new bridges to other protocols, changes to the CLI tools' contracts, new core tooling.

**Approval:** Requires an ACP (see §4) that passes through public review and is accepted by the relevant working group OR the Steering Committee.

### 3.4 Constitutional decisions

Changes to this GOVERNANCE document, the Code of Conduct, the trademark policy, version-policy guarantees, removal or significant alteration of any normative requirement in the specification.

**Approval:** Two-thirds supermajority of the Steering Committee, with a 30-day public review period that cannot be shortened.

### 3.5 Tie-breaking

If a vote ties at any level, the matter escalates to the next tier. A tie at the Steering Committee level is broken by the Protocol Architect.

---

## 4. The ACP Process

AAEP Change Proposals (ACPs) are the mechanism for proposing significant or constitutional changes. The process is modeled on Python's PEP process and the IETF's RFC process, adapted for our smaller scale.

### 4.1 ACP lifecycle

```
Draft → Discussion → Last Call → Accepted | Rejected | Withdrawn
                                       ↓
                                    Final (after implementation)
```

- **Draft** — Author writes the proposal using the template in `proposals/template.md`. They submit it as a pull request adding `proposals/ACP-NNNN-short-title.md`. The ACP number is the next sequential integer.
- **Discussion** — At least 14 days of open discussion on the pull request. Major objections must be substantively addressed. The author may revise the proposal in response to feedback.
- **Last Call** — When discussion stabilizes and no major objections remain, a Maintainer or working group chair calls for a final vote with a 7-day window. This is announced on the announcement channel.
- **Accepted** — The proposal passes its approval requirement (working group consensus, Steering Committee vote, etc.) and is merged. The author or designated implementer begins work.
- **Final** — The proposal's implementation has shipped in a release. The status field updates to Final.
- **Rejected** — The proposal fails to gain approval. The PR is closed with a rationale comment. The author may submit a substantially revised proposal as a new ACP.
- **Withdrawn** — The author chooses to withdraw the proposal at any time before Acceptance.

### 4.2 ACP authoring

Any Contributor may author an ACP. The proposal must:

- Use the template in `proposals/template.md`
- State the problem clearly and concretely
- Describe the proposed change with sufficient detail to implement
- Discuss alternatives considered and why they were rejected
- Analyze impact on existing implementations and conformance levels
- Identify accessibility implications explicitly (which AT user groups benefit; whether any group is disadvantaged)
- Include a backward compatibility analysis
- Propose a migration path if the change is not fully backward compatible

ACPs that omit the accessibility implications section are returned to the author without further review.

### 4.3 ACP approval

| ACP type | Approval requirement |
|---|---|
| New optional extension | Working group consensus + Protocol Architect technical review |
| New core feature | Working group consensus + Steering Committee simple majority |
| Schema change to optional field | Working group consensus + Steering Committee simple majority |
| Schema change to required field | Steering Committee two-thirds supermajority |
| Removal of any feature | Steering Committee two-thirds supermajority + deprecation period per §5 |
| Constitutional change | Steering Committee two-thirds supermajority + 30-day public review |

### 4.4 ACP implementation

After an ACP is Accepted, the changes are made via standard pull requests citing the ACP number. The ACP moves to Final status only when the implementation ships in a release. ACPs that remain Accepted but unimplemented for 18 months automatically expire and must be re-proposed.

---

## 5. Version policy

AAEP follows [Semantic Versioning 2.0.0](https://semver.org/) strictly. The protocol version applies to the wire format of events, not to tooling or documentation.

### 5.1 Version structure

`MAJOR.MINOR.PATCH`:

- **MAJOR** — Backwards-incompatible changes to required behavior. Subscribers written for the previous major MUST NOT be expected to parse events from a producer using the new major.
- **MINOR** — Backwards-compatible additions. New optional fields, new optional event types, new conformance levels. Subscribers ignoring unknown fields/events MUST continue to work.
- **PATCH** — Bug fixes, clarifications, security updates. No new fields, no new behavior. Existing implementations need no changes.

### 5.2 Deprecation policy

Features are not removed without a deprecation period:

- **Optional features** must be deprecated for at least one MAJOR version before removal.
- **Required features** must be deprecated for at least two MAJOR versions before removal.
- **Deprecation announcement** must appear in the changelog of the version that begins deprecation.
- **Deprecation rationale** must be documented in the ACP that initiates the deprecation.

### 5.3 Long-term support

Each MAJOR version is supported for at least 5 years from its initial release. During the support window:

- Security patches are guaranteed.
- New optional fields may be added in MINOR releases.
- Required behavior is guaranteed not to change.

After 5 years, a MAJOR version enters maintenance mode for an additional 2 years (security patches only), then sunsets. The community is notified 12 months before sunset.

This means: a producer that ships against AAEP 1.0.0 has at least 5 years of full-features support and 7 years until the protocol version sunsets. This stability commitment is what makes AAEP suitable for AT software with long support cycles (Narrator, NVDA, JAWS, VoiceOver).

### 5.4 Release process

1. A Maintainer opens a release pull request that bumps the version and updates `CHANGELOG.md`.
2. At least one other Maintainer reviews and approves.
3. The release is tagged with `vMAJOR.MINOR.PATCH`.
4. Schemas are republished at the canonical URL (`https://aaep-protocol.org/schemas/vMAJOR/`).
5. The release is announced on the announcement channel.

MAJOR version releases additionally require Steering Committee approval per §3.3.

---

## 6. Trademark and branding

The names "AAEP", "Agent Accessibility Event Protocol", and the AAEP logo are governed marks. Their use is permitted under the conditions in `governance/TRADEMARK.md` (to be ratified by ACP-0003).

In summary: any conformant implementation may state "supports AAEP" or "AAEP conformant" with the conformance level achieved. Non-conformant implementations may not use the marks. The Steering Committee may grant naming exceptions to long-standing community projects.

The marks are owned by Abdulrafiu Izuafa during the bootstrap period and transferred to a non-profit foundation (to be selected) when the bootstrap period ends. This transfer is irrevocable.

---

## 7. Code of Conduct

All participation in AAEP is governed by `CODE_OF_CONDUCT.md`. The Steering Committee is the final arbiter of Code of Conduct disputes. During the bootstrap period, the Protocol Architect handles initial reports and may consult with the Advisory Committee for non-binding input; appeals go to the (future) full Steering Committee.

---

## 8. Conflict resolution

Disagreements about technical decisions follow the ACP process. Disagreements about Code of Conduct follow the procedures in `CODE_OF_CONDUCT.md`. Disagreements about governance itself are constitutional matters per §3.4.

For disputes that don't fit the above categories, the Steering Committee may convene a one-time arbitration panel of three Maintainers (not parties to the dispute) to make a binding recommendation.

---

## 9. Foundation transition

When AAEP has at least 10 production implementations across at least 5 distinct organizations on at least 3 continents, the Steering Committee will initiate transition to a neutral non-profit foundation. Candidate foundations include the Linux Foundation, the OpenSSF, the World Wide Web Consortium, and the GNOME Foundation. The choice is made by Steering Committee simple majority after public discussion.

After transition:
- The marks are transferred to the foundation.
- The foundation provides legal, fiscal, and infrastructure services.
- The Steering Committee continues to govern technical decisions.
- The Protocol Architect role continues.

The transition is irrevocable. The protocol becomes the property of the foundation; the original author retains no special status beyond their Steering Committee seat (if they hold one).

---

## 10. Changes to this document

This document may only be amended by an ACP at the constitutional decision tier (§3.4). The amendment must:

1. Be proposed as an ACP.
2. Pass through 30 days of public review.
3. Receive a two-thirds supermajority of the Steering Committee.
4. Be documented in `CHANGELOG.md` with the ACP number.

The current version of this document applies until an amendment is Final.

---

## Acknowledgments

This governance structure is informed by:

- The Python PEP process — for the change proposal lifecycle
- The IETF RFC process — for normative language and stability commitments
- The W3C Process Document — for working group structure
- The Rust governance model — for the Steering Committee + Architect pattern
- The TODO Group's open source governance maturity model — for the foundation transition path

We thank these communities for paving the way.
