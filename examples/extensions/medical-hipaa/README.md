# Medical HIPAA-Aware Extension

A canonical AAEP extension that adapts the protocol for healthcare contexts where Protected Health Information (PHI) is involved. Adds HIPAA-aware redaction rules, audit-friendly event structures, BAA-compatible capability negotiation, and medical-domain risk classification.

This is the second canonical extension after [Multilingual African Languages](../multilingual-african-languages/), and the first to demonstrate AAEP's "profile" extension pattern — one that adds privacy and security constraints rather than translating content.

Referenced from Specification Chapter 7 §7.7.2 and the [FAQ](../../../FAQ.md#can-aaep-be-used-in-healthcare).

---

## Why this extension exists

Healthcare is one of the largest accessibility-relevant domains: clinicians who are blind, low-vision, deaf, or have motor impairments need access to the same agent-driven tools as their colleagues. But healthcare has stricter privacy requirements than most domains. A naive AAEP integration in a clinical setting would leak PHI through:

- `summary_normal` strings containing patient names or conditions
- `args_summary` exposing medication doses or diagnoses
- `request_text` echoing the clinician's spoken query verbatim
- `output.streaming` chunks streaming PHI-laden agent responses
- OTEL bridge spans accidentally indexing PHI in observability backends

This extension addresses each leak point with explicit redaction rules, audit log formats that match HIPAA's "minimum necessary" standard, and a Business Associate Agreement (BAA) capability flag for negotiating PHI-cleared sessions.

The extension does NOT make AAEP HIPAA-compliant by itself. HIPAA compliance is a property of the entire system (producer, subscriber, network, storage, business processes). This extension provides the protocol-layer building blocks; the operator still owns compliance.

---

## What the extension provides

### 1. PHI redaction in event fields

| Event field | Default behavior in PHI mode |
|---|---|
| `summary_normal` | Replace patient names/identifiers with `[PATIENT]`; replace specific dosages with `[DOSE]` |
| `args_summary` | Use placeholders for any field containing PHI |
| `request_text` | Hash-only, do NOT echo verbatim |
| `output.streaming` chunks | Subscribers MUST NOT log chunks; MAY display ephemerally |
| `tool` names | Tool names themselves are not PHI; pass through |
| `error_message` | Strip identifiers but preserve technical detail |

A `producer_phi_redaction` capability field signals the producer's commitment:
```json
"capabilities": {
  "ext_medical_hipaa.producer_phi_redaction": "strict"
}
```

### 2. BAA capability negotiation

A Business Associate Agreement (BAA) is a legal document required when one party (e.g., a software vendor) handles PHI on behalf of a covered entity (e.g., a hospital). AAEP can't make this contract for you, but it can mark sessions where both parties have one in force:

```json
"capabilities": {
  "ext_medical_hipaa.baa_in_force": true,
  "ext_medical_hipaa.baa_party": "MyAgentVendor, Inc.",
  "ext_medical_hipaa.baa_document_id": "BAA-2026-001"
}
```

Subscribers in BAA-cleared sessions MAY relax redaction; subscribers in non-BAA sessions MUST apply strict redaction or refuse to operate. The default is strict redaction.

### 3. Medical-domain risk classification

The extension recommends additional high-risk irreversible categorizations specific to healthcare:

| Tool category | Default classification |
|---|---|
| Prescribe medication | high-risk, irreversible |
| Order test | high-risk (cost/wait implications), reversible |
| Send referral | high-risk, reversible-with-effort |
| Update medical record | high-risk, reversible-with-audit |
| Order imaging | high-risk (radiation exposure), reversible-with-effort |
| Read patient chart | medium-risk, reversible (audit logged) |
| Search drug database | low-risk, reversible |

Each gets an `awaiting.confirmation` by default to satisfy the spec's safety-by-default principle for irreversible high-risk actions.

### 4. Audit log integration

HIPAA requires audit logging of PHI access. The extension defines an `audit_metadata` envelope field that subscribers and OTEL bridges can forward to compliance systems:

```json
{
  "type": "aaep:agent.tool.invoked",
  "ext_medical_hipaa.audit_metadata": {
    "minimum_necessary": true,
    "purpose_of_use": "treatment",
    "user_role": "physician",
    "patient_identifier_hash": "sha256:abc...",
    "session_correlation_id": "session-2026-001"
  }
}
```

The `minimum_necessary` flag declares the producer's assertion that this access is the minimum PHI required for the task. `purpose_of_use` uses HL7-defined values (`treatment`, `payment`, `operations`, etc.).

### 5. Critical event escalation for medical alerts

The extension adds two new critical event subtypes:

- `aaep:agent.medical.alert` — for clinical-significance alerts (drug interaction warning, abnormal lab value, allergy alert)
- `aaep:agent.medical.override_required` — for situations where the agent recommends an action but requires a credentialed user's override

These extend the core `awaiting.confirmation` model with medical-specific metadata.

---

## What this extension does NOT do

To be unambiguous about scope:

- **Does NOT make a system HIPAA-compliant.** HIPAA compliance requires policies, training, business processes, and infrastructure security beyond the scope of any single protocol.
- **Does NOT replace a BAA.** The `baa_in_force` capability is an *assertion*; the actual legal agreement must exist independently.
- **Does NOT define clinical decision support semantics.** AAEP carries the alerts; the medical correctness of those alerts is the agent's responsibility.
- **Does NOT cover non-US regulations** (GDPR healthcare-specific provisions, UK Caldicott Principles, etc.) — separate extensions could address these.

---

## Installation

```bash
cd examples/extensions/medical-hipaa
pip install -e .
```

Requires Python 3.10 or newer.

---

## Usage

### Producer side

```python
from aaep_minimal_producer.emitter import AAEPEmitter
from aaep_ext_medical_hipaa import (
    classify_medical_risk,
    redact_phi,
    audit_metadata_for,
)

emitter = AAEPEmitter(
    send_event=my_transport,
    agent_id="clinical-agent",
)

# Begin a session with BAA capability
session_id = emitter.start_session(
    summary_normal="Reviewing patient chart.",  # No PHI in summary
    capabilities={
        "ext_medical_hipaa.producer_phi_redaction": "strict",
        "ext_medical_hipaa.baa_in_force": True,
        "ext_medical_hipaa.baa_party": "MyAgentVendor, Inc.",
    },
    extension_data={
        "ext_medical_hipaa.audit_metadata": audit_metadata_for(
            purpose_of_use="treatment",
            user_role="physician",
            patient_identifier="MRN12345678",  # gets hashed
        ),
    },
)

# Risk-classify a medical tool
risk = classify_medical_risk("prescribe_medication")
# RiskAssessment(risk_level="high", irreversible=True, requires_confirmation=True)

emitter.tool_invoked(
    session_id=session_id,
    tool="prescribe_medication",
    args_summary=redact_phi(
        "patient=MRN12345678 medication=amoxicillin dose=500mg",
    ),
    risk_level=risk.risk_level,
    irreversible=risk.irreversible,
)
```

### Subscriber side

Subscribers integrating this extension SHOULD:

1. Refuse to operate without a BAA-cleared session OR strict redaction
2. Treat `medical.alert` and `medical.override_required` events as critical
3. Forward audit metadata to compliance systems (not just speak it to the user)
4. Avoid logging PHI to any persistent store the user hasn't explicitly authorized

---

## Risk classification reference

The shipped classifier includes 14 default tool categorizations. The full table is in `aaep_ext_medical_hipaa/risk_table.json` and editable per-deployment.

---

## Project layout

```
medical-hipaa/
├── README.md
├── extension.json              # Extension manifest
├── pyproject.toml
├── aaep_ext_medical_hipaa/
│   ├── __init__.py
│   ├── redaction.py            # PHI pattern detection and replacement
│   ├── risk_classification.py  # Medical-domain risk classifier
│   └── audit.py                # audit_metadata_for() helper
├── risk_table.json             # Default tool→risk mappings
└── tests/
    └── test_redaction.py
```

---

## Conformance

This extension is non-normative (per AAEP Chapter 7 §7.3). It defines optional capabilities, optional events, and recommended practices. Producers and subscribers MAY adopt it; the spec does not require it for AAEP conformance.

Conformance to the extension is signaled via:

```json
{
  "supported_extensions": ["aaep-ext-medical-hipaa-1.0"]
}
```

A producer signaling this extension MUST follow its redaction rules in PHI-context sessions. A subscriber signaling this extension MUST handle the additional event types and audit metadata fields appropriately.

---

## Compliance disclaimer

This extension is informational and does not constitute legal or compliance advice. Healthcare operators MUST consult their HIPAA Privacy and Security Officers, qualified counsel, and applicable regulations before deploying AAEP-based agents in clinical settings. Anthropic, the AAEP project, and the author of this extension do not assume responsibility for compliance failures in any deployment.

---

## See also

- [`../multilingual-african-languages/`](../multilingual-african-languages/) — sister canonical extension for languages
- [Specification Chapter 7](../../../spec/07-extensions.md) — extension mechanism
- [Specification Chapter 8](../../../spec/08-privacy-and-security.md) — privacy and security baseline
- [HIPAA Security Rule (HHS)](https://www.hhs.gov/hipaa/for-professionals/security/index.html)
- [HL7 Purpose of Use code system](https://terminology.hl7.org/CodeSystem-v3-PurposeOfUse.html)
