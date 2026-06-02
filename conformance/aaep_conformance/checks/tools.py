"""
Tool invocation checks.

Verifies the agent.tool.invoked → agent.tool.completed pairing rules:
every invocation must be followed by completion, tool_call_id must match
across the pair, status must be a valid enum value, and there must be no
orphan completion events (completions without a prior invocation).
"""

from __future__ import annotations

from typing import Any

from aaep_conformance.reporter import Severity, TestResult


TOOL_INVOKED_TYPE = "aaep:agent.tool.invoked"
TOOL_COMPLETED_TYPE = "aaep:agent.tool.completed"
VALID_TOOL_STATUSES = {"success", "error", "timeout"}


def check_tool_invoked_before_completed(
    events: list[dict[str, Any]],
    *,
    session_id: str | None = None,
    test_id: str = "L1-TOOL-001",
) -> TestResult:
    """
    Check that every agent.tool.completed is preceded by a matching
    agent.tool.invoked with the same tool_call_id (or same tool name if
    tool_call_id is absent).
    """
    relevant = _filter_session(events, session_id)
    seen_invocations: set[str] = set()
    orphans: list[dict[str, Any]] = []

    for event in relevant:
        event_type = event.get("type")
        if event_type == TOOL_INVOKED_TYPE:
            key = _pairing_key(event)
            seen_invocations.add(key)
        elif event_type == TOOL_COMPLETED_TYPE:
            key = _pairing_key(event)
            if key not in seen_invocations:
                orphans.append(event)

    if orphans:
        orphan_descs = [
            f"tool={e.get('tool')!r} tool_call_id={e.get('tool_call_id')!r}"
            for e in orphans[:5]
        ]
        return TestResult(
            test_id=test_id,
            description="Every tool.completed is preceded by a matching tool.invoked",
            passed=False,
            severity=Severity.ERROR,
            message=f"Found {len(orphans)} orphan completion(s): {orphan_descs}",
            expected="Each tool.completed preceded by matching tool.invoked",
            actual=f"{len(orphans)} orphan completion(s)",
            spec_reference="Chapter 4 §4.3.2",
        )

    return TestResult(
        test_id=test_id,
        description="Every tool.completed is preceded by a matching tool.invoked",
        passed=True,
        spec_reference="Chapter 4 §4.3.2",
    )


def check_tool_call_id_pairing(
    events: list[dict[str, Any]],
    *,
    session_id: str | None = None,
    test_id: str = "L1-TOOL-002",
) -> TestResult:
    """
    Check that every tool.invoked event with a tool_call_id has exactly
    one matching tool.completed with the same tool_call_id.
    """
    relevant = _filter_session(events, session_id)

    invocations: dict[str, dict[str, Any]] = {}
    completions: dict[str, list[dict[str, Any]]] = {}

    for event in relevant:
        call_id = event.get("tool_call_id")
        if not call_id:
            continue
        if event.get("type") == TOOL_INVOKED_TYPE:
            if call_id in invocations:
                return TestResult(
                    test_id=test_id,
                    description="tool_call_id values are unique within a session",
                    passed=False,
                    severity=Severity.ERROR,
                    message=f"Duplicate tool_call_id: {call_id}",
                    expected="Each tool_call_id used exactly once for invocation",
                    actual=f"tool_call_id {call_id!r} used multiple times",
                    spec_reference="Chapter 4 §4.3.1",
                )
            invocations[call_id] = event
        elif event.get("type") == TOOL_COMPLETED_TYPE:
            completions.setdefault(call_id, []).append(event)

    issues: list[str] = []
    for call_id, invoke_event in invocations.items():
        matching = completions.get(call_id, [])
        if len(matching) == 0:
            issues.append(f"tool_call_id {call_id!r} (tool={invoke_event.get('tool')!r}) has no completion")
        elif len(matching) > 1:
            issues.append(
                f"tool_call_id {call_id!r} has {len(matching)} completions (expected 1)"
            )

    # Also check for completions without matching invocations
    for call_id in completions:
        if call_id not in invocations:
            issues.append(f"tool_call_id {call_id!r} completion without invocation")

    if issues:
        return TestResult(
            test_id=test_id,
            description="tool_call_id pairing is one-to-one between invoked and completed",
            passed=False,
            severity=Severity.ERROR,
            message="; ".join(issues[:5]),
            spec_reference="Chapter 4 §4.3.1, §4.3.2",
        )

    return TestResult(
        test_id=test_id,
        description="tool_call_id pairing is one-to-one between invoked and completed",
        passed=True,
        spec_reference="Chapter 4 §4.3.1, §4.3.2",
    )


