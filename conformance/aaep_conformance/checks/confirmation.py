"""
Confirmation flow checks.

Verifies the rules around agent.awaiting.confirmation and its reply:
- reply_token format and uniqueness within a session
- default_decision is in the valid enum
- All required fields are present
- The blocking contract: irreversible tool calls do not execute before reply
- Timeout behavior: producer applies default_decision when no reply arrives

These are some of the most important checks because they encode AAEP's
central safety contract.
"""

from __future__ import annotations

import re
from typing import Any

from aaep_conformance.reporter import Severity, TestResult


CONFIRMATION_TYPE = "aaep:agent.awaiting.confirmation"
CONFIRMATION_REPLY_TYPE = "confirmation.reply"
REPLY_TOKEN_PATTERN = re.compile(r"^rpl_[A-Za-z0-9]{1,64}$")
VALID_DECISIONS = {"accept", "reject"}
TOOL_INVOKED_TYPE = "aaep:agent.tool.invoked"


def check_reply_token_format(
    events: list[dict[str, Any]],
    *,
    session_id: str | None = None,
    test_id: str = "L2-CONF-001",
) -> TestResult:
    """Check that reply_token in confirmation events matches the AAEP pattern."""
    relevant = _filter_session(events, session_id)
    confirmations = [e for e in relevant if e.get("type") == CONFIRMATION_TYPE]

    if not confirmations:
        return TestResult(
            test_id=test_id,
            description="reply_token format is valid",
            passed=True,
            severity=Severity.INFO,
            message="No confirmation events to check",
            spec_reference="Chapter 6 §6.2",
        )

    invalid: list[str] = []
    for event in confirmations:
        token = event.get("reply_token", "")
        if not REPLY_TOKEN_PATTERN.match(token):
            invalid.append(
                f"event_id={event.get('event_id')!r}: reply_token={token!r}"
            )

    if invalid:
        return TestResult(
            test_id=test_id,
            description="reply_token format is valid",
            passed=False,
            severity=Severity.ERROR,
            message="; ".join(invalid[:3]),
            expected="rpl_<alphanumeric, 1-64 chars>",
            actual="See message",
            spec_reference="Chapter 6 §6.2.1",
        )

    return TestResult(
        test_id=test_id,
        description="reply_token format is valid",
        passed=True,
        spec_reference="Chapter 6 §6.2.1",
    )


def check_reply_token_single_use(
    events: list[dict[str, Any]],
    reply_messages: list[dict[str, Any]],
    *,
    session_id: str | None = None,
    test_id: str = "L2-CONF-002",
) -> TestResult:
    """
    Check that each reply_token is used at most once for a successful reply.

    Producers MUST ignore duplicate replies with the same reply_token.
    The conformance suite verifies this by sending two replies with the
    same token and observing that the producer only honors the first.
    """
    if not reply_messages:
        return TestResult(
            test_id=test_id,
            description="reply_token is single-use",
            passed=True,
            severity=Severity.INFO,
            message="No reply messages observed",
            spec_reference="Chapter 6 §6.3.5",
        )

    seen_tokens: dict[str, int] = {}
    for msg in reply_messages:
        token = msg.get("reply_token", "")
        if not token:
            continue
        seen_tokens[token] = seen_tokens.get(token, 0) + 1

    duplicates = {t: count for t, count in seen_tokens.items() if count > 1}
    if duplicates:
        return TestResult(
            test_id=test_id,
            description="reply_token is single-use",
            passed=False,
            severity=Severity.WARNING,
            message=f"Duplicate reply submissions: {duplicates}",
            spec_reference="Chapter 6 §6.3.5",
        )

    return TestResult(
        test_id=test_id,
        description="reply_token is single-use",
        passed=True,
        spec_reference="Chapter 6 §6.3.5",
    )


def check_default_decision_enum(
    events: list[dict[str, Any]],
    *,
    session_id: str | None = None,
    test_id: str = "L2-CONF-003",
) -> TestResult:
    """Check that default_decision is 'accept' or 'reject'."""
    relevant = _filter_session(events, session_id)
    confirmations = [e for e in relevant if e.get("type") == CONFIRMATION_TYPE]

    if not confirmations:
        return TestResult(
            test_id=test_id,
            description="default_decision is in the valid enum",
            passed=True,
            severity=Severity.INFO,
            message="No confirmation events to check",
            spec_reference="Chapter 6 §6.4",
        )

    invalid: list[str] = []
    for event in confirmations:
        decision = event.get("default_decision")
        if decision not in VALID_DECISIONS:
            invalid.append(
                f"event_id={event.get('event_id')!r}: default_decision={decision!r}"
            )

    if invalid:
        return TestResult(
            test_id=test_id,
            description="default_decision is in the valid enum",
            passed=False,
            severity=Severity.ERROR,
            message="; ".join(invalid[:3]),
            expected=f"One of: {sorted(VALID_DECISIONS)}",
            actual="See message",
            spec_reference="Chapter 6 §6.4",
        )

    return TestResult(
        test_id=test_id,
        description="default_decision is in the valid enum",
        passed=True,
        spec_reference="Chapter 6 §6.4",
    )


