# aaep-tools

Official command-line tools for the [Agent Accessibility Event Protocol](https://aaep-protocol.org). Install once, get three commands for working with AAEP event streams.

```bash
pip install aaep-tools
```

After installation:

```
aaep-validate --help
aaep-capture --help
aaep-replay --help
```

Requires Python 3.10 or newer.

---

## What's included

| Command | What it does |
|---|---|
| `aaep-validate` | Validates events against the AAEP JSON Schemas |
| `aaep-capture` | Records SSE event streams from a running producer to JSONL |
| `aaep-replay` | Replays JSONL streams as SSE servers for testing subscribers |

All three are language-and-framework agnostic. They work with any conformant AAEP producer or subscriber regardless of implementation language.

---

## Quick reference

### Validate

```bash
# Validate a single event from stdin
cat event.json | aaep-validate

# Validate a captured stream
aaep-validate captured.jsonl

# Validate multiple files
aaep-validate event1.json event2.json stream.jsonl

# Machine-readable JSON output
aaep-validate --json captured.jsonl | jq 'select(.valid == false)'

# CI mode (silent, exit code only)
aaep-validate --quiet captured.jsonl
```

Exit codes: `0` (all valid), `1` (any invalid), `2` (usage/I/O error).

### Capture

```bash
# Capture from a running producer until Ctrl-C
aaep-capture --endpoint http://localhost:8080 --output session.jsonl

# Capture for 60 seconds
aaep-capture --endpoint http://localhost:8080 --output session.jsonl --timeout 60

# Capture exactly 100 events
aaep-capture --endpoint http://localhost:8080 --output session.jsonl --max-events 100

# Capture only critical-urgency events
aaep-capture --endpoint http://localhost:8080 --output critical.jsonl --filter-urgency critical

# Capture only tool events from one session
aaep-capture --endpoint http://localhost:8080 --output debug.jsonl \
    --filter-type tool.invoked --filter-type tool.completed \
    --filter-session sess_abc123
```

The output file is always closed cleanly on Ctrl-C — no partial JSON lines.

### Replay

```bash
# Replay a captured stream at original pace on port 9000
aaep-replay --file session.jsonl --port 9000

# Replay 10x faster
aaep-replay --file session.jsonl --port 9000 --speed 10

# Replay as fast as possible (no inter-event delay)
aaep-replay --file session.jsonl --port 9000 --no-delay

# Loop replay continuously for soak testing
aaep-replay --file session.jsonl --port 9000 --loop --no-delay
```

The server provides standard AAEP endpoints:
- `GET /events` — SSE stream of replayed events
- `GET /healthz` — health check with current state

---

## Programmatic API

If you need to invoke the functionality from Python code rather than the CLI:

```python
from aaep_tools.validate import validate_event, validate_stream
from aaep_tools.capture import capture_stream
from aaep_tools.replay import load_events, run_replay

# Validate a single event
result = validate_event({
    "type": "aaep:agent.session.started",
    # ... rest of event ...
})
if not result.valid:
    for error in result.errors:
        print(error)

# Validate a JSONL stream
with open("captured.jsonl") as f:
    for result in validate_stream(f):
        if not result.valid:
            print(f"{result.location}: {result.errors}")

# Capture (async)
import asyncio, sys
async def grab():
    captured, reason = await capture_stream(
        endpoint="http://localhost:8080",
        output=sys.stdout,
        timeout_seconds=30,
    )
    return captured

asyncio.run(grab())

# Load and inspect captured events
events = load_events(Path("captured.jsonl"))
print(f"Captured {len(events)} events")
```

---

## Use cases

**Producer development.** Run `aaep-validate` in CI on every captured event stream. Catch malformed events before they ship.

**Subscriber development.** Capture real production traces with `aaep-capture`, then replay them with `aaep-replay` to test subscribers against canonical inputs. Replays are deterministic and shareable.

**Conformance verification.** The `aaep-conformance` package uses these tools for advanced test scenarios. They also stand alone as a lightweight verification harness.

**Production debugging.** Capture an incident in real time:
```bash
aaep-capture --endpoint http://prod.example.com --output incident.jsonl --timeout 300
```
Then inspect offline, validate, and share with your team.

**Accessibility research.** Capture event streams from various producers, share as datasets, analyze cross-producer behavior. Researchers can study how different agents emit AAEP events without needing to run those agents themselves.

---

## Design philosophy

These tools are intentionally minimal:

- **One thing each, well.** Following the Unix tradition. Validate doesn't capture, capture doesn't validate, replay doesn't filter.
- **Composable.** Chain them together with pipes. Use them in scripts. Run them in CI.
- **Offline-friendly.** Schemas are bundled with the package. Works behind firewalls and air gaps.
- **Standard I/O conventions.** Reads from stdin, writes to stdout, exit codes follow Unix convention.
- **No surprises.** No GUI, no configuration files, no plugins. What you type is what happens.

If you need richer functionality (live web dashboards, complex pipelines, multi-step automation), build it on top of these tools rather than asking us to bloat them.

---

## Stability

`aaep-tools` is **Production/Stable**. The three commands have stable CLIs and stable programmatic APIs. Breaking changes follow semver: a major version bump (2.0.0) signals breaking changes; minor versions add features compatibly.

The bundled JSON Schemas track the AAEP specification version. Currently AAEP 1.0.0.

---

## Links

- [AAEP Protocol homepage](https://aaep-protocol.org)
- [Repository](https://github.com/Ramseyxlil/aaep)
- [Specification](https://aaep-protocol.org/spec/)
- [Bug Reports](https://github.com/Ramseyxlil/aaep/issues)
- [Reference Implementations](https://github.com/Ramseyxlil/aaep/tree/main/examples)

---

## License

MIT. See LICENSE in the repository.
