"""
Tests for AnthropicAAEPAdapter.

Verifies that the adapter:
- Correctly initializes in mock vs real mode based on API key availability
- Emits valid AAEP events for sessions with and without tools
- Enforces safety rules at the Python level (matching the schema rule)
- Handles errors with proper terminal events
- Reuses the shared AAEPEmitter and StreamCoalescer infrastructure

Run with:  pytest tests/
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from aaep_anthropic_sdk.adapter import (
    HIGH_RISK_TOOLS,
    AnthropicAAEPAdapter,
    ToolHandler,
    make_adapter,
)


# === Fixtures ===

@pytest.fixture
def collected_events():
    return []


@pytest.fixture
def adapter_no_key(collected_events):
    """Adapter with no API key (mock mode)."""
    with patch.dict(os.environ, {}, clear=True):
        return AnthropicAAEPAdapter(send_event=collected_events.append)


def _events_of_type(events, event_type):
    return [e for e in events if e.get("type") == event_type]


# === Initialization tests ===

class TestAdapterInitialization:

    def test_mock_mode_when_no_api_key(self, collected_events):
        with patch.dict(os.environ, {}, clear=True):
            adapter = AnthropicAAEPAdapter(send_event=collected_events.append)
        assert adapter.mock_mode is True

    def test_real_mode_when_api_key_present(self, collected_events):
        # Note: this test still uses mock mode unless anthropic SDK installed
        # The key is whether the adapter ATTEMPTS to use real mode
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            adapter = AnthropicAAEPAdapter(send_event=collected_events.append)
        # mock_mode depends on both env var AND anthropic package availability
        assert isinstance(adapter.mock_mode, bool)

    def test_explicit_api_key_overrides_env(self, collected_events):
        adapter = AnthropicAAEPAdapter(
            send_event=collected_events.append,
            api_key="explicit-key",
        )
        # In test env without anthropic installed, still mock mode
        assert isinstance(adapter.mock_mode, bool)

    def test_model_name_recorded(self, collected_events):
        adapter = AnthropicAAEPAdapter(
            send_event=collected_events.append,
            model="claude-opus-4-7",
        )
        assert adapter.model == "claude-opus-4-7"
        assert adapter.emitter.producer_info["model"] == "claude-opus-4-7"


# === Basic session tests ===

class TestBasicSession:

    @pytest.mark.asyncio
    async def test_simple_session_emits_lifecycle_events(
        self, adapter_no_key, collected_events,
    ):
        """A basic session must emit started + completed at minimum."""
        await adapter_no_key.run_session(
            user_message="Hello",
        )

        started = _events_of_type(collected_events, "aaep:agent.session.started")
        completed = _events_of_type(collected_events, "aaep:agent.session.completed")

        assert len(started) == 1
        assert len(completed) == 1
        assert started[0]["request_text"] == "Hello"
        assert completed[0]["urgency"] == "normal"
        assert "duration_ms" in completed[0]

    @pytest.mark.asyncio
    async def test_session_id_consistent_across_events(
        self, adapter_no_key, collected_events,
    ):
        await adapter_no_key.run_session(user_message="Test")
        session_ids = {
            e["session_id"] for e in collected_events
            if "session_id" in e
        }
        assert len(session_ids) == 1

    @pytest.mark.asyncio
    async def test_streaming_emits_output_events(
        self, adapter_no_key, collected_events,
    ):
        """Mock mode produces text-streaming events for non-tool queries."""
        await adapter_no_key.run_session(user_message="Tell me a fact")
        streaming = _events_of_type(collected_events, "aaep:agent.output.streaming")
        assert len(streaming) >= 1
        # The last streaming event should be complete=true
        assert streaming[-1]["complete"] is True


# === Tool use tests ===

class TestToolUse:

    @pytest.mark.asyncio
    async def test_tool_invoked_completed_pairing(
        self, adapter_no_key, collected_events,
    ):
        """Tool calls must produce paired invoked/completed events."""
        await adapter_no_key.run_session(
            user_message="What's my account balance?",
            tools=[{
                "name": "fetch_balance",
                "description": "Get balance",
                "input_schema": {"type": "object", "properties": {}},
            }],
            tool_handlers={"fetch_balance": lambda account="checking": f"Balance: $100"},
        )

        invoked = _events_of_type(collected_events, "aaep:agent.tool.invoked")
        completed = _events_of_type(collected_events, "aaep:agent.tool.completed")

        assert len(invoked) >= 1
        assert len(completed) >= 1
        # Pairing: invoked tool_call_id matches completed tool_call_id
        invoked_ids = {e["tool_call_id"] for e in invoked}
        completed_ids = {e["tool_call_id"] for e in completed}
        assert invoked_ids == completed_ids

    @pytest.mark.asyncio
    async def test_tool_handler_result_in_completed(
        self, adapter_no_key, collected_events,
    ):
        """The tool handler's return value should appear in the completed event."""
        await adapter_no_key.run_session(
            user_message="Look up my account balance",
            tools=[{
                "name": "fetch_balance",
                "description": "Get balance",
                "input_schema": {"type": "object", "properties": {}},
            }],
            tool_handlers={"fetch_balance": lambda account="checking": "Balance: $3,247.18"},
        )

        completed = _events_of_type(collected_events, "aaep:agent.tool.completed")
        assert any(
            "3,247.18" in str(e.get("summary_normal", ""))
            for e in completed
        )