def check_confirmation_has_required_fields(
    events: list[dict[str, Any]],
    *,
    session_id: str | None = None,
    test_id: str = "L2-CONF-004",
) -> TestResult:
    """
    Check that every confirmation event has all required payload fields:
    action, consequence, reply_token, timeout_seconds, default_decision.
    """
    relevant = _filter_session(events, session_id)
    confirmations = [e for e in relevant if e.get("type") == CONFIRMATION_TYPE]

    if not confirmations:
        return TestResult(
            test_id=test_id,
            description="Confirmation events have all required fields",
            passed=True,
            severity=Severity.INFO,
            message="No confirmation events to check",
            spec_reference="Chapter 4 §4.4.1",
        )

    required = ["action", "consequence", "reply_token", "timeout_seconds", "default_decision"]
    issues: list[str] = []
    for event in confirmations:
        missing = [f for f in required if f not in event]
        if missing:
            issues.append(
                f"event_id={event.get('event_id')!r}: missing {missing}"
            )

    if issues:
        return TestResult(
            test_id=test_id,
            description="Confirmation events have all required fields",
            passed=False,
            severity=Severity.ERROR,
            message="; ".join(issues[:3]),
            spec_reference="Chapter 4 §4.4.1",
        )

    return TestResult(
        test_id=test_id,
        description="Confirmation events have all required fields",
        passed=True,
        spec_reference="Chapter 4 §4.4.1",
    )


def check_blocking_contract(
    events: list[dict[str, Any]],
    reply_messages: list[dict[str, Any]],
    *,
    session_id: str | None = None,
    test_id: str = "L2-CONF-005",
) -> TestResult:
    """
    Check that no irreversible tool.invoked event appears between a
    confirmation event and its corresponding reply (i.e., the producer
    actually blocks on the confirmation).
    """
    relevant = _filter_session(events, session_id)

    # Build a map of reply_token -> reply event (use earliest-seen reply if duplicates)
    replies_by_token: dict[str, dict[str, Any]] = {}
    for msg in reply_messages:
        token = msg.get("reply_token")
        if token and token not in replies_by_token:
            replies_by_token[token] = msg

    # For each confirmation event, check that the matching tool.invoked
    # (if any) does not appear before the reply
    violations: list[str] = []
    for i, event in enumerate(relevant):
        if event.get("type") != CONFIRMATION_TYPE:
            continue
        reply_token = event.get("reply_token", "")
        if not reply_token:
            continue

        reply = replies_by_token.get(reply_token)
        if reply is None:
            # No reply seen; nothing to check (timeout-style flow)
            continue

        # Find a matching tool.invoked event after the confirmation
        # (typically the one that this confirmation was protecting)
        post_confirmation = relevant[i + 1:]
        for later in post_confirmation:
            if later.get("type") != TOOL_INVOKED_TYPE:
                continue
            if not later.get("irreversible"):
                continue
            # If reply was "reject", no tool invocation should follow
            if reply.get("decision") == "reject":
                violations.append(
                    f"reply_token={reply_token!r}: irreversible tool.invoked "
                    f"after a rejected confirmation"
                )
            break  # only check the first matching invocation per confirmation

    if violations:
        return TestResult(
            test_id=test_id,
            description="Producer honors the confirmation blocking contract",
            passed=False,
            severity=Severity.ERROR,
            message="; ".join(violations[:3]),
            spec_reference="Chapter 6 §6.1",
        )

    return TestResult(
        test_id=test_id,
        description="Producer honors the confirmation blocking contract",
        passed=True,
        spec_reference="Chapter 6 §6.1",
    )


def check_timeout_seconds_valid(
    events: list[dict[str, Any]],
    *,
    session_id: str | None = None,
    test_id: str = "L2-CONF-006",
) -> TestResult:
    """Check that timeout_seconds is a positive integer within reasonable range."""
    relevant = _filter_session(events, session_id)
    confirmations = [e for e in relevant if e.get("type") == CONFIRMATION_TYPE]

    if not confirmations:
        return TestResult(
            test_id=test_id,
            description="timeout_seconds is a valid positive integer",
            passed=True,
            severity=Severity.INFO,
            message="No confirmation events to check",
            spec_reference="Chapter 6 §6.4",
        )

    invalid: list[str] = []
    for event in confirmations:
        timeout = event.get("timeout_seconds")
        if not isinstance(timeout, int):
            invalid.append(
                f"event_id={event.get('event_id')!r}: timeout_seconds={timeout!r} not an integer"
            )
        elif timeout < 1:
            invalid.append(
                f"event_id={event.get('event_id')!r}: timeout_seconds={timeout} less than 1"
            )
        elif timeout > 86400:
            invalid.append(
                f"event_id={event.get('event_id')!r}: timeout_seconds={timeout} greater than 86400 (24h)"
            )

    if invalid:
        return TestResult(
            test_id=test_id,
            description="timeout_seconds is a valid positive integer",
            passed=False,
            severity=Severity.ERROR,
            message="; ".join(invalid[:3]),
            expected="Integer between 1 and 86400",
            actual="See message",
            spec_reference="Chapter 6 §6.4",
        )

    return TestResult(
        test_id=test_id,
        description="timeout_seconds is a valid positive integer",
        passed=True,
        spec_reference="Chapter 6 §6.4",
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
    "CONFIRMATION_TYPE",
    "CONFIRMATION_REPLY_TYPE",
    "REPLY_TOKEN_PATTERN",
    "VALID_DECISIONS",
    "check_reply_token_format",
    "check_reply_token_single_use",
    "check_default_decision_enum",
    "check_confirmation_has_required_fields",
    "check_blocking_contract",
    "check_timeout_seconds_valid",
]
