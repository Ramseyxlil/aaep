"""
audit.py — HIPAA-aligned audit metadata helpers.

Builds the `ext_medical_hipaa.audit_metadata` envelope field documented in
the extension. Uses HL7 Purpose-of-Use codes for the `purpose_of_use` field
so output is compatible with existing healthcare audit infrastructure.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class PurposeOfUse(str, Enum):
    """
    HL7 v3 PurposeOfUse codes (subset).

    Full code system at:
        https://terminology.hl7.org/CodeSystem-v3-PurposeOfUse.html

    Use the most specific value that applies. TREATMENT is the most common
    in clinical AI contexts.
    """

    TREATMENT = "treatment"
    PAYMENT = "payment"
    OPERATIONS = "operations"
    RESEARCH = "research"
    PUBLIC_HEALTH = "public_health"
    QUALITY_ASSURANCE = "quality_assurance"
    DISCLOSURE = "disclosure"
    EMERGENCY = "emergency"


def hash_patient_identifier(
    patient_id: str,
    *,
    salt: str | None = None,
) -> str:
    """
    Hash a patient identifier for audit logging.

    Returns a string of the form "sha256:<64-hex-chars>".

    The salt (if provided) is mixed into the hash. Using a per-deployment
    salt prevents cross-deployment correlation of the same patient.

    NOTE: This does not anonymize the patient — the same ID always produces
    the same hash. The purpose is to obscure the raw identifier in logs
    while preserving deterministic correlation for audit queries.
    """
    if not patient_id:
        return "sha256:" + "0" * 64

    h = hashlib.sha256()
    if salt is not None:
        h.update(salt.encode("utf-8"))
        h.update(b":")
    h.update(patient_id.encode("utf-8"))
    return f"sha256:{h.hexdigest()}"


def audit_metadata_for(
    *,
    purpose_of_use: PurposeOfUse | str,
    user_role: str,
    patient_identifier: str | None = None,
    patient_id_salt: str | None = None,
    minimum_necessary: bool = True,
    session_correlation_id: str | None = None,
    additional_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Build a HIPAA-aligned audit metadata block.

    Returns a dict suitable for inclusion in an AAEP event's
    `ext_medical_hipaa.audit_metadata` field.

    Args:
        purpose_of_use: HL7 purpose-of-use code (use PurposeOfUse enum)
        user_role: Role of the user driving the agent (e.g., "physician",
                   "nurse", "pharmacist", "patient")
        patient_identifier: Optional patient ID to hash for audit correlation
        patient_id_salt: Per-deployment salt for the patient ID hash
        minimum_necessary: Producer's assertion that this is the minimum
                           PHI access required for the task (per HIPAA)
        session_correlation_id: Optional ID linking related events;
                                auto-generated if not provided
        additional_context: Extra fields to include (e.g., facility_id, role_specialty)

    Returns:
        A dict with the audit metadata fields.

    Example:

        >>> meta = audit_metadata_for(
        ...     purpose_of_use=PurposeOfUse.TREATMENT,
        ...     user_role="physician",
        ...     patient_identifier="MRN12345678",
        ...     patient_id_salt="hospital-deployment-2026",
        ... )
        >>> meta["purpose_of_use"]
        'treatment'
        >>> meta["minimum_necessary"]
        True
        >>> meta["patient_identifier_hash"].startswith("sha256:")
        True
    """
    purpose_str = (
        purpose_of_use.value
        if isinstance(purpose_of_use, PurposeOfUse)
        else str(purpose_of_use)
    )

    metadata: dict[str, Any] = {
        "purpose_of_use": purpose_str,
        "user_role": user_role,
        "minimum_necessary": bool(minimum_necessary),
        "session_correlation_id": (
            session_correlation_id
            or f"audit-{uuid.uuid4()}"
        ),
        "audit_timestamp": datetime.now(timezone.utc).isoformat(),
    }

    if patient_identifier is not None:
        metadata["patient_identifier_hash"] = hash_patient_identifier(
            patient_identifier,
            salt=patient_id_salt,
        )

    if additional_context:
        # Don't allow override of standard fields
        protected = set(metadata.keys())
        safe_extras = {
            k: v for k, v in additional_context.items()
            if k not in protected
        }
        metadata.update(safe_extras)

    return metadata
