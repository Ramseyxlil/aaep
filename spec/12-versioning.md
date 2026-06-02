# Chapter 12 — Versioning and evolution

*Status: Normative*

---

This chapter specifies how the AAEP specification **changes over time**, what implementers can rely on across versions, what constitutes a breaking change, and how the protocol evolves while preserving the interoperability that makes it useful.

A protocol that changes unpredictably is worse than no protocol. Implementers need to know that the contract they implement today will continue to mean the same thing in six months, two years, and ten years. Disabled users depend on this stability because assistive technology shipping AAEP support has a long replacement cycle and cannot adapt to breaking changes on the schedule the AI industry prefers. AAEP's versioning policy explicitly prioritizes stability for downstream implementers and users over velocity for protocol editors.

## 12.1 Versioning scheme

The AAEP specification follows [Semantic Versioning 2.0.0]. Version numbers have the form `MAJOR.MINOR.PATCH`:

[Semantic Versioning 2.0.0]: https://semver.org/spec/v2.0.0.html

- **MAJOR** — increments on breaking changes to the protocol. Implementations conforming to a prior MAJOR version may not conform to the new MAJOR version without modification.
- **MINOR** — increments on backward-compatible additions. New event types, new optional fields, new conformance levels, new transport bindings, new extension mechanisms. Implementations conforming to a prior MINOR version of the same MAJOR remain conforming.
- **PATCH** — increments on clarifications, errata, typo fixes, and editorial improvements that do not change protocol semantics. No implementation behavior is required to change.

### 12.1.1 Pre-release versions

Versions before the first stable release are marked `-draft`, `-alpha`, `-beta`, or `-rc.N`. For example:

- `0.1.0-draft` — initial draft of the specification.
- `0.2.0-alpha` — early prototype of a new MINOR version.
- `1.0.0-rc.1` — first release candidate of the stable 1.0.

Implementations against pre-release versions SHOULD NOT claim general conformance; they may claim conformance against the specific pre-release version cited.

### 12.1.2 Stable releases

The first stable release of AAEP is `1.0.0`. From `1.0.0` onward, the stability commitments in this chapter apply in full.

## 12.2 What counts as a breaking change

A change is **breaking** if it can cause an implementation conforming to the previous version to fail conformance against the new version, without modification. The following are breaking changes:

1. **Removing or renaming a core event type.** An implementation that emits `aaep:agent.tool.invoked` cannot continue emitting it if the type is removed.
2. **Changing the semantics of a core event type.** Even without renaming, a meaning change is breaking.
3. **Removing or renaming a required envelope field.** All events would become invalid.
4. **Changing the type of a required field.** A field that was a string becoming an integer is breaking.
5. **Adding a new required field to an existing event type.** Producers not aware of the new field become non-conforming.
6. **Removing or renaming a conformance level.** Implementations claiming the removed level lose their claim.
7. **Tightening normative requirements on existing fields.** A field that was OPTIONAL becoming REQUIRED is breaking.
8. **Changing the JSON-LD context URI.** Producers and subscribers expecting the old URI cease to function.
9. **Removing or breaking a transport binding's normative requirements.** Transports that conformed previously become non-conforming.
10. **Removing or significantly changing the confirmation protocol's blocking contract.** Safety-critical implementers depend on these guarantees.

The following are NOT breaking changes:

1. Adding a new event type (subscribers gracefully handle unknown types per Chapter 4).
2. Adding new optional fields to existing event types.
3. Adding new conformance levels (above existing ones).
4. Adding new transport bindings.
5. Adding new capability fields in the subscription handshake.
6. Adding new error reason codes (subscribers handle unknown codes gracefully).
7. Loosening normative requirements (MUST becoming SHOULD, REQUIRED becoming RECOMMENDED).
8. Clarifying ambiguous text without changing meaning.
9. Fixing typos and editorial errors.
10. Updating non-normative examples.

### 12.2.1 Borderline cases

Some changes appear additive but have breaking effects on certain implementations. Examples:

