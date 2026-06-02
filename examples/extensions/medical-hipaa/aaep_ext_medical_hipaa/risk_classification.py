"""
risk_classification.py — Medical-domain risk classification.

Loads the default risk_table.json shipped with this extension and provides
a classifier function. Tool names match category keys exactly OR by prefix
(e.g., "prescribe_medication_v2" matches "prescribe_medication").

Deployments can override the table by passing a custom dict to
classify_medical_risk() or by loading a different JSON file.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files
from pathlib import Path
from typing import Literal

logger = logging.getLogger("aaep_ext_medical_hipaa.risk_classification")


MedicalRiskLevel = Literal["low", "medium", "high"]


@dataclass(frozen=True)
class MedicalRiskAssessment:
    """Outcome of medical risk classification for one tool."""

    tool_name: str
    risk_level: MedicalRiskLevel
    irreversible: bool
    rationale: str
    matched_category: str | None = None

    @property
    def requires_confirmation(self) -> bool:
        """True if this assessment requires an awaiting.confirmation event."""
        return self.irreversible or self.risk_level == "high"


@lru_cache(maxsize=1)
def load_risk_table(path: str | None = None) -> dict[str, dict]:
    """
    Load the default risk table. Cached so repeated calls don't re-read disk.

    If `path` is provided, loads from that file. Otherwise tries the bundled
    `risk_table.json` first, then a sibling file for dev checkouts.
    """
    if path is not None:
        return _read_table_from(Path(path))

    # Try package resources (works after pip install)
    try:
        resource = files("aaep_ext_medical_hipaa").joinpath(
            "..", "risk_table.json",
        )
        if resource.is_file():
            return _read_table_from_resource(resource)
    except (FileNotFoundError, AttributeError, ModuleNotFoundError):
        pass

    # Filesystem fallback for development checkouts
    here = Path(__file__).resolve().parent
    candidates = [
        here.parent / "risk_table.json",
        here.parent.parent / "risk_table.json",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return _read_table_from(candidate)

    raise FileNotFoundError(
        f"risk_table.json not found in any of: {candidates}",
    )


def _read_table_from(path: Path) -> dict[str, dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("categories", {})


def _read_table_from_resource(resource) -> dict[str, dict]:
    data = json.loads(resource.read_text(encoding="utf-8"))
    return data.get("categories", {})


def classify_medical_risk(
    tool_name: str,
    *,
    table: dict[str, dict] | None = None,
    default_risk_level: MedicalRiskLevel = "high",
    default_irreversible: bool = False,
) -> MedicalRiskAssessment:
    """
    Classify the risk of a medical tool invocation.

    Matching strategy:
        1. Exact match against table category names
        2. Prefix match (e.g., "prescribe_medication_v2" matches "prescribe_medication")
        3. Substring match for common patterns
        4. Default (configurable; defaults to high-risk reversible)

    The default is deliberately cautious: an unknown medical tool gets
    high-risk treatment until classified.

    Args:
        tool_name: The tool the agent is invoking
        table: Override the loaded risk table (for tests or custom configs)
        default_risk_level: Risk level for unmatched tools
        default_irreversible: Whether unmatched tools are treated as irreversible

    Returns:
        A MedicalRiskAssessment with classification and rationale
    """
    if table is None:
        try:
            table = load_risk_table()
        except FileNotFoundError:
            logger.warning("Risk table unavailable; using default classification")
            table = {}

    tool_lower = tool_name.lower()

    # 1. Exact match
    if tool_lower in table:
        entry = table[tool_lower]
        return MedicalRiskAssessment(
            tool_name=tool_name,
            risk_level=entry["risk_level"],
            irreversible=entry["irreversible"],
            rationale=entry.get("rationale", ""),
            matched_category=tool_lower,
        )

    # 2. Prefix match (tool_lower starts with a category name)
    for category, entry in table.items():
        if tool_lower.startswith(category):
            return MedicalRiskAssessment(
                tool_name=tool_name,
                risk_level=entry["risk_level"],
                irreversible=entry["irreversible"],
                rationale=f"Matched by prefix: {entry.get('rationale', '')}",
                matched_category=category,
            )

    # 3. Substring match for common keywords
    keyword_patterns = {
        "prescribe": "prescribe_medication",
        "order_": "order_lab_test",  # generic
        "imaging": "order_imaging",
        "referral": "send_referral",
        "appointment": "schedule_appointment",
        "chart": "read_patient_chart",
        "drug": "search_drug_database",
        "icd": "lookup_icd_code",
    }
    for keyword, category in keyword_patterns.items():
        if keyword in tool_lower and category in table:
            entry = table[category]
            return MedicalRiskAssessment(
                tool_name=tool_name,
                risk_level=entry["risk_level"],
                irreversible=entry["irreversible"],
                rationale=f"Matched by keyword '{keyword}': {entry.get('rationale', '')}",
                matched_category=category,
            )

    # 4. Default
    return MedicalRiskAssessment(
        tool_name=tool_name,
        risk_level=default_risk_level,
        irreversible=default_irreversible,
        rationale=(
            f"No match in risk table; defaulting to {default_risk_level} risk "
            f"({'irreversible' if default_irreversible else 'reversible'})"
        ),
        matched_category=None,
    )
