# AAEP Quickstart

**Ten minutes from zero to your first working AAEP integration.**

This guide walks you through emitting AAEP events from a tiny Python script and watching them arrive at a subscriber. By the end, you will understand what an AAEP event looks like on the wire, how a session is structured, and how confirmations work. You will not have built a production-ready agent, but you will have built enough that the rest of the documentation makes sense.

If you want more context before diving in, read the project [README](../README.md) and [Chapter 1 of the specification](../spec/01-introduction.md). Otherwise, let's build.

---

## What you'll build

A tiny Python agent that:

1. Starts an AAEP session.
2. Announces a state change.
3. Asks the user for confirmation before performing a fake action.
4. Streams output.
5. Completes the session.

And a tiny subscriber that:

1. Receives the events.
2. Prints them to the terminal in a screen-reader-like style.
3. Replies to the confirmation when prompted.

Everything runs on your local machine over stdin/stdout. No network, no servers, no accounts.

---

## Prerequisites

- **Python 3.10 or newer.** Verify with `python3 --version`.
- A terminal you're comfortable with.
- About 10 minutes of focused attention.

That's it. No libraries to install. AAEP doesn't have a "library" you install in the traditional sense; it's a protocol you implement directly. The total amount of code you'll write is under 100 lines.

---

## Step 1: Create your working directory

Open a terminal and create a folder for this tutorial:

```bash
mkdir aaep-quickstart
cd aaep-quickstart
```

You'll create two files here: `producer.py` and `subscriber.py`.

---

## Step 2: Write the producer

Create `producer.py` with the following content:

```python
"""
AAEP Quickstart: tiny producer that emits a complete session.
Outputs each event as one JSON object per line on stdout.
"""

import json
import sys
import time
import uuid
from datetime import datetime, timezone


def now():
    """Return current time as RFC 3339 string with millisecond precision."""
    t = datetime.now(timezone.utc)
    return t.strftime("%Y-%m-%dT%H:%M:%S.") + f"{t.microsecond // 1000:03d}Z"


def make_id(prefix):
    """Generate an AAEP-style identifier: prefix_<32hex chars>."""
    return f"{prefix}_{uuid.uuid4().hex}"


# Stable IDs for this session
SESSION_ID = make_id("sess")
PRODUCER = {
    "agent_id": "quickstart-demo",
    "agent_version": "0.1.0",
    "agent_name": "AAEP Quickstart Demo",
}


def emit(event):
    """Print one AAEP event as a single line of JSON to stdout."""
    print(json.dumps(event), flush=True)


def envelope(event_type, **fields):
    """Build an event envelope with common fields filled in."""
    return {
        "@context": "https://aaep-protocol.org/context/v1",
        "type": event_type,
        "event_id": make_id("evt"),
        "session_id": SESSION_ID,
        "timestamp": now(),
        "producer": PRODUCER,
        **fields,
    }


def wait_for_reply(reply_token, timeout_seconds=30):
    """Block until a confirmation.reply arrives on stdin or timeout elapses."""
    sys.stdin.reconfigure(line_buffering=True)
    end_time = time.monotonic() + timeout_seconds
    while time.monotonic() < end_time:
        line = sys.stdin.readline()
        if not line:
            time.sleep(0.05)
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        if (msg.get("type") == "confirmation.reply"
                and msg.get("reply_token") == reply_token):
            return msg.get("decision")
    return None  # timeout


def main():
    # Step 1: session.started
    emit(envelope(
        "aaep:agent.session.started",
        urgency="normal",
        summary_normal="Quickstart demo session started.",
    ))
    time.sleep(0.3)

    # Step 2: state changes to thinking
    emit(envelope(
        "aaep:agent.state.changed",
        urgency="background",
        from_state="idle",
        to_state="thinking",
        summary_normal="Thinking about what to do.",
    ))
    time.sleep(0.5)

    # Step 3: ask for confirmation before doing something
    reply_token = make_id("rpl")
    emit(envelope(
        "aaep:agent.awaiting.confirmation",
        urgency="critical",
        action="Demonstrate AAEP by emitting a few events.",
        consequence="Five events will be printed to your terminal. No real side effects.",
        reply_token=reply_token,
        timeout_seconds=30,
        default_decision="reject",
        risk_level="low",
        irreversible=False,
        summary_normal="Confirmation required. Demonstrate AAEP by printing events?",
    ))

    decision = wait_for_reply(reply_token)
    if decision != "accept":
        emit(envelope(
            "aaep:agent.session.cancelled",
            urgency="normal",
            cancelled_by="user" if decision == "reject" else "timeout",
            summary_normal="User declined the demo (or timed out).",
        ))
        return

    # Step 4: state changes to writing output
    emit(envelope(
        "aaep:agent.state.changed",
        urgency="background",
        from_state="thinking",
        to_state="writing_output",
        summary_normal="Generating output.",
    ))
    time.sleep(0.3)

    # Step 5: stream three chunks of output
    output_id = make_id("out")
    chunks = [
        "Welcome to AAEP. ",
        "You just used the confirmation protocol. ",
        "This is the same flow Microsoft Narrator would use to make agentic AI accessible.",
    ]
    position = 0
    for i, chunk in enumerate(chunks):
        is_final = (i == len(chunks) - 1)
        emit(envelope(
            "aaep:agent.output.streaming",
            urgency="normal",
            chunk=chunk,
            position=position,
            complete=is_final,
            coalesce_hint="completion" if is_final else "sentence",
            output_id=output_id,
        ))
        position += len(chunk)
        time.sleep(0.4)

    # Step 6: session.completed
    emit(envelope(
        "aaep:agent.session.completed",
        urgency="normal",
        summary_normal="Quickstart demo complete.",
        duration_ms=3000,
    ))


if __name__ == "__main__":
    main()
```

