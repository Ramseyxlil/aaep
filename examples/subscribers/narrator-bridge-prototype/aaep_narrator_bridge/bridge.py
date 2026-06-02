"""
bridge.py — Main subscriber loop and CLI for the Narrator bridge.

Connects to AAEP producers, routes events through NarratorEventHandler, and
exposes announcements via NarratorAnnouncer. CLI entry point installed as
`aaep-narrator-bridge` via pyproject.toml.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import signal
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import httpx
except ImportError as e:
    print(f"httpx is required: pip install httpx (got: {e})", file=sys.stderr)
    sys.exit(2)

from aaep_narrator_bridge.announcer import NarratorAnnouncer
from aaep_narrator_bridge.handler import (
    AnnouncementPriority,
    Configuration,
    NarratorEventHandler,
)


logger = logging.getLogger("aaep_narrator_bridge.bridge")


# === Reply transport ===

async def _send_reply(
    *,
    endpoint: str,
    reply_token: str,
    message_type: str,
    payload: dict[str, Any],
    client: httpx.AsyncClient,
) -> bool:
    url = endpoint.rstrip("/") + "/messages"
    body = {
        "type": message_type,
        "reply_token": reply_token,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **payload,
    }
    try:
        response = await client.post(url, json=body, timeout=10.0)
        return response.status_code < 400
    except httpx.HTTPError as e:
        logger.warning("Reply POST failed: %s", e)
        return False


# === SSE consumption ===

async def _run_bridge(
    *,
    endpoint: str,
    config: Configuration,
    prefer_mock: bool,
    cancel_event: asyncio.Event,
    auto_decision: str | None,
) -> int:
    """The main bridge coroutine."""
    announcer = NarratorAnnouncer(prefer_mock=prefer_mock)
    announcer.start()

    events_processed = 0
    pending_replies: list[tuple[str, str, dict[str, Any]]] = []

    def announce(text: str, priority: AnnouncementPriority) -> None:
        announcer.announce(text, priority)

    def queue_reply(token: str, mt: str, payload: dict[str, Any]) -> None:
        pending_replies.append((token, mt, payload))

    def confirm_dialog(action: str, consequence: str, timeout: int) -> str:
        """Confirmation dialog stub.

        In production this opens a Windows dialog. Here, we either auto-decide
        based on the CLI flag or default to reject.
        """
        if auto_decision in ("accept", "reject"):
            logger.info(
                "Auto-deciding confirmation '%s' as: %s",
                action, auto_decision,
            )
            return auto_decision
        logger.warning(
            "No interactive dialog in this build; defaulting to reject. "
            "Use --auto-accept or --auto-reject for unattended mode."
        )
        return "reject"

    handler = NarratorEventHandler(
        announce=announce,
        reply=queue_reply,
        confirm_dialog=confirm_dialog,
        config=config,
    )

    events_url = endpoint.rstrip("/") + "/events"

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(None, connect=10.0)) as client:
            async with client.stream(
                "GET",
                events_url,
                headers={"Accept": "text/event-stream"},
            ) as response:
                response.raise_for_status()
                logger.info("Connected to AAEP producer at %s", events_url)
                announcer.announce(
                    f"AAEP bridge connected to {endpoint}",
                    AnnouncementPriority.POLITE,
                )

                buffer = ""
                async for chunk in response.aiter_text():
                    if cancel_event.is_set():
                        break
                    buffer += chunk
                    while "\n\n" in buffer:
                        message, buffer = buffer.split("\n\n", 1)
                        event = _parse_sse_message(message)
                        if event is None:
                            continue
                        handler.handle(event)
                        events_processed += 1

                        # Drain any pending replies
                        while pending_replies:
                            token, mt, payload = pending_replies.pop(0)
                            await _send_reply(
                                endpoint=endpoint,
                                reply_token=token,
                                message_type=mt,
                                payload=payload,
                                client=client,
                            )

    except httpx.ConnectError as e:
        logger.error("Cannot connect to %s: %s", endpoint, e)
        return 1
    except httpx.HTTPStatusError as e:
        logger.error("HTTP error %d from %s", e.response.status_code, endpoint)
        return 1
    except asyncio.CancelledError:
        logger.info("Bridge cancelled")
    finally:
        logger.info("Processed %d events; shutting down", events_processed)
        announcer.stop()

    return 0


def _parse_sse_message(message: str) -> dict[str, Any] | None:
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


# === Config loading ===

def _load_config(config_path: Path | None) -> Configuration:
    """Load configuration from JSON file, falling back to defaults."""
    if config_path is None:
        return Configuration()
    if not config_path.is_file():
        logger.info("Config file %s not found; using defaults", config_path)
        return Configuration()
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
        return Configuration(
            preferred_languages=data.get("preferred_languages", ["en"]),
            announce_normal_events=data.get("announce_normal_events", True),
            announce_progress=data.get("announce_progress", False),
            play_critical_chime=data.get("play_critical_chime", True),
            log_file_path=data.get("log_file_path"),
            auto_reject_after_seconds=data.get("auto_reject_after_seconds", 0),
            auto_connect_on_start=data.get("auto_connect_on_start", True),
            endpoints=data.get("endpoints", ["http://localhost:8080"]),
        )
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("Could not load config from %s: %s", config_path, e)
        return Configuration()


# === CLI entry ===

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="aaep-narrator-bridge",
        description="Bridge AAEP events to Microsoft Narrator on Windows",
        epilog=(
            "Examples:\n"
            "  aaep-narrator-bridge --endpoint http://localhost:8080\n"
            "  aaep-narrator-bridge --endpoint http://localhost:8080 --mock\n"
            "  aaep-narrator-bridge --endpoint http://localhost:8080 --auto-reject\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--endpoint", "-e", required=True,
        help="AAEP producer base URL",
    )
    parser.add_argument(
        "--config", type=Path, default=None,
        help="Path to a config.json file",
    )
    parser.add_argument(
        "--mock", action="store_true",
        help="Force mock mode (log announcements only, no UIA)",
    )
    parser.add_argument(
        "--auto-accept", action="store_true",
        help="Auto-accept confirmations (DANGEROUS — for testing only)",
    )
    parser.add_argument(
        "--auto-reject", action="store_true",
        help="Auto-reject confirmations (for unattended use)",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Verbose logging",
    )
    parser.add_argument(
        "--version", action="version",
        version="aaep-narrator-bridge 0.1.0 (AAEP spec 1.0.0)",
    )

    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(name)s [%(levelname)s] %(message)s",
    )

    if args.auto_accept and args.auto_reject:
        print("Cannot combine --auto-accept and --auto-reject", file=sys.stderr)
        return 2

    auto_decision: str | None = None
    if args.auto_accept:
        auto_decision = "accept"
    elif args.auto_reject:
        auto_decision = "reject"

    config = _load_config(args.config)
    cancel_event = asyncio.Event()

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.add_signal_handler(signal.SIGINT, cancel_event.set)
            loop.add_signal_handler(signal.SIGTERM, cancel_event.set)
        except NotImplementedError:
            pass  # Windows
        exit_code = loop.run_until_complete(_run_bridge(
            endpoint=args.endpoint,
            config=config,
            prefer_mock=args.mock,
            cancel_event=cancel_event,
            auto_decision=auto_decision,
        ))
        return exit_code
    except KeyboardInterrupt:
        print("\n  Interrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
