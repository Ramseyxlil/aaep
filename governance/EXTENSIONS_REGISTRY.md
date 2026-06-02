# AAEP Extensions Registry

The canonical registry of approved AAEP extensions. Listed here are extensions that have either shipped with AAEP v1.0.0 (the "canonical" extensions) or been formally approved through the ACP process and assigned a reserved namespace.

This registry is maintained by the Steering Committee. Changes to the registry require an ACP at the significant decision tier (per [`GOVERNANCE.md`](./GOVERNANCE.md) §3.3).

---

## What gets listed here

An extension qualifies for the registry when it:

1. Has an extension manifest (`extension.json`) conforming to the AAEP extension manifest schema
2. Has been reviewed through the ACP process or shipped with v1.0.0
3. Has a maintained reference implementation OR is documented in the specification appendix
4. Has a Steering Committee–assigned namespace prefix
5. Commits to backward-compatible evolution within its major version

Extensions that fail any of these criteria may still exist and be useful, but are not listed here. The registry is not a complete catalog of AAEP-compatible extensions; it's the curated set the project supports.

---

## Currently registered extensions

### Canonical extensions (shipped with AAEP v1.0.0)

These extensions ship in the main repository alongside the specification and are subject to the same governance and stability commitments.

#### `aaep-ext-african-languages` — Multilingual African Languages

| Field | Value |
|---|---|
| Extension ID | `aaep-ext-african-languages` |
| Namespace | `ext_african_languages` |
| Current version | 1.0.0 |
| Conformance class | Informational |
| Status | Active |
| Reference implementation | [`examples/extensions/multilingual-african-languages/`](../examples/extensions/multilingual-african-languages/) |
| Capability signal | `aaep-ext-african-languages-1.0` |
| Maintainer | Abdulrafiu Izuafa (`Abdulrafiu@izusoft.tech`) |

First-class translation support for Yoruba, Hausa, and Igbo. Demonstrates the **content extension pattern** — adds translations and locale-aware metadata without changing core protocol semantics.

#### `aaep-ext-medical-hipaa` — Medical HIPAA-Aware Extension

| Field | Value |
|---|---|
| Extension ID | `aaep-ext-medical-hipaa` |
| Namespace | `ext_medical_hipaa` |
| Current version | 1.0.0 |
| Conformance class | Informational |
| Status | Active |
| Reference implementation | [`examples/extensions/medical-hipaa/`](../examples/extensions/medical-hipaa/) |
| Capability signal | `aaep-ext-medical-hipaa-1.0` |
| Maintainer | Abdulrafiu Izuafa (`Abdulrafiu@izusoft.tech`) |

PHI redaction rules, BAA capability negotiation, medical-domain risk classification, and HL7-aligned audit metadata for healthcare deployments. Demonstrates the **profile extension pattern** — adds privacy and security constraints with new envelope fields and event subtypes.

### Reserved namespaces for upcoming extensions

The following namespace prefixes are reserved for extensions in active development. They are not yet shipped or registered, but the namespace is held to prevent collision.

| Namespace | Planned extension | Anticipated availability |
|---|---|---|
| `ext_swahili` | Swahili language extension | v1.2 (Q1 2027) |
| `ext_finance_sox` | SOX-aware financial services extension | v1.4 (Q3 2027) |
| `ext_education_ferpa` | FERPA-aware education extension | v1.4 (Q3 2027) |
| `ext_braille` | Braille output capability metadata | v1.1 (Q4 2026) |
| `ext_signing` | Signed-event cryptographic extension | v1.5 (Q4 2027) |

Reservations expire after 18 months if no implementation work has begun. Reservations are made via ACP and require Steering Committee approval.

---

## Namespace conventions

Extension namespaces follow these rules:

1. **Format:** `ext_<domain>_<focus>` where `<domain>` is the broad area (medical, education, language) and `<focus>` is the specific subdomain
2. **Lowercase only:** `ext_medical_hipaa`, not `ext_Medical_HIPAA`
3. **Underscores between words:** `ext_african_languages`, not `ext-african-languages`
4. **Stable across versions:** the namespace doesn't change between major versions of the extension; only the version number changes