---

## Step 3: Write the subscriber

Create `subscriber.py`:

```python
"""
AAEP Quickstart: tiny subscriber that reads events from a producer's stdout
and prints them in a screen-reader-like format. Replies 'accept' to any
confirmation event for demo purposes.
"""

import json
import subprocess
import sys


def announce(text):
    """Pretend to be a screen reader: print announcements with a prefix."""
    print(f"[AAEP] {text}", flush=True)


def handle_event(event, producer_stdin):
    """Convert an event into a screen-reader-style announcement."""
    event_type = event.get("type", "<unknown>")
    summary = event.get("summary_normal") or event.get("summary_terse") or ""

    if event_type == "aaep:agent.session.started":
        announce(f"Session started. {summary}")

    elif event_type == "aaep:agent.state.changed":
        from_s = event.get("from_state", "?")
        to_s = event.get("to_state", "?")
        announce(f"State: {from_s} → {to_s}. {summary}")

    elif event_type == "aaep:agent.awaiting.confirmation":
        announce(f"Confirmation required: {event.get('action')}")
        announce(f"Consequence: {event.get('consequence')}")
        announce("Auto-replying with ACCEPT in 1 second...")
        # In a real subscriber, this is where the user would respond.
        # For the demo, we send "accept" automatically.
        reply = {
            "type": "confirmation.reply",
            "reply_token": event["reply_token"],
            "decision": "accept",
            "subscription_id": "sub_quickstart-demo",
            "timestamp": event["timestamp"],
        }
        producer_stdin.write(json.dumps(reply) + "\n")
        producer_stdin.flush()

    elif event_type == "aaep:agent.output.streaming":
        chunk = event.get("chunk", "")
        if event.get("complete"):
            announce(f"Output: \"{chunk}\" (complete)")
        else:
            announce(f"Output: \"{chunk}\"")

    elif event_type == "aaep:agent.session.completed":
        announce(f"Session completed. {summary}")

    elif event_type == "aaep:agent.session.cancelled":
        announce(f"Session cancelled. {summary}")

    elif event_type == "aaep:agent.session.errored":
        announce(f"Session errored. {summary}")

    else:
        announce(f"Unknown event type: {event_type}")


def main():
    proc = subprocess.Popen(
        [sys.executable, "producer.py"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    try:
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            handle_event(event, proc.stdin)
    finally:
        proc.wait()


if __name__ == "__main__":
    main()
```

---

## Step 4: Run it

In your terminal:

```bash
python3 subscriber.py
```

You should see output similar to this:

