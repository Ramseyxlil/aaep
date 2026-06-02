"""
Envelope structure checks.

Validates AAEP events against the envelope schema and event-type-specific
schemas. Provides both simple validation functions (returning lists of error
strings) for the CLI's `validate` command and TestResult-returning checks
for the conformance runner.
"""

from __future__ import annotations

import functools
import importlib.resources as resources
import json
import re
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, RefResolver

from aaep_conformance.reporter import Severity, TestResult


# === Schema loading ===

# Patterns for identifier validation (matches the spec's ABNF)
EVENT_ID_PATTERN = re.compile(r"^evt_[A-Za-z0-9]{1,64}$")
SESSION_ID_PATTERN = re.compile(r"^sess_[A-Za-z0-9]{1,64}$")
REPLY_TOKEN_PATTERN = re.compile(r"^rpl_[A-Za-z0-9]{1,64}$")
SUBSCRIPTION_ID_PATTERN = re.compile(r"^sub_[A-Za-z0-9]{1,64}$")
TOOL_CALL_ID_PATTERN = re.compile(r"^call_[A-Za-z0-9]{1,64}$")
OUTPUT_ID_PATTERN = re.compile(r"^out_[A-Za-z0-9]{1,64}$")
TIMESTAMP_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$"
)


# Core event types defined by the AAEP specification
CORE_EVENT_TYPES = {
    "aaep:agent.session.started",
    "aaep:agent.session.completed",
    "aaep:agent.session.errored",
    "aaep:agent.session.cancelled",
    "aaep:agent.state.changed",
    "aaep:agent.progress.updated",
    "aaep:agent.tool.invoked",
    "aaep:agent.tool.completed",
    "aaep:agent.output.streaming",
    "aaep:agent.awaiting.confirmation",
    "aaep:agent.awaiting.clarification",
    "aaep:agent.handoff.requested",
}


@functools.lru_cache(maxsize=None)
def _load_schema(schema_name: str) -> dict[str, Any]:
    """Load a JSON Schema file from the bundled schemas/ directory."""
    # Try multiple lookup locations: installed package, repo layout
    candidates = [
        Path(__file__).parent.parent.parent.parent / "schemas" / schema_name,
        Path(__file__).parent / "schemas" / schema_name,
    ]
    for path in candidates:
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))
    raise FileNotFoundError(f"Could not locate schema: {schema_name}")


@functools.lru_cache(maxsize=None)
def _envelope_schema() -> dict[str, Any]:
    return _load_schema("envelope.schema.json")


@functools.lru_cache(maxsize=None)
def _event_schema(event_type: str) -> dict[str, Any] | None:
    """Find the JSON Schema for a core event type, or None if unknown."""
    if event_type not in CORE_EVENT_TYPES:
        return None
    bare = event_type.removeprefix("aaep:")
    return _load_schema(f"core/{bare}.schema.json")


def _build_resolver(schema: dict[str, Any]) -> RefResolver:
    """Build a JSON Schema resolver that knows about the envelope schema."""
    envelope = _envelope_schema()
    store = {
        envelope["$id"]: envelope,
        schema.get("$id", "https://aaep-protocol.org/schemas/v1/unknown"): schema,
    }
    return RefResolver.from_schema(schema, store=store)


# === Simple validation API (used by the `validate` CLI command) ===

def validate_event(event: dict[str, Any]) -> list[str]:
    """
    Validate a full AAEP event against the envelope and its event-type schema.
    Returns a list of error messages; an empty list means valid.
    """
    errors: list[str] = []

    if not isinstance(event, dict):
        return ["Event must be a JSON object."]

    event_type = event.get("type")
    if not event_type:
        errors.append("Missing required field: 'type'")
        return errors

    # Validate against envelope
    envelope = _envelope_schema()
    envelope_validator = Draft202012Validator(envelope)
    for err in envelope_validator.iter_errors(event):
        errors.append(f"Envelope: {err.message} (at {'/'.join(str(p) for p in err.absolute_path) or '<root>'})")

    # If it's a known core event type, validate against the event-specific schema
    type_schema = _event_schema(event_type)
    if type_schema is not None:
        resolver = _build_resolver(type_schema)
        type_validator = Draft202012Validator(type_schema, resolver=resolver)
        for err in type_validator.iter_errors(event):
            errors.append(
                f"Event type '{event_type}': {err.message} "
                f"(at {'/'.join(str(p) for p in err.absolute_path) or '<root>'})"
            )

    return errors


def validate_envelope_only(event: dict[str, Any]) -> list[str]:
    """Validate only the envelope structure, ignoring event-specific fields."""
    if not isinstance(event, dict):
        return ["Event must be a JSON object."]

    envelope = _envelope_schema()
    validator = Draft202012Validator(envelope)
    return [
        f"{err.message} (at {'/'.join(str(p) for p in err.absolute_path) or '<root>'})"
        for err in validator.iter_errors(event)
    ]


