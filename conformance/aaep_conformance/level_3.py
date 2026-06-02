"""
Level 3 (Negotiated) test suite.

Level 3 adds the full subscription handshake, capability negotiation, backpressure,
event filtering, and optional signed-manifest validation.

These tests verify the producer's ability to negotiate capabilities with subscribers
and to honor the negotiated contract, including the central safety guarantee that
producers can never escape the subscriber's constraints.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Callable
from uuid import uuid4

from aaep_conformance.checks.handshake import (
    check_subscription_request_valid,
    check_subscription_accepted_valid,
    check_subscription_rejected_valid,
    check_honored_capabilities_not_more_permissive,
    check_subscription_response_received,
)
from aaep_conformance.checks.safety import (
    check_critical_events_bypass_filters,
    check_backpressure_honored,
)
from aaep_conformance.checks.lifecycle import TERMINAL_EVENT_TYPES
from aaep_conformance.reporter import Severity, TestResult


SUBSCRIPTION_ACCEPTED_TYPE = "subscription.accepted"
SUBSCRIPTION_REJECTED_TYPE = "subscription.rejected"


# === Test scenarios ===

async def test_basic_handshake(ctx) -> list[TestResult]:
    """
    L3-HS-BASIC: Subscriber sends subscription.request, producer responds with
    subscription.accepted (or subscription.rejected with a valid reason).
    """
    request = _build_subscription_request(
        subscriber_id="aaep-conformance-test",
        capabilities={
            "max_events_per_second": 5,
            "preferred_verbosity": "normal",
            "languages": ["en-US"],
            "supports_confirmation_reply": True,
            "supports_clarification_reply": True,
            "coalesce_boundaries": ["sentence", "completion"],
            "supported_conformance_levels": [1, 2, 3],
        },
    )

    results: list[TestResult] = []
    results.append(check_subscription_request_valid(request))

    sent_at = time.monotonic()
    await ctx.send(request)
    response = await ctx.receive(timeout=10)
    received_at = time.monotonic() if response else None

    results.append(check_subscription_response_received(
        sent_at, received_at, timeout_seconds=10,
    ))

    if response is None:
        return results

    if response.get("type") == SUBSCRIPTION_ACCEPTED_TYPE:
        results.append(check_subscription_accepted_valid(response))
        results.append(check_honored_capabilities_not_more_permissive(request, response))
    elif response.get("type") == SUBSCRIPTION_REJECTED_TYPE:
        results.append(check_subscription_rejected_valid(response))
    else:
        results.append(TestResult(
            test_id="L3-HS-BASIC-005",
            description="Producer responds with valid handshake message",
            passed=False,
            severity=Severity.ERROR,
            message=f"Unexpected response type: {response.get('type')!r}",
            spec_reference="Chapter 5 §5.4-§5.5",
        ))

    return results


async def test_capability_negotiation_rate_limit(ctx) -> list[TestResult]:
    """
    L3-CAP-RATE: Subscriber requests strict rate limit (1 event/sec).
    Producer must honor at or below that rate.
    """
    request = _build_subscription_request(
        subscriber_id="aaep-conformance-ratetest",
        capabilities={
            "max_events_per_second": 1,
            "supports_confirmation_reply": True,
        },
    )
    await ctx.send(request)
    response = await ctx.receive(timeout=10)

    results: list[TestResult] = []
    if response is None or response.get("type") != SUBSCRIPTION_ACCEPTED_TYPE:
        results.append(TestResult(
            test_id="L3-CAP-RATE-001",
            description="Producer accepts subscription with strict rate limit",
            passed=False,
            severity=Severity.INFO,
            message="Producer did not accept (may have rejected — acceptable behavior)",
            spec_reference="Chapter 5 §5.6.1",
        ))
        return results

    results.append(check_honored_capabilities_not_more_permissive(request, response))

    # Trigger a busy session and measure event rate
    session_request = {
        "kind": "user_input",
        "text": "Please give me a detailed step-by-step explanation of how rainbows form, "
                "thinking through each step before responding.",
    }
    await ctx.send(session_request)

    start = time.monotonic()
    events = await _collect_events(ctx, duration_seconds=5.0)
    duration = time.monotonic() - start

    results.append(check_backpressure_honored(
        events,
        max_events_per_second=1,
        window_seconds=duration,
    ))
    return results


async def test_capability_negotiation_languages(ctx) -> list[TestResult]:
    """
    L3-CAP-LANG: Subscriber requests Yoruba; producer honors Yoruba or
    rejects with capabilities_incompatible.
    """
    request = _build_subscription_request(
        subscriber_id="aaep-conformance-langtest",
        capabilities={
            "languages": ["yo-NG", "en-US"],
        },
    )
    await ctx.send(request)
    response = await ctx.receive(timeout=10)

    results: list[TestResult] = []
    if response is None:
        results.append(TestResult(
            test_id="L3-CAP-LANG-001",
            description="Producer responds to language capability request",
            passed=False,
            severity=Severity.ERROR,
            message="No response received",
            spec_reference="Chapter 5 §5.3.1.3",
        ))
        return results

    if response.get("type") == SUBSCRIPTION_ACCEPTED_TYPE:
        results.append(check_honored_capabilities_not_more_permissive(request, response))
    elif response.get("type") == SUBSCRIPTION_REJECTED_TYPE:
        # Acceptable: producer doesn't support Yoruba
        reason = response.get("reason_code")
        results.append(TestResult(
            test_id="L3-CAP-LANG-002",
            description="Producer rejects with valid reason when unable to serve language",
            passed=reason == "capabilities_incompatible",
            severity=Severity.WARNING if reason != "capabilities_incompatible" else Severity.INFO,
            message=f"Rejected with reason_code={reason!r}",
            spec_reference="Chapter 5 §5.5.3",
        ))
    return results


async def test_event_filter_critical_bypass(ctx) -> list[TestResult]:
    """
    L3-FILTER-CRIT: Subscriber requests exclude filter for tool events;
    critical events MUST still arrive.
    """
    request = _build_subscription_request(
        subscriber_id="aaep-conformance-filtertest",
        capabilities={
            "event_filters": {
                "exclude": ["aaep:agent.tool.*"],
            },
            "supports_confirmation_reply": True,
        },
    )
    await ctx.send(request)
    accepted = await ctx.receive(timeout=10)

    if not accepted or accepted.get("type") != SUBSCRIPTION_ACCEPTED_TYPE:
        return [TestResult(
            test_id="L3-FILTER-CRIT-001",
            description="Producer accepts filtered subscription",
            passed=False,
            severity=Severity.INFO,
            message="Producer did not accept filtered subscription",
            spec_reference="Chapter 5 §5.6.3",
        )]

    # Trigger an error session
    await ctx.send({"kind": "user_input", "text": "Please trigger a deliberate error."})
    events = await _collect_events(ctx, duration_seconds=15.0)

    honored = accepted.get("honored_capabilities", {})
    return [
        check_critical_events_bypass_filters(events, honored.get("event_filters")),
    ]


async def test_subscription_rejection_reasons(ctx) -> list[TestResult]:
    """
    L3-REJECT: Subscriber requests something incompatible (unsupported version).
    Producer must reject with a valid reason_code.
    """
    request = _build_subscription_request(
        subscriber_id="aaep-conformance-rejecttest",
        aaep_version="99.99.99",  # impossible version
        capabilities={},
    )
    await ctx.send(request)
    response = await ctx.receive(timeout=10)

    if response is None:
        return [TestResult(
            test_id="L3-REJECT-001",
            description="Producer responds with rejection for unsupported version",
            passed=False,
            severity=Severity.ERROR,
            message="No response received",
            spec_reference="Chapter 5 §5.5",
        )]

    if response.get("type") == SUBSCRIPTION_REJECTED_TYPE:
        return [
            check_subscription_rejected_valid(response),
            TestResult(
                test_id="L3-REJECT-002",
                description="Producer uses version_unsupported for invalid version",
                passed=response.get("reason_code") == "version_unsupported",
                severity=Severity.WARNING,
                message=f"reason_code={response.get('reason_code')!r}",
                spec_reference="Chapter 5 §5.5.3",
            ),
        ]

    return [TestResult(
        test_id="L3-REJECT-003",
        description="Producer rejects subscription with invalid version",
        passed=False,
        severity=Severity.WARNING,
        message=f"Producer responded {response.get('type')!r} for invalid version "
                f"(expected subscription.rejected with version_unsupported)",
        spec_reference="Chapter 5 §5.5",
    )]


async def test_signed_manifest_validation(ctx) -> list[TestResult]:
    """
    L3-SIG-MANIFEST: Subscriber requires signed manifests; producer must
    provide one or reject with manifest_signature_required.
    """
    request = _build_subscription_request(
        subscriber_id="aaep-conformance-sigtest",
        capabilities={
            "accept_signed_manifests_only": True,
        },
    )
    await ctx.send(request)
    response = await ctx.receive(timeout=10)

    if response is None:
        return [TestResult(
            test_id="L3-SIG-001",
            description="Producer responds to signed-manifest requirement",
            passed=False,
            severity=Severity.ERROR,
            message="No response received",
            spec_reference="Chapter 10 §10.4",
        )]

    if response.get("type") == SUBSCRIPTION_ACCEPTED_TYPE:
        has_signed = "signed_manifest" in response
        return [TestResult(
            test_id="L3-SIG-002",
            description="Producer provides signed_manifest when required",
            passed=has_signed,
            severity=Severity.ERROR if not has_signed else Severity.INFO,
            message="" if has_signed else "Producer accepted but did not include signed_manifest",
            spec_reference="Chapter 10 §10.4",
        )]

    if response.get("type") == SUBSCRIPTION_REJECTED_TYPE:
        reason = response.get("reason_code")
        return [TestResult(
            test_id="L3-SIG-003",
            description="Producer rejects with manifest_signature_required when unable to sign",
            passed=reason == "manifest_signature_required",
            severity=Severity.INFO,
            message=f"Rejected with reason_code={reason!r}",
            spec_reference="Chapter 5 §5.5.3, Chapter 10 §10.4",
        )]

    return [TestResult(
        test_id="L3-SIG-004",
        description="Producer handles signed-manifest requirement appropriately",
        passed=False,
        severity=Severity.WARNING,
        message=f"Unexpected response: {response.get('type')!r}",
        spec_reference="Chapter 10 §10.4",
    )]


# === Helpers ===

def _build_subscription_request(
    *,
    subscriber_id: str,
    capabilities: dict[str, Any],
    aaep_version: str = "1.0.0",
) -> dict[str, Any]:
    return {
        "type": "subscription.request",
        "aaep_version": aaep_version,
        "subscriber_id": subscriber_id,
        "subscriber_name": "AAEP Conformance Test Suite",
        "subscriber_version": "1.0.0",
        "capabilities": capabilities,
    }


async def _collect_events(ctx, *, duration_seconds: float) -> list[dict[str, Any]]:
    """Collect all events arriving within duration_seconds."""
    events: list[dict[str, Any]] = []
    deadline = time.monotonic() + duration_seconds
    while time.monotonic() < deadline:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        event = await ctx.receive(timeout=min(remaining, 1.0))
        if event is None:
            continue
        events.append(event)
    return events


# === Test registry ===

PRODUCER_TESTS: list[tuple[str, Callable]] = [
    ("L3-HS-BASIC", test_basic_handshake),
    ("L3-CAP-RATE", test_capability_negotiation_rate_limit),
    ("L3-CAP-LANG", test_capability_negotiation_languages),
    ("L3-FILTER-CRIT", test_event_filter_critical_bypass),
    ("L3-REJECT", test_subscription_rejection_reasons),
    ("L3-SIG-MANIFEST", test_signed_manifest_validation),
]

SUBSCRIBER_TESTS: list[tuple[str, Callable]] = []


def get_tests(target_kind: str, profile: str = "default") -> list[tuple[str, Callable]]:
    """Return Level 3 test cases applicable to the given target."""
    if target_kind == "producer":
        return list(PRODUCER_TESTS)
    if target_kind == "subscriber":
        return list(SUBSCRIBER_TESTS)
    return []


__all__ = ["get_tests", "PRODUCER_TESTS", "SUBSCRIBER_TESTS"]
