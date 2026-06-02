"""
Runnable demo of the Anthropic SDK AAEP integration.

Drives the AnthropicAAEPAdapter through three example scenarios:
  1. Basic query without tools
  2. Tool use with low-risk tool (fetch_balance)
  3. Tool use with high-risk irreversible tool (send_email)

Run with:
    python -m aaep_anthropic_sdk.example_agent

The demo uses real Claude calls if ANTHROPIC_API_KEY is set; otherwise it
falls back to mock mode (same code paths, no API calls).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from typing import Any

from aaep_anthropic_sdk.adapter import AnthropicAAEPAdapter, make_adapter


def _print_event(event: dict[str, Any]) -> None:
    """Pretty-print an AAEP event for terminal output."""
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
        print(f"          args={event.get('args_summary')!r}")
    elif event_type == "agent.tool.completed":
        print(f"          status={event.get('status')!r}")
    elif event_type == "agent.output.streaming":
        chunk = event.get("chunk", "")
        if chunk:
            display = repr(chunk) if len(chunk) <= 80 else repr(chunk[:77]) + "..."
            print(f"          chunk={display}, position={event.get('position')}, "
                  f"complete={event.get('complete')}")
    elif event_type == "agent.awaiting.confirmation":
        print(f"          action={event.get('action')!r}")
        print(f"          default_decision={event.get('default_decision')!r}")


# === Tool definitions and handlers ===

def fetch_balance(account: str = "checking") -> str:
    """Mock implementation of an account balance lookup."""
    balances = {
        "checking": "$3,247.18",
        "savings": "$12,891.40",
        "credit": "-$847.22 (balance owed)",
    }
    return f"Balance for {account}: {balances.get(account, '$0.00')}"


def send_email(to: str, subject: str, body: str = "") -> str:
    """Mock implementation of an email send (high-risk irreversible)."""
    return f"Email sent to {to} with subject {subject!r}"


def search_records(query: str = "") -> str:
    """Mock implementation of a records search."""
    return f"Found 3 records matching {query!r}"


TOOLS = [
    {
        "name": "fetch_balance",
        "description": "Look up an account balance by account name.",
        "input_schema": {
            "type": "object",
            "properties": {
                "account": {
                    "type": "string",
                    "description": "The account name (checking, savings, credit)",
                },
            },
            "required": ["account"],
        },
    },
    {
        "name": "send_email",
        "description": "Send an email message (HIGH-RISK, irreversible).",
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {"type": "string"},
                "subject": {"type": "string"},
                "body": {"type": "string"},
            },
            "required": ["to", "subject"],
        },
    },
    {
        "name": "search_records",
        "description": "Search internal records by query.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
            },
            "required": ["query"],
        },
    },
]

TOOL_HANDLERS = {
    "fetch_balance": fetch_balance,
    "send_email": send_email,
    "search_records": search_records,
}


# === Demo scenarios ===

async def run_demo() -> None:
    """Drive three scenarios through the adapter."""
    print("=" * 70)
    print("  AAEP Anthropic SDK Integration Demo")
    print("=" * 70)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        print(f"  Mode: REAL (using ANTHROPIC_API_KEY)")
    else:
        print(f"  Mode: MOCK (no ANTHROPIC_API_KEY set)")
    print("=" * 70)

    adapter = make_adapter(send_event=_print_event, model="claude-opus-4-7")

    # === Scenario 1: basic query without tools ===
    print("\n" + "-" * 70)
    print("Scenario 1: Basic query, no tools")
    print("-" * 70 + "\n")

    await adapter.run_session(
        user_message="Briefly explain what AAEP is in two sentences.",
    )

    # === Scenario 2: low-risk tool ===
    print("\n" + "-" * 70)
    print("Scenario 2: Low-risk tool (fetch_balance)")
    print("-" * 70 + "\n")

    await adapter.run_session(
        user_message="What's my checking account balance?",
        tools=TOOLS,
        tool_handlers=TOOL_HANDLERS,
    )

    # === Scenario 3: high-risk irreversible tool ===
    print("\n" + "-" * 70)
    print("Scenario 3: High-risk irreversible tool (send_email)")
    print("Note: a real Anthropic call would emit a confirmation event;")
    print("the subscriber must accept before the tool executes.")
    print("-" * 70 + "\n")

    # For the demo, pre-resolve the confirmation reply so the session completes
    original_emit = adapter.emitter._emit

    async def _auto_reply_to_confirmation():
        """Simulate a subscriber that auto-accepts after a brief delay."""
        await asyncio.sleep(0.5)
        # Find any pending confirmation and resolve it
        for reply_token in list(adapter.emitter._reply_decisions.keys()):
            adapter.emitter.submit_reply(reply_token, "accept")

    asyncio.create_task(_auto_reply_to_confirmation())

    try:
        await adapter.run_session(
            user_message="Please send a confirmation email to alice@example.com.",
            tools=TOOLS,
            tool_handlers=TOOL_HANDLERS,
        )
    except Exception as exc:
        print(f"\n  (Session ended with exception: {type(exc).__name__})")

    print("\n" + "=" * 70)
    print("Demo complete.")
    print()
    print("Three scenarios exercised. In a real deployment, the events would")
    print("stream to your AT/subscriber transport (HTTP/SSE, WebSocket, etc.)")
    print("rather than printing to stdout.")
    print("=" * 70)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="aaep-anthropic-demo",
        description="Demo of the AAEP Anthropic SDK integration",
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
    except Exception as exc:
        print(f"\nDemo failed: {type(exc).__name__}: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
