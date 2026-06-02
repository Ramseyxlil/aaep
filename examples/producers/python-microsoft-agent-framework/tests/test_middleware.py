"""
Tests for MAFAAEPMiddleware.

Verifies that the middleware:
- Initializes correctly with sensible defaults
- Emits AAEP events for agent lifecycle (start, tool calls, chunks, end)
- Enforces safety rules at runtime
- Handles Azure content filter signals
- Produces proper terminal events on success and error

Run with:  pytest tests/
"""

from __future__ import annotations

import pytest

from aaep_maf.middleware import (
    HIGH_RISK_TOOLS,
    AgentContext,
    MAFAAEPMiddleware,
    ResponseChunkContext,
    ToolCallContext,
    make_middleware,
)


# === Fixtures ===

@pytest.fixture
def collected_events():
    return []


@pytest.fixture
def middleware(collected_events):
    return MAFAAEPMiddleware(send_event=collected_events.append)


def _events_of_type(events, event_type):
    return [e for e in events if e.get("type") == event_type]


# === Initialization tests ===

class TestInitialization:

    def test_default_model_is_gpt4o(self, collected_events):
        mw = MAFAAEPMiddleware(send_event=collected_events.append)
        assert mw.model == "gpt-4o"

    def test_custom_model_recorded(self, collected_events):
        mw = MAFAAEPMiddleware(
            send_event=collected_events.append,
            model="gpt-4-turbo",
        )
        assert mw.model == "gpt-4-turbo"
        assert mw.emitter.producer_info["model"] == "gpt-4-turbo"

    def test_high_risk_tools_default(self, collected_events):
        mw = MAFAAEPMiddleware(send_event=collected_events.append)
        assert "send_email" in mw.high_risk_tools
        assert "delete_record" in mw.high_risk_tools


# === Lifecycle tests ===

class TestAgentLifecycle:

    @pytest.mark.asyncio
    async def test_on_agent_start_emits_session_started(
        self, middleware, collected_events,
    ):
        ctx = AgentContext(user_message="Hello", user_id="alice")

        async def _no_op(c):
            return "done"

        await middleware.on_agent_start(ctx, _no_op)

        started = _events_of_type(collected_events, "aaep:agent.session.started")
        assert len(started) == 1
        assert started[0]["request_text"] == "Hello"
        assert started[0]["urgency"] == "normal"

    @pytest.mark.asyncio
    async def test_on_agent_end_emits_session_completed(
        self, middleware, collected_events,
    ):
        ctx = AgentContext(user_message="Hello")

        async def _no_op(c):
            return "done"

        await middleware.on_agent_start(ctx, _no_op)
        await middleware.on_agent_end(ctx, _no_op)

        completed = _events_of_type(collected_events, "aaep:agent.session.completed")
        assert len(completed) == 1
        assert "duration_ms" in completed[0]

    @pytest.mark.asyncio
    async def test_agent_exception_emits_critical_errored(
        self, middleware, collected_events,
    ):
        """An exception in the agent body MUST produce session.errored with critical urgency."""
        ctx = AgentContext(user_message="Trigger error")

        async def _explode(c):
            raise ConnectionError("Network down")

        with pytest.raises(ConnectionError):
            await middleware.on_agent_start(ctx, _explode)

        errored = _events_of_type(collected_events, "aaep:agent.session.errored")
        assert len(errored) == 1
        assert errored[0]["urgency"] == "critical"
        assert errored[0]["error_category"] == "network"


# === Tool call tests ===

class TestToolCalls:

    @pytest.mark.asyncio
    async def test_tool_call_emits_invoked_completed_pair(
        self, middleware, collected_events,
    ):
        # Set up an active session first
        agent_ctx = AgentContext(user_message="Test")

        async def _run_inner(c):
            tool_ctx = ToolCallContext(
                tool_name="search_records",
                tool_arguments={"query": "test"},
            )
            tool_ctx.agent_context = agent_ctx

            async def _execute(tc):
                return "result"

            await middleware.on_tool_call(tool_ctx, _execute)
            return "done"

        await middleware.on_agent_start(agent_ctx, _run_inner)

        invoked = _events_of_type(collected_events, "aaep:agent.tool.invoked")
        completed = _events_of_type(collected_events, "aaep:agent.tool.completed")
        assert len(invoked) == 1
        assert len(completed) == 1
        assert invoked[0]["tool"] == "search_records"
        assert completed[0]["status"] == "success"
        assert invoked[0]["tool_call_id"] == completed[0]["tool_call_id"]

    @pytest.mark.asyncio
    async def test_high_risk_tool_emits_confirmation(
        self, middleware, collected_events,
    ):
        """send_email is in HIGH_RISK_TOOLS — middleware must emit confirmation."""
        agent_ctx = AgentContext(user_message="Send email")

        async def _run_inner(c):
            tool_ctx = ToolCallContext(
                tool_name="send_email",
                tool_arguments={"to": "alice@example.com"},
            )
            tool_ctx.agent_context = agent_ctx

            async def _execute(tc):
                return "Sent"

            # Auto-accept the confirmation in background
            import asyncio

            async def _auto_accept():
                await asyncio.sleep(0.1)
                for token in list(middleware.emitter._reply_decisions.keys()):
                    middleware.emitter.submit_reply(token, "accept")

            asyncio.create_task(_auto_accept())
            await middleware.on_tool_call(tool_ctx, _execute)
            return "done"

        await middleware.on_agent_start(agent_ctx, _run_inner)

        conf = _events_of_type(collected_events, "aaep:agent.awaiting.confirmation")
        assert len(conf) == 1
        assert conf[0]["urgency"] == "critical"
        assert conf[0]["risk_level"] == "high"
        assert conf[0]["irreversible"] is True
        assert conf[0]["default_decision"] == "reject"


