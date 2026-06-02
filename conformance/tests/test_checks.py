"""
Self-tests for the AAEP conformance check functions.

These tests verify that the check_* functions in aaep_conformance/checks/
correctly identify valid and invalid AAEP events. They run against the
bundled fixtures in fixtures/valid/ and fixtures/invalid/.

Run with:  pytest tests/
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aaep_conformance.checks.envelope import (
    validate_event,
    check_envelope_required_fields,
    check_event_id_format,
    check_session_id_format,
    check_timestamp_format,
    check_producer_field,
)
from aaep_conformance.checks.lifecycle import (
    check_session_terminates,
    check_terminal_event_types,
    check_lifecycle_ordering,
    check_session_started_present,
)
from aaep_conformance.checks.tools import (
    check_tool_invoked_before_completed,
    check_tool_call_id_pairing,
    check_tool_status_enum,
    check_tool_name_consistency,
)
from aaep_conformance.checks.streaming import (
    check_position_monotonic,
    check_exactly_one_completion,
    check_coalesce_hint_valid,
    check_no_chunks_after_completion,
)
from aaep_conformance.checks.confirmation import (
    check_reply_token_format,
    check_default_decision_enum,
    check_confirmation_has_required_fields,
    check_timeout_seconds_valid,
)
from aaep_conformance.checks.handshake import (
    check_subscription_request_valid,
    check_subscription_accepted_valid,
    check_honored_capabilities_not_more_permissive,
)
from aaep_conformance.checks.safety import (
    check_irreversible_high_risk_rule,
    check_critical_urgency_on_confirmation,
    check_critical_urgency_on_errored,
    check_no_secrets_in_args_summary,
)
from aaep_conformance.reporter import Severity, TestResult, Report, Verdict


# Fixture directory locations
FIXTURES_DIR = Path(__file__).parent.parent / "aaep_conformance" / "fixtures"
VALID_DIR = FIXTURES_DIR / "valid"
INVALID_DIR = FIXTURES_DIR / "invalid"


def _load_fixture(directory: Path, name: str) -> dict:
    """Load a JSON fixture file."""
    return json.loads((directory / name).read_text(encoding="utf-8"))


# === Envelope tests ===

@pytest.mark.level1
class TestEnvelopeChecks:

    def test_valid_session_started_passes_all_envelope_checks(self):
        event = _load_fixture(VALID_DIR, "agent.session.started.json")
        assert check_envelope_required_fields(event).passed
        assert check_event_id_format(event).passed
        assert check_session_id_format(event).passed
        assert check_timestamp_format(event).passed
        assert check_producer_field(event).passed

    def test_full_schema_validation_on_valid_fixtures(self):
            """Every valid event fixture must validate against its type-specific schema."""
            for fixture_file in VALID_DIR.glob("*.json"):
                event = json.loads(fixture_file.read_text())
                if not isinstance(event.get("type"), str) or not event["type"].startswith("aaep:agent."):
                    continue
                errors = validate_event(event)
                assert not errors, (
                    f"{fixture_file.name} failed validation: {errors}"
                )

    def test_invalid_fixtures_fail_validation(self):
        """Each invalid fixture should produce schema errors."""
        for fixture_file in INVALID_DIR.glob("*.json"):
            if fixture_file.name == "duplicate-completion-streaming.json":
                # Conceptual violation; single-event schema passes
                continue
            event = json.loads(fixture_file.read_text())
            errors = validate_event(event)
            assert errors, (
                f"{fixture_file.name} should have produced validation errors"
            )

    def test_missing_event_id_caught(self):
        event = {"@context": "https://aaep-protocol.org/context/v1",
                 "type": "aaep:agent.session.started", "session_id": "sess_x",
                 "timestamp": "2026-01-01T00:00:00Z",
                 "producer": {"agent_id": "x"}, "summary_normal": "X"}
        result = check_envelope_required_fields(event)
        assert not result.passed
        assert "event_id" in result.message

    def test_malformed_event_id_caught(self):
        event = {"event_id": "not-following-pattern"}
        result = check_event_id_format(event)
        assert not result.passed
        assert "evt_" in result.message or "pattern" in result.message.lower()


# === Lifecycle tests ===

@pytest.mark.level1
class TestLifecycleChecks:

    def test_complete_session_terminates(self):
        events = [
            {"type": "aaep:agent.session.started", "session_id": "s"},
            {"type": "aaep:agent.session.completed", "session_id": "s"},
        ]
        assert check_session_terminates(events).passed
        assert check_terminal_event_types(events).passed
        assert check_lifecycle_ordering(events).passed
        assert check_session_started_present(events).passed

    def test_session_without_terminal_fails(self):
        events = [
            {"type": "aaep:agent.session.started", "session_id": "s"},
            {"type": "aaep:agent.state.changed", "session_id": "s"},
        ]
        result = check_session_terminates(events)
        assert not result.passed
        assert result.severity == Severity.ERROR

    def test_multiple_terminals_fail(self):
        events = [
            {"type": "aaep:agent.session.started", "session_id": "s"},
            {"type": "aaep:agent.session.completed", "session_id": "s"},
            {"type": "aaep:agent.session.errored", "session_id": "s"},
        ]
        result = check_terminal_event_types(events)
        assert not result.passed
        assert "Multiple" in result.message or "expected 1" in result.message

    def test_event_after_terminal_fails(self):
        events = [
            {"type": "aaep:agent.session.started", "session_id": "s"},
            {"type": "aaep:agent.session.completed", "session_id": "s"},
            {"type": "aaep:agent.output.streaming", "session_id": "s"},
        ]
        result = check_lifecycle_ordering(events)
        assert not result.passed


# === Tool tests ===

@pytest.mark.level1
class TestToolChecks:

    def test_valid_tool_pairing(self):
        events = [
            {"type": "aaep:agent.tool.invoked", "tool": "x", "tool_call_id": "call_1"},
            {"type": "aaep:agent.tool.completed", "tool": "x", "tool_call_id": "call_1", "status": "success"},
        ]
        assert check_tool_invoked_before_completed(events).passed
        assert check_tool_call_id_pairing(events).passed
        assert check_tool_status_enum(events).passed
        assert check_tool_name_consistency(events).passed

    def test_orphan_completion_fails(self):
        events = [{"type": "aaep:agent.tool.completed", "tool": "x",
                   "tool_call_id": "call_orphan", "status": "success"}]
        result = check_tool_invoked_before_completed(events)
        assert not result.passed
        assert "orphan" in result.message.lower()

    def test_invalid_tool_status_fails(self):
        events = [
            {"type": "aaep:agent.tool.invoked", "tool": "x", "tool_call_id": "call_y"},
            {"type": "aaep:agent.tool.completed", "tool": "x", "tool_call_id": "call_y", "status": "partial"},
        ]
        result = check_tool_status_enum(events)
        assert not result.passed
        assert "partial" in result.message


# === Streaming tests ===

@pytest.mark.level1
class TestStreamingChecks:

    def test_valid_streaming_passes(self):
        events = [
            {"type": "aaep:agent.output.streaming", "session_id": "s",
             "output_id": "out_a", "position": 0, "complete": False, "coalesce_hint": "sentence"},
            {"type": "aaep:agent.output.streaming", "session_id": "s",
             "output_id": "out_a", "position": 15, "complete": True, "coalesce_hint": "completion"},
        ]
        assert check_position_monotonic(events).passed
        assert check_exactly_one_completion(events).passed
        assert check_no_chunks_after_completion(events).passed
        assert check_coalesce_hint_valid(events).passed

    def test_position_regression_fails(self):
        events = [
            {"type": "aaep:agent.output.streaming", "session_id": "s",
             "output_id": "out_b", "position": 20, "complete": False},
            {"type": "aaep:agent.output.streaming", "session_id": "s",
             "output_id": "out_b", "position": 10, "complete": False},
        ]
        result = check_position_monotonic(events)
        assert not result.passed


# === Confirmation tests ===

@pytest.mark.level2
class TestConfirmationChecks:

    def test_valid_confirmation_event(self):
        event = _load_fixture(VALID_DIR, "agent.awaiting.confirmation.json")
        events = [event]
        assert check_reply_token_format(events).passed
        assert check_default_decision_enum(events).passed
        assert check_confirmation_has_required_fields(events).passed
        assert check_timeout_seconds_valid(events).passed

    def test_missing_required_fields_fails(self):
        events = [{"type": "aaep:agent.awaiting.confirmation",
                   "event_id": "evt_x", "reply_token": "rpl_x"}]
        result = check_confirmation_has_required_fields(events)
        assert not result.passed


# === Handshake tests ===

@pytest.mark.level3
class TestHandshakeChecks:

    def test_valid_subscription_request(self):
        msg = _load_fixture(VALID_DIR, "subscription.request.multilingual.json")
        assert check_subscription_request_valid(msg).passed

    def test_more_permissive_rate_fails(self):
        request = {
            "type": "subscription.request", "aaep_version": "1.0.0",
            "subscriber_id": "test",
            "capabilities": {"max_events_per_second": 5},
        }
        accepted = {
            "type": "subscription.accepted", "subscription_id": "sub_x",
            "aaep_version": "1.0.0", "producer": {"agent_id": "p"},
            "honored_capabilities": {"max_events_per_second": 10},
        }
        result = check_honored_capabilities_not_more_permissive(request, accepted)
        assert not result.passed

    def test_subscription_with_unrequested_language_fails(self):
        request = {
            "type": "subscription.request", "aaep_version": "1.0.0",
            "subscriber_id": "test",
            "capabilities": {"languages": ["en-US"]},
        }
        accepted = {
            "type": "subscription.accepted", "subscription_id": "sub_x",
            "aaep_version": "1.0.0", "producer": {"agent_id": "p"},
            "honored_capabilities": {"languages": ["en-US", "fr-FR"]},
        }
        result = check_honored_capabilities_not_more_permissive(request, accepted)
        assert not result.passed


# === Safety tests ===

@pytest.mark.level2
class TestSafetyChecks:

    def test_safe_irreversible_high_risk_with_reject(self):
        event = _load_fixture(VALID_DIR, "agent.awaiting.confirmation.json")
        result = check_irreversible_high_risk_rule([event])
        assert result.passed

    def test_unsafe_irreversible_high_risk_with_accept_fails(self):
        event = _load_fixture(INVALID_DIR, "wrong-default-decision.json")
        result = check_irreversible_high_risk_rule([event])
        assert not result.passed
        assert result.severity == Severity.ERROR

    def test_critical_urgency_required_on_confirmation(self):
        event = _load_fixture(VALID_DIR, "agent.awaiting.confirmation.json")
        result = check_critical_urgency_on_confirmation([event])
        assert result.passed

    def test_non_critical_urgency_on_errored_fails(self):
        event = _load_fixture(INVALID_DIR, "no-critical-urgency-on-errored.json")
        result = check_critical_urgency_on_errored([event])
        assert not result.passed

    def test_no_secrets_in_valid_events(self):
        for fixture_file in VALID_DIR.glob("*.json"):
            event = json.loads(fixture_file.read_text())
            result = check_no_secrets_in_args_summary([event])
            assert result.passed, f"Valid fixture {fixture_file.name} flagged as containing secrets"

    def test_secrets_in_args_summary_caught(self):
        events = [{
            "type": "aaep:agent.tool.invoked",
            "tool": "fetch",
            "args_summary": "url=https://api.example.com, api_key=sk-leaked-12345",
        }]
        result = check_no_secrets_in_args_summary(events)
        assert not result.passed


# === Report tests ===

class TestReportGeneration:

    def test_report_pass_verdict_when_no_errors(self):
        results = [
            TestResult("T-001", "ok", True, severity=Severity.INFO),
            TestResult("T-002", "ok", True, severity=Severity.INFO),
        ]
        report = Report.from_results(
            results, conformance_level=1, endpoint="test://x", duration_seconds=1.0
        )
        assert report.verdict == Verdict.PASS

    def test_report_fail_verdict_on_error(self):
        results = [
            TestResult("T-001", "ok", True, severity=Severity.INFO),
            TestResult("T-002", "bad", False, severity=Severity.ERROR, message="X"),
        ]
        report = Report.from_results(
            results, conformance_level=1, endpoint="test://x", duration_seconds=1.0
        )
        assert report.verdict == Verdict.FAIL

    def test_report_serializes_to_json(self):
        results = [TestResult("T-001", "ok", True, severity=Severity.INFO)]
        report = Report.from_results(
            results, conformance_level=1, endpoint="test://x", duration_seconds=1.0
        )
        d = report.to_dict()
        assert d["verdict"] == "PASS"
        assert d["conformance_level"] == 1
        assert d["tests_run"] == 1
        # round-trip
        s = json.dumps(d)
        assert json.loads(s)["verdict"] == "PASS"

    def test_report_renders_html(self):
        results = [TestResult("T-001", "ok", True, severity=Severity.INFO)]
        report = Report.from_results(
            results, conformance_level=2, endpoint="test://x", duration_seconds=1.0
        )
        html = report.to_html()
        assert "<!DOCTYPE html>" in html
        assert "PASS" in html
        assert "Conformance Level" in html
        assert "T-001" in html
