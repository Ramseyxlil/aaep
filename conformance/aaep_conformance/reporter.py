"""
Report generation — produces JSON and HTML conformance reports.

A Report aggregates TestResults from a conformance run and can be
serialized to JSON (for CI consumption) or HTML (for human review).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


# === Enums ===

class Severity(str, Enum):
    """Severity of a test failure."""

    ERROR = "error"
    """Hard spec violation. Blocks conformance claim."""

    WARNING = "warning"
    """Spec ambiguity or SHOULD-not-MUST violation. Worth investigating."""

    INFO = "info"
    """Behavior worth noting. Does not affect conformance."""


class Verdict(str, Enum):
    """Overall verdict for a conformance run."""

    PASS = "PASS"
    """All required tests passed."""

    FAIL = "FAIL"
    """One or more required tests failed."""

    SKIPPED = "SKIPPED"
    """No tests ran (filtered out or unsupported configuration)."""


# === Data classes ===

@dataclass
class TestResult:
    """The result of a single test case."""

    test_id: str
    """Identifier in the form 'L1-ENV-001' or similar."""

    description: str
    """One-line summary of what the test verified."""

    passed: bool
    """True if the implementation conformed to the test's expectation."""

    severity: Severity = Severity.INFO
    """If passed=False, how severe the failure is."""

    message: str = ""
    """Human-readable message about the result."""

    expected: str | None = None
    """What the test expected to observe."""

    actual: str | None = None
    """What the test actually observed."""

    duration_ms: float = 0.0
    """How long the test took."""

    spec_reference: str | None = None
    """Optional reference to the spec section this test verifies."""

    def to_dict(self) -> dict[str, Any]:
        return {
            "test_id": self.test_id,
            "description": self.description,
            "passed": self.passed,
            "severity": self.severity.value,
            "message": self.message,
            "expected": self.expected,
            "actual": self.actual,
            "duration_ms": self.duration_ms,
            "spec_reference": self.spec_reference,
        }


