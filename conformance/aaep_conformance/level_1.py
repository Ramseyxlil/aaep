"""
Level 1 (Notification) test suite.

Level 1 verifies that a producer emits well-formed AAEP events with valid
envelopes, lifecycle, tool invocations, and streaming output. No reply
channel is required at Level 1.

The runner invokes get_tests(target_kind, profile) to obtain a list of
(test_id, test_function) tuples. Each test function is an async coroutine
that takes a TestContext and returns a list of TestResult objects.
"""

from __future__ import annotations

from typing import Any, Callable

from aaep_conformance.checks import (
    check_envelope_required_fields,
    check_event_id_format,
    check_session_id_format,
    check_timestamp_format,
    check_producer_field,
    check_session_terminates,
    check_terminal_event_types,
    check_lifecycle_ordering,
    check_tool_invoked_before_completed,
    check_tool_call_id_pairing,
    check_tool_status_enum,
    check_position_monotonic,
    check_exactly_one_completion,
    check_coalesce_hint_valid,
    check_critical_urgency_on_errored,
)
from aaep_conformance.checks.envelope import validate_event
from aaep_conformance.checks.lifecycle import check_session_started_present
from aaep_conformance.checks.streaming import check_no_chunks_after_completion
from aaep_conformance.checks.safety import check_no_secrets_in_args_summary
from aaep_conformance.checks.tools import check_tool_name_consistency
from aaep_conformance.reporter import Severity, TestResult


# === Test scenarios ===

async def test_envelope_structure_simple_session(ctx) -> list[TestResult]:
    """L1-ENV: Verify envelope structure across a simple session."""
    session_id = await ctx.request_session("Hello, please respond briefly.")
    events = await _collect_session_events(ctx, session_id, timeout=10)

    results: list[TestResult] = []
    for i, event in enumerate(events):
        results.append(check_envelope_required_fields(
            event, test_id=f"L1-ENV-001-evt{i}"
        ))
        results.append(check_event_id_format(
            event, test_id=f"L1-ENV-002-evt{i}"
        ))
        results.append(check_session_id_format(
            event, test_id=f"L1-ENV-003-evt{i}"
        ))
        results.append(check_timestamp_format(
            event, test_id=f"L1-ENV-004-evt{i}"
        ))
        results.append(check_producer_field(
            event, test_id=f"L1-ENV-005-evt{i}"
        ))

    # Also do a full schema validation
    for i, event in enumerate(events):
        errors = validate_event(event)
        results.append(TestResult(
            test_id=f"L1-ENV-006-evt{i}",
            description="Event validates against its type-specific JSON Schema",
            passed=not errors,
            severity=Severity.ERROR if errors else Severity.INFO,
            message="; ".join(errors[:3]) if errors else "",
            spec_reference="Chapter 3",
        ))

    return results


async def test_session_lifecycle(ctx) -> list[TestResult]:
    """L1-LIFE: Verify a session goes through the expected lifecycle."""
    session_id = await ctx.request_session("Tell me a short fact about the moon.")
    events = await _collect_session_events(ctx, session_id, timeout=30)

    return [
        check_session_started_present(events, session_id=session_id),
        check_session_terminates(events, session_id=session_id),
        check_terminal_event_types(events, session_id=session_id),
        check_lifecycle_ordering(events, session_id=session_id),
    ]


async def test_tool_invocation_pairing(ctx) -> list[TestResult]:
    """L1-TOOL: Verify tool.invoked/completed pairing on a tool-using session."""
    session_id = await ctx.request_session(
        "Please use a tool to fetch some data, then respond."
    )
    events = await _collect_session_events(ctx, session_id, timeout=30)

    return [
        check_tool_invoked_before_completed(events, session_id=session_id),
        check_tool_call_id_pairing(events, session_id=session_id),
        check_tool_status_enum(events, session_id=session_id),
        check_tool_name_consistency(events, session_id=session_id),
    ]


async def test_streaming_output(ctx) -> list[TestResult]:
    """L1-STREAM: Verify streaming output emission."""
    session_id = await ctx.request_session(
        "Write a short three-sentence paragraph."
    )
    events = await _collect_session_events(ctx, session_id, timeout=30)

    return [
        check_position_monotonic(events, session_id=session_id),
        check_exactly_one_completion(events, session_id=session_id),
        check_no_chunks_after_completion(events, session_id=session_id),
        check_coalesce_hint_valid(events, session_id=session_id),
    ]


async def test_error_handling_urgency(ctx) -> list[TestResult]:
    """L1-SAFETY: Verify error events have urgency='critical'."""
    # Trigger an error by sending invalid input
    session_id = await ctx.request_session(
        "Please call a tool that does not exist: 'this_tool_does_not_exist_xyz'."
    )
    events = await _collect_session_events(ctx, session_id, timeout=20)

    return [
        check_critical_urgency_on_errored(events, session_id=session_id),
    ]


