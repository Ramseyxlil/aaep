# CLI Debug Subscriber

A reference AAEP subscriber that connects to any producer's `/events` SSE endpoint and prints the event stream in a screen-reader-friendly terminal format. Useful for debugging, demos, and as a starting point for your own subscriber.

If you're new to AAEP and want to see what events look like in practice, this is the easiest way.

---

## What this subscriber does

- Connects to any AAEP producer's `/events` SSE endpoint
- Parses each event and prints it in a clear human-readable format
- Handles all 12 core event types
- Replies to `awaiting.confirmation` and `awaiting.clarification` events interactively
- Color-codes critical-urgency events when the terminal supports it
- Validates each received event against the AAEP schemas (optional, via `--validate`)
- Saves the captured stream to a JSONL file (optional, via `--save`)

This subscriber is the simplest possible AAEP consumer. It demonstrates the protocol's value without any AT integration — you can run it against any producer and observe how the protocol surfaces information to users.

---

## Installation

```bash
cd examples/subscribers/cli-debug
pip install -e .
```

Requires Python 3.10 or newer.

---

## Quick start

In one terminal, start any AAEP producer (e.g., the python-minimal example):

```bash
python -m aaep_minimal_producer.server --port 8080
```

In another terminal, run this subscriber:

```bash
aaep-listen --endpoint http://localhost:8080
```

In a third terminal, send a request to the producer:

```bash
curl -X POST http://localhost:8080/sessions \
    -H "Content-Type: application/json" \
    -d '{"user_message": "What is my balance?"}'
```

You should see events stream into the subscriber's terminal in real time, including state changes, tool invocations, streaming output, and the session completion event.

For the confirmation flow, try:

```bash
curl -X POST http://localhost:8080/sessions \
    -H "Content-Type: application/json" \
    -d '{"user_message": "Send an email to alice@example.com"}'
```

The subscriber will display the confirmation prompt and ask you (in the terminal) to accept or reject. Your decision is sent back to the producer via POST /messages.

---

## Usage

```
aaep-listen --endpoint URL [OPTIONS]

Required:
    --endpoint URL          Producer base URL (e.g., http://localhost:8080)

Optional:
    --save FILE             Also save events to this JSONL file
    --validate              Validate each event against AAEP schemas
    --filter-urgency LEVEL  Only display events with this urgency (normal|critical)
    --filter-type TYPE      Only display events of this type (repeatable)
    --auto-reject           Auto-reject all confirmations (for unattended use)
    --auto-accept           Auto-accept all confirmations (DANGEROUS, debug only)
    --no-color              Disable terminal colors
    --quiet                 Print events as compact one-line JSON only
    --help                  Show this help
    --version               Show version
```

---

## Sample output

```
[12:34:56.789] aaep:agent.session.started        Processing: What is my balance?
[12:34:56.823] aaep:agent.state.changed          Considering the request.
                  from_state: idle -> to_state: thinking
[12:34:57.105] aaep:agent.tool.invoked           Calling fetch_balance.
                  tool: fetch_balance
                  risk_level: low
                  irreversible: false
[12:34:57.401] aaep:agent.tool.completed         $3,247.18
                  tool: fetch_balance
                  status: success
[12:34:57.452] aaep:agent.state.changed          Generating response.
                  from_state: calling_tool -> to_state: writing_output
[12:34:57.501] aaep:agent.output.streaming       Your balance is $3,247.18.
                  position: 0  complete: false
[12:34:57.612] aaep:agent.output.streaming       Anything else?
                  position: 27  complete: true
[12:34:57.701] aaep:agent.session.completed      Response complete.
                  duration_ms: 912
                  tool_invocations_count: 1
```

Critical-urgency events appear in red (or with `!!` prefix if `--no-color`).

---

## Confirmation flow

When the producer emits an `awaiting.confirmation` event, the subscriber pauses and prompts:

```
!! [12:34:57.300] aaep:agent.awaiting.confirmation    Confirm: call send_email?
                    action: Call send_email with: to=alice@example.com, subject=Hello
                    consequence: This action cannot be easily undone.
                    risk_level: high
                    irreversible: true
                    default_decision: reject
                    timeout: 300 seconds

Accept this action? [y/N/?]:
```

- `y` or `yes` → accept (sends `decision: "accept"`)
- `n` or `no` or just Enter → reject (sends `decision: "reject"`)
- `?` → show the full event JSON

The default is reject, matching the protocol's safe-by-default contract for irreversible high-risk actions.

---

## Using as a debugging tool

Common debug recipes:

```bash
# Save everything from a session for later inspection
aaep-listen --endpoint http://localhost:8080 --save session.jsonl

# Only see critical events
aaep-listen --endpoint http://localhost:8080 --filter-urgency critical

# Validate every event against schemas (catches malformed producers)
aaep-listen --endpoint http://localhost:8080 --validate

# Capture without prompting in CI
aaep-listen --endpoint http://localhost:8080 --auto-reject --save run.jsonl

# Compact JSON output for piping into jq or other tools
aaep-listen --endpoint http://localhost:8080 --quiet | jq 'select(.urgency == "critical")'
```

---

## Using as the basis for your own subscriber

This subscriber's source (`aaep_cli_debug/listener.py`) is structured as a starting point for real subscribers:

- The SSE consumer is in `aaep_cli_debug/listener.py:listen()`
- The event-to-text rendering is in `aaep_cli_debug/listener.py:format_event()`
- The reply mechanism is in `aaep_cli_debug/listener.py:send_reply()`

To build an AT-integrated subscriber, replace `format_event()` with calls to your AT's speech engine, and `send_reply()` with your AT's user-input mechanism. The transport layer (SSE consumption, reply posting) doesn't change.

See [`../nvda-addon-prototype/`](../nvda-addon-prototype/) for a worked example of replacing the rendering layer with an NVDA speech-engine integration.

---

## Project layout

```
cli-debug/
├── README.md
├── pyproject.toml
├── aaep_cli_debug/
│   ├── __init__.py
│   └── listener.py        # SSE consumer + event formatter + reply sender
└── tests/
    └── test_listener.py
```

---

## See also

- [Subscribers Guide](../../../guides/SUBSCRIBERS_GUIDE.md) — full guide to building AAEP subscribers
- [`../nvda-addon-prototype/`](../nvda-addon-prototype/) — NVDA add-on subscriber example
- [`../web-subscriber-react/`](../web-subscriber-react/) — browser-based subscriber example
- [`aaep-tools`](../../../tools/) — capture and replay tools that complement this debugger
