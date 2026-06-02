"""
Tests for LangChainAAEPHandler.

Verifies that LangChain callbacks correctly produce AAEP events with the
right structure, urgency, and safety properties. Uses synthesized callbacks
rather than a real LangChain agent for hermetic testing.

Run with:  pytest tests/
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from aaep_langchain.callback_handler import (
    HIGH_RISK_TOOL_NAMES,
    LangChainAAEPHandler,
    make_aaep_handler,
)


# === Fixtures ===

@pytest.fixture
def handler_and_events():
    """Build a handler that collects emitted events into a list."""
    events = []
    handler = LangChainAAEPHandler(send_event=events.append)
    return handler, events


def _events_of_type(events, event_type):
    return [e for e in events if e.get("type") == event_type]


# === Chain lifecycle tests ===

class TestChainCallbacks:

    def test_outer_chain_start_emits_session_started(self, handler_and_events):
        handler, events = handler_and_events
        run_id = uuid4()
        handler.on_chain_start(
            serialized={"name": "Agent"},
            inputs={"input": "Hello"},
            run_id=run_id,
            parent_run_id=None,
        )

        started = _events_of_type(events, "aaep:agent.session.started")
        assert len(started) == 1
        assert started[0]["request_text"] == "Hello"
        assert started[0]["urgency"] == "normal"

        # Should also emit a state.changed (idle -> thinking)
        state_changes = _events_of_type(events, "aaep:agent.state.changed")
        assert any(e.get("to_state") == "thinking" for e in state_changes)

    def test_nested_chain_start_reuses_session(self, handler_and_events):
        handler, events = handler_and_events
        outer = uuid4()
        inner = uuid4()
        handler.on_chain_start(
            serialized={"name": "Outer"}, inputs={"input": "X"},
            run_id=outer, parent_run_id=None,
        )
        events_before = len(events)
        handler.on_chain_start(
            serialized={"name": "Inner"}, inputs={"input": "X"},
            run_id=inner, parent_run_id=outer,
        )
        # Nested chain should NOT emit a new session.started
        new_starts = [
            e for e in events[events_before:]
            if e.get("type") == "aaep:agent.session.started"
        ]
        assert len(new_starts) == 0

    def test_outer_chain_end_emits_session_completed(self, handler_and_events):
        handler, events = handler_and_events
        run_id = uuid4()
        handler.on_chain_start(
            serialized={"name": "Agent"}, inputs={"input": "Hello"},
            run_id=run_id, parent_run_id=None,
        )
        handler.on_chain_end(
            outputs={"output": "Hi there"},
            run_id=run_id, parent_run_id=None,
        )

        completed = _events_of_type(events, "aaep:agent.session.completed")
        assert len(completed) == 1
        assert completed[0]["urgency"] == "normal"
        assert "duration_ms" in completed[0]
        assert completed[0]["tool_invocations_count"] == 0

    def test_chain_error_emits_critical_session_errored(self, handler_and_events):
        """An error during the agent run must produce session.errored with critical urgency."""
        handler, events = handler_and_events
        run_id = uuid4()
        handler.on_chain_start(
            serialized={"name": "Agent"}, inputs={"input": "X"},
            run_id=run_id, parent_run_id=None,
        )
        handler.on_chain_error(
            error=ConnectionError("Network down"),
            run_id=run_id, parent_run_id=None,
        )

        errored = _events_of_type(events, "aaep:agent.session.errored")
        assert len(errored) == 1
        assert errored[0]["urgency"] == "critical"
        assert errored[0]["error_category"] == "network"


# === Tool callback tests ===

class TestToolCallbacks:

    def test_tool_start_emits_invoked_with_low_risk(self, handler_and_events):
        handler, events = handler_and_events
        chain_id, tool_id = uuid4(), uuid4()
        handler.on_chain_start(
            serialized={"name": "Agent"}, inputs={"input": "X"},
            run_id=chain_id, parent_run_id=None,
        )
        handler.on_tool_start(
            serialized={"name": "fetch_balance"},
            input_str='{"account": "checking"}',
            run_id=tool_id, parent_run_id=chain_id,
            inputs={"account": "checking"},
        )

        invoked = _events_of_type(events, "aaep:agent.tool.invoked")
        assert len(invoked) == 1
        assert invoked[0]["tool"] == "fetch_balance"
        assert invoked[0]["risk_level"] == "low"
        assert invoked[0]["irreversible"] is False
        assert "account=checking" in invoked[0]["args_summary"]

    def test_high_risk_tool_classified_correctly(self, handler_and_events):
        """Tools in HIGH_RISK_TOOL_NAMES must be flagged as high-risk irreversible."""
        handler, events = handler_and_events
        chain_id, tool_id = uuid4(), uuid4()
        handler.on_chain_start(
            serialized={"name": "Agent"}, inputs={"input": "X"},
            run_id=chain_id, parent_run_id=None,
        )
        handler.on_tool_start(
            serialized={"name": "send_email"},
            input_str='{"to": "x"}',
            run_id=tool_id, parent_run_id=chain_id,
            inputs={"to": "alice@example.com"},
        )

        invoked = _events_of_type(events, "aaep:agent.tool.invoked")
        assert len(invoked) == 1
        assert invoked[0]["risk_level"] == "high"
        assert invoked[0]["irreversible"] is True

    def test_tool_end_emits_completed_success(self, handler_and_events):
        handler, events = handler_and_events
        chain_id, tool_id = uuid4(), uuid4()
        handler.on_chain_start(
            serialized={"name": "Agent"}, inputs={"input": "X"},
            run_id=chain_id, parent_run_id=None,
        )
        handler.on_tool_start(
            serialized={"name": "fetch_balance"}, input_str='{}',
            run_id=tool_id, parent_run_id=chain_id,
        )
        handler.on_tool_end(output="$100.00", run_id=tool_id)

        completed = _events_of_type(events, "aaep:agent.tool.completed")
        assert len(completed) == 1
        assert completed[0]["status"] == "success"
        assert completed[0]["tool"] == "fetch_balance"

    def test_tool_error_emits_completed_error(self, handler_and_events):
        handler, events = handler_and_events
        chain_id, tool_id = uuid4(), uuid4()
        handler.on_chain_start(
            serialized={"name": "Agent"}, inputs={"input": "X"},
            run_id=chain_id, parent_run_id=None,
        )
        handler.on_tool_start(
            serialized={"name": "fetch_balance"}, input_str='{}',
            run_id=tool_id, parent_run_id=chain_id,
        )
        handler.on_tool_error(
            error=ValueError("Bad arguments"), run_id=tool_id,
        )

        completed = _events_of_type(events, "aaep:agent.tool.completed")
        assert len(completed) == 1
        assert completed[0]["status"] == "error"

    def test_tool_timeout_emits_completed_timeout(self, handler_and_events):
        handler, events = handler_and_events
        chain_id, tool_id = uuid4(), uuid4()
        handler.on_chain_start(
            serialized={"name": "Agent"}, inputs={"input": "X"},
            run_id=chain_id, parent_run_id=None,
        )
        handler.on_tool_start(
            serialized={"name": "fetch_balance"}, input_str='{}',
            run_id=tool_id, parent_run_id=chain_id,
        )
        handler.on_tool_error(
            error=TimeoutError("Took too long"), run_id=tool_id,
        )

        completed = _events_of_type(events, "aaep:agent.tool.completed")
        assert completed[0]["status"] == "timeout"

    def test_tool_invocations_counted(self, handler_and_events):
        """session.completed should report the correct tool count."""
        handler, events = handler_and_events
        chain_id = uuid4()
        handler.on_chain_start(
            serialized={"name": "Agent"}, inputs={"input": "X"},
            run_id=chain_id, parent_run_id=None,
        )
        for _ in range(3):
            tool_id = uuid4()
            handler.on_tool_start(
                serialized={"name": "fetch_balance"}, input_str='{}',
                run_id=tool_id, parent_run_id=chain_id,
            )
            handler.on_tool_end(output="result", run_id=tool_id)

        handler.on_chain_end(outputs={"output": "done"}, run_id=chain_id, parent_run_id=None)

        completed = _events_of_type(events, "aaep:agent.session.completed")
        assert completed[0]["tool_invocations_count"] == 3


# === Streaming tests ===

class TestStreamingCallbacks:

    def test_streaming_tokens_emit_streaming_events(self, handler_and_events):
        handler, events = handler_and_events
        chain_id, llm_id = uuid4(), uuid4()
        handler.on_chain_start(
            serialized={"name": "Agent"}, inputs={"input": "X"},
            run_id=chain_id, parent_run_id=None,
        )
        handler.on_llm_start(
            serialized={"name": "ChatModel"}, prompts=["X"],
            run_id=llm_id, parent_run_id=chain_id,
        )

        for token in ("Hello ", "world. ", "How are you?"):
            handler.on_llm_new_token(token, run_id=llm_id)
        handler.on_llm_end(response=None, run_id=llm_id)

        streaming = _events_of_type(events, "aaep:agent.output.streaming")
        assert len(streaming) >= 1
        # Final event must be complete=true
        assert streaming[-1]["complete"] is True
        # Concatenating chunks reconstructs the original
        reconstructed = "".join(e["chunk"] for e in streaming)
        assert reconstructed == "Hello world. How are you?"


# === Risk override tests ===

class TestRiskOverrides:

    def test_user_override_takes_precedence(self):
        """tool_risk_overrides MUST override the default heuristic."""
        events = []
        handler = LangChainAAEPHandler(
            send_event=events.append,
            tool_risk_overrides={"fetch_balance": "high"},
        )
        chain_id, tool_id = uuid4(), uuid4()
        handler.on_chain_start(
            serialized={"name": "Agent"}, inputs={"input": "X"},
            run_id=chain_id, parent_run_id=None,
        )
        handler.on_tool_start(
            serialized={"name": "fetch_balance"},
            input_str='{}', run_id=tool_id, parent_run_id=chain_id,
        )

        invoked = _events_of_type(events, "aaep:agent.tool.invoked")
        assert invoked[0]["risk_level"] == "high"
        assert invoked[0]["irreversible"] is True


# === Constants tests ===

class TestConstants:

    def test_high_risk_set_contains_expected_tools(self):
        for name in ("send_email", "transfer_funds", "delete_record", "delete_file"):
            assert name in HIGH_RISK_TOOL_NAMES


# === Factory tests ===

class TestFactory:

    def test_make_aaep_handler_returns_configured_handler(self):
        events = []
        handler = make_aaep_handler(
            send_event=events.append,
            agent_id="my-agent",
            agent_name="My Agent",
            model="gpt-4",
        )
        assert isinstance(handler, LangChainAAEPHandler)
        # Exercise by emitting a session.started
        run_id = uuid4()
        handler.on_chain_start(
            serialized={"name": "Agent"}, inputs={"input": "X"},
            run_id=run_id, parent_run_id=None,
        )
        started = _events_of_type(events, "aaep:agent.session.started")
        assert started[0]["producer"]["agent_id"] == "my-agent"
