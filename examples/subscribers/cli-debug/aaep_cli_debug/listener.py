"""
listener.py — the SSE consumer, event formatter, and reply sender for the
CLI debug subscriber.

Layered design so this file doubles as a starting point for real subscribers:

  1. SSE consumption (listen)                — replace nothing; this layer
                                                stays the same in any subscriber
  2. Event rendering (format_event)          — replace this with your AT's
                                                speech engine
  3. User reply (prompt_for_reply)           — replace this with your AT's
                                                user-input mechanism
  4. Reply transport (send_reply)            — stays the same; AAEP replies
                                                always go via POST /messages

The CLI in aaep_cli_debug.main wires these together.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime
from typing import Any, Awaitable, Callable, TextIO

try:
    import httpx
except ImportError as e:
    print(f"httpx is required: pip install httpx (got: {e})", file=sys.stderr)
    sys.exit(2)


# === Terminal color support ===

# ANSI escape codes; disabled if NO_COLOR is set or output isn't a TTY.
_USE_COLOR = sys.stdout.isatty() and "NO_COLOR" not in os.environ

_RED = "\033[31m" if _USE_COLOR else ""
_YELLOW = "\033[33m" if _USE_COLOR else ""
_CYAN = "\033[36m" if _USE_COLOR else ""
_GRAY = "\033[90m" if _USE_COLOR else ""
_BOLD = "\033[1m" if _USE_COLOR else ""
_RESET = "\033[0m" if _USE_COLOR else ""


def disable_color() -> None:
    """Disable terminal colors globally for this process."""
    global _USE_COLOR, _RED, _YELLOW, _CYAN, _GRAY, _BOLD, _RESET
    _USE_COLOR = False
    _RED = _YELLOW = _CYAN = _GRAY = _BOLD = _RESET = ""


# === Event formatter ===

# Fields that we surface inline below an event's headline, in display order.
_DETAIL_FIELDS = {
    "aaep:agent.session.started": ["request_text", "requested_by", "tools_available"],
    "aaep:agent.session.completed": ["duration_ms", "tool_invocations_count"],
    "aaep:agent.session.errored": ["error_category", "error_message", "recoverable", "remediation_hint"],
    "aaep:agent.session.cancelled": ["cancelled_by", "cancellation_reason"],
    "aaep:agent.state.changed": ["from_state", "to_state"],
    "aaep:agent.progress.updated": ["progress_percent", "progress_message", "estimated_remaining_ms"],
    "aaep:agent.tool.invoked": ["tool", "risk_level", "irreversible", "args_summary"],
    "aaep:agent.tool.completed": ["tool", "status", "error_message"],
    "aaep:agent.output.streaming": ["position", "complete", "coalesce_hint"],
    "aaep:agent.awaiting.confirmation": [
        "action", "consequence", "risk_level", "irreversible",
        "default_decision", "timeout_seconds",
    ],
    "aaep:agent.awaiting.clarification": [
        "question", "options", "multi_select", "free_form_allowed",
    ],
    "aaep:agent.handoff.requested": ["reason", "handoff_target", "context_summary"],
}


def format_event(event: dict[str, Any], *, compact: bool = False) -> str:
    """
    Render an AAEP event for terminal display.

    Returns a multi-line string. The first line is the event headline
    (timestamp, type, summary). Subsequent indented lines show event-specific
    detail fields. In compact mode, returns a single JSON line.

    Replace this function with your AT's speech-engine integration to build
    a real subscriber.
    """
    if compact:
        return json.dumps(event, ensure_ascii=False)

    event_type = event.get("type", "<unknown>")
    summary = event.get("summary_normal", "")
    urgency = event.get("urgency", "normal")
    timestamp = event.get("timestamp", "")

    # Format timestamp as HH:MM:SS.mmm for readability
    try:
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        time_str = dt.strftime("%H:%M:%S") + f".{dt.microsecond // 1000:03d}"
    except (ValueError, AttributeError):
        time_str = timestamp[:12] if timestamp else "????????????"

    if urgency == "critical":
        marker = f"{_RED}!!{_RESET}"
        type_color = _RED + _BOLD
    else:
        marker = "  "
        type_color = _CYAN

    headline = (
        f"{marker} {_GRAY}[{time_str}]{_RESET} "
        f"{type_color}{event_type:38s}{_RESET}  {summary}"
    )

    lines = [headline]

    # Add detail fields specific to this event type
    detail_keys = _DETAIL_FIELDS.get(event_type, [])
    for key in detail_keys:
        if key not in event:
            continue
        value = event[key]
        if value is None:
            continue
        if isinstance(value, list):
            value_str = ", ".join(str(v) for v in value)
        else:
            value_str = str(value)
        if len(value_str) > 120:
            value_str = value_str[:117] + "..."
        lines.append(f"                  {_GRAY}{key}:{_RESET} {value_str}")

    return "\n".join(lines)


# === Reply prompting (terminal user input) ===

def prompt_for_confirmation(event: dict[str, Any]) -> str:
    """
    Display a confirmation event and prompt the user for accept/reject.

    Replace this with your AT's user-input mechanism (voice command,
    switch input, etc.) in a real subscriber.
    """
    print(file=sys.stderr)
    print(f"{_BOLD}Accept this action?{_RESET} [y/N/?]: ", end="", file=sys.stderr, flush=True)
    while True:
        try:
            reply = input().strip().lower()
        except (EOFError, KeyboardInterrupt):
            print(file=sys.stderr)
            return "reject"
        if reply in ("y", "yes"):
            return "accept"
        if reply in ("n", "no", ""):
            return "reject"
        if reply == "?":
            print(json.dumps(event, indent=2, ensure_ascii=False), file=sys.stderr)
            print(f"{_BOLD}Accept this action?{_RESET} [y/N/?]: ",
                  end="", file=sys.stderr, flush=True)
            continue
        print(f"  Please answer y, n, or ? (default: n): ",
              end="", file=sys.stderr, flush=True)


def prompt_for_clarification(event: dict[str, Any]) -> Any:
    """
    Display a clarification event and prompt the user for a response.

    Replace this with your AT's user-input mechanism in a real subscriber.
    """
    print(file=sys.stderr)
    options = event.get("options") or []
    multi = event.get("multi_select", False)
    free_form = event.get("free_form_allowed", True)

    if options:
        for i, option in enumerate(options, start=1):
            print(f"  {i}. {option}", file=sys.stderr)
        if multi:
            print(f"{_BOLD}Select option(s) by number (comma-separated):{_RESET} ",
                  end="", file=sys.stderr, flush=True)
        else:
            print(f"{_BOLD}Select option (1-{len(options)}):{_RESET} ",
                  end="", file=sys.stderr, flush=True)

        try:
            reply = input().strip()
        except (EOFError, KeyboardInterrupt):
            print(file=sys.stderr)
            return None

        if multi:
            try:
                nums = [int(n.strip()) for n in reply.split(",") if n.strip()]
                return [options[n - 1] for n in nums if 1 <= n <= len(options)]
            except (ValueError, IndexError):
                return reply if free_form else None
        try:
            n = int(reply)
            if 1 <= n <= len(options):
                return options[n - 1]
        except ValueError:
            pass
        return reply if free_form else None
    else:
        print(f"{_BOLD}Your response:{_RESET} ", end="", file=sys.stderr, flush=True)
        try:
            return input().strip()
        except (EOFError, KeyboardInterrupt):
            print(file=sys.stderr)
            return None


# === Reply transport ===

async def send_reply(
    *,
    endpoint: str,
    reply_token: str,
    message_type: str,
    payload: dict[str, Any],
    client: httpx.AsyncClient,
) -> bool:
    """POST a reply message to the producer's /messages endpoint."""
    url = endpoint.rstrip("/") + "/messages"
    body: dict[str, Any] = {
        "type": message_type,
        "reply_token": reply_token,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        **payload,
    }
    try:
        response = await client.post(url, json=body, timeout=10.0)
        return response.status_code < 400
    except httpx.HTTPError as e:
        print(f"  {_YELLOW}(reply failed: {e}){_RESET}", file=sys.stderr)
        return False