- **Adding a new value to an enumeration.** If `error_category` accepts a new value `"requires_admin"` and an old subscriber crashes on unknown enum values, the change is effectively breaking for that subscriber. AAEP requires subscribers to gracefully handle unknown enum values (Chapter 4 §4.1.3). Implementations that crash on unknown values were already non-conforming.

- **Changing the recommended default for an OPTIONAL field.** If `urgency` defaults change from `"normal"` to `"background"` for a particular event type, existing implementations may behave differently. AAEP treats this as MINOR-version change since the field remains optional and behavior remains within spec; implementers should test their assumptions.

- **Strengthening a SHOULD to a MUST.** If a SHOULD requirement becomes a MUST, implementations that were violating the SHOULD lose conformance. AAEP treats this as MAJOR-version change because of the conformance impact.

When borderline, the AAEP maintainers err on the side of treating changes as breaking. Reviewers prefer over-cautious versioning to surprise breakage.

## 12.3 Stability commitments

The following stability commitments apply from `1.0.0` onward.

### 12.3.1 Forever-stable

The following SHALL NOT change in any future version (MAJOR or otherwise):

1. The JSON-LD context URI `https://aaep-protocol.org/context/v1` continues to mean the same as it does in `1.0.0`. A new major version uses a new URI (`/v2`).
2. The semantic meaning of the twelve core event types defined in [Chapter 4](04-core-event-types.md). A future major version may add new event types or deprecate old ones, but the meaning of existing types is preserved.
3. The blocking contract for confirmations (Chapter 6 §6.1). Implementations depending on the contract continue to be safe.
4. The conformance level numbering scheme (Level 1 = Notification, Level 2 = Interactive, Level 3 = Negotiated). Future versions may add Level 4 but cannot reorder existing levels.
5. The reserved `aaep:` namespace. Third parties never gain rights to publish in this namespace.

### 12.3.2 MAJOR-stable

Within a given MAJOR version, the following commitments hold:

1. Implementations conforming to the version at release continue to conform throughout the MAJOR version.
2. No backward-incompatible changes to the protocol's wire format, exchange model, or conformance requirements.
3. New MINOR versions may add features; existing features retain their semantics.
4. Extensions published against the MAJOR version remain compatible throughout the MAJOR version.

### 12.3.3 MINOR-stable

Within a given MINOR version, the following commitments hold:

1. No protocol-level changes at all. PATCH releases within a MINOR version only fix typos, clarify ambiguity, and update examples.

## 12.4 Deprecation policy

When a feature is deprecated, the protocol announces that the feature is intended to be removed in a future MAJOR version. Deprecation does not remove the feature; implementations conforming to the current MAJOR version continue to support deprecated features for the remainder of that MAJOR version's lifetime.

### 12.4.1 Deprecation process

1. **Proposal.** Deprecation of a feature is proposed via an AAEP Change Proposal (ACP) in [governance/proposals/](../governance/proposals/).
2. **Review.** The proposal undergoes community review for at least 90 days.
3. **Acceptance.** If accepted, the feature is marked deprecated in the next MINOR release, with a notice in the spec text and in CHANGELOG.md.
4. **Deprecation period.** The feature remains supported for at least one MAJOR version cycle (typically 18-36 months) after deprecation is announced.
5. **Removal.** The feature is removed in the next MAJOR version after the deprecation period.

### 12.4.2 Communicating deprecations to implementers

Deprecated features are marked in the specification with explicit text:

> **DEPRECATED in version 1.4.0.** This field will be removed in version 2.0.0. Implementations SHOULD use `<replacement field>` instead.

The CHANGELOG and release notes summarize deprecations. Implementations SHOULD consult deprecation notes at each version upgrade.

### 12.4.3 Emergency deprecation

If a feature is found to be a security risk, the maintainers MAY deprecate it on an accelerated schedule. Security-driven deprecations:

