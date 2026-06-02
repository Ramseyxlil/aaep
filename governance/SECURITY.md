# AAEP Security Policy

This document explains how to report security vulnerabilities in the Agent Accessibility Event Protocol, its reference implementations, and its tooling. It also describes our handling process, supported versions, and recognition for security researchers.

**Please do not file public issues for security vulnerabilities.** Use the private reporting channels described below.

---

## 1. What's in scope

This policy covers:

- The AAEP specification (when an ambiguity creates security risk)
- All official JSON Schemas under `schemas/`
- Reference implementations in `examples/producers/` and `examples/subscribers/`
- The conformance suite (`conformance/`)
- The official CLI tools (`tools/aaep-tools/`)
- The website source (`website/`) including any forms or interactive elements
- Cryptographic recommendations in the spec (signed manifests, capability negotiation)

This policy does NOT cover:

- Third-party implementations of AAEP not maintained by this project. Report those to their respective maintainers.
- Vulnerabilities in upstream dependencies that don't affect AAEP code (report to the dependency maintainer; we may add a notice if relevant).
- Theoretical attacks that require capabilities the threat model doesn't grant (see §6).

If you're unsure whether something is in scope, report it. We'd rather triage out-of-scope reports than miss a real one.

---

## 2. How to report

### 2.1 Preferred channel: encrypted email

Email **security@aaep-protocol.org**.

Encrypt your message with the AAEP security team's PGP key. The key is published at:

- https://aaep-protocol.org/security-team.asc
- The `keys/` directory in this repository
- Key servers (search for `security@aaep-protocol.org`)

The key fingerprint will be published in the first release notice and the website. During the bootstrap period, the key is held by the Protocol Architect (Abdulrafiu Izuafa).

### 2.2 GitHub private vulnerability reporting

You may use GitHub's [private vulnerability reporting feature](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability). Go to the repository's Security tab → "Report a vulnerability."

This routes to the same team as the email channel.

### 2.3 What to include

Your report should include enough information for us to reproduce and assess the issue:

