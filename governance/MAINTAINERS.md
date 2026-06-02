# AAEP Maintainers

This document lists the current active Maintainers, Reviewers, and Steering Committee members of the AAEP project, along with their areas of responsibility.

For role definitions, see [`GOVERNANCE.md`](./GOVERNANCE.md) §2.
For how to become a Maintainer, see §5 below.

---

## Current Steering Committee

### Protocol Architect

**Abdulrafiu Izuafa** ([@Ramseyxlil](https://github.com/Ramseyxlil))
- Email: Abdulrafiu@izusoft.tech
- Areas: Protocol design, all specification chapters, technical coherence
- ORCID: To be registered before v1.0.0 release
- Affiliation: Onyx Data Ltd (UK); Veritas University Abuja; independent capacity for this project

During the bootstrap period (per [`GOVERNANCE.md`](./GOVERNANCE.md) §2.4), the Protocol Architect is the sole Steering Committee member. Additional Steering Committee members will be appointed when the adoption threshold is met (5 production implementations from 3+ distinct organizations).

---

## Current Maintainers

### Abdulrafiu Izuafa ([@Ramseyxlil](https://github.com/Ramseyxlil))

- **Areas of responsibility:** All components during the bootstrap period
- **Active since:** Initial creation
- **Time zone:** WAT (West Africa Time, UTC+1)
- **Availability:** Asynchronous; aim for 7-day response on PRs and issues; 14-day response on ACPs
- **Email:** Abdulrafiu@izusoft.tech

---

## Reviewers

No Reviewers are appointed yet. The first Reviewer invitations will go to sustained contributors after launch.

If you've made substantive contributions and would like to be invited as a Reviewer in a specific area, see §5 below.

---

## Areas of responsibility

When we have multiple Maintainers, each will own one or more areas. Owning an area means: this person is the default reviewer for PRs touching that area, and their approval carries extra weight on technical decisions in that area.

The defined areas are:

| Area | Scope |
|---|---|
| **Specification** | `spec/` — the formal AAEP specification chapters |
| **Schemas** | `schemas/` — JSON Schemas and registry |
| **Conformance** | `conformance/` — test harness and conformance levels |
| **Tools** | `tools/` — CLI utilities (aaep-validate, aaep-capture, aaep-replay) |
| **Python examples** | `examples/producers/python-*` and `examples/subscribers/python-*` |
| **TypeScript examples** | `examples/producers/typescript-*` and equivalents |
| **Other-language examples** | Go, Rust, C#, etc. (each adds its own area when introduced) |
| **Bridges** | `examples/bridges/` — MCP, OpenTelemetry, etc. |
| **Extensions** | `extensions/` — multilingual, medical, etc. |
| **Guides** | `guides/` — implementer's guide, quickstart, etc. |
| **Website** | `website/` — aaep-protocol.org source |
| **Governance** | `governance/` — this document, GOVERNANCE.md, etc. |
| **CI/CD** | `.github/` — workflows, automation |
| **Security** | Coordinated disclosure handling, key management, audits |

A Maintainer's areas appear next to their name above.

---

## Inactive Maintainers

Per [`GOVERNANCE.md`](./GOVERNANCE.md) §2.3, Maintainers become inactive automatically after 6 months without a substantive contribution. They may resume active status at any time.

No inactive Maintainers yet (the project is new).

---

## Becoming a Maintainer

The path to Maintainer is:

1. **Make sustained contributions** over at least 3 months. This means multiple PRs across multiple weeks, not a single large change.
2. **Earn an invitation to Reviewer status** in one or more areas. This is done by a current Maintainer recognizing your work; you can also ask if you're interested.
3. **Continue reviewing and contributing** as a Reviewer for at least 3 more months.
4. **A current Maintainer nominates you** to the Steering Committee.
5. **The Steering Committee approves** by simple majority (per [`GOVERNANCE.md`](./GOVERNANCE.md) §2.3).

During the bootstrap period, step 5 is a decision by the Protocol Architect, consulting the Advisory Committee for input. This will broaden as the Steering Committee expands.

Things that strengthen a Maintainer nomination:

- Demonstrated technical judgment (reviewing PRs well, not just opening them)
- Constructive participation in ACPs (asking good questions, surfacing edge cases)
- Mentoring other contributors
- Visible commitment to accessibility — not just technical excellence but using that excellence in service of users
- Bringing perspective the existing team lacks (geographic, organizational, lived experience)

Things that don't:

- Volume alone (50 typo PRs don't qualify)
- Self-nomination without prior engagement
- Being employed by a sponsoring organization (Maintainer status is personal, not corporate)
- Filing a bug, even if it's a good one

---

## Stepping down

Maintainers may step down at any time. To step down:

1. Email the Steering Committee at steering@aaep-protocol.org with your decision.
2. Optionally, propose a successor or recommend any pending work for handoff.
3. Update this document to move yourself to the "Emeritus Maintainers" section below.

Stepping down is honorable. We do not pressure anyone to stay. Maintainership should be sustainable; if it isn't, stepping down protects both the person and the project.

---

## Emeritus Maintainers

This section lists Maintainers who have stepped down but whose contributions are recognized permanently.

(None yet — the project is new.)

---

## Contact

For matters not covered by the standard contribution channels:

| Concern | Address |
|---|---|
| Maintainer escalation (technical) | steering@aaep-protocol.org |
| Maintainer escalation (conduct) | conduct-escalation@aaep-protocol.org |
| Security disclosures | security@aaep-protocol.org (see [`SECURITY.md`](./SECURITY.md)) |
| Press and partnership inquiries | Abdulrafiu@izusoft.tech |
| Commercial support and custom development | Abdulrafiu@izusoft.tech |
| All other inquiries | Open a GitHub Discussion |

---

## Updates to this document

This document is updated by Maintainers as roles change. Updates to the document structure (adding new role types, changing approval requirements) require an ACP per [`GOVERNANCE.md`](./GOVERNANCE.md) §3.3.

Routine updates (adding/removing names, updating contact info) require only a standard Maintainer-approved PR.
