"""
Subscription handshake checks.

Verifies Conformance Level 3 handshake behavior:
- subscription.request has all required fields and valid capabilities
- subscription.accepted has all required fields and a valid subscription_id
- honored_capabilities is NEVER more permissive than the subscriber's request
  (this is the central safety guarantee of the negotiation model)
"""

from __future__ import annotations

import re
from typing import Any

from aaep_conformance.reporter import Severity, TestResult


SUBSCRIPTION_REQUEST_TYPE = "subscription.request"
SUBSCRIPTION_ACCEPTED_TYPE = "subscription.accepted"
SUBSCRIPTION_REJECTED_TYPE = "subscription.rejected"
SUBSCRIPTION_ID_PATTERN = re.compile(r"^sub_[A-Za-z0-9]{1,64}$")
VALID_REJECT_REASONS = {
    "version_unsupported",
    "manifest_signature_required",
    "capabilities_incompatible",
    "rate_limit",
    "authentication_required",
    "authorization_denied",
    "transport_unavailable",
    "unknown",
}


def check_subscription_request_valid(
    message: dict[str, Any],
    *,
    test_id: str = "L3-HS-001",
) -> TestResult:
    """Validate the structure of a subscription.request message."""
    if message.get("type") != SUBSCRIPTION_REQUEST_TYPE:
        return TestResult(
            test_id=test_id,
            description="subscription.request has valid type",
            passed=False,
            severity=Severity.ERROR,
            message=f"Expected type={SUBSCRIPTION_REQUEST_TYPE!r}, got {message.get('type')!r}",
            spec_reference="Chapter 5 §5.2",
        )

    required = ["type", "aaep_version", "subscriber_id", "capabilities"]
    missing = [f for f in required if f not in message]

    if missing:
        return TestResult(
            test_id=test_id,
            description="subscription.request has all required fields",
            passed=False,
            severity=Severity.ERROR,
            message=f"Missing required field(s): {missing}",
            spec_reference="Chapter 5 §5.2",
        )

    capabilities = message.get("capabilities")
    if not isinstance(capabilities, dict):
        return TestResult(
            test_id=test_id,
            description="subscription.request has all required fields",
            passed=False,
            severity=Severity.ERROR,
            message=f"capabilities must be an object, got {type(capabilities).__name__}",
            spec_reference="Chapter 5 §5.3",
        )

    return TestResult(
        test_id=test_id,
        description="subscription.request is well-formed",
        passed=True,
        spec_reference="Chapter 5 §5.2-§5.3",
    )


def check_subscription_accepted_valid(
    message: dict[str, Any],
    *,
    test_id: str = "L3-HS-002",
) -> TestResult:
    """Validate the structure of a subscription.accepted message."""
    if message.get("type") != SUBSCRIPTION_ACCEPTED_TYPE:
        return TestResult(
            test_id=test_id,
            description="subscription.accepted has valid type",
            passed=False,
            severity=Severity.ERROR,
            message=f"Expected type={SUBSCRIPTION_ACCEPTED_TYPE!r}, got {message.get('type')!r}",
            spec_reference="Chapter 5 §5.4",
        )

    required = ["type", "subscription_id", "aaep_version", "producer", "honored_capabilities"]
    missing = [f for f in required if f not in message]

    if missing:
        return TestResult(
            test_id=test_id,
            description="subscription.accepted has all required fields",
            passed=False,
            severity=Severity.ERROR,
            message=f"Missing required field(s): {missing}",
            spec_reference="Chapter 5 §5.4",
        )

    # subscription_id format
    sub_id = message.get("subscription_id", "")
    if not SUBSCRIPTION_ID_PATTERN.match(sub_id):
        return TestResult(
            test_id=test_id,
            description="subscription_id format is valid",
            passed=False,
            severity=Severity.ERROR,
            message=f"subscription_id {sub_id!r} does not match ^sub_[A-Za-z0-9]{{1,64}}$",
            expected="sub_<alphanumeric, 1-64 chars>",
            actual=sub_id,
            spec_reference="Chapter 5 §5.4.1",
        )

    # producer must be a structured object with agent_id
    producer = message.get("producer")
    if not isinstance(producer, dict) or not producer.get("agent_id"):
        return TestResult(
            test_id=test_id,
            description="producer has valid agent_id",
            passed=False,
            severity=Severity.ERROR,
            message="producer must be an object with a non-empty agent_id",
            spec_reference="Chapter 5 §5.4.2",
        )

    return TestResult(
        test_id=test_id,
        description="subscription.accepted is well-formed",
        passed=True,
        spec_reference="Chapter 5 §5.4",
    )