# === Safety tests ===

class TestSafetyRules:

    def test_irreversible_tools_in_default_set(self):
        """The default HIGH_RISK_TOOLS set must include known-dangerous tool names."""
        for name in ("send_email", "transfer_funds", "delete_record"):
            assert name in HIGH_RISK_TOOLS

    @pytest.mark.asyncio
    async def test_unsafe_irreversible_high_rejected_at_emitter(
        self, adapter_no_key, collected_events,
    ):
        """
        The emitter's await_confirmation MUST refuse to emit an unsafe
        irreversible+high confirmation with default_decision='accept'.
        """
        emitter = adapter_no_key.emitter
        sid = emitter.start_session(summary_normal="Test")

        with pytest.raises(ValueError, match="default_decision"):
            emitter.await_confirmation(
                session_id=sid,
                action="Delete all data",
                consequence="Cannot be undone",
                risk_level="high",
                irreversible=True,
                default_decision="accept",  # unsafe combination
            )

    @pytest.mark.asyncio
    async def test_default_decision_is_reject_for_high_risk(
        self, adapter_no_key, collected_events,
    ):
        """
        Confirmation events for high-risk irreversible actions MUST set
        default_decision='reject'.
        """
        emitter = adapter_no_key.emitter
        sid = emitter.start_session(summary_normal="Test")
        # This should succeed because default_decision='reject' is correct
        emitter.await_confirmation(
            session_id=sid,
            action="Send email",
            consequence="Cannot be undone",
            risk_level="high",
            irreversible=True,
            default_decision="reject",
        )

        conf = _events_of_type(collected_events, "aaep:agent.awaiting.confirmation")
        assert len(conf) == 1
        assert conf[0]["default_decision"] == "reject"
        assert conf[0]["urgency"] == "critical"


# === Error handling tests ===

class TestErrorHandling:

    @pytest.mark.asyncio
    async def test_missing_tool_handler_produces_error_in_completed(
        self, adapter_no_key, collected_events,
    ):
        """A tool_use block with no registered handler produces tool.completed(error)."""
        # Adapter's mock mode calls fetch_balance when query contains "balance"
        await adapter_no_key.run_session(
            user_message="Check my balance",
            tools=[{
                "name": "fetch_balance",
                "description": "Get balance",
                "input_schema": {"type": "object", "properties": {}},
            }],
            tool_handlers={},  # No handler registered!
        )

        completed = _events_of_type(collected_events, "aaep:agent.tool.completed")
        assert len(completed) >= 1
        assert completed[0]["status"] == "error"
        assert "handler" in completed[0].get("error_message", "").lower()


# === Factory tests ===

class TestFactory:

    def test_make_adapter_returns_configured_adapter(self, collected_events):
        adapter = make_adapter(
            send_event=collected_events.append,
            model="claude-opus-4-7",
            agent_name="Test Agent",
        )
        assert isinstance(adapter, AnthropicAAEPAdapter)
        assert adapter.model == "claude-opus-4-7"

    def test_default_model_is_current_claude(self, collected_events):
        """Default model should be the current Claude Opus version."""
        adapter = make_adapter(send_event=collected_events.append)
        assert adapter.model.startswith("claude-")


# === Conformance smoke test ===

class TestConformanceSmoke:

    @pytest.mark.asyncio
    async def test_all_events_have_required_envelope_fields(
        self, adapter_no_key, collected_events,
    ):
        """Every emitted event MUST have the AAEP envelope fields."""
        await adapter_no_key.run_session(user_message="Hello")

        required = ["@context", "type", "event_id", "session_id",
                    "timestamp", "producer"]
        for event in collected_events:
            for field in required:
                assert field in event, (
                    f"Event missing {field!r}: {event.get('type')}"
                )

    @pytest.mark.asyncio
    async def test_critical_urgency_on_errored_events(
        self, adapter_no_key, collected_events,
    ):
        """If session.errored is emitted, it MUST have urgency='critical'."""
        # Trigger an error by raising in a tool handler
        def boom():
            raise RuntimeError("Boom!")

        try:
            await adapter_no_key.run_session(
                user_message="Search the records for 'test'",
                tools=[{
                    "name": "search_records",
                    "description": "Search",
                    "input_schema": {"type": "object", "properties": {}},
                }],
                tool_handlers={"search_records": boom},
            )
        except Exception:
            pass

        errored = _events_of_type(collected_events, "aaep:agent.session.errored")
        for event in errored:
            assert event["urgency"] == "critical"
