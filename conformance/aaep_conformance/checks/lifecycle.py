"""
Session lifecycle checks.

Verifies that every session has the expected lifecycle: starts with
agent.session.started, ends with exactly one terminal event (completed,
errored, or cancelled), and emits no events after the terminal event.
"""

from __future__ import annotations

from typing import Any

from aaep_conformance.reporter import Severity, TestResult


TERMINAL_EVENT_TYPES = {
    "aaep:agent.session.completed",
    "aaep:agent.session.errored",
    "aaep:agent.session.cancelled",
}

STARTED_EVENT_TYPE = "aaep:agent.session.started"


def check_session_terminates(
    events: list[dict[str, Any]],
    *,
    session_id: str | None = None,
    test_id: str = "L1-LIFE-001",
) -> TestResult:
    """
    Check that the session has at least one terminal event.

    If session_id is provided, filter to events of that session; otherwise
    check across all events (useful when only one session is being tested).
    """
    relevant = _filter_session(events, session_id)

    terminal_events = [
        e for e in relevant
        if e.get("type") in TERMINAL_EVENT_TYPES
    ]

    if terminal_events:
        return TestResult(
            test_id=test_id,
            description="Session terminates with a terminal lifecycle event",
            passed=True,
            spec_reference="Chapter 4 §4.1",
        )

    return TestResult(
        test_id=test_id,
        description="Session terminates with a terminal lifecycle event",
        passed=False,
        severity=Severity.ERROR,
        message="No terminal event (completed, errored, or cancelled) was emitted",
        expected="One of: agent.session.completed, agent.session.errored, agent.session.cancelled",
        actual=f"Events seen: {sorted({e.get('type', '') for e in relevant})}",
        spec_reference="Chapter 4 §4.1",
    )


def check_terminal_event_types(
    events: list[dict[str, Any]],
    *,
    session_id: str | None = None,
    test_id: str = "L1-LIFE-002",
) -> TestResult:
    """Check that the session has exactly ONE terminal event."""
    relevant = _filter_session(events, session_id)
    terminals = [e for e in relevant if e.get("type") in TERMINAL_EVENT_TYPES]

    if len(terminals) == 0:
        return TestResult(
            test_id=test_id,
            description="Session has exactly one terminal event",
            passed=False,
            severity=Severity.ERROR,
            message="No terminal event found",
            expected="Exactly 1",
            actual="0",
            spec_reference="Chapter 4 §4.1",
        )

    if len(terminals) > 1:
        types = [e.get("type") for e in terminals]
        return TestResult(
            test_id=test_id,
            description="Session has exactly one terminal event",
            passed=False,
            severity=Severity.ERROR,
            message=f"Multiple terminal events emitted: {types}",
            expected="Exactly 1",
            actual=f"{len(terminals)}: {types}",
            spec_reference="Chapter 4 §4.1",
        )

    return TestResult(
        test_id=test_id,
        description="Session has exactly one terminal event",
        passed=True,
        spec_reference="Chapter 4 §4.1",
    )


def check_lifecycle_ordering(
    events: list[dict[str, Any]],
    *,
    session_id: str | None = None,
    test_id: str = "L1-LIFE-003",
) -> TestResult:
    """
    Check lifecycle ordering rules:

    1. session.started must be the first event (if present at all)
    2. terminal event must be the last event
    3. No events emitted after a terminal event
    """
    relevant = _filter_session(events, session_id)

    if not relevant:
        return TestResult(
            test_id=test_id,
            description="Lifecycle event ordering is valid",
            passed=False,
            severity=Severity.ERROR,
            message="No events to check",
            spec_reference="Chapter 4 §4.1",
        )

    issues: list[str] = []

    # 1. Started must be first if present
    started_indices = [
        i for i, e in enumerate(relevant) if e.get("type") == STARTED_EVENT_TYPE
    ]
    if started_indices and started_indices[0] != 0:
        issues.append(
            f"agent.session.started appears at position {started_indices[0]}, "
            f"not the first event"
        )
    if len(started_indices) > 1:
        issues.append(
            f"agent.session.started emitted {len(started_indices)} times "
            f"(expected at most once)"
        )

    # 2. Terminal events must be last
    terminal_indices = [
        i for i, e in enumerate(relevant)
        if e.get("type") in TERMINAL_EVENT_TYPES
    ]
    if terminal_indices:
        last_terminal = max(terminal_indices)
        if last_terminal != len(relevant) - 1:
            after = relevant[last_terminal + 1].get("type")
            issues.append(
                f"Event of type {after!r} emitted after terminal event "
                f"(at position {last_terminal + 1})"
            )

    if issues:
        return TestResult(
            test_id=test_id,
            description="Lifecycle event ordering is valid",
            passed=False,
            severity=Severity.ERROR,
            message="; ".join(issues),
            spec_reference="Chapter 4 §4.1",
        )

    return TestResult(
        test_id=test_id,
        description="Lifecycle event ordering is valid",
        passed=True,
        spec_reference="Chapter 4 §4.1",
    )


def check_session_started_present(
    events: list[dict[str, Any]],
    *,
    session_id: str | None = None,
    test_id: str = "L1-LIFE-004",
) -> TestResult:
    """Check that the session has at least one agent.session.started event."""
    relevant = _filter_session(events, session_id)
    has_started = any(e.get("type") == STARTED_EVENT_TYPE for e in relevant)

    if has_started:
        return TestResult(
            test_id=test_id,
            description="Session has an agent.session.started event",
            passed=True,
            spec_reference="Chapter 4 §4.1.1",
        )

    return TestResult(
        test_id=test_id,
        description="Session has an agent.session.started event",
        passed=False,
        severity=Severity.ERROR,
        message="No agent.session.started event found",
        expected="agent.session.started present",
        actual="Not present",
        spec_reference="Chapter 4 §4.1.1",
    )


# === Helpers ===

def _filter_session(
    events: list[dict[str, Any]],
    session_id: str | None,
) -> list[dict[str, Any]]:
    """Filter events to those belonging to the given session_id."""
    if session_id is None:
        return events
    return [e for e in events if e.get("session_id") == session_id]


__all__ = [
    "TERMINAL_EVENT_TYPES",
    "STARTED_EVENT_TYPE",
    "check_session_terminates",
    "check_terminal_event_types",
    "check_lifecycle_ordering",
    "check_session_started_present",
]