def check_subscription_rejected_valid(
    message: dict[str, Any],
    *,
    test_id: str = "L3-HS-003",
) -> TestResult:
    """Validate the structure of a subscription.rejected message."""
    if message.get("type") != SUBSCRIPTION_REJECTED_TYPE:
        return TestResult(
            test_id=test_id,
            description="subscription.rejected has valid type",
            passed=False,
            severity=Severity.ERROR,
            message=f"Expected type={SUBSCRIPTION_REJECTED_TYPE!r}, got {message.get('type')!r}",
            spec_reference="Chapter 5 §5.5",
        )

    required = ["type", "reason_code", "reason_message"]
    missing = [f for f in required if f not in message]
    if missing:
        return TestResult(
            test_id=test_id,
            description="subscription.rejected has all required fields",
            passed=False,
            severity=Severity.ERROR,
            message=f"Missing required field(s): {missing}",
            spec_reference="Chapter 5 §5.5.2",
        )

    reason = message.get("reason_code")
    if reason not in VALID_REJECT_REASONS:
        return TestResult(
            test_id=test_id,
            description="subscription.rejected uses a valid reason_code",
            passed=False,
            severity=Severity.ERROR,
            message=f"reason_code {reason!r} is not one of the normative enum values",
            expected=f"One of: {sorted(VALID_REJECT_REASONS)}",
            actual=reason,
            spec_reference="Chapter 5 §5.5.3",
        )

    return TestResult(
        test_id=test_id,
        description="subscription.rejected is well-formed",
        passed=True,
        spec_reference="Chapter 5 §5.5",
    )


def check_honored_capabilities_not_more_permissive(
    request: dict[str, Any],
    accepted: dict[str, Any],
    *,
    test_id: str = "L3-HS-004",
) -> TestResult:
    """
    Verify honored_capabilities is not MORE permissive than the subscriber's
    requested capabilities. This is the central safety guarantee of the
    negotiation model (Chapter 5 §5.4.4).

    Specifically:
    - honored max_events_per_second <= requested max_events_per_second
    - honored supports_confirmation_reply <= requested
    - honored supports_clarification_reply <= requested
    - honored languages ⊆ requested languages
    - honored coalesce_boundaries ⊆ requested coalesce_boundaries
    - honored supported_conformance_levels ⊆ requested
    """
    requested = request.get("capabilities", {})
    honored = accepted.get("honored_capabilities", {})

    violations: list[str] = []

    # Numeric: honored max rate must be <= requested max rate
    req_rate = requested.get("max_events_per_second")
    hon_rate = honored.get("max_events_per_second")
    if req_rate is not None and hon_rate is not None and hon_rate > req_rate:
        violations.append(
            f"max_events_per_second: honored={hon_rate} > requested={req_rate}"
        )

    # Boolean: honored must not promise reply capability the subscriber didn't request
    for cap in ("supports_confirmation_reply", "supports_clarification_reply"):
        if requested.get(cap) is False and honored.get(cap) is True:
            violations.append(
                f"{cap}: honored=True but requested=False"
            )

    # Sets: honored must be a subset of requested (when requested is present)
    for set_cap in ("languages", "coalesce_boundaries", "supported_conformance_levels",
                    "supported_extensions"):
        req_set = requested.get(set_cap)
        hon_set = honored.get(set_cap)
        if req_set is not None and hon_set is not None:
            extras = set(hon_set) - set(req_set)
            if extras:
                violations.append(
                    f"{set_cap}: honored contains {sorted(extras)} not in requested"
                )

    # accept_signed_manifests_only: subscriber may have required signed; producer may either
    # provide them or reject. Producer must NOT honor as False when subscriber requested True.
    if requested.get("accept_signed_manifests_only") is True:
        if honored.get("accept_signed_manifests_only") is False:
            violations.append(
                "accept_signed_manifests_only: subscriber required signed manifests "
                "but producer honored=False"
            )

    if violations:
        return TestResult(
            test_id=test_id,
            description="honored_capabilities is not more permissive than requested",
            passed=False,
            severity=Severity.ERROR,
            message="; ".join(violations[:3]),
            spec_reference="Chapter 5 §5.4.4",
        )

    return TestResult(
        test_id=test_id,
        description="honored_capabilities is not more permissive than requested",
        passed=True,
        spec_reference="Chapter 5 §5.4.4",
    )


def check_subscription_response_received(
    request_sent_at: float,
    response_received_at: float | None,
    *,
    timeout_seconds: float = 30.0,
    test_id: str = "L3-HS-005",
) -> TestResult:
    """Verify the producer responded to subscription.request within timeout."""
    if response_received_at is None:
        return TestResult(
            test_id=test_id,
            description="Producer responds to subscription.request",
            passed=False,
            severity=Severity.ERROR,
            message=f"No response received within {timeout_seconds}s",
            spec_reference="Chapter 5 §5.4, §5.5",
        )

    elapsed = response_received_at - request_sent_at
    if elapsed > timeout_seconds:
        return TestResult(
            test_id=test_id,
            description="Producer responds to subscription.request promptly",
            passed=False,
            severity=Severity.WARNING,
            message=f"Response took {elapsed:.1f}s (above {timeout_seconds}s threshold)",
            spec_reference="Chapter 5 §5.4, §5.5",
        )

    return TestResult(
        test_id=test_id,
        description="Producer responds to subscription.request within timeout",
        passed=True,
        spec_reference="Chapter 5 §5.4, §5.5",
    )


__all__ = [
    "SUBSCRIPTION_REQUEST_TYPE",
    "SUBSCRIPTION_ACCEPTED_TYPE",
    "SUBSCRIPTION_REJECTED_TYPE",
    "SUBSCRIPTION_ID_PATTERN",
    "VALID_REJECT_REASONS",
    "check_subscription_request_valid",
    "check_subscription_accepted_valid",
    "check_subscription_rejected_valid",
    "check_honored_capabilities_not_more_permissive",
    "check_subscription_response_received",
]
