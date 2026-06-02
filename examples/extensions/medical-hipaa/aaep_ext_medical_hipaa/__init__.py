"""
Medical HIPAA-Aware Extension for AAEP.

Provides PHI redaction, BAA capability negotiation, medical-domain risk
classification, and HL7-aligned audit metadata helpers.

Public API:

    from aaep_ext_medical_hipaa import (
        redact_phi,                  # Apply PHI redaction to a string
        RedactionLevel,              # Strictness enum
        classify_medical_risk,       # Get risk assessment for a tool
        MedicalRiskAssessment,       # Risk outcome dataclass
        audit_metadata_for,          # Build audit metadata block
        hash_patient_identifier,     # Hash an MRN for audit logs
        PurposeOfUse,                # HL7 purpose-of-use codes
    )

See README.md for usage examples and compliance scope notes.
"""

from __future__ import annotations

__version__ = "1.0.0"
__author__ = "Abdulrafiu Izuafa"
__email__ = "Abdulrafiu@izusoft.tech"
__license__ = "MIT"
__aaep_spec_version__ = "1.0.0"
__extension_id__ = "aaep-ext-medical-hipaa"


from aaep_ext_medical_hipaa.redaction import (
    RedactionLevel,
    redact_phi,
    is_likely_phi,
    PHI_PATTERNS,
)
from aaep_ext_medical_hipaa.risk_classification import (
    MedicalRiskAssessment,
    classify_medical_risk,
    load_risk_table,
)
from aaep_ext_medical_hipaa.audit import (
    PurposeOfUse,
    audit_metadata_for,
    hash_patient_identifier,
)


__all__ = [
    "__version__",
    "__author__",
    "__email__",
    "__license__",
    "__aaep_spec_version__",
    "__extension_id__",
    # Redaction
    "redact_phi",
    "is_likely_phi",
    "RedactionLevel",
    "PHI_PATTERNS",
    # Risk
    "classify_medical_risk",
    "MedicalRiskAssessment",
    "load_risk_table",
    # Audit
    "audit_metadata_for",
    "hash_patient_identifier",
    "PurposeOfUse",
]
