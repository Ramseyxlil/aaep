"""
Runnable demo of the LangChain AAEP integration.

This module shows how to attach LangChainAAEPHandler to a real LangChain
chain and exercise it with example queries. The demo prints every emitted
AAEP event so you can see the full event stream.

Run with:
    python -m aaep_langchain.example_agent

For production use, you would route the events to your AT/subscriber
transport rather than printing them.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any
from uuid import uuid4

from aaep_langchain.callback_handler import LangChainAAEPHandler


def _print_event(event: dict[str, Any]) -> None:
    """Format and print an AAEP event for human-readable terminal output."""
    event_type = event.get("type", "<unknown>").replace("aaep:", "")
    urgency = event.get("urgency", "normal")
    summary = event.get("summary_normal", "")
    seq = event.get("sequence_number", "?")

    urgency_marker = "!!" if urgency == "critical" else "  "
    print(f"{urgency_marker} [{seq:>2}] {event_type:30s}  {summary}")

    # Add a few key fields for specific event types
    if event_type == "agent.tool.invoked":
        print(f"          tool={event.get('tool')!r}, args={event.get('args_summary')!r}")
    elif event_type == "agent.tool.completed":
        print(f"          status={event.get('status')!r}")
    elif event_type == "agent.output.streaming":
        chunk = event.get("chunk", "")
        if chunk:
            chunk_display = repr(chunk) if len(chunk) <= 80 else repr(chunk[:77]) + "..."
            print(f"          chunk={chunk_display}, position={event.get('position')}, complete={event.get('complete')}")
    elif event_type == "agent.awaiting.confirmation":
        print(f"          action={event.get('action')!r}")
        print(f"          default_decision={event.get('default_decision')!r}")


def run_demo() -> None:
    """
    Run the demo. We construct a minimal stand-in for a LangChain agent
    that exercises the callback handler's full surface, then drive it
    with example queries.

    A real adopter would replace this stand-in with their actual
    LangChain agent (AgentExecutor, RunnableSequence, etc.).
    """
    print("=" * 70)
    print("  AAEP LangChain Integration Demo")
    print("=" * 70)
    print()
    print("This demo simulates the LangChain callbacks that a real agent")
    print("would emit. The handler translates each callback into AAEP events.")
    print()

    # Create the handler
    handler = LangChainAAEPHandler(
        send_event=_print_event,
        agent_id="demo-agent",
        agent_name="LangChain Demo Agent",
        model="gpt-4-mock",
    )

    # === Scenario 1: simple query with one tool call ===
    print("\n" + "-" * 70)
    print("Scenario 1: Simple query with low-risk tool")
    print("-" * 70 + "\n")

    chain_run_id = uuid4()
    handler.on_chain_start(
        serialized={"name": "OpenAITools Agent"},
        inputs={"input": "What is my checking account balance?"},
        run_id=chain_run_id,
        parent_run_id=None,
    )

    tool_run_id = uuid4()
    handler.on_tool_start(
        serialized={"name": "fetch_balance"},
        input_str='{"account": "checking"}',
        run_id=tool_run_id,
        parent_run_id=chain_run_id,
        inputs={"account": "checking"},
    )
    time.sleep(0.05)
    handler.on_tool_end(
        output="$3,247.18",
        run_id=tool_run_id,
        parent_run_id=chain_run_id,
    )

    llm_run_id = uuid4()
    handler.on_llm_start(
        serialized={"name": "ChatOpenAI"},
        prompts=["..."],
        run_id=llm_run_id,
        parent_run_id=chain_run_id,
    )
    for token in (
        "Your ", "checking ", "account ", "balance ", "is ", "$3,247.18. ",
        "Is ", "there ", "anything ", "else ", "I ", "can ", "help ", "with?"
    ):
        handler.on_llm_new_token(token, run_id=llm_run_id)
        time.sleep(0.02)
    handler.on_llm_end(response=None, run_id=llm_run_id)

    handler.on_chain_end(
        outputs={"output": "Your checking account balance is $3,247.18."},
        run_id=chain_run_id,
        parent_run_id=None,
    )

    # === Scenario 2: high-risk tool that needs confirmation ===
    print("\n" + "-" * 70)
    print("Scenario 2: High-risk irreversible tool (send_email)")
    print("-" * 70)
    print("Note: In a real LangChain integration, you would interrupt the")
    print("agent loop for the confirmation event. See README §3.")
    print("-" * 70 + "\n")

    chain_run_id = uuid4()
    handler.on_chain_start(
        serialized={"name": "OpenAITools Agent"},
        inputs={"input": "Send a confirmation email to billing@example.com"},
        run_id=chain_run_id,
        parent_run_id=None,
    )

    tool_run_id = uuid4()
    handler.on_tool_start(
        serialized={"name": "send_email"},
        input_str='{"to": "billing@example.com", "subject": "Confirmation"}',
        run_id=tool_run_id,
        parent_run_id=chain_run_id,
        inputs={
            "to": "billing@example.com",
            "subject": "Confirmation",
            "body": "Confirming our agreement.",
        },
    )
    # In a real integration, the agent loop would now wait for confirmation
    # before continuing to on_tool_end.
    time.sleep(0.05)
    handler.on_tool_end(
        output="Email sent successfully",
        run_id=tool_run_id,
        parent_run_id=chain_run_id,
    )

    handler.on_chain_end(
        outputs={"output": "Email sent."},
        run_id=chain_run_id,
        parent_run_id=None,
    )

    # === Scenario 3: error handling ===
    print("\n" + "-" * 70)
    print("Scenario 3: Tool failure (network error)")
    print("-" * 70 + "\n")

    chain_run_id = uuid4()
    handler.on_chain_start(
        serialized={"name": "OpenAITools Agent"},
        inputs={"input": "Fetch the latest market data"},
        run_id=chain_run_id,
        parent_run_id=None,
    )

    tool_run_id = uuid4()
    handler.on_tool_start(
        serialized={"name": "fetch_market_data"},
        input_str="{}",
        run_id=tool_run_id,
        parent_run_id=chain_run_id,
        inputs={},
    )
    handler.on_tool_error(
        error=ConnectionError("Could not reach market data API"),
        run_id=tool_run_id,
        parent_run_id=chain_run_id,
    )

    handler.on_chain_error(
        error=ConnectionError("Could not reach market data API"),
        run_id=chain_run_id,
        parent_run_id=None,
    )

    print("\n" + "=" * 70)
    print("Demo complete. Three sessions emitted with full AAEP event streams.")
    print()
    print("To use with a real LangChain agent, replace the manual callback")
    print("invocations above with your AgentExecutor.invoke(...) call:")
    print()
    print("    agent_executor.invoke(")
    print('        {"input": "..."},')
    print("        config={\"callbacks\": [handler]},")
    print("    )")
    print("=" * 70)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="aaep-langchain-demo",
        description="Demo of the LangChain AAEP integration",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Emit events as raw JSON instead of formatted output",
    )
    args = parser.parse_args(argv)

    if args.json:
        # Replace the printer with raw JSON output
        global _print_event

        def _print_json(event: dict) -> None:
            print(json.dumps(event, ensure_ascii=False))

        _print_event = _print_json

    try:
        run_demo()
    except KeyboardInterrupt:
        print("\nInterrupted.")
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