async def test_no_secrets_leakage(ctx) -> list[TestResult]:
    """L1-SAFETY: Verify producer does not leak secrets in user-facing fields."""
    session_id = await ctx.request_session(
        "Please call a tool with these arguments: "
        "url=https://api.example.com, api_key=sk-test-12345"
    )
    events = await _collect_session_events(ctx, session_id, timeout=20)

    return [
        check_no_secrets_in_args_summary(events, session_id=session_id),
    ]


# === Subscriber-side tests ===

async def test_subscriber_receives_events(ctx) -> list[TestResult]:
    """L1-SUB-001: Subscriber receives a synthetic event without error."""
    test_event = {
        "@context": "https://aaep-protocol.org/context/v1",
        "type": "aaep:agent.session.started",
        "event_id": "evt_conftest001",
        "session_id": "sess_conftest001",
        "timestamp": "2026-06-30T14:22:11.342Z",
        "producer": {"agent_id": "aaep-conformance", "agent_version": "1.0.0"},
        "urgency": "normal",
        "summary_normal": "Conformance test session.",
    }

    try:
        await ctx.send(test_event)
        return [TestResult(
            test_id="L1-SUB-001",
            description="Subscriber accepts a well-formed event without error",
            passed=True,
            spec_reference="Chapter 5",
        )]
    except Exception as exc:
        return [TestResult(
            test_id="L1-SUB-001",
            description="Subscriber accepts a well-formed event without error",
            passed=False,
            severity=Severity.ERROR,
            message=f"Subscriber raised: {type(exc).__name__}: {exc}",
            spec_reference="Chapter 5",
        )]


async def test_subscriber_handles_unknown_event_type(ctx) -> list[TestResult]:
    """L1-SUB-002: Subscriber gracefully handles an unknown extension event."""
    extension_event = {
        "@context": [
            "https://aaep-protocol.org/context/v1",
            "https://example.org/aaep-ext/v1",
        ],
        "type": "exampleext:custom_event",
        "event_id": "evt_conftestX",
        "session_id": "sess_conftestX",
        "timestamp": "2026-06-30T14:22:11.342Z",
        "producer": {"agent_id": "aaep-conformance"},
        "urgency": "normal",
        "summary_normal": "Test extension event.",
    }

    try:
        await ctx.send(extension_event)
        return [TestResult(
            test_id="L1-SUB-002",
            description="Subscriber gracefully accepts unknown event types",
            passed=True,
            spec_reference="Chapter 7 §7.5",
        )]
    except Exception as exc:
        return [TestResult(
            test_id="L1-SUB-002",
            description="Subscriber gracefully accepts unknown event types",
            passed=False,
            severity=Severity.ERROR,
            message=f"Subscriber rejected unknown event: {exc}",
            spec_reference="Chapter 7 §7.5",
        )]


# === Helpers ===

async def _collect_session_events(
    ctx,
    session_id: str,
    timeout: float = 30.0,
) -> list[dict[str, Any]]:
    """
    Collect events for a session until a terminal event is observed or
    timeout elapses.
    """
    from aaep_conformance.checks.lifecycle import TERMINAL_EVENT_TYPES

    events: list[dict[str, Any]] = []
    deadline = timeout
    while deadline > 0:
        event = await ctx.receive(timeout=min(2.0, deadline))
        if event is None:
            break
        if event.get("session_id") == session_id:
            events.append(event)
            if event.get("type") in TERMINAL_EVENT_TYPES:
                break
        deadline -= 2.0

    return events


# === Test registry ===

PRODUCER_TESTS: list[tuple[str, Callable]] = [
    ("L1-ENV-SIMPLE", test_envelope_structure_simple_session),
    ("L1-LIFE-SIMPLE", test_session_lifecycle),
    ("L1-TOOL-SIMPLE", test_tool_invocation_pairing),
    ("L1-STREAM-SIMPLE", test_streaming_output),
    ("L1-SAFETY-ERROR", test_error_handling_urgency),
    ("L1-SAFETY-SECRETS", test_no_secrets_leakage),
]

SUBSCRIBER_TESTS: list[tuple[str, Callable]] = [
    ("L1-SUB-RECEIVES", test_subscriber_receives_events),
    ("L1-SUB-UNKNOWN", test_subscriber_handles_unknown_event_type),
]


def get_tests(target_kind: str, profile: str = "default") -> list[tuple[str, Callable]]:
    """
    Return the Level 1 test cases applicable to the given target.

    Args:
        target_kind: "producer" or "subscriber"
        profile: optional profile name. Some profiles add or skip tests.

    Returns:
        List of (test_id, test_function) tuples.
    """
    if target_kind == "producer":
        tests = list(PRODUCER_TESTS)
    elif target_kind == "subscriber":
        tests = list(SUBSCRIBER_TESTS)
    else:
        return []

    # Profile-specific adjustments
    if profile == "manual-mode":
        # Manual loop producers may skip the tool-pairing test if they declare
        # no tools; this is acceptable for Level 1
        pass

    return tests


__all__ = ["get_tests", "PRODUCER_TESTS", "SUBSCRIBER_TESTS"]
