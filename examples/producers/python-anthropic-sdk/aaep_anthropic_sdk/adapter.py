"""
AnthropicAAEPAdapter — translates Anthropic SDK calls into AAEP events.

The adapter wraps an `anthropic.AsyncAnthropic()` client and exposes a single
async method, `run_session()`, that drives a complete agent loop while emitting
AAEP events. It handles:

- Multi-turn conversations until stop_reason == 'end_turn'
- Streaming text via content_block_delta events
- Tool use via content_block_start with type='tool_use'
- Safety-gated confirmation for irreversible/high-risk tools
- Proper terminal events on success, error, and cancellation

The adapter reuses the AAEPEmitter and StreamCoalescer from the python-minimal
package, so all the safety machinery (irreversible+high → MUST reject, secret
redaction, etc.) is inherited.

Falls back to a mock mode if the `anthropic` package is not installed or if
no API key is set. This makes the adapter testable in any environment.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    anthropic = None  # type: ignore[assignment]
    HAS_ANTHROPIC = False

from aaep_minimal_producer.emitter import (
    AAEPEmitter,
    StreamCoalescer,
    classify_error_category,
    classify_risk,
    make_id,
    safe_args_summary,
)


# Tools considered high-risk irreversible by default.
# Override per-call via the irreversible_tools parameter to run_session.
HIGH_RISK_TOOLS = {
    "send_email", "transfer_funds", "delete_record", "delete_file",
    "publish_post", "make_payment", "execute_trade",
}


@dataclass
class ToolHandler:
    """Wraps a tool callable with its risk metadata."""

    name: str
    handler: Callable[..., Awaitable[Any] | Any]
    risk_level: str = "low"
    irreversible: bool = False


# === The adapter ===

class AnthropicAAEPAdapter:
    """
    Bridges the Anthropic Python SDK to AAEP. Instantiate once and reuse
    across multiple sessions.

    Example:
        adapter = AnthropicAAEPAdapter(send_event=my_transport, model="claude-opus-4-7")
        session_id = await adapter.run_session(
            user_message="Tell me about Lagos.",
            tools=[{...}],
            tool_handlers={"name": handler_fn},
        )
    """

    def __init__(
        self,
        send_event: Callable[[dict[str, Any]], Any],
        *,
        model: str = "claude-opus-4-7",
        api_key: str | None = None,
        agent_id: str = "aaep-anthropic-adapter",
        agent_name: str = "AAEP Anthropic Adapter",
        max_tokens: int = 1024,
        max_iterations: int = 10,
    ):
        self.emitter = AAEPEmitter(
            send_event=send_event,
            agent_id=agent_id,
            agent_version="1.0.0",
            agent_name=agent_name,
            model=model,
        )
        self.model = model
        self.max_tokens = max_tokens
        self.max_iterations = max_iterations

        # Initialize Anthropic client; fall back to mock if unavailable
        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if HAS_ANTHROPIC and key:
            self.client = anthropic.AsyncAnthropic(api_key=key)
            self._mock_mode = False
        else:
            self.client = None
            self._mock_mode = True

    @property
    def mock_mode(self) -> bool:
        """True if no Anthropic client is configured (mock responses used)."""
        return self._mock_mode

    # === Public API ===

    async def run_session(
        self,
        user_message: str,
        *,
        tools: list[dict[str, Any]] | None = None,
        tool_handlers: dict[str, Callable] | None = None,
        irreversible_tools: set[str] | None = None,
        high_risk_tools: set[str] | None = None,
        user_id: str | None = None,
    ) -> str:
        """
        Run a complete agent session.

        Args:
            user_message: The user's input message
            tools: List of Anthropic tool definitions (name, description, input_schema)
            tool_handlers: Map of tool name -> async/sync callable
            irreversible_tools: Tool names that MUST require confirmation
            high_risk_tools: Tool names classified as high-risk (default: HIGH_RISK_TOOLS set)
            user_id: Optional user identifier for the requested_by field

        Returns:
            The new AAEP session_id
        """
        tools = tools or []
        tool_handlers = tool_handlers or {}
        irreversible_tools = irreversible_tools or HIGH_RISK_TOOLS
        high_risk_tools = high_risk_tools or HIGH_RISK_TOOLS

        session_id = self.emitter.start_session(
            summary_normal=f"Processing: {user_message[:80]}",
            request_text=user_message,
            requested_by=f"user:{user_id}" if user_id else None,
            tools_available=[t["name"] for t in tools],
        )

        start_time = time.monotonic()
        tool_count = 0
        messages = [{"role": "user", "content": user_message}]

        try:
            for iteration in range(self.max_iterations):
                self.emitter.state_changed(
                    session_id=session_id,
                    from_state="idle" if iteration == 0 else "calling_tool",
                    to_state="thinking",
                    summary_normal="Considering the request.",
                )

                # Call the model
                response_content, stop_reason = await self._call_model(
                    session_id=session_id,
                    messages=messages,
                    tools=tools,
                )

                if stop_reason == "tool_use":
                    # Process tool_use blocks
                    self.emitter.state_changed(
                        session_id=session_id,
                        from_state="thinking",
                        to_state="calling_tool",
                        summary_normal="Executing tools.",
                    )

                    tool_results, tool_count_iter = await self._execute_tools(
                        session_id=session_id,
                        response_content=response_content,
                        tool_handlers=tool_handlers,
                        irreversible_tools=irreversible_tools,
                        high_risk_tools=high_risk_tools,
                    )
                    tool_count += tool_count_iter

                    # Append assistant message and tool results
                    messages.append({"role": "assistant", "content": response_content})
                    messages.append({"role": "user", "content": tool_results})
                    continue

                # end_turn or other terminal stop reason
                break

            # Success
            duration_ms = int((time.monotonic() - start_time) * 1000)
            self.emitter.complete_session(
                session_id=session_id,
                summary_normal="Response complete.",
                duration_ms=duration_ms,
                tool_invocations_count=tool_count,
            )

        except Exception as exc:
            self.emitter.error_session(
                session_id=session_id,
                error_category=classify_error_category(exc),
                summary_normal=f"Error: {type(exc).__name__}",
                error_message=str(exc)[:1000],
                recoverable=isinstance(exc, (TimeoutError, ConnectionError)),
            )
            raise

        return session_id

    # === Internal: calling the model ===

    async def _call_model(
        self,
        *,
        session_id: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], str]:
        """
        Call the Anthropic model and process the streaming response.
        Returns (response_content_blocks, stop_reason).
        """
        if self._mock_mode:
            return await self._mock_call_model(session_id, messages, tools)

        output_id = make_id("out")
        coalescer = StreamCoalescer(
            emitter=self.emitter,
            session_id=session_id,
            output_id=output_id,
            coalesce_at="sentence",
        )

        response_content: list[dict[str, Any]] = []
        stop_reason = "end_turn"
        text_started = False
        current_tool_use: dict[str, Any] | None = None
        current_tool_json: list[str] = []

        request_args: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": messages,
        }
        if tools:
            request_args["tools"] = tools

        try:
            async with self.client.messages.stream(**request_args) as stream:
                async for event in stream:
                    if event.type == "content_block_start":
                        if event.content_block.type == "tool_use":
                            current_tool_use = {
                                "type": "tool_use",
                                "id": event.content_block.id,
                                "name": event.content_block.name,
                                "input": {},
                            }
                            current_tool_json = []

                    elif event.type == "content_block_delta":
                        if hasattr(event.delta, "text") and event.delta.text:
                            if not text_started:
                                self.emitter.state_changed(
                                    session_id=session_id,
                                    from_state="thinking",
                                    to_state="writing_output",
                                    summary_normal="Generating response.",
                                )
                                text_started = True
                            coalescer.add_token(event.delta.text)
                        elif hasattr(event.delta, "partial_json"):
                            current_tool_json.append(event.delta.partial_json)

                    elif event.type == "content_block_stop":
                        if current_tool_use is not None:
                            try:
                                current_tool_use["input"] = json.loads(
                                    "".join(current_tool_json)
                                )
                            except json.JSONDecodeError:
                                current_tool_use["input"] = {}
                            response_content.append(current_tool_use)
                            current_tool_use = None
                            current_tool_json = []

                    elif event.type == "message_delta":
                        if event.delta.stop_reason:
                            stop_reason = event.delta.stop_reason

                # Finalize text content if any was emitted
                if text_started:
                    coalescer.finish()
                    # Get full text from the final message for the messages history
                    final_message = await stream.get_final_message()
                    text_blocks = [
                        {"type": "text", "text": block.text}
                        for block in final_message.content
                        if block.type == "text"
                    ]
                    response_content = text_blocks + [
                        b for b in response_content if b.get("type") == "tool_use"
                    ]
        except Exception:
            try:
                coalescer.finish()
            except Exception:
                pass
            raise

        return response_content, stop_reason

    async def _mock_call_model(
        self,
        session_id: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], str]:
        """Mock model call used when Anthropic SDK is unavailable."""
        await asyncio.sleep(0.1)

        last_user_msg = ""
        for m in reversed(messages):
            if m.get("role") == "user" and isinstance(m.get("content"), str):
                last_user_msg = m["content"]
                break

        lower = last_user_msg.lower()

        # Decide on a tool call based on keywords
        if tools and any(kw in lower for kw in ("balance", "account", "lookup")):
            tool = next(
                (t for t in tools if "balance" in t["name"].lower() or "fetch" in t["name"].lower()),
                tools[0] if tools else None,
            )
            if tool:
                return ([{
                    "type": "tool_use",
                    "id": f"toolu_{make_id('use')[4:]}",
                    "name": tool["name"],
                    "input": {"account": "checking"},
                }], "tool_use")

        # Otherwise stream a mock text response
        output_id = make_id("out")
        coalescer = StreamCoalescer(
            emitter=self.emitter,
            session_id=session_id,
            output_id=output_id,
            coalesce_at="sentence",
        )
        self.emitter.state_changed(
            session_id=session_id,
            from_state="thinking",
            to_state="writing_output",
            summary_normal="Generating response.",
        )

        chunks = (
            "I can help with that. ",
            "This is a mock response from the AAEP Anthropic SDK adapter. ",
            "Anything else?"
        )
        full_text = ""
        for chunk in chunks:
            coalescer.add_token(chunk)
            full_text += chunk
            await asyncio.sleep(0.02)
        coalescer.finish()

        return ([{"type": "text", "text": full_text}], "end_turn")

    # === Internal: tool execution ===

    async def _execute_tools(
        self,
        *,
        session_id: str,
        response_content: list[dict[str, Any]],
        tool_handlers: dict[str, Callable],
        irreversible_tools: set[str],
        high_risk_tools: set[str],
    ) -> tuple[list[dict[str, Any]], int]:
        """Execute all tool_use blocks in the response. Returns tool_result blocks + count."""
        results = []
        count = 0

        for block in response_content:
            if block.get("type") != "tool_use":
                continue

            tool_name = block["name"]
            tool_use_id = block["id"]
            tool_input = block.get("input", {})
            aaep_call_id = make_id("call")

            risk_level = "high" if tool_name in high_risk_tools else "low"
            irreversible = tool_name in irreversible_tools
            if risk_level == "low":
                inferred_risk, inferred_irrev = classify_risk(tool_name)
                if inferred_risk == "high":
                    risk_level = "high"
                    irreversible = irreversible or inferred_irrev

            # Emit tool.invoked BEFORE any side effect
            self.emitter.tool_invoked(
                session_id=session_id,
                tool=tool_name,
                tool_call_id=aaep_call_id,
                args_summary=safe_args_summary(tool_input),
                risk_level=risk_level,
                irreversible=irreversible,
                summary_normal=f"Calling {tool_name}.",
            )
            count += 1

            # Confirmation gating
            if irreversible or risk_level == "high":
                reply_token = self.emitter.await_confirmation(
                    session_id=session_id,
                    action=f"Call {tool_name} with: {safe_args_summary(tool_input, 200)}",
                    consequence=(
                        "This action cannot be easily undone."
                        if irreversible
                        else "This action will be executed."
                    ),
                    timeout_seconds=300,
                    default_decision="reject",
                    risk_level=risk_level,
                    irreversible=irreversible,
                    summary_normal=f"Confirm: call {tool_name}?",
                )
                try:
                    decision = await asyncio.wait_for(
                        self.emitter.wait_for_decision(reply_token),
                        timeout=300,
                    )
                except asyncio.TimeoutError:
                    decision = "reject"

                if decision != "accept":
                    self.emitter.tool_completed(
                        session_id=session_id,
                        tool=tool_name,
                        tool_call_id=aaep_call_id,
                        status="error",
                        error_message="User declined to authorize this action.",
                    )
                    results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": "User declined this action.",
                        "is_error": True,
                    })
                    continue

            # Execute
            handler = tool_handlers.get(tool_name)
            if handler is None:
                error_msg = f"No handler registered for tool {tool_name!r}"
                self.emitter.tool_completed(
                    session_id=session_id,
                    tool=tool_name,
                    tool_call_id=aaep_call_id,
                    status="error",
                    error_message=error_msg,
                )
                results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use_id,
                    "content": error_msg,
                    "is_error": True,
                })
                continue

            try:
                result = handler(**tool_input)
                if asyncio.iscoroutine(result):
                    result = await result

                self.emitter.tool_completed(
                    session_id=session_id,
                    tool=tool_name,
                    tool_call_id=aaep_call_id,
                    status="success",
                    summary_normal=str(result)[:200],
                )
                results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use_id,
                    "content": str(result),
                })
            except Exception as exc:
                self.emitter.tool_completed(
                    session_id=session_id,
                    tool=tool_name,
                    tool_call_id=aaep_call_id,
                    status="error",
                    error_message=str(exc)[:1000],
                )
                results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use_id,
                    "content": str(exc),
                    "is_error": True,
                })

        return results, count


# === Convenience factory ===

def make_adapter(
    send_event: Callable[[dict[str, Any]], Any],
    *,
    model: str = "claude-opus-4-7",
    api_key: str | None = None,
    agent_name: str = "AAEP Anthropic Adapter",
) -> AnthropicAAEPAdapter:
    """Create an AnthropicAAEPAdapter with sensible defaults."""
    return AnthropicAAEPAdapter(
        send_event=send_event,
        model=model,
        api_key=api_key,
        agent_name=agent_name,
    )


__all__ = ["AnthropicAAEPAdapter", "ToolHandler", "make_adapter", "HIGH_RISK_TOOLS"]