# === Streaming tests ===

class TestStreaming:

    @pytest.mark.asyncio
    async def test_chunks_produce_streaming_events(
        self, middleware, collected_events,
    ):
        agent_ctx = AgentContext(user_message="Stream test")

        async def _run_inner(c):
            chunks = ["Hello ", "world. ", "How are you?"]
            for i, text in enumerate(chunks):
                chunk_ctx = ResponseChunkContext(
                    chunk_text=text,
                    is_final=(i == len(chunks) - 1),
                )
                chunk_ctx.agent_context = agent_ctx

                async def _no_op(cc):
                    pass

                await middleware.on_response_chunk(chunk_ctx, _no_op)
            return "done"

        await middleware.on_agent_start(agent_ctx, _run_inner)

        streaming = _events_of_type(collected_events, "aaep:agent.output.streaming")
        assert len(streaming) >= 1
        # Final must be complete=true
        assert streaming[-1]["complete"] is True
        # Reconstructed text matches input
        reconstructed = "".join(e["chunk"] for e in streaming)
        assert reconstructed == "Hello world. How are you?"


# === Azure content filter tests ===

class TestContentFilter:

    @pytest.mark.asyncio
    async def test_content_filter_emits_policy_errored(
        self, middleware, collected_events,
    ):
        """When Azure content filter signals a block, emit session.errored(policy)."""
        agent_ctx = AgentContext(user_message="<filtered>")

        async def _run_inner(c):
            c.metadata["content_filter_triggered"] = "hate_speech"
            return "done"

        await middleware.on_agent_start(agent_ctx, _run_inner)

        async def _no_op(c):
            pass

        await middleware.on_agent_end(agent_ctx, _no_op)

        errored = _events_of_type(collected_events, "aaep:agent.session.errored")
        completed = _events_of_type(collected_events, "aaep:agent.session.completed")
        assert len(errored) == 1
        assert len(completed) == 0  # NOT completed; errored took its place
        assert errored[0]["error_category"] == "policy"
        assert errored[0]["urgency"] == "critical"
        assert "remediation_hint" in errored[0]


# === Safety rule tests ===

class TestSafetyRules:

    def test_unsafe_irreversible_high_rejected_at_emitter(
        self, middleware, collected_events,
    ):
        """The emitter's runtime check MUST refuse unsafe confirmations."""
        emitter = middleware.emitter
        sid = emitter.start_session(summary_normal="Test")

        with pytest.raises(ValueError, match="default_decision"):
            emitter.await_confirmation(
                session_id=sid,
                action="Delete all records",
                consequence="Cannot be undone",
                risk_level="high",
                irreversible=True,
                default_decision="accept",
            )

    def test_high_risk_tools_set_contains_expected(self):
        for name in ("send_email", "transfer_funds", "delete_record", "delete_file"):
            assert name in HIGH_RISK_TOOLS


# === Factory tests ===

class TestFactory:

    def test_make_middleware_returns_configured_middleware(self, collected_events):
        mw = make_middleware(
            send_event=collected_events.append,
            model="gpt-4o",
            agent_name="Test Agent",
        )
        assert isinstance(mw, MAFAAEPMiddleware)
        assert mw.model == "gpt-4o"

    def test_make_middleware_accepts_custom_high_risk(self, collected_events):
        custom_set = {"custom_dangerous_tool"}
        mw = make_middleware(
            send_event=collected_events.append,
            high_risk_tools=custom_set,
        )
        assert "custom_dangerous_tool" in mw.high_risk_tools


# === Conformance smoke test ===

class TestConformanceSmoke:

    @pytest.mark.asyncio
    async def test_all_events_have_envelope_fields(
        self, middleware, collected_events,
    ):
        agent_ctx = AgentContext(user_message="Hello")

        async def _run_inner(c):
            return "done"

        async def _no_op(c):
            pass

        await middleware.on_agent_start(agent_ctx, _run_inner)
        await middleware.on_agent_end(agent_ctx, _no_op)

        required = ["@context", "type", "event_id", "session_id",
                    "timestamp", "producer"]
        for event in collected_events:
            for field in required:
                assert field in event, (
                    f"Event missing {field!r}: {event.get('type')}"
                )
