"""
sse_client.py — SSE consumer for the NVDA AAEP subscriber.

Connects to an AAEP producer's /events SSE endpoint and feeds each parsed
event to a handler callback. Runs in a background thread so it doesn't block
NVDA's main thread.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any, Callable
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

logger = logging.getLogger("aaep_nvda_subscriber.sse_client")


class AAEPSSEClient:
    """
    SSE consumer running in a background thread.

    Uses urllib (no extra dependencies, since NVDA's bundled Python may not
    have httpx). Reconnects with exponential backoff on connection failure.
    """

    def __init__(
        self,
        *,
        endpoint: str,
        on_event: Callable[[dict[str, Any]], None],
        on_status: Callable[[str], None] | None = None,
    ):
        self.endpoint = endpoint.rstrip("/")
        self._on_event = on_event
        self._on_status = on_status or (lambda _: None)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._connect_attempts = 0

    def start(self) -> None:
        """Start the background SSE consumer thread."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="aaep-nvda-sse-client",
            daemon=True,
        )
        self._thread.start()
        logger.info("SSE client started for %s", self.endpoint)

    def stop(self, *, timeout: float = 5.0) -> None:
        """Signal the thread to stop and wait briefly for it to finish."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
        logger.info("SSE client stopped")

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # === Internal loop ===

    def _run(self) -> None:
        """Background thread main loop: connect, consume, reconnect."""
        while not self._stop_event.is_set():
            try:
                self._consume_once()
            except (URLError, HTTPError) as e:
                logger.warning("SSE connection error: %s", e)
                self._on_status(f"disconnected: {e}")
            except Exception:
                logger.exception("Unexpected SSE error")
                self._on_status("error")

            if self._stop_event.is_set():
                break

            # Exponential backoff: 1, 2, 4, 8, 16, 32, then cap at 60
            self._connect_attempts += 1
            backoff = min(60, 2 ** min(6, self._connect_attempts - 1))
            logger.info("Reconnecting in %d seconds", backoff)
            self._on_status(f"reconnecting in {backoff}s")
            self._stop_event.wait(timeout=backoff)

    def _consume_once(self) -> None:
        """Open one SSE connection and read until disconnected or stop signaled."""
        url = f"{self.endpoint}/events"
        request = Request(url, headers={"Accept": "text/event-stream"})

        with urlopen(request, timeout=30) as response:
            self._connect_attempts = 0
            self._on_status("connected")
            logger.info("Connected to %s", url)

            buffer = ""
            while not self._stop_event.is_set():
                chunk = response.readline()
                if not chunk:
                    logger.info("SSE stream ended")
                    return
                buffer += chunk.decode("utf-8", errors="replace")
                while "\n\n" in buffer:
                    message, buffer = buffer.split("\n\n", 1)
                    event = _parse_sse_message(message)
                    if event is not None:
                        try:
                            self._on_event(event)
                        except Exception:
                            logger.exception("Error in event handler")


def _parse_sse_message(message: str) -> dict[str, Any] | None:
    """Extract the data field from an SSE message and parse as JSON."""
    data_parts: list[str] = []
    for line in message.split("\n"):
        if line.startswith("data:"):
            data_parts.append(line[5:].lstrip())
        elif line.startswith(":"):
            continue  # Comment / heartbeat
    if not data_parts:
        return None
    try:
        result = json.loads("\n".join(data_parts))
        return result if isinstance(result, dict) else None
    except json.JSONDecodeError:
        return None


def send_reply(
    *,
    endpoint: str,
    reply_token: str,
    message_type: str,
    payload: dict[str, Any],
) -> bool:
    """
    POST a reply message to /messages. Synchronous (called from NVDA's
    main thread typically; the call is short-lived).

    Returns True on success, False on failure.
    """
    import urllib.request
    from datetime import datetime, timezone

    url = endpoint.rstrip("/") + "/messages"
    body = {
        "type": message_type,
        "reply_token": reply_token,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **payload,
    }
    data = json.dumps(body).encode("utf-8")

    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status < 400
    except (URLError, HTTPError) as e:
        logger.warning("Reply POST failed: %s", e)
        return False