# === SSE consumer ===

async def listen(
    endpoint: str,
    *,
    on_event: Callable[[dict[str, Any]], Awaitable[None] | None] | None = None,
    save_stream: TextIO | None = None,
    validate_events: bool = False,
    cancel_event: asyncio.Event | None = None,
) -> tuple[int, str]:
    """
    Connect to an AAEP producer's /events SSE endpoint and stream events.

    For each event:
        1. Optionally save to the JSONL file
        2. Optionally validate against AAEP schemas
        3. Call the on_event callback

    Returns (events_consumed, stop_reason).
    """
    events_url = endpoint.rstrip("/") + "/events"
    events_consumed = 0
    stop_reason = "completed"
    validator = _make_validator() if validate_events else None

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(None, connect=10.0)) as client:
            async with client.stream(
                "GET",
                events_url,
                headers={"Accept": "text/event-stream"},
            ) as response:
                response.raise_for_status()

                buffer = ""
                async for chunk in response.aiter_text():
                    if cancel_event is not None and cancel_event.is_set():
                        stop_reason = "interrupted"
                        break
                    buffer += chunk
                    while "\n\n" in buffer:
                        message, buffer = buffer.split("\n\n", 1)
                        event = _parse_sse_message(message)
                        if event is None:
                            continue

                        if save_stream is not None:
                            save_stream.write(json.dumps(event, ensure_ascii=False) + "\n")
                            save_stream.flush()

                        if validator is not None:
                            error = validator(event)
                            if error is not None:
                                print(
                                    f"  {_YELLOW}(validation error: {error}){_RESET}",
                                    file=sys.stderr,
                                )

                        events_consumed += 1

                        if on_event is not None:
                            result = on_event(event)
                            if asyncio.iscoroutine(result):
                                await result

    except httpx.ConnectError as e:
        return events_consumed, f"connection_error: {e}"
    except httpx.HTTPStatusError as e:
        return events_consumed, f"http_{e.response.status_code}"
    except asyncio.CancelledError:
        stop_reason = "interrupted"
        raise

    return events_consumed, stop_reason


