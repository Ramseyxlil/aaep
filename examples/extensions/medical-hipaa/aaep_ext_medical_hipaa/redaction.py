"""
redaction.py — PHI pattern detection and replacement.

Implements the redaction rules documented in the extension README. Three
strictness levels:

    strict   — replace any detected PHI pattern with a placeholder
    relaxed  — replace only definite identifiers (SSN, MRN); leave other patterns
    none     — pass through (use only in BAA-cleared, locally-trusted contexts)

The patterns are heuristic, not exhaustive. Production deployments SHOULD
use a HIPAA-certified de-identification pipeline (e.g., Microsoft Presidio,
Amazon Comprehend Medical) for higher accuracy.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Pattern


class RedactionLevel(str, Enum):
    """Redaction strictness levels."""

    STRICT = "strict"
    RELAXED = "relaxed"
    NONE = "none"


# PHI pattern catalog. Order matters: more-specific patterns first so that
# e.g. SSN replacement happens before generic number replacement.
PHI_PATTERNS: list[tuple[str, Pattern[str], str, set[RedactionLevel]]] = [
    # === Definite identifiers (replaced at all levels above NONE) ===

    # Medical Record Number patterns:
    # MRN12345678, MRN-12345678, MRN:12345678, "MRN" then 6-12 digits
    (
        "MRN",
        re.compile(r"\bMRN[-:\s]*([0-9]{6,12})\b", re.IGNORECASE),
        "[MRN]",
        {RedactionLevel.STRICT, RedactionLevel.RELAXED},
    ),

    # Social Security Numbers: 123-45-6789 or 123 45 6789 or 123456789
    (
        "SSN",
        re.compile(r"\b(\d{3}[-\s]?\d{2}[-\s]?\d{4})\b"),
        "[SSN]",
        {RedactionLevel.STRICT, RedactionLevel.RELAXED},
    ),

    # Phone numbers: (555) 123-4567, 555-123-4567, +1 555 123 4567
    (
        "phone",
        re.compile(
            r"\b(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b",
        ),
        "[PHONE]",
        {RedactionLevel.STRICT, RedactionLevel.RELAXED},
    ),

    # Email addresses
    (
        "email",
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
        "[EMAIL]",
        {RedactionLevel.STRICT, RedactionLevel.RELAXED},
    ),

    # === Less-definite identifiers (strict mode only) ===

    # Dates that could be DOB: 01/01/1950, 1950-01-01, Jan 1, 1950
    (
        "date",
        re.compile(
            r"\b(?:"
            r"(?:0?[1-9]|1[0-2])[-/](?:0?[1-9]|[12][0-9]|3[01])[-/](?:19|20)\d{2}"
            r"|(?:19|20)\d{2}-(?:0?[1-9]|1[0-2])-(?:0?[1-9]|[12][0-9]|3[01])"
            r"|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.?\s+"
            r"\d{1,2},?\s+(?:19|20)\d{2}"
            r")\b",
        ),
        "[DATE]",
        {RedactionLevel.STRICT},
    ),

    # Names following honorifics: Mr./Mrs./Ms./Dr. + Capitalized words
    # This is heuristic and will produce false positives. Strict mode only.
    (
        "name_after_honorific",
        re.compile(
            r"\b(?:Mr|Mrs|Ms|Mx|Dr|Prof|Rev)\.?\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b",
        ),
        "\\1[NAME]",  # Wrong substitution intentionally left for example
        {RedactionLevel.STRICT},
    ),

    # Patient labels followed by names: "patient John Smith"
    (
        "patient_named",
        re.compile(
            r"\bpatient\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b",
            re.IGNORECASE,
        ),
        "patient [NAME]",
        {RedactionLevel.STRICT},
    ),

    # Dosage patterns: 500 mg, 10mg, 2.5 mL, 100 units
    (
        "dose",
        re.compile(
            r"\b(\d+(?:\.\d+)?)\s*(mg|mcg|g|ml|mL|cc|units?|IU|tablets?|"
            r"pills?|drops?|sprays?|puffs?)\b",
        ),
        "[DOSE]",
        {RedactionLevel.STRICT},
    ),

    # ICD-10 codes (e.g., E11.9, I10) — diagnostic codes
    (
        "icd10",
        re.compile(r"\b([A-Z]\d{2}(?:\.\d{1,3})?)\b"),
        "[ICD]",
        {RedactionLevel.STRICT},
    ),
]


def redact_phi(
    text: str,
    *,
    level: RedactionLevel = RedactionLevel.STRICT,
) -> str:
    """
    Apply PHI redaction patterns to a string.

    Returns the redacted text. The original string is not modified.

    Examples:

        >>> redact_phi("Patient MRN12345678 prescribed 500 mg amoxicillin")
        'Patient [MRN] prescribed [DOSE] amoxicillin'

        >>> redact_phi(
        ...     "Call Dr. Smith at 555-123-4567",
        ...     level=RedactionLevel.RELAXED,
        ... )
        'Call Dr. Smith at [PHONE]'

        >>> redact_phi("No PHI here", level=RedactionLevel.NONE)
        'No PHI here'
    """
    if level == RedactionLevel.NONE:
        return text

    result = text
    for name, pattern, placeholder, applicable_levels in PHI_PATTERNS:
        if level not in applicable_levels:
            continue
        # Use the placeholder; fix the bug where name_after_honorific uses
        # the captured group incorrectly. We replace the whole match here.
        if name == "name_after_honorific":
            result = pattern.sub("[HONORIFIC][NAME]", result)
        else:
            result = pattern.sub(placeholder, result)
    return result


def is_likely_phi(text: str) -> bool:
    """
    Heuristic check: does this string likely contain PHI?

    Returns True if any STRICT-level pattern matches. Use as a guard before
    emitting potentially-leaky summary fields.
    """
    for _, pattern, _, applicable_levels in PHI_PATTERNS:
        if RedactionLevel.STRICT not in applicable_levels:
            continue
        if pattern.search(text):
            return True
    return False
