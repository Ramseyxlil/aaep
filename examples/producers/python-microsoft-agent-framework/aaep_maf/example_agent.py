"""
Runnable demo of the Microsoft Agent Framework AAEP integration.

Drives a MAF-style middleware chain through three example scenarios:
  1. Basic query without tools
  2. Microsoft Graph calendar lookup (low-risk tool)
  3. Microsoft Graph send_email (high-risk irreversible tool, confirmation flow)

Run with:
    python -m aaep_maf.example_agent

The demo runs in mock mode by default. Set AZURE_OPENAI_API_KEY and install
the [maf] extra for real MAF + Azure OpenAI integration.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from typing import Any

from aaep_maf.middleware import (
    AgentContext,
    MAFAAEPMiddleware,
    ResponseChunkContext,
    ToolCallContext,
    make_middleware,
)


def _print_event(event: dict[str, Any]) -> None:
    """Format and print an AAEP event for human-readable terminal output."""
    event_type = event.get("type", "<unknown>").replace("aaep:", "")
    urgency = event.get("urgency", "normal")
    summary = event.get("summary_normal", "")
    seq = event.get("sequence_number", "?")

    marker = "!!" if urgency == "critical" else "  "
    print(f"{marker} [{seq:>2}] {event_type:30s}  {summary}")

    if event_type == "agent.tool.invoked":
        print(f"          tool={event.get('tool')!r}, "
              f"risk={event.get('risk_level')!r}, "
              f"irreversible={event.get('irreversible')}")
    elif event_type == "agent.tool.completed":
        print(f"          status={event.get('status')!r}")
    elif event_type == "agent.output.streaming":
        chunk = event.get("chunk", "")
        if chunk:
            display = repr(chunk) if len(chunk) <= 80 else repr(chunk[:77]) + "..."
            print(f"          chunk={display}")
    elif event_type == "agent.awaiting.confirmation":
        print(f"          action={event.get('action')!r}")
        print(f"          default_decision={event.get('default_decision')!r}")
    elif event_type == "agent.session.errored":
        print(f"          error_category={event.get('error_category')!r}")


# === Mock MAF agent harness ===

async def _drive_middleware(
    middleware: MAFAAEPMiddleware,
    user_message: str,
    *,
    user_id: str | None = None,
    tools: list[dict[str, Any]] | None = None,
    tool_calls: list[tuple[str, dict[str, Any], Any]] | None = None,
    response_chunks: list[str] | None = None,
    content_filter_triggered: str | None = None,
) -> None:
    """
    Drive the middleware chain manually, simulating what MAF would do.

    This stand-in lets us exercise the middleware in mock mode without
    needing the real MAF package installed.
    """
    context = AgentContext(
        user_message=user_message,
        user_id=user_id,
        tools=tools or [],
        metadata={},
    )

    async def _run_agent(ctx: AgentContext) -> str:
        """Inner agent body — runs the tools and chunks."""
        # Tool calls
        for tool_name, tool_args, tool_result in (tool_calls or []):
            tool_ctx = ToolCallContext(
                tool_name=tool_name,
                tool_arguments=tool_args,
            )
            # Attach the agent_context so the middleware can find it
            tool_ctx.agent_context = ctx  # type: ignore[attr-defined]

            async def _execute_tool(c: ToolCallContext) -> Any:
                await asyncio.sleep(0.05)
                if isinstance(tool_result, Exception):
                    raise tool_result
                return tool_result

            try:
                await middleware.on_tool_call(tool_ctx, _execute_tool)
            except PermissionError:
                pass  # User declined; continue with what we have

        # Response chunks
        for i, chunk_text in enumerate(response_chunks or []):
            chunk_ctx = ResponseChunkContext(
                chunk_text=chunk_text,
                is_final=(i == len(response_chunks or []) - 1),
            )
            chunk_ctx.agent_context = ctx  # type: ignore[attr-defined]

            async def _no_op(c: ResponseChunkContext) -> None:
                pass

            await middleware.on_response_chunk(chunk_ctx, _no_op)

        if content_filter_triggered:
            ctx.metadata["content_filter_triggered"] = content_filter_triggered

        return "Agent run complete"

    # Run the full chain
    async def _no_op_end(c: AgentContext) -> None:
        pass

    try:
        await middleware.on_agent_start(context, _run_agent)
        await middleware.on_agent_end(context, _no_op_end)
    except Exception as exc:
        print(f"  (Exception during demo: {type(exc).__name__}: {exc})")


# === Demo scenarios ===

async def run_demo() -> None:
    print("=" * 70)
    print("  AAEP Microsoft Agent Framework Integration Demo")
    print("=" * 70)
    print("  Mode: MOCK (real MAF integration requires [maf] extra)")
    print("=" * 70)

    middleware = make_middleware(
        send_event=_print_event,
        model="gpt-4o",
        agent_name="MAF Demo Agent",
    )

    # === Scenario 1: basic query ===
    print("\n" + "-" * 70)
    print("Scenario 1: Basic query, no tools")
    print("-" * 70 + "\n")

    await _drive_middleware(
        middleware,
        user_message="What is AAEP in one sentence?",
        response_chunks=[
            "AAEP is ",
            "an open protocol ",
            "that lets AI agents ",
            "talk to assistive technology. ",
            "It standardizes ",
            "what to announce ",
            "and when.",
        ],
    )

    # === Scenario 2: Microsoft Graph calendar lookup ===
    print("\n" + "-" * 70)
    print("Scenario 2: Microsoft Graph calendar lookup (low-risk)")
    print("-" * 70 + "\n")

    await _drive_middleware(
        middleware,
        user_message="What's on my calendar today?",
        tools=[{"name": "list_calendar_events"}],
        tool_calls=[
            ("list_calendar_events",
             {"date": "today"},
             "3 events: standup at 9am, design review at 2pm, gym at 6pm"),
        ],
        response_chunks=[
            "You have three meetings today. ",
            "Standup at 9am, design review at 2pm, ",
            "and gym at 6pm.",
        ],
    )

    # === Scenario 3: high-risk irreversible (send email) ===
    print("\n" + "-" * 70)
    print("Scenario 3: send_email (high-risk irreversible)")
    print("Note: Will emit a confirmation event; demo auto-accepts after 0.5s.")
    print("-" * 70 + "\n")

    # Auto-accept the pending confirmation for the demo
    async def _auto_accept():
        await asyncio.sleep(0.5)
        for token in list(middleware.emitter._reply_decisions.keys()):
            middleware.emitter.submit_reply(token, "accept")

    asyncio.create_task(_auto_accept())

    await _drive_middleware(
        middleware,
        user_message="Send a confirmation email to alice@contoso.com.",
        tools=[{"name": "send_email"}],
        tool_calls=[
            ("send_email",
             {"to": "alice@contoso.com", "subject": "Confirmation"},
             "Email sent successfully"),
        ],
        response_chunks=[
            "Done. ",
            "I sent the confirmation email ",
            "to alice@contoso.com.",
        ],
    )

    # === Scenario 4: Azure content filter triggered ===
    print("\n" + "-" * 70)
    print("Scenario 4: Azure content filter blocks response")
    print("Note: emits session.errored with error_category='policy'.")
    print("-" * 70 + "\n")

    await _drive_middleware(
        middleware,
        user_message="<request that would trigger content filter>",
        content_filter_triggered="hate_speech",
    )

    print("\n" + "=" * 70)
    print("Demo complete.")
    print()
    print("To use with real MAF, install with:")
    print("    pip install aaep-maf-producer[maf]")
    print()
    print("Then attach the middleware to your MAF agent:")
    print("    agent.add_middleware(middleware)")
    print("=" * 70)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="aaep-maf-demo",
        description="Demo of the AAEP Microsoft Agent Framework integration",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Emit events as raw JSON instead of formatted output",
    )
    args = parser.parse_args(argv)

    if args.json:
        global _print_event

        def _print_json(event: dict) -> None:
            print(json.dumps(event, ensure_ascii=False))

        _print_event = _print_json  # type: ignore[assignment]

    try:
        asyncio.run(run_demo())
    except KeyboardInterrupt:
        print("\nInterrupted.")
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