```
[AAEP] Session started. Quickstart demo session started.
[AAEP] State: idle → thinking. Thinking about what to do.
[AAEP] Confirmation required: Demonstrate AAEP by emitting a few events.
[AAEP] Consequence: Five events will be printed to your terminal. No real side effects.
[AAEP] Auto-replying with ACCEPT in 1 second...
[AAEP] State: thinking → writing_output. Generating output.
[AAEP] Output: "Welcome to AAEP. "
[AAEP] Output: "You just used the confirmation protocol. "
[AAEP] Output: "This is the same flow Microsoft Narrator would use to make agentic AI accessible." (complete)
[AAEP] Session completed. Quickstart demo complete.
```

If you see that output, **congratulations: you've just shipped a working AAEP integration.** A real subscriber (like a screen reader) would speak these announcements instead of printing them. A real producer (like a customer-service agent or coding assistant) would emit events at the same lifecycle points but with real semantic content.

---

## Step 5: Inspect the raw events

To see the actual JSON flying between producer and subscriber, run the producer alone with a forced reject input:

```bash
echo '{"type":"confirmation.reply","reply_token":"x","decision":"reject","subscription_id":"sub_x","timestamp":"2026-01-01T00:00:00.000Z"}' | python3 producer.py
```

Each line of output is one complete AAEP event. Copy any of them into a JSON formatter to see the full envelope structure.

You'll notice every event carries:

- `@context` pointing to the AAEP JSON-LD context
- `type` identifying the event kind
- `event_id` and `session_id` for correlation
- `timestamp` for ordering
- `producer` for identity
- `urgency` for priority
- Plus event-specific payload fields

That's the full envelope spec from [Chapter 3](../spec/03-event-envelope.md) at work.

---

## What just happened

In about 100 lines of Python, you implemented:

- **Conformance Level 1** — emitted lifecycle, state, and output events
- **Conformance Level 2** — blocked on a confirmation, waited for a valid reply
- **The safety contract from [Chapter 6 §6.1](../spec/06-confirmation-protocol.md)** — the producer literally did not proceed until the subscriber sent a reply

What's missing for production:

- **Subscription handshake (Level 3)** — your producer started emitting events immediately. A real Level-3 producer would wait for `subscription.request` and respond with `subscription.accepted` first.
- **Capability negotiation** — your subscriber didn't declare a rate limit, language, or coalescing preference.
- **Real authentication** — there's no auth between producer and subscriber here.
- **Multiple subscribers** — the demo has a single producer-subscriber pair.

The [Implementer's Guide](IMPLEMENTERS_GUIDE.md) shows how to add all of these to a production agent.

---

## Where to go next

**To build a real producer** in your existing agent framework:

- [Implementer's Guide](IMPLEMENTERS_GUIDE.md) — framework-specific integration patterns
- [Integration patterns](patterns/) — middleware, callback, decorator, event-emitter, manual-loop
- Reference examples in [`../examples/producers/`](../examples/producers/) for Python, TypeScript, C#, Go, and Rust

**To build an AAEP-aware subscriber** (screen reader, voice control, etc.):

- [Subscribers' Guide](SUBSCRIBERS_GUIDE.md) — assistive technology integration patterns
- Reference examples in [`../examples/subscribers/`](../examples/subscribers/) including an NVDA add-on prototype

**To extend AAEP for a specific domain**:

- [Extensions Guide](EXTENSIONS_GUIDE.md) — how to publish your own AAEP extension
- The multilingual African languages extension in [`../examples/extensions/multilingual-african-languages/`](../examples/extensions/multilingual-african-languages/) as a worked template

**To verify your implementation conforms**:

- The conformance test suite in [`../conformance/`](../conformance/) — run it against your endpoint and publish the result

**For common questions**:

- [FAQ](FAQ.md) — frequently asked questions and common misconceptions

---

## A word on what's special here

You just built an agent that pauses before doing something irreversible, surfaces the action and its consequence in clear human-readable text, and only proceeds when the user (through the subscriber) explicitly consents. The same mechanism works whether the subscriber is your terminal, Windows Narrator, an NVDA add-on, a voice-control system, a switch-input device, or an AT not yet invented.

This is not aspirational. The code above is normatively conforming to AAEP Conformance Level 2. Any subscriber implementing AAEP Level 2 will work with your producer. Any producer implementing AAEP Level 2 will work with your subscriber. That interoperability is the whole point of the protocol.

You're ready to read the rest of the documentation. Welcome to AAEP.
