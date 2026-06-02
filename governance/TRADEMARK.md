# AAEP Trademark Policy

This document defines who owns the AAEP marks (names, abbreviations, and logos), who may use them, and under what conditions. It is intended to be readable by developers, lawyers, and adopters alike — not just one of those audiences.

This policy is governed by an ACP at the constitutional decision tier (per [`GOVERNANCE.md`](./GOVERNANCE.md) §3.4). Changes require two-thirds Steering Committee supermajority plus 30-day public review.

---

## 1. Marks covered

This policy applies to:

- **AAEP** (the abbreviation, in any capitalization or styling)
- **Agent Accessibility Event Protocol** (the full name)
- The AAEP logo (when published)
- The wordmarks "aaep" and "aaep-protocol"
- The domain name `aaep-protocol.org` (and any related domains controlled by the project)

These collectively are referred to as "the Marks" throughout this document.

---

## 2. Ownership

**Current ownership (bootstrap period):**

During the bootstrap period defined in [`GOVERNANCE.md`](./GOVERNANCE.md) §2.4, the Marks are held by **Abdulrafiu Izuafa** in trust for the AAEP project. This includes any registered trademarks, domain names, and source files for the logo.

This trust arrangement means:
- The owner does NOT use the Marks for personal commercial purposes
- The Marks are held for the benefit of the AAEP community
- All licensing decisions follow the policy in §4 below, not personal preference
- The owner cannot revoke community use rights granted under this policy

**Future ownership (after foundation transition):**

When AAEP completes the foundation transition described in [`GOVERNANCE.md`](./GOVERNANCE.md) §9, the Marks transfer to the receiving foundation as an irrevocable assignment. The foundation then assumes the role of trustee.

The choice of foundation is made by Steering Committee majority after public discussion. Candidates include the Linux Foundation, OpenSSF, W3C, and GNOME Foundation.

---

## 3. Permitted uses without permission

You may use the Marks without asking when you are:

### 3.1 Truthfully describing AAEP

Writing about AAEP in articles, documentation, blog posts, conference talks, or social media. Examples:

- "AAEP is a protocol for accessibility..."
- "Our application uses AAEP to expose agent activity..."
- "I built an AAEP subscriber for NVDA..."

You do not need our permission to refer to AAEP by name in factual discussion.

### 3.2 Stating conformance

If your implementation passes the AAEP conformance suite at Level N, you may state:

- "supports AAEP" (any level)
- "AAEP Level N conformant"
- "AAEP-compatible"
- "Implements AAEP 1.0"

These claims must be accurate. See §5.1 for what makes them inaccurate.

### 3.3 Educational and academic use

Teaching, researching, or writing about AAEP for academic or educational purposes. This includes use of the full name and abbreviation in:

- Course materials and lecture slides
- Academic papers and theses
- Tutorials and training videos
- Books and articles about accessibility or AI agents

### 3.4 Linking and reference

Linking to https://aaep-protocol.org or quoting from the specification, with proper attribution.

### 3.5 Fan content and community projects

Independent community projects (community-built tools, websites about AAEP, podcasts discussing it, etc.) may use the Marks as long as:

- The use is non-commercial OR clearly distinguished from official project material
- The user does not falsely claim affiliation with the official project
- The community project does not misrepresent the protocol

---

## 4. Uses requiring permission

Contact `trademark@aaep-protocol.org` for permission before:

### 4.1 Commercial product naming

Naming a commercial product "AAEP X" or "X AAEP" in a way that suggests it is the official AAEP implementation. Commercial uses like "X for AAEP" or "X with AAEP support" are generally fine without permission (§3.2).

### 4.2 Modifying the logo

Modifying, recoloring, or remixing the AAEP logo. The logo as published may be used in factual discussion; modifications require permission so we can ensure the modified version still represents the project accurately.

### 4.3 Domain registration

Registering domain names that include "aaep" or "agentaccessibility" with the intent to be the official AAEP destination for some audience. Defensive registrations by community members are welcome; aggressive squatting is not.

### 4.4 Certification, training, or branding services

Selling AAEP certification, training, or "AAEP-approved" branding services. We do not currently run a paid certification program ([`GOVERNANCE.md`](./GOVERNANCE.md) §6), and we want to be careful that third parties don't establish one in our name without our involvement.

### 4.5 Fundraising in the name of AAEP

Soliciting donations or sponsorships "for AAEP" without coordinating with the project. The project's official funding (when established) flows through the foundation post-transition; we want to prevent fraudulent fundraising claims.

---

## 5. Prohibited uses

