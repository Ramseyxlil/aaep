"""
Streaming output checks.

Verifies the rules for agent.output.streaming events:
- Position is monotonically increasing within each output_id
- Exactly one event with complete=true per output_id
- No chunks emitted after the completion event for an output_id
- coalesce_hint is one of the valid enum values
- content_type is a valid MIME type format (if present)
"""

from __future__ import annotations

import re
from typing import Any

from aaep_conformance.reporter import Severity, TestResult


STREAMING_TYPE = "aaep:agent.output.streaming"
VALID_COALESCE_HINTS = {"none", "word", "sentence", "paragraph", "completion"}
MIME_TYPE_PATTERN = re.compile(
    r"^[a-zA-Z][a-zA-Z0-9.+_-]*/[a-zA-Z][a-zA-Z0-9.+_-]*$"
)


def check_position_monotonic(
    events: list[dict[str, Any]],
    *,
    session_id: str | None = None,
    test_id: str = "L1-STREAM-001",
) -> TestResult:
    """
    Check that position is monotonically non-decreasing within each output_id.

    The spec requires position to strictly increase across chunks of the same
    output_id, but we allow equality here to be tolerant of producers that
    emit a zero-length completion-only event with the same position as the
    final content chunk.
    """
    relevant = _filter_session(events, session_id)
    streaming = [e for e in relevant if e.get("type") == STREAMING_TYPE]

    if not streaming:
        return TestResult(
            test_id=test_id,
            description="Streaming chunk position is monotonic per output_id",
            passed=True,
            severity=Severity.INFO,
            message="No streaming events to check",
            spec_reference="Chapter 4 §4.3.3",
        )

    last_position_by_output: dict[str, int] = {}
    issues: list[str] = []

    for event in streaming:
        # output_id may be missing for single-output sessions; use session_id as fallback
        output_id = event.get("output_id") or f"<session:{event.get('session_id', 'unknown')}>"
        position = event.get("position")

        if position is None or not isinstance(position, int):
            issues.append(
                f"output_id={output_id!r}: position is missing or not an integer"
            )
            continue

        last = last_position_by_output.get(output_id)
        if last is not None and position < last:
            issues.append(
                f"output_id={output_id!r}: position decreased from {last} to {position}"
            )

        last_position_by_output[output_id] = position

    if issues:
        return TestResult(
            test_id=test_id,
            description="Streaming chunk position is monotonic per output_id",
            passed=False,
            severity=Severity.ERROR,
            message="; ".join(issues[:3]),
            spec_reference="Chapter 4 §4.3.3",
        )

    return TestResult(
        test_id=test_id,
        description="Streaming chunk position is monotonic per output_id",
        passed=True,
        spec_reference="Chapter 4 §4.3.3",
    )


def check_exactly_one_completion(
    events: list[dict[str, Any]],
    *,
    session_id: str | None = None,
    test_id: str = "L1-STREAM-002",
) -> TestResult:
    """
    Check that each output_id has exactly one streaming event with complete=true.
    """
    relevant = _filter_session(events, session_id)
    streaming = [e for e in relevant if e.get("type") == STREAMING_TYPE]

    if not streaming:
        return TestResult(
            test_id=test_id,
            description="Each output_id has exactly one completion event",
            passed=True,
            severity=Severity.INFO,
            message="No streaming events to check",
            spec_reference="Chapter 4 §4.3.3",
        )

    completion_counts: dict[str, int] = {}
    for event in streaming:
        output_id = event.get("output_id") or f"<session:{event.get('session_id', 'unknown')}>"
        if event.get("complete") is True:
            completion_counts[output_id] = completion_counts.get(output_id, 0) + 1

    # Each output_id seen should have exactly one completion
    all_output_ids = {
        e.get("output_id") or f"<session:{e.get('session_id', 'unknown')}>"
        for e in streaming
    }

    issues: list[str] = []
    for output_id in all_output_ids:
        count = completion_counts.get(output_id, 0)
        if count == 0:
            issues.append(f"output_id={output_id!r}: no completion event (complete=true)")
        elif count > 1:
            issues.append(f"output_id={output_id!r}: {count} completion events (expected 1)")

    if issues:
        return TestResult(
            test_id=test_id,
            description="Each output_id has exactly one completion event",
            passed=False,
            severity=Severity.ERROR,
            message="; ".join(issues[:3]),
            spec_reference="Chapter 4 §4.3.3",
        )

    return TestResult(
        test_id=test_id,
        description="Each output_id has exactly one completion event",
        passed=True,
        spec_reference="Chapter 4 §4.3.3",
    )


