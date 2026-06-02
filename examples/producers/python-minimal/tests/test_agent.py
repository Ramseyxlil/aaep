"""
Tests for the python-minimal AAEP producer example.

Verifies that the emitter produces valid AAEP events, the AgentLoop runs
cleanly end-to-end, the safety rules are enforced, and terminal events
are emitted on all paths (success, error, cancellation).

Run with:  pytest tests/
"""

from __future__ import annotations

import asyncio
import re

import pytest

from aaep_minimal_producer.agent import AgentLoop, ToolDescriptor
from aaep_minimal_producer.emitter import (
    AAEPEmitter,
    StreamCoalescer,
    classify_error_category,
    classify_risk,
    make_id,
    safe_args_summary,
)


# === make_id tests ===

class TestMakeId:

    def test_event_id_format(self):
        eid = make_id("evt")
        assert re.match(r"^evt_[A-Za-z0-9]{1,64}$", eid)

    def test_session_id_format(self):
        sid = make_id("sess")
        assert re.match(r"^sess_[A-Za-z0-9]{1,64}$", sid)

    def test_reply_token_format(self):
        rt = make_id("rpl")
        assert re.match(r"^rpl_[A-Za-z0-9]{1,64}$", rt)

    def test_ids_are_unique(self):
        ids = {make_id("evt") for _ in range(100)}
        assert len(ids) == 100

    def test_invalid_prefix_rejected(self):
        with pytest.raises(ValueError):
            make_id("Evt")  # uppercase
        with pytest.raises(ValueError):
            make_id("evt_x")  # underscore
        with pytest.raises(ValueError):
            make_id("123")  # digits


# === Helper tests ===

class TestHelpers:

    def test_classify_error_category(self):
        assert classify_error_category(TimeoutError("x")) == "timeout"
        assert classify_error_category(ConnectionError("x")) == "network"
        assert classify_error_category(PermissionError("x")) == "authorization"
        assert classify_error_category(ValueError("x")) == "invalid_input"
        assert classify_error_category(RuntimeError("x")) == "unknown"

    def test_classify_risk_high_irreversible(self):
        risk, irrev = classify_risk("send_email")
        assert risk == "high"
        assert irrev is True

    def test_classify_risk_low_reversible(self):
        risk, irrev = classify_risk("fetch_balance")
        assert risk == "low"
        assert irrev is False

    def test_safe_args_summary_redacts_secrets(self):
        result = safe_args_summary({
            "url": "https://api.example.com",
            "api_key": "sk-secret-12345",
            "password": "swordfish",
            "user": "alice",
        })
        assert "sk-secret-12345" not in result
        assert "swordfish" not in result
        assert "redacted" in result.lower()
        assert "alice" in result  # non-secret field preserved


# === Emitter tests ===

class TestAAEPEmitter:

    @pytest.fixture
    def collected_events(self):
        events = []

        def collect(event):
            events.append(event)

        emitter = AAEPEmitter(send_event=collect)
        return emitter, events

    def test_start_session_emits_correctly(self, collected_events):
        emitter, events = collected_events
        sid = emitter.start_session(summary_normal="Test session")

        assert re.match(r"^sess_", sid)
        assert len(events) == 1
        event = events[0]
        assert event["type"] == "aaep:agent.session.started"
        assert event["session_id"] == sid
        assert event["urgency"] == "normal"
        assert event["summary_normal"] == "Test session"
        assert "event_id" in event
        assert event["@context"] == "https://aaep-protocol.org/context/v1"

    def test_error_session_has_critical_urgency(self, collected_events):
        emitter, events = collected_events
        sid = emitter.start_session(summary_normal="Test")
        emitter.error_session(
            session_id=sid,
            error_category="timeout",
            summary_normal="Failed.",
        )
        error_event = events[-1]
        assert error_event["type"] == "aaep:agent.session.errored"
        assert error_event["urgency"] == "critical"
        assert error_event["error_category"] == "timeout"

    def test_confirmation_has_critical_urgency(self, collected_events):
        emitter, events = collected_events
        sid = emitter.start_session(summary_normal="Test")
        emitter.await_confirmation(
            session_id=sid,
            action="Test action",
            consequence="Test consequence",
            risk_level="low",
        )
        conf = events[-1]
        assert conf["type"] == "aaep:agent.awaiting.confirmation"
        assert conf["urgency"] == "critical"

    def test_safety_rule_runtime_enforcement(self, collected_events):
        """Irreversible+high+accept MUST be rejected at runtime."""
        emitter, _ = collected_events
        sid = emitter.start_session(summary_normal="Test")
        with pytest.raises(ValueError, match="default_decision"):
            emitter.await_confirmation(
                session_id=sid,
                action="Delete records",
                consequence="Permanent",
                risk_level="high",
                irreversible=True,
                default_decision="accept",  # ← unsafe combination
            )

    def test_safety_rule_allows_irreversible_low_risk(self, collected_events):
        """Irreversible+low+accept is allowed (not a safety violation)."""
        emitter, events = collected_events
        sid = emitter.start_session(summary_normal="Test")
        # Should not raise
        emitter.await_confirmation(
            session_id=sid,
            action="Mark notification as read",
            consequence="Notification will not appear again",
            risk_level="low",
            irreversible=True,
            default_decision="accept",
        )

    def test_tool_invoked_completed_pairing(self, collected_events):
        emitter, events = collected_events
        sid = emitter.start_session(summary_normal="Test")
        emitter.tool_invoked(
            session_id=sid,
            tool="lookup",
            tool_call_id="call_x",
            args_summary="query=test",
        )
        emitter.tool_completed(
            session_id=sid,
            tool="lookup",
            tool_call_id="call_x",
            status="success",
            summary_normal="OK",
        )
        invocation = events[-2]
        completion = events[-1]
        assert invocation["type"] == "aaep:agent.tool.invoked"
        assert completion["type"] == "aaep:agent.tool.completed"
        assert invocation["tool_call_id"] == completion["tool_call_id"]
        assert completion["status"] == "success"

    def test_tool_status_enum_enforced(self, collected_events):
        emitter, _ = collected_events
        with pytest.raises(ValueError, match="success/error/timeout"):
            emitter.tool_completed(
                session_id="sess_x",
                tool="lookup",
                tool_call_id="call_y",
                status="partial",  # invalid
            )

    def test_sequence_numbers_increment(self, collected_events):
        emitter, events = collected_events
        sid = emitter.start_session(summary_normal="Test")
        emitter.state_changed(session_id=sid, from_state="idle",
                              to_state="thinking", summary_normal="Thinking.")
        emitter.state_changed(session_id=sid, from_state="thinking",
                              to_state="writing_output", summary_normal="Writing.")
        seqs = [e["sequence_number"] for e in events]
        assert seqs == [0, 1, 2]


