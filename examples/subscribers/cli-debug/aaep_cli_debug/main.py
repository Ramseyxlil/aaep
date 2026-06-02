"""
main.py — CLI entry point for aaep-listen.

Wires together listener.py's components into a complete subscriber that
matches the contract documented in the README:

    aaep-listen --endpoint URL [OPTIONS]

This is what gets installed as the `aaep-listen` console script via
the [project.scripts] entry in pyproject.toml.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import signal
import sys
from pathlib import Path
from typing import Any

try:
    import httpx
except ImportError as e:
    print(f"httpx is required: pip install httpx (got: {e})", file=sys.stderr)
    sys.exit(2)

from aaep_cli_debug import listener


# === Reply handling for awaiting.* events ===

async def _handle_event(
    event: dict[str, Any],
    *,
    args: argparse.Namespace,
    filter_predicate,
    http_client: httpx.AsyncClient,
    compact: bool,
) -> None:
    """Process a single event: maybe display it, maybe respond to it."""
    if not filter_predicate(event):
        return

    # Display the event
    print(listener.format_event(event, compact=compact), flush=True)

    event_type = event.get("type", "")

    # Handle awaiting.confirmation
    if event_type == "aaep:agent.awaiting.confirmation":
        reply_token = event.get("reply_token")
        if not reply_token:
            return

        if args.auto_accept:
            decision = "accept"
            print(f"  (auto-accepted)", file=sys.stderr)
        elif args.auto_reject:
            decision = "reject"
            print(f"  (auto-rejected)", file=sys.stderr)
        else:
            decision = listener.prompt_for_confirmation(event)

        sent = await listener.send_reply(
            endpoint=args.endpoint,
            reply_token=reply_token,
            message_type="confirmation.reply",
            payload={"decision": decision},
            client=http_client,
        )
        if not sent:
            print(f"  (warning: reply not delivered)", file=sys.stderr)

    # Handle awaiting.clarification
    elif event_type == "aaep:agent.awaiting.clarification":
        reply_token = event.get("reply_token")
        if not reply_token:
            return

        if args.auto_reject or args.auto_accept:
            # Auto modes can't sensibly answer clarifications;
            # send empty response to unblock the agent
            response: Any = ""
        else:
            response = listener.prompt_for_clarification(event)
            if response is None:
                response = ""

        await listener.send_reply(
            endpoint=args.endpoint,
            reply_token=reply_token,
            message_type="clarification.reply",
            payload={"response": response},
            client=http_client,
        )


# === Main loop ===

async def _run(args: argparse.Namespace) -> int:
    """Top-level coroutine; sets up signal handler, listener, and runs to completion."""
    cancel_event = asyncio.Event()

    # Install signal handler for clean shutdown
    loop = asyncio.get_running_loop()
    try:
        loop.add_signal_handler(signal.SIGINT, cancel_event.set)
        loop.add_signal_handler(signal.SIGTERM, cancel_event.set)
    except NotImplementedError:
        # Windows
        pass

    # Open save-stream if requested
    save_handle = None
    if args.save:
        save_path = Path(args.save)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        save_handle = open(save_path, "w", encoding="utf-8")
        print(f"  Saving stream to: {save_path}", file=sys.stderr)

    # Build the filter predicate
    filter_types = set(args.filter_type) if args.filter_type else None
    filter_predicate = listener.make_filter(
        filter_types=filter_types,
        filter_urgency=args.filter_urgency,
        filter_session=args.filter_session,
    )

    if args.no_color:
        listener.disable_color()

    print(f"  Connecting to: {args.endpoint}", file=sys.stderr)
    if args.validate:
        print(f"  Schema validation: enabled", file=sys.stderr)
    print(file=sys.stderr)

    # Wire it all up
    try:
        async with httpx.AsyncClient() as client:

            async def on_event(event: dict[str, Any]) -> None:
                await _handle_event(
                    event,
                    args=args,
                    filter_predicate=filter_predicate,
                    http_client=client,
                    compact=args.quiet,
                )

            count, stop_reason = await listener.listen(
                endpoint=args.endpoint,
                on_event=on_event,
                save_stream=save_handle,
                validate_events=args.validate,
                cancel_event=cancel_event,
            )

        print(file=sys.stderr)
        print(f"  Received {count} event(s). Stop reason: {stop_reason}", file=sys.stderr)

        if stop_reason.startswith("connection_error") or stop_reason.startswith("http_"):
            return 1
        return 0

    finally:
        if save_handle is not None:
            save_handle.close()


# === CLI parsing ===

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="aaep-listen",
        description="Subscribe to an AAEP producer's event stream and display it in the terminal",
        epilog=(
            "Examples:\n"
            "  aaep-listen --endpoint http://localhost:8080\n"
            "  aaep-listen --endpoint http://localhost:8080 --save session.jsonl\n"
            "  aaep-listen --endpoint http://localhost:8080 --validate --filter-urgency critical\n"
            "  aaep-listen --endpoint http://localhost:8080 --quiet | jq '.type'\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--endpoint", "-e", required=True,
        help="Producer base URL (e.g., http://localhost:8080)",
    )
    parser.add_argument(
        "--save", "-s", default=None,
        help="Also save events to this JSONL file",
    )
    parser.add_argument(
        "--validate", action="store_true",
        help="Validate each event against AAEP schemas (requires aaep-tools)",
    )
    parser.add_argument(
        "--filter-urgency", choices=["normal", "critical"], default=None,
        help="Only display events with this urgency",
    )
    parser.add_argument(
        "--filter-type", action="append", default=[],
        help="Only display events of this type (repeatable)",
    )
    parser.add_argument(
        "--filter-session", default=None,
        help="Only display events for this session_id",
    )
    parser.add_argument(
        "--auto-reject", action="store_true",
        help="Auto-reject all confirmations (for unattended use)",
    )
    parser.add_argument(
        "--auto-accept", action="store_true",
        help="Auto-accept all confirmations (DANGEROUS — for debug only)",
    )
    parser.add_argument(
        "--no-color", action="store_true",
        help="Disable terminal colors",
    )
    parser.add_argument(
        "--quiet", "-q", action="store_true",
        help="Print events as compact one-line JSON only",
    )
    parser.add_argument(
        "--version", action="version",
        version="aaep-listen 1.0.0 (AAEP spec 1.0.0)",
    )

    args = parser.parse_args(argv)

    if args.auto_accept and args.auto_reject:
        print("aaep-listen: --auto-accept and --auto-reject are mutually exclusive",
              file=sys.stderr)
        return 2

    try:
        return asyncio.run(_run(args))
    except KeyboardInterrupt:
        print("\n  Interrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