1. Are announced via the AAEP security advisory channel (see [governance/SECURITY.md](../governance/SECURITY.md)).
2. Carry an explicit risk explanation and recommended mitigation.
3. May have a shortened deprecation period (as short as 30 days) where the risk warrants.

## 12.5 Implementation version signaling

Implementations SHOULD signal which AAEP version they conform to, so peers can adjust behavior accordingly.

### 12.5.1 Envelope field

The optional envelope field `aaep_version` (Chapter 3 §3.4.4) carries the spec version the producer claims to follow:

```json
{
  "aaep_version": "1.2.0"
}
```

### 12.5.2 Handshake fields

The subscription handshake (`subscription.request` and `subscription.accepted`) carries `aaep_version` (Chapter 5 §5.2.1 and §5.4.1) for explicit negotiation:

```json
{
  "type": "subscription.request",
  "aaep_version": "1.0.0"
}
```

If the producer cannot support the subscriber's requested version, it MAY:

- Respond with `subscription.rejected` and `reason_code: "version_unsupported"`.
- Respond with `subscription.accepted` declaring a different version it does support, leaving the subscriber to renegotiate or accept the alternative.

### 12.5.3 Manifest

The producer manifest (Chapter 5 §5.10) declares `aaep_versions_supported`, the list of MAJOR.MINOR versions the producer offers:

```json
{
  "aaep_versions_supported": ["1.0.0", "1.1.0", "1.2.0"]
}
```

Subscribers consulting the manifest before connecting can select the version best aligned with their own support.

## 12.6 Coexistence of multiple versions

Multiple versions of AAEP can coexist in the ecosystem indefinitely. A producer may speak version 1.4 to one subscriber and version 2.0 to another. A subscriber may simultaneously consume version 1.4 events from one producer and version 2.0 events from another.

### 12.6.1 Forward compatibility

Subscribers built for version `1.0.0` can gracefully consume events from producers using version `1.1.0` or `1.2.0`:

- New optional fields are ignored.
- New event types are handled per the "unknown type" rule (Chapter 4 §3.2.2).
- New extensions are ignored per the "unknown extension" rule (Chapter 3 §3.4.3).

This forward compatibility is by design and SHOULD be preserved within a MAJOR version.

### 12.6.2 Backward compatibility

Producers should NOT depend on subscribers being on the same version. Producers SHOULD emit events that are consumable by the oldest version of the spec the subscriber's declared `aaep_version` permits.

### 12.6.3 Cross-MAJOR coexistence

When two MAJOR versions coexist (e.g., 1.x and 2.x), producers MAY support both via:

- Separate manifest entries for each MAJOR version.
- Separate transport endpoints per MAJOR version.
- Per-subscription version negotiation, with the producer emitting events in the negotiated MAJOR version's format for each subscription.

A producer that supports both 1.x and 2.x has more complex code; this is a trade-off between supporting older subscribers and minimizing implementation surface.

## 12.7 Spec evolution process

Changes to the AAEP specification follow the AAEP Change Proposal (ACP) process documented in [governance/proposals/README.md](../governance/proposals/README.md) and summarized here.

### 12.7.1 ACP workflow

1. **Drafting.** A contributor drafts an ACP using the template at [governance/proposals/template.md](../governance/proposals/template.md). The ACP states the motivation, the proposed change, alternatives considered, backward compatibility analysis, security analysis, and implementation guidance.

2. **Submission.** The ACP is submitted as a pull request adding a numbered file (e.g., `0042-add-haptic-extension.md`) to [governance/proposals/](../governance/proposals/).

3. **Discussion.** Community members discuss the ACP via the pull request comments and the project's discussion channels. Discussion typically runs 30-90 days.

4. **Decision.** AAEP maintainers, after weighing community input, accept or reject the ACP. Decisions are recorded in the ACP file. Decisions consider:
   - Is the change a genuine improvement over the status quo?
   - Does the change preserve interoperability?
   - Does the change preserve safety properties?
   - Has formative input from disabled users been considered?
   - Is the change implementable?