# === StreamCoalescer tests ===

class TestStreamCoalescer:

    @pytest.fixture
    def emitter_and_events(self):
        events = []
        emitter = AAEPEmitter(send_event=lambda e: events.append(e))
        emitter.start_session(summary_normal="Test")
        return emitter, events

    def test_sentence_coalescing(self, emitter_and_events):
        emitter, events = emitter_and_events
        coalescer = StreamCoalescer(
            emitter=emitter,
            session_id="sess_test",
            output_id="out_test",
            coalesce_at="sentence",
        )
        coalescer.add_token("Hello ")
        coalescer.add_token("world. ")  # sentence boundary -> emit
        coalescer.add_token("Goodbye.")
        coalescer.finish()  # final emit

        stream_events = [e for e in events if e["type"] == "aaep:agent.output.streaming"]
        assert len(stream_events) >= 2  # at least one chunk + completion
        assert any(e.get("complete") for e in stream_events)
        # Concatenated chunks should reconstruct the original
        reconstructed = "".join(e["chunk"] for e in stream_events)
        assert reconstructed == "Hello world. Goodbye."

    def test_finish_emits_completion(self, emitter_and_events):
        emitter, events = emitter_and_events
        coalescer = StreamCoalescer(
            emitter=emitter, session_id="s", output_id="o",
            coalesce_at="completion",
        )
        coalescer.add_token("Some text")
        coalescer.finish()
        stream_events = [e for e in events if e["type"] == "aaep:agent.output.streaming"]
        assert len(stream_events) == 1
        assert stream_events[0]["complete"] is True


# === AgentLoop integration tests ===

class TestAgentLoop:

    @pytest.fixture
    def agent_and_events(self):
        events = []
        emitter = AAEPEmitter(send_event=lambda e: events.append(e))
        agent = AgentLoop(emitter=emitter)
        return agent, events

    @pytest.mark.asyncio
    async def test_simple_session_completes(self, agent_and_events):
        agent, events = agent_and_events
        session_id = await agent.run("Tell me a fact.")

        types = [e["type"] for e in events]
        assert "aaep:agent.session.started" in types
        assert "aaep:agent.session.completed" in types
        # Session ID consistent across events
        session_events = [e for e in events if e.get("session_id") == session_id]
        assert len(session_events) >= 3  # started + state changes + completed

    @pytest.mark.asyncio
    async def test_session_terminates(self, agent_and_events):
        """Every session MUST end with a terminal event."""
        agent, events = agent_and_events
        await agent.run("Tell me about the weather.")

        terminal_types = {
            "aaep:agent.session.completed",
            "aaep:agent.session.errored",
            "aaep:agent.session.cancelled",
        }
        terminals = [e for e in events if e["type"] in terminal_types]
        assert len(terminals) == 1
