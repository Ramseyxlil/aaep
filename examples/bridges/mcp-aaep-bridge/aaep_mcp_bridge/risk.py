"""
risk.py — Risk classification for MCP tools.

Decides whether a given MCP tool invocation requires an
`agent.awaiting.confirmation` event before proceeding. The default heuristic
matches python-minimal's classify_risk. User overrides via RiskConfig let
operators tune the policy without modifying code.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal


# Tool name substrings that imply high-risk irreversible action.
# Matches python-minimal's classify_risk heuristic for consistency.
_HIGH_RISK_PATTERNS = (
    "send_", "delete_", "transfer_", "write_",
    "execute_", "publish_", "make_payment", "purchase",
    "create_", "remove_", "drop_",  # MCP-flavored variations
)


RiskLevel = Literal["low", "medium", "high"]


@dataclass(frozen=True)
class RiskAssessment:
    """Outcome of risk classification for one tool."""

    risk_level: RiskLevel
    irreversible: bool

    @property
    def requires_confirmation(self) -> bool:
        """True if this assessment requires an awaiting.confirmation event."""
        return self.irreversible or self.risk_level == "high"


@dataclass
class RiskConfig:
    """User-configurable risk policy. Empty config falls back to heuristics."""

    tool_overrides: dict[str, RiskAssessment] = field(default_factory=dict)
    default: RiskAssessment | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RiskConfig":
        overrides_raw = data.get("tool_overrides", {})
        overrides = {
            name: RiskAssessment(
                risk_level=v.get("risk_level", "low"),
                irreversible=bool(v.get("irreversible", False)),
            )
            for name, v in overrides_raw.items()
        }
        default_raw = data.get("default")
        default = None
        if isinstance(default_raw, dict):
            default = RiskAssessment(
                risk_level=default_raw.get("risk_level", "low"),
                irreversible=bool(default_raw.get("irreversible", False)),
            )
        return cls(tool_overrides=overrides, default=default)

    @classmethod
    def from_file(cls, path: str | Path) -> "RiskConfig":
        """Load risk config from a JSON file. Raises FileNotFoundError if missing."""
        text = Path(path).read_text(encoding="utf-8")
        return cls.from_dict(json.loads(text))

    def classify(self, tool_name: str) -> RiskAssessment:
        """Determine risk for one tool, with override precedence."""
        # 1. Explicit override wins
        if tool_name in self.tool_overrides:
            return self.tool_overrides[tool_name]
        # 2. Default if set
        if self.default is not None:
            # But still apply heuristic for known-dangerous names
            if _matches_high_risk(tool_name):
                return RiskAssessment(risk_level="high", irreversible=True)
            return self.default
        # 3. Pure heuristic
        if _matches_high_risk(tool_name):
            return RiskAssessment(risk_level="high", irreversible=True)
        return RiskAssessment(risk_level="low", irreversible=False)


def _matches_high_risk(tool_name: str) -> bool:
    lower = tool_name.lower()
    return any(p in lower for p in _HIGH_RISK_PATTERNS)