5. **Implementation.** Accepted ACPs are implemented in the specification text, schemas, and reference implementations. The CHANGELOG is updated.

6. **Release.** The implementation appears in the next release of appropriate version (MAJOR or MINOR depending on impact).

### 12.7.2 Roles in the process

- **Authors** draft ACPs. Anyone may be an author.
- **Reviewers** comment on ACPs. Any community member may review.
- **Disabled-user representatives** are specifically invited to review changes affecting accessibility properties. Their feedback receives weighted consideration.
- **Maintainers** make final acceptance decisions. Maintainers are listed in [governance/MAINTAINERS.md](../governance/MAINTAINERS.md).

### 12.7.3 Vetoes

Maintainers may veto changes that violate core principles:

- A change that breaks the rigid-core/extensible-periphery model.
- A change that materially harms safety properties (the blocking contract, default decisions).
- A change that introduces vendor capture.
- A change that breaks backward compatibility in a way the deprecation policy does not justify.

Vetoes are documented in the ACP record.

## 12.8 Errata

Errata are corrections to published versions of the specification. They are PATCH releases that fix typographical errors, clarify ambiguity, or correct mistakes in examples. Errata never change protocol behavior.

Errata are recorded in CHANGELOG.md with `[ERRATA]` markers. Implementers consulting an erratum should note the original text and the corrected text.

A list of all errata for each release is maintained at the project website ([aaep-protocol.org](https://aaep-protocol.org/errata/) once published).

## 12.9 Long-term support and end-of-life

### 12.9.1 LTS designation

Selected MAJOR versions are designated as Long-Term Support (LTS), meaning they receive errata and security advisories for at least three years after release. LTS designation is decided by the AAEP maintainers based on adoption and stability metrics.

### 12.9.2 End-of-life

When a MAJOR version reaches end-of-life:

1. No further changes are made to the spec for that version.
2. The conformance test suite for that version is preserved indefinitely as a reference, but is not updated.
3. Security advisories continue to be issued for that version for at least 12 months after end-of-life, where the AAEP maintainers can reasonably analyze them.
4. Implementations using the version remain valid AAEP implementations of that version forever; conformance against an end-of-life version is still verifiable using the preserved test suite.

End-of-life is announced at least 12 months in advance. The first version reaching end-of-life will be announced via the AAEP project channels and the website.

### 12.9.3 Migration support

When a major version is approaching end-of-life, the AAEP project SHOULD provide:

- A migration guide from the prior version to the current version.
- Tooling to assist with migration (e.g., schema converters).
- Reference implementations of migration patterns.

The goal is to make migration as low-friction as possible so the ecosystem can advance without leaving implementations stranded.

## 12.10 Implementation responsibilities

Implementers of AAEP have responsibilities for version handling:

1. **Document version.** Document which AAEP version(s) the implementation conforms to.
2. **Test against the suite.** Run the conformance test suite at the corresponding version and publish the report.
3. **Track deprecations.** Watch for deprecation notices and plan migration during the deprecation period.
4. **Communicate version in events.** Include `aaep_version` in events and manifest declarations.
5. **Plan for major upgrades.** When a MAJOR version is released, plan migration before the prior version reaches end-of-life.

## 12.11 Where to go next

This chapter completes the main body of the specification. Readers should now consult the appendices:

- [Appendix A (Event state machine)](appendix/A-event-state-machine.md) — non-normative reference for legal event orderings.
- [Appendix B (Transport bindings)](appendix/B-transport-bindings.md) — concrete examples for each transport.
- [Appendix C (Glossary)](appendix/C-glossary.md) — alphabetical index of terms.
- [Appendix D (References)](appendix/D-references.md) — normative and informative references.

Implementers ready to build an AAEP integration should next read the [Implementer's Guide](../guides/IMPLEMENTERS_GUIDE.md). Implementers preparing to publish an extension should consult the [Extensions Guide](../guides/EXTENSIONS_GUIDE.md).