@dataclass
class Report:
    """Aggregate report of a conformance test run."""

    conformance_level: int
    endpoint: str
    verdict: Verdict
    duration_seconds: float
    test_results: list[TestResult]
    metadata: dict[str, Any] = field(default_factory=dict)
    started_at: str = ""
    completed_at: str = ""

    def __post_init__(self) -> None:
        from aaep_conformance import __version__, __aaep_spec_version__
        if not self.metadata:
            self.metadata = {}
        self.metadata.setdefault("aaep_spec_version", __aaep_spec_version__)
        self.metadata.setdefault("suite_version", __version__)
        if not self.completed_at:
            self.completed_at = datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%S.") + f"{datetime.now(timezone.utc).microsecond // 1000:03d}Z"
        if not self.started_at:
            from datetime import timedelta
            start_dt = datetime.now(timezone.utc) - timedelta(seconds=self.duration_seconds)
            self.started_at = start_dt.strftime(
                "%Y-%m-%dT%H:%M:%S.") + f"{start_dt.microsecond // 1000:03d}Z"

    # === Aggregates ===

    @property
    def tests_run(self) -> int:
        return len(self.test_results)

    @property
    def tests_passed(self) -> int:
        return sum(1 for r in self.test_results if r.passed)

    @property
    def tests_failed(self) -> int:
        return sum(1 for r in self.test_results if not r.passed and r.severity != Severity.INFO)

    @property
    def tests_skipped(self) -> int:
        return sum(1 for r in self.test_results if not r.passed and r.severity == Severity.INFO)

    @property
    def pass_rate(self) -> float:
        if self.tests_run == 0:
            return 0.0
        # Pass rate excludes info-level "skipped" results
        countable = self.tests_run - self.tests_skipped
        if countable == 0:
            return 0.0
        return self.tests_passed / countable

    @property
    def failures(self) -> list[TestResult]:
        return [r for r in self.test_results if not r.passed]

    @property
    def errors(self) -> list[TestResult]:
        return [r for r in self.test_results if not r.passed and r.severity == Severity.ERROR]

    @property
    def warnings(self) -> list[TestResult]:
        return [r for r in self.test_results if not r.passed and r.severity == Severity.WARNING]

    # === Factory ===

    @classmethod
    def from_results(
        cls,
        test_results: list[TestResult],
        *,
        conformance_level: int,
        endpoint: str,
        duration_seconds: float,
        metadata: dict[str, Any] | None = None,
    ) -> "Report":
        """Build a Report by computing the verdict from results."""
        verdict = _compute_verdict(test_results)
        return cls(
            conformance_level=conformance_level,
            endpoint=endpoint,
            verdict=verdict,
            duration_seconds=duration_seconds,
            test_results=test_results,
            metadata=metadata or {},
        )

    # === Serialization ===

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dict representation."""
        return {
            "aaep_spec_version": self.metadata.get("aaep_spec_version", "unknown"),
            "suite_version": self.metadata.get("suite_version", "unknown"),
            "conformance_level": self.conformance_level,
            "endpoint": self.endpoint,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_seconds": round(self.duration_seconds, 3),
            "verdict": self.verdict.value,
            "tests_run": self.tests_run,
            "tests_passed": self.tests_passed,
            "tests_failed": self.tests_failed,
            "tests_skipped": self.tests_skipped,
            "pass_rate": round(self.pass_rate, 4),
            "metadata": self.metadata,
            "test_results": [r.to_dict() for r in self.test_results],
            "failures": [r.to_dict() for r in self.failures],
        }

    def save_json(self, path: Path | str) -> None:
        """Write the report to a JSON file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def save_html(self, path: Path | str) -> None:
        """Write the report to an HTML file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_html(), encoding="utf-8")

    def to_html(self) -> str:
        """Render the report as a standalone HTML document."""
        verdict_color = {
            Verdict.PASS: "#0a7d27",
            Verdict.FAIL: "#c22020",
            Verdict.SKIPPED: "#b88600",
        }.get(self.verdict, "#444")

        rows_html = []
        for result in self.test_results:
            status_color = "#0a7d27" if result.passed else (
                "#c22020" if result.severity == Severity.ERROR else "#b88600"
            )
            status_text = "PASS" if result.passed else result.severity.value.upper()
            rows_html.append(f"""
            <tr>
              <td class="mono">{_escape(result.test_id)}</td>
              <td>{_escape(result.description)}</td>
              <td style="color: {status_color}; font-weight: 600;">{status_text}</td>
              <td>{_escape(result.message)}</td>
            </tr>""")

        rows_str = "".join(rows_html)
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>AAEP Conformance Report</title>
<style>
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
    max-width: 1200px;
    margin: 2rem auto;
    padding: 0 1rem;
    color: #222;
  }}
  h1 {{ margin-bottom: 0.5rem; }}
  .meta {{ color: #666; font-size: 0.9rem; margin-bottom: 2rem; }}
  .verdict {{
    display: inline-block;
    padding: 0.5rem 1.5rem;
    background: {verdict_color};
    color: white;
    font-size: 1.5rem;
    font-weight: 600;
    border-radius: 4px;
    margin-bottom: 1rem;
  }}
  .stats {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 1rem; margin-bottom: 2rem; }}
  .stat {{ padding: 1rem; background: #f5f5f5; border-radius: 4px; }}
  .stat-label {{ font-size: 0.8rem; text-transform: uppercase; color: #666; }}
  .stat-value {{ font-size: 1.8rem; font-weight: 600; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 1rem; }}
  th, td {{ padding: 0.5rem; text-align: left; border-bottom: 1px solid #ddd; }}
  th {{ background: #f5f5f5; font-weight: 600; }}
  .mono {{ font-family: "SF Mono", Monaco, Consolas, monospace; font-size: 0.9rem; }}
  footer {{ margin-top: 3rem; color: #999; font-size: 0.85rem; }}
</style>
</head>
<body>
  <h1>AAEP Conformance Report</h1>
  <div class="meta">
    Endpoint: <span class="mono">{_escape(self.endpoint)}</span><br>
    Tested at: {_escape(self.completed_at)}<br>
    Duration: {self.duration_seconds:.1f}s<br>
    Spec version: {_escape(self.metadata.get("aaep_spec_version", "unknown"))} ·
    Suite version: {_escape(self.metadata.get("suite_version", "unknown"))}
  </div>

  <div class="verdict">{self.verdict.value}</div>
  <div style="font-size: 1.1rem; margin-bottom: 2rem;">
    Conformance Level <strong>{self.conformance_level}</strong>
  </div>

  <div class="stats">
    <div class="stat">
      <div class="stat-label">Tests Run</div>
      <div class="stat-value">{self.tests_run}</div>
    </div>
    <div class="stat">
      <div class="stat-label">Passed</div>
      <div class="stat-value" style="color: #0a7d27;">{self.tests_passed}</div>
    </div>
    <div class="stat">
      <div class="stat-label">Failed</div>
      <div class="stat-value" style="color: #c22020;">{self.tests_failed}</div>
    </div>
    <div class="stat">
      <div class="stat-label">Skipped</div>
      <div class="stat-value" style="color: #b88600;">{self.tests_skipped}</div>
    </div>
    <div class="stat">
      <div class="stat-label">Pass Rate</div>
      <div class="stat-value">{self.pass_rate:.1%}</div>
    </div>
  </div>

  <h2>Test Results</h2>
  <table>
    <thead>
      <tr><th>Test ID</th><th>Description</th><th>Status</th><th>Message</th></tr>
    </thead>
    <tbody>
      {rows_str}
    </tbody>
  </table>

  <footer>
    Generated by <a href="https://github.com/Ramseyxlil/aaep">aaep-conformance</a>
    against AAEP specification version {_escape(self.metadata.get("aaep_spec_version", "unknown"))}.
    See <a href="https://aaep-protocol.org/conformance/">aaep-protocol.org/conformance/</a>
    for documentation.
  </footer>
</body>
</html>"""


# === Helpers ===

def _compute_verdict(results: list[TestResult]) -> Verdict:
    """Determine the overall verdict from a list of test results."""
    if not results:
        return Verdict.SKIPPED
    has_errors = any(
        not r.passed and r.severity == Severity.ERROR for r in results
    )
    return Verdict.FAIL if has_errors else Verdict.PASS


def _escape(text: Any) -> str:
    """HTML-escape a value."""
    if text is None:
        return ""
    s = str(text)
    return (s.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;")
             .replace('"', "&quot;")
             .replace("'", "&#39;"))


__all__ = [
    "Severity",
    "Verdict",
    "TestResult",
    "Report",
]
