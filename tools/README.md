# AAEP Command-Line Tools

This directory hosts the official AAEP command-line utilities. They share a single Python package, `aaep-tools`, which installs three commands:

| Command | What it does |
|---|---|
| `aaep-validate` | Validates a JSON file or stdin against the AAEP JSON Schemas |
| `aaep-capture` | Captures the SSE event stream from a running AAEP producer into a file |
| `aaep-replay` | Replays a captured event file as an SSE stream, useful for testing subscribers |

All three commands work with any conformant AAEP producer or subscriber regardless of language. They are language-and-framework agnostic just like the protocol itself.

---

## Installation

```bash
pip install aaep-tools
```

After installation, all three commands are available globally:

```bash
aaep-validate --help
aaep-capture --help
aaep-replay --help
```

Requires Python 3.10 or newer.

---

## Quick examples

### Validate a single event

```bash
cat event.json | aaep-validate
```

If the event passes, the command exits 0 with no output. If validation fails, it prints the schema error and exits 1.

### Validate a captured event stream

```bash
aaep-validate --file captured.jsonl
```

### Capture an event stream from a running producer

```bash
# Capture for 60 seconds, then exit
aaep-capture --endpoint http://localhost:8080 --output session.jsonl --timeout 60

# Capture until manually stopped (Ctrl-C)
aaep-capture --endpoint http://localhost:8080 --output session.jsonl
```

### Replay a captured stream to test subscribers

```bash
aaep-replay --file session.jsonl --port 9000

# In another terminal, point your subscriber at the replay
curl http://localhost:9000/events
```

By default, `aaep-replay` preserves the original timestamp deltas so subscribers receive events at the same pace they were originally emitted. Use `--speed 10x` to fast-forward.

---

## Use cases

**For producer authors:** Use `aaep-validate` in your CI to ensure every event your agent emits is schema-valid. Use `aaep-capture` to grab a real production trace and inspect it offline.

**For subscriber authors:** Use `aaep-replay` to test your subscriber against canonical event streams without needing to run a live producer. Captured replays make for excellent regression tests.

**For conformance verification:** The `aaep-conformance` package (in `../conformance/`) uses these tools internally for advanced test scenarios.

**For accessibility researchers:** Capture event streams from various producers, share them as datasets, and analyze how different agents emit AAEP events. Replays are deterministic, reproducible, and shareable.

---

## Design notes

These tools are intentionally minimal. They do **one thing each, well**, in the Unix tradition. They have no GUI, no configuration files, no plugins. They read from stdin or files, write to stdout or files, and exit with proper status codes.

If you need richer functionality (live debugging UIs, web-based replay viewers, etc.), build it on top of these tools rather than asking us to bloat them.

---

## Source layout

```
tools/
├── README.md
└── aaep-tools/
    ├── pyproject.toml
    └── aaep_tools/
        ├── __init__.py
        ├── cli.py            # Dispatcher (chooses validate/capture/replay)
        ├── validate.py       # aaep-validate implementation
        ├── capture.py        # aaep-capture implementation
        └── replay.py         # aaep-replay implementation
```

---

## See also

- [Specification](../spec/) — The AAEP v1.0.0 specification
- [JSON Schemas](../schemas/) — The schemas these tools validate against
- [Conformance Suite](../conformance/) — Comprehensive test harness for full producer/subscriber conformance
- [Reference Examples](../examples/) — Implementations to validate, capture from, and replay to
