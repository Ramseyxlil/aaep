"""
Conformance check modules.

Each module in this package implements checks for one category of AAEP
behavior. Test cases in level_1.py / level_2.py / level_3.py compose these
checks into full test scenarios.

Module organization:
  envelope.py     - Envelope structure (required fields, ID patterns, schema)
  lifecycle.py    - Session lifecycle (started, completed, errored, cancelled)
  tools.py        - Tool invocation pairing (tool.invoked → tool.completed)
  streaming.py    - Streaming output (position monotonicity, completion semantics)
  confirmation.py - Confirmation flow (blocking, reply tokens, timeouts)
  handshake.py    - Subscription handshake (capability negotiation)
  safety.py       - Safety rules (irreversible+high MUST default reject)

Each check function returns a TestResult or list[TestResult], and follows
the signature `def check_xxx(event, context) -> TestResult | list[TestResult]`.
"""

from __future__ import annotations

from aaep_conformance.checks.envelope import (
    validate_event,
    validate_envelope_only,
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
)
from aaep_conformance.checks.tools import (
    check_tool_invoked_before_completed,
    check_tool_call_id_pairing,
    check_tool_status_enum,
)
from aaep_conformance.checks.streaming import (
    check_position_monotonic,
    check_exactly_one_completion,
    check_coalesce_hint_valid,
)
from aaep_conformance.checks.confirmation import (
    check_blocking_contract,
    check_reply_token_format,
    check_reply_token_single_use,
    check_default_decision_enum,
)
from aaep_conformance.checks.handshake import (
    check_subscription_request_valid,
    check_subscription_accepted_valid,
    check_honored_capabilities_not_more_permissive,
)
from aaep_conformance.checks.safety import (
    check_irreversible_high_risk_rule,
    check_critical_urgency_on_errored,
    check_critical_urgency_on_confirmation,
    check_critical_events_bypass_filters,
)


__all__ = [
    # From envelope.py
    "validate_event",
    "validate_envelope_only",
    "check_envelope_required_fields",
    "check_event_id_format",
    "check_session_id_format",
    "check_timestamp_format",
    "check_producer_field",
    # From lifecycle.py
    "check_session_terminates",
    "check_terminal_event_types",
    "check_lifecycle_ordering",
    # From tools.py
    "check_tool_invoked_before_completed",
    "check_tool_call_id_pairing",
    "check_tool_status_enum",
    # From streaming.py
    "check_position_monotonic",
    "check_exactly_one_completion",
    "check_coalesce_hint_valid",
    # From confirmation.py
    "check_blocking_contract",
    "check_reply_token_format",
    "check_reply_token_single_use",
    "check_default_decision_enum",
    # From handshake.py
    "check_subscription_request_valid",
    "check_subscription_accepted_valid",
    "check_honored_capabilities_not_more_permissive",
    # From safety.py
    "check_irreversible_high_risk_rule",
    "check_critical_urgency_on_errored",
    "check_critical_urgency_on_confirmation",
    "check_critical_events_bypass_filters",
]