- A clear description of the vulnerability
- Steps to reproduce
- Affected versions, components, and configurations
- Proof of concept if you have one (we'll never publish it without your permission)
- Your assessment of the severity
- Whether you've disclosed this to anyone else
- Your preferred name for hall of fame attribution (or "anonymous")

You do not need to:

- Be a security professional
- Provide a fix (we'll figure that part out)
- Have a CVE number (we'll request one if needed)
- Have explored every implication (just report what you found)

---

## 3. Our response

### 3.1 Timeline commitments

| Stage | Timeframe |
|---|---|
| Acknowledgment of receipt | Within 2 business days |
| Initial severity assessment | Within 5 business days |
| Detailed response with action plan | Within 10 business days |
| Patch released for critical/high severity | Within 30 days |
| Patch released for medium severity | Within 90 days |
| Patch released for low severity | Within 180 days |

These are commitments, not approximations. If we miss a timeline, you'll be told why and given a revised estimate.

### 3.2 Severity assessment

We use the [CVSS 3.1 Base Score](https://www.first.org/cvss/) as a starting point but adjust based on context. AAEP-specific severity considerations:

- **Critical:** Vulnerabilities that could compromise the safety contract (e.g., bypassing irreversible+high+default_reject enforcement), expose secrets at rest, or allow agents to misrepresent themselves to AT.
- **High:** Vulnerabilities that allow privilege escalation, unauthorized event injection, or man-in-the-middle attacks against the transport layer.
- **Medium:** Vulnerabilities that allow information disclosure (other than secrets), denial of service against a single producer/subscriber, or schema-validation bypass.
- **Low:** Vulnerabilities with minimal practical impact, requiring unrealistic prerequisites, or affecting only optional features.

### 3.3 What we'll do

Once a report is confirmed, we will:

1. Assign an internal tracking ID.
2. Work with you on a coordinated disclosure timeline (see §4).
3. Develop and test a patch.
4. Request a CVE if the vulnerability warrants one.
5. Prepare a security advisory.
6. Release patched versions of affected components.
7. Publish the advisory on the announcement channel and in GitHub Security Advisories.
8. Credit you in the advisory (with your preferred name or anonymously, per your choice).

---

## 4. Coordinated disclosure

We follow a coordinated disclosure model. The default timeline is **90 days** from initial report to public disclosure. This may be:

- **Shortened** if a patch is ready earlier and there's no benefit to delay.
- **Extended by mutual agreement** if more time is genuinely needed (e.g., to give downstream implementers time to update).
- **Shortened unilaterally** if the vulnerability is being actively exploited in the wild.

Public disclosure means:

- A security advisory published on the website and GitHub Security Advisories
- Notification to known production users via the security mailing list
- Inclusion in `CHANGELOG.md` of the patched release
- Attribution to the reporter (unless they prefer anonymity)

You may not disclose publicly before the coordinated date except in two cases:

1. **Active exploitation:** if the vulnerability is being exploited in the wild and users need immediate notification, we may agree on accelerated disclosure.
2. **Unresponsive maintainer:** if we miss our timeline commitments without explanation for an extended period, you may disclose. We don't anticipate this happening, but we acknowledge your right to protect users.

---

## 5. Supported versions

Security patches are released for:

| Version branch | Status | Receives security patches? |
|---|---|---|
| 1.x.y (current major) | Active | Yes |
| 0.x.y (pre-1.0 betas) | Deprecated | No (please upgrade) |

When AAEP 2.0.0 ships, the support matrix will update:

- 2.x.y will become the active branch.
- 1.x.y will remain supported for security patches per the LTS policy in `GOVERNANCE.md` §5.3 (5 years of full support + 2 years of security-only patches after).

You can verify the current supported versions at https://aaep-protocol.org/security/supported-versions.

---

## 6. Threat model

AAEP's reference threat model assumes:

**Trusted:**
- The user (the human running an AT)
- The user's AT software itself
- The AT's local environment (OS, IPC mechanisms)

**Untrusted:**
- The network between producer and subscriber (unless explicitly secured)
- Other software on the user's machine that could intercept events
- Third-party producers and bridges

**Out of scope:**
- An attacker with full root/admin on the user's machine (game over regardless)
- Side-channel attacks on TLS implementations (defer to TLS spec)
- Compromised AT software (we trust the AT we're talking to)

Vulnerabilities that only manifest under out-of-scope conditions are noted but typically not classified as security issues for AAEP itself.

---

## 7. Hall of fame

We recognize security researchers who report vulnerabilities responsibly. Hall of fame is maintained at:

- https://aaep-protocol.org/security/hall-of-fame
- `security/HALL_OF_FAME.md` in the repository

To be added, your report must:

- Be the first to describe a specific issue
- Result in a security advisory (i.e., a real fix shipped)
- Comply with this policy

You may decline attribution and remain anonymous. The hall of fame is non-monetary recognition. We do not run a bug bounty program at this time.

---

## 8. Safe harbor

We commit to:

1. Not pursue legal action against security researchers who comply with this policy.
2. Work with researchers to understand and resolve issues quickly.
3. Recognize researchers publicly with their consent.
4. Not require researchers to sign non-disclosure agreements as a condition of acceptance.

Researchers, in turn, commit to:

1. Make a good faith effort to avoid privacy violations, destruction of data, or interruption of services.
2. Provide reasonable time for us to address issues before public disclosure.
3. Not exploit issues beyond what's necessary to demonstrate them.
4. Comply with the laws of their jurisdiction.

If you're a security researcher operating in a jurisdiction where our policy creates legal ambiguity, contact us before testing. We'd rather help you research safely than have you avoid AAEP entirely.

---

## 9. PGP key information

The AAEP security team's PGP key:

```
Key type:     RSA 4096
User ID:      AAEP Security <security@aaep-protocol.org>
Fingerprint:  TO BE PUBLISHED at v1.0.0 release
```

The fingerprint will be:

1. Announced in the v1.0.0 release notice
2. Published at https://aaep-protocol.org/security-team.asc
3. Signed by the Protocol Architect's personal key (also published)
4. Available from public key servers

Verify the key's fingerprint via multiple channels before sending sensitive reports.

---

## 10. Reporting non-security bugs

If you have a bug that isn't a security issue, please file a public GitHub issue. We triage public issues actively and you'll typically get a response within a week.

If you're not sure whether something is a security issue, err on the side of reporting it privately. We'll route it to the right place from there.

---

## 11. Updates to this policy

This document may be amended by an ACP at the constitutional decision tier (`GOVERNANCE.md` §3.4). Changes that materially weaken our security commitments require:

1. 60-day public review (extended from the standard 30 days for constitutional changes)
2. Two-thirds supermajority of the Steering Committee
3. Explicit notification on the announcement channel

Material updates appear in `CHANGELOG.md`.

---

## 12. Acknowledgments

This security policy draws on:

- [security.txt](https://securitytxt.org/) — disclosure channel conventions
- [GitHub Security Advisories guidance](https://docs.github.com/en/code-security/security-advisories)
- [OpenSSF Best Practices](https://bestpractices.coreinfrastructure.org/) — security maturity model
- The [disclose.io](https://disclose.io/) safe harbor model

We thank these projects for advancing the state of coordinated disclosure in open source.