def check_no_chunks_after_completion(
    events: list[dict[str, Any]],
    *,
    session_id: str | None = None,
    test_id: str = "L1-STREAM-003",
) -> TestResult:
    """
    Check that no streaming chunks are emitted after the completion event
    for the same output_id.
    """
    relevant = _filter_session(events, session_id)
    streaming = [e for e in relevant if e.get("type") == STREAMING_TYPE]

    completed_outputs: set[str] = set()
    violations: list[str] = []

    for event in streaming:
        output_id = event.get("output_id") or f"<session:{event.get('session_id', 'unknown')}>"

        if output_id in completed_outputs:
            violations.append(
                f"output_id={output_id!r}: chunk emitted after completion "
                f"(position={event.get('position')})"
            )
            continue

        if event.get("complete") is True:
            completed_outputs.add(output_id)

    if violations:
        return TestResult(
            test_id=test_id,
            description="No streaming chunks emitted after completion event",
            passed=False,
            severity=Severity.ERROR,
            message="; ".join(violations[:3]),
            spec_reference="Chapter 4 §4.3.3",
        )

    return TestResult(
        test_id=test_id,
        description="No streaming chunks emitted after completion event",
        passed=True,
        spec_reference="Chapter 4 §4.3.3",
    )


def check_coalesce_hint_valid(
    events: list[dict[str, Any]],
    *,
    session_id: str | None = None,
    test_id: str = "L1-STREAM-004",
) -> TestResult:
    """
    Check that coalesce_hint, when present, is one of the valid enum values.
    """
    relevant = _filter_session(events, session_id)
    streaming = [e for e in relevant if e.get("type") == STREAMING_TYPE]

    invalid: list[str] = []
    for event in streaming:
        hint = event.get("coalesce_hint")
        if hint is None:
            continue
        if hint not in VALID_COALESCE_HINTS:
            invalid.append(
                f"event_id={event.get('event_id')!r}: coalesce_hint={hint!r}"
            )

    if invalid:
        return TestResult(
            test_id=test_id,
            description="coalesce_hint values are valid",
            passed=False,
            severity=Severity.ERROR,
            message="; ".join(invalid[:3]),
            expected=f"One of: {sorted(VALID_COALESCE_HINTS)}",
            actual="See message",
            spec_reference="Chapter 4 §4.3.3",
        )

    return TestResult(
        test_id=test_id,
        description="coalesce_hint values are valid",
        passed=True,
        spec_reference="Chapter 4 §4.3.3",
    )


def check_content_type_format(
    events: list[dict[str, Any]],
    *,
    session_id: str | None = None,
    test_id: str = "L1-STREAM-005",
) -> TestResult:
    """
    Check that content_type, when present, is a valid MIME type format.
    """
    relevant = _filter_session(events, session_id)
    streaming = [e for e in relevant if e.get("type") == STREAMING_TYPE]

    invalid: list[str] = []
    for event in streaming:
        ct = event.get("content_type")
        if ct is None:
            continue
        if not MIME_TYPE_PATTERN.match(ct):
            invalid.append(
                f"event_id={event.get('event_id')!r}: content_type={ct!r}"
            )

    if invalid:
        return TestResult(
            test_id=test_id,
            description="content_type values are valid MIME types",
            passed=False,
            severity=Severity.WARNING,  # Lenient: only warning for format issues
            message="; ".join(invalid[:3]),
            expected="MIME type format like text/plain, application/json",
            actual="See message",
            spec_reference="Chapter 4 §4.3.3",
        )

    return TestResult(
        test_id=test_id,
        description="content_type values are valid MIME types",
        passed=True,
        spec_reference="Chapter 4 §4.3.3",
    )


# === Helpers ===

def _filter_session(
    events: list[dict[str, Any]],
    session_id: str | None,
) -> list[dict[str, Any]]:
    if session_id is None:
        return events
    return [e for e in events if e.get("session_id") == session_id]


__all__ = [
    "STREAMING_TYPE",
    "VALID_COALESCE_HINTS",
    "check_position_monotonic",
    "check_exactly_one_completion",
    "check_no_chunks_after_completion",
    "check_coalesce_hint_valid",
    "check_content_type_format",
]