The namespace appears as the prefix on all extension-specific fields:
- `ext_medical_hipaa.audit_metadata` (envelope field)
- `ext_medical_hipaa.baa_in_force` (capability field)
- `aaep:agent.medical.alert` (event type — uses domain shorthand for readability)

---

## Registration process

To register a new extension:

1. **Develop the extension** with a working reference implementation. Half-finished concepts don't qualify.
2. **Write an ACP** that includes:
   - Problem statement (what gap does this extension fill?)
   - Proposed namespace
   - Manifest specification
   - Capability signal string
   - Backward compatibility analysis
   - Accessibility implications
3. **Open a PR** adding the extension to the "Currently registered" section above
4. **Pass ACP review** (significant decision tier per [`GOVERNANCE.md`](./GOVERNANCE.md) §3.3)
5. **Get Steering Committee approval** for the namespace allocation
6. **Ship a reference implementation** before the extension reaches Final status

Process duration is typically 6-12 weeks from ACP submission to registry inclusion.

---

## Deprecation and removal

Registered extensions follow the same deprecation policy as the core protocol ([`GOVERNANCE.md`](./GOVERNANCE.md) §5.2):

- **Optional extensions** must be deprecated for at least one major version before removal
- **Deprecation announcement** must appear in the changelog and the extension's manifest (`deprecated: true` field)
- **Rationale** must be documented in the deprecation ACP
- **Removal** of a registered extension requires Steering Committee two-thirds supermajority

When an extension is removed from the registry, its namespace remains reserved for 5 years to prevent collision with implementations still in use. After 5 years, the namespace returns to the available pool.

---

## Conformance classes

Each registered extension declares one of four conformance classes:

| Class | Meaning |
|---|---|
| **Informational** | Optional; producers and subscribers MAY implement; absent extensions don't affect AAEP conformance |
| **Recommended** | Strongly encouraged; producers SHOULD implement; subscribers SHOULD handle gracefully |
| **Required for profile** | Required for a specific deployment profile (e.g., healthcare); core AAEP conformance unaffected |
| **Normative** | Affects core protocol semantics; rare, requires constitutional ACP approval |

Both currently-registered extensions are **Informational** — they add capabilities without requiring adoption. The medical extension may be promoted to **Required for profile** for HIPAA deployments in a future ACP.

---

## Third-party extensions

Implementations are welcome to create AAEP extensions not in this registry. Such extensions:

- Should use a unique namespace prefix (typically the organization's reverse-DNS name, e.g., `org_example_widget`)
- Are not eligible for canonical extension status
- Don't receive Steering Committee review
- Must not use the `ext_` namespace prefix (reserved for registry-listed extensions)
- Should still follow the AAEP extension manifest schema for interoperability

If a third-party extension reaches sufficient adoption (multiple independent implementations), its maintainers may propose moving it into the registry via the standard ACP process.

---

## Changes to this document

This document is maintained by the Steering Committee. Routine updates (registering new extensions, updating versions, expiring reservations) require simple PR approval by Maintainers. Structural changes (modifying the conformance classes, changing the registration process) require an ACP at the constitutional decision tier ([`GOVERNANCE.md`](./GOVERNANCE.md) §3.4).

Material changes are announced in the CHANGELOG and on the announcement channel.

---

## Acknowledgments

The registry structure draws on:

- [IANA Considerations](https://www.iana.org/assignments/iana-considerations/iana-considerations.xhtml) — for namespace allocation conventions
- [W3C Extension Specifications policy](https://www.w3.org/TR/process/#extension-specs) — for the canonical-vs-third-party distinction
- The [CSS Working Group's vendor prefix policy](https://www.w3.org/2003/01/css-shipping-prefixes.html) — for namespace stability commitments

Acknowledgments to these communities for working through registry governance problems that AAEP can learn from rather than rediscover.