def _parse_sse_message(message: str) -> dict[str, Any] | None:
    """Extract the data field from an SSE message and parse as JSON."""
    data_parts: list[str] = []
    for line in message.split("\n"):
        if line.startswith("data:"):
            data_parts.append(line[5:].lstrip())
        elif line.startswith(":"):
            continue
    if not data_parts:
        return None
    try:
        result = json.loads("\n".join(data_parts))
        return result if isinstance(result, dict) else None
    except json.JSONDecodeError:
        return None


def _make_validator() -> Callable[[dict[str, Any]], str | None] | None:
    """Lazily import jsonschema; returns None if it's not installed."""
    try:
        from aaep_tools.validate import validate_event as aaep_validate
    except ImportError:
        return None

    def validate(event: dict[str, Any]) -> str | None:
        result = aaep_validate(event)
        if result.valid:
            return None
        return f"{result.event_type or '<no type>'}: {'; '.join(result.errors[:2])}"

    return validate


# === Filter predicate ===

def make_filter(
    *,
    filter_types: set[str] | None = None,
    filter_urgency: str | None = None,
    filter_session: str | None = None,
) -> Callable[[dict[str, Any]], bool]:
    """Build a predicate that returns True if an event matches the filters."""

    def predicate(event: dict[str, Any]) -> bool:
        if filter_types is not None:
            t = event.get("type", "")
            if not any(f == t or t.endswith(f) for f in filter_types):
                return False
        if filter_urgency is not None and event.get("urgency") != filter_urgency:
            return False
        if filter_session is not None and event.get("session_id") != filter_session:
            return False
        return True

    return predicate