The following uses are prohibited regardless of context:

### 5.1 False conformance claims

Stating "AAEP conformant" or "AAEP Level N" for an implementation that does not pass the [conformance suite](../conformance/) at the claimed level. Conformance is objective; lying about it harms users who rely on these claims.

### 5.2 False affiliation

Implying official endorsement, partnership, or affiliation when none exists. Examples:
- "Official AAEP partner" (no partnership program exists)
- "Endorsed by AAEP" (we don't formally endorse implementations)
- "Built with the AAEP team" (when no such collaboration exists)

### 5.3 Harmful association

Using the Marks in contexts that are harmful, hateful, or discriminatory. The project's values ([`CODE_OF_CONDUCT.md`](./CODE_OF_CONDUCT.md) §1) explicitly prioritize disability community welfare; we will defend the Marks against use in materials that work against those values.

### 5.4 Defaming the project

Using the Marks while making knowingly false claims about the project, its members, or its governance. We accept criticism freely — see §7 — but defamation is different.

### 5.5 Trademark confusion

Using a name confusingly similar to "AAEP" or "Agent Accessibility Event Protocol" to identify a competing protocol or product. Examples of likely confusion:
- "AAAEP" or "AAEPv2" (without project authorization)
- "Agent Accessibility Events Protocol" (plural, attempting to brand a fork)

---

## 6. Quality requirements for conformance claims

Implementations claiming AAEP conformance must:

1. **Pass the conformance suite** at the claimed level on the current major version of the protocol
2. **Re-test on each major release** within 6 months to maintain the claim
3. **Update their conformance level** publicly within 12 months of a new conformance level being introduced (e.g., when Level 4 ships, Level 3 conformant implementations must indicate whether they still claim Level 3 specifically)
4. **Not claim higher conformance** than they actually achieve (no "Level 3" claims for Level 2 implementations)

The conformance suite is at [`conformance/`](../conformance/). Running it produces a machine-readable certificate that can be referenced in adopter listings.

---

## 7. Constructive enforcement approach

When we discover trademark misuse, our default response is **constructive, not aggressive**:

1. **First contact:** an informal note explaining the issue and asking the user to update their materials. Most issues resolve at this stage.
2. **Reminder:** if no response in 30 days, a more formal follow-up.
3. **Public correction:** if the misuse persists and could mislead users, we may publicly correct the record on our website or social media.
4. **Legal action:** only as a last resort for serious harm (commercial confusion, fraudulent fundraising, etc.). Our preferred outcome is always the user updating their materials, not a lawsuit.

We commit not to use trademark law as a tool against criticism, parody, or commentary. Critical articles about AAEP, alternative implementations of similar protocols, and fair-use commentary are all welcome.

---

## 8. Forks of the project

If you fork AAEP and create a derivative protocol, the fork must:

1. **Use a clearly different name** — not "AAEP" or "Agent Accessibility Event Protocol" or confusingly similar
2. **Indicate that it is derived from AAEP** in its documentation (we appreciate the attribution)
3. **Not claim it is "the next version" of AAEP** unless the AAEP project has formally adopted it

Forks are welcome. The protocol's specification is CC-BY-4.0 and the code is MIT. We hope you build something useful. We just ask that you name it clearly so users know what they're getting.

---

## 9. Reporting trademark misuse

To report apparent trademark misuse:

- **Email:** `trademark@aaep-protocol.org`
- **For urgent issues:** Open a public issue on the GitHub repository

We acknowledge reports within 5 business days. Investigation typically takes 14-30 days depending on complexity. We share the outcome with the reporter except where confidentiality is needed.

---

## 10. Updates to this policy

This document may be amended only via an ACP at the constitutional decision tier ([`GOVERNANCE.md`](./GOVERNANCE.md) §3.4). The amendment requires:

1. Public discussion of at least 30 days
2. Two-thirds Steering Committee supermajority
3. Documentation in the CHANGELOG

Material changes are announced on the announcement channel and via direct email to known adopters listed in [`ADOPTERS.md`](./ADOPTERS.md).

---

## Acknowledgments

This policy is informed by:

- The [Open Source Initiative's trademark guidance](https://opensource.org/trademark)
- The [Mozilla Trademark Policy](https://www.mozilla.org/foundation/trademarks/policy/)
- The [Linux Foundation projects' trademark practices](https://www.linuxfoundation.org/trademark-usage/)
- The [Python Software Foundation trademark policy](https://www.python.org/psf/trademarks/)

We thank these projects for working through trademark questions before us and publishing their reasoning openly.