# === TestResult-returning checks (used by the runner) ===

def check_envelope_required_fields(event: dict[str, Any], *,
                                    test_id: str = "L1-ENV-001") -> TestResult:
    """Check that the envelope has all required fields."""
    required = ["@context", "type", "event_id", "session_id", "timestamp", "producer"]
    missing = [field for field in required if field not in event]

    if missing:
        return TestResult(
            test_id=test_id,
            description="Envelope contains all required fields",
            passed=False,
            severity=Severity.ERROR,
            message=f"Missing required field(s): {', '.join(missing)}",
            expected=f"All of: {required}",
            actual=f"Missing: {missing}",
            spec_reference="Chapter 3 §3.2",
        )

    return TestResult(
        test_id=test_id,
        description="Envelope contains all required fields",
        passed=True,
        spec_reference="Chapter 3 §3.2",
    )


def check_event_id_format(event: dict[str, Any], *,
                            test_id: str = "L1-ENV-002") -> TestResult:
    """Check that event_id matches the AAEP ABNF pattern."""
    event_id = event.get("event_id", "")
    valid = bool(EVENT_ID_PATTERN.match(event_id))

    return TestResult(
        test_id=test_id,
        description="event_id matches required pattern",
        passed=valid,
        severity=Severity.ERROR if not valid else Severity.INFO,
        message="" if valid else f"event_id {event_id!r} does not match ^evt_[A-Za-z0-9]{{1,64}}$",
        expected="evt_<alphanumeric, 1-64 chars>",
        actual=event_id,
        spec_reference="Chapter 3 §3.2.3",
    )


def check_session_id_format(event: dict[str, Any], *,
                              test_id: str = "L1-ENV-003") -> TestResult:
    """Check that session_id matches the AAEP ABNF pattern."""
    session_id = event.get("session_id", "")
    valid = bool(SESSION_ID_PATTERN.match(session_id))

    return TestResult(
        test_id=test_id,
        description="session_id matches required pattern",
        passed=valid,
        severity=Severity.ERROR if not valid else Severity.INFO,
        message="" if valid else f"session_id {session_id!r} does not match ^sess_[A-Za-z0-9]{{1,64}}$",
        expected="sess_<alphanumeric, 1-64 chars>",
        actual=session_id,
        spec_reference="Chapter 3 §3.2.4",
    )


def check_timestamp_format(event: dict[str, Any], *,
                             test_id: str = "L1-ENV-004") -> TestResult:
    """Check that timestamp is RFC 3339 format."""
    timestamp = event.get("timestamp", "")
    valid = bool(TIMESTAMP_PATTERN.match(timestamp))

    return TestResult(
        test_id=test_id,
        description="timestamp is in RFC 3339 format",
        passed=valid,
        severity=Severity.ERROR if not valid else Severity.INFO,
        message="" if valid else f"timestamp {timestamp!r} is not valid RFC 3339",
        expected="YYYY-MM-DDTHH:MM:SS[.sss](Z|±HH:MM)",
        actual=timestamp,
        spec_reference="Chapter 3 §3.2.5",
    )


def check_producer_field(event: dict[str, Any], *,
                          test_id: str = "L1-ENV-005") -> TestResult:
    """Check that the producer field has a valid agent_id."""
    producer = event.get("producer")
    if not isinstance(producer, dict):
        return TestResult(
            test_id=test_id,
            description="producer field is a structured object",
            passed=False,
            severity=Severity.ERROR,
            message=f"producer must be an object, got {type(producer).__name__}",
            spec_reference="Chapter 3 §3.2.6",
        )

    agent_id = producer.get("agent_id", "")
    if not isinstance(agent_id, str) or not agent_id:
        return TestResult(
            test_id=test_id,
            description="producer.agent_id is a non-empty string",
            passed=False,
            severity=Severity.ERROR,
            message=f"producer.agent_id must be a non-empty string, got {agent_id!r}",
            spec_reference="Chapter 3 §3.2.6.1",
        )

    return TestResult(
        test_id=test_id,
        description="producer field is valid",
        passed=True,
        spec_reference="Chapter 3 §3.2.6",
    )


__all__ = [
    # Constants
    "CORE_EVENT_TYPES",
    "EVENT_ID_PATTERN",
    "SESSION_ID_PATTERN",
    "REPLY_TOKEN_PATTERN",
    "SUBSCRIPTION_ID_PATTERN",
    "TOOL_CALL_ID_PATTERN",
    "OUTPUT_ID_PATTERN",
    # Simple validators (return list of error strings)
    "validate_event",
    "validate_envelope_only",
    # TestResult-returning checks
    "check_envelope_required_fields",
    "check_event_id_format",
    "check_session_id_format",
    "check_timestamp_format",
    "check_producer_field",
]