def check_tool_status_enum(
    events: list[dict[str, Any]],
    *,
    session_id: str | None = None,
    test_id: str = "L1-TOOL-003",
) -> TestResult:
    """
    Check that every agent.tool.completed event has a status that is one
    of the normative enum values: success, error, timeout.
    """
    relevant = _filter_session(events, session_id)
    completions = [e for e in relevant if e.get("type") == TOOL_COMPLETED_TYPE]

    if not completions:
        return TestResult(
            test_id=test_id,
            description="tool.completed events have valid status values",
            passed=True,
            severity=Severity.INFO,
            message="No tool.completed events to check",
            spec_reference="Chapter 4 §4.3.2",
        )

    invalid: list[str] = []
    for event in completions:
        status = event.get("status")
        if status not in VALID_TOOL_STATUSES:
            invalid.append(
                f"tool={event.get('tool')!r} status={status!r} "
                f"(call_id={event.get('tool_call_id')!r})"
            )

    if invalid:
        return TestResult(
            test_id=test_id,
            description="tool.completed events have valid status values",
            passed=False,
            severity=Severity.ERROR,
            message=f"Invalid status value(s): {'; '.join(invalid[:3])}",
            expected=f"One of: {sorted(VALID_TOOL_STATUSES)}",
            actual="See message",
            spec_reference="Chapter 4 §4.3.2",
        )

    return TestResult(
        test_id=test_id,
        description="tool.completed events have valid status values",
        passed=True,
        spec_reference="Chapter 4 §4.3.2",
    )


def check_tool_name_consistency(
    events: list[dict[str, Any]],
    *,
    session_id: str | None = None,
    test_id: str = "L1-TOOL-004",
) -> TestResult:
    """
    Check that for each tool_call_id, the tool name in the invoked event
    matches the tool name in its completion.
    """
    relevant = _filter_session(events, session_id)

    invoked_names: dict[str, str] = {}
    mismatches: list[str] = []

    for event in relevant:
        call_id = event.get("tool_call_id")
        if not call_id:
            continue
        tool_name = event.get("tool", "")
        event_type = event.get("type")

        if event_type == TOOL_INVOKED_TYPE:
            invoked_names[call_id] = tool_name
        elif event_type == TOOL_COMPLETED_TYPE:
            expected_name = invoked_names.get(call_id)
            if expected_name is not None and expected_name != tool_name:
                mismatches.append(
                    f"call_id={call_id!r}: invoked tool={expected_name!r}, "
                    f"completed tool={tool_name!r}"
                )

    if mismatches:
        return TestResult(
            test_id=test_id,
            description="Tool name is consistent between invoked and completed",
            passed=False,
            severity=Severity.ERROR,
            message="; ".join(mismatches[:3]),
            spec_reference="Chapter 4 §4.3.2",
        )

    return TestResult(
        test_id=test_id,
        description="Tool name is consistent between invoked and completed",
        passed=True,
        spec_reference="Chapter 4 §4.3.2",
    )


def check_tool_invoked_before_side_effect(
    events: list[dict[str, Any]],
    irreversible_events: list[dict[str, Any]],
    *,
    test_id: str = "L2-TOOL-005",
) -> TestResult:
    """
    For irreversible tool invocations, check that agent.awaiting.confirmation
    was emitted BEFORE the tool.invoked in the event stream.
    """
    issues: list[str] = []
    for event in irreversible_events:
        if event.get("type") != TOOL_INVOKED_TYPE:
            continue
        if not event.get("irreversible"):
            continue

        idx = events.index(event)
        prior_events = events[:idx]
        had_confirmation = any(
            e.get("type") == "aaep:agent.awaiting.confirmation"
            and e.get("session_id") == event.get("session_id")
            for e in prior_events
        )
        if not had_confirmation:
            issues.append(
                f"Irreversible tool {event.get('tool')!r} (call_id={event.get('tool_call_id')!r}) "
                f"invoked without prior confirmation event"
            )

    if issues:
        return TestResult(
            test_id=test_id,
            description="Irreversible tool calls are preceded by confirmation events",
            passed=False,
            severity=Severity.ERROR,
            message="; ".join(issues[:3]),
            spec_reference="Chapter 4 §4.3.1, Chapter 6 §6.1",
        )

    return TestResult(
        test_id=test_id,
        description="Irreversible tool calls are preceded by confirmation events",
        passed=True,
        spec_reference="Chapter 4 §4.3.1, Chapter 6 §6.1",
    )


# === Helpers ===

def _filter_session(
    events: list[dict[str, Any]],
    session_id: str | None,
) -> list[dict[str, Any]]:
    if session_id is None:
        return events
    return [e for e in events if e.get("session_id") == session_id]


def _pairing_key(event: dict[str, Any]) -> str:
    """
    Compute a key for pairing tool.invoked with tool.completed.
    Uses tool_call_id when present, otherwise falls back to tool name.
    """
    call_id = event.get("tool_call_id")
    if call_id:
        return f"call:{call_id}"
    return f"tool:{event.get('tool', '')}"


__all__ = [
    "TOOL_INVOKED_TYPE",
    "TOOL_COMPLETED_TYPE",
    "VALID_TOOL_STATUSES",
    "check_tool_invoked_before_completed",
    "check_tool_call_id_pairing",
    "check_tool_status_enum",
    "check_tool_name_consistency",
    "check_tool_invoked_before_side_effect",
]
