# AAEP Conformance Test Suite

The official test suite for verifying AAEP implementations. This package, `aaep-conformance`, lets producers and subscribers prove they conform to a claimed AAEP Conformance Level by running a comprehensive battery of automated tests.

If you ship a product claiming AAEP support, you should run this suite and publish the report.

---

## Installation

```bash
pip install aaep-conformance
```

Or from source:

```bash
git clone https://github.com/Ramseyxlil/aaep.git
cd aaep/conformance
pip install -e .
```

Requires Python 3.10 or newer.

---

## Quick start

### Verify a producer at Conformance Level 1

```bash
aaep-conformance producer --endpoint http://localhost:8080/agent --level 1
```

The suite connects to your producer endpoint, exercises it with a battery of test scenarios, captures the events it emits, and verifies each event against the AAEP specification.

### Verify a subscriber at Conformance Level 2

```bash
aaep-conformance subscriber --connect tcp://localhost:9999 --level 2
```

The suite acts as a synthetic producer, emits a battery of test events to your subscriber, and verifies your subscriber's behavior (including reply handling).

### Validate a single AAEP event against the schema

```bash
aaep-conformance validate event.json
```

Pure schema validation without exercising any endpoint.

---

## What each level tests

### Level 1 (Notification)

Tests verify the producer:

- Emits well-formed AAEP events
- Includes all required envelope fields
- Uses correct event types from the core vocabulary
- Properly terminates sessions with `session.completed`, `session.errored`, or `session.cancelled`
- Emits events in valid sequences (no `tool.completed` without preceding `tool.invoked`)
- Includes `summary_normal` on user-facing events
- Sets `urgency: critical` on `session.errored` events
- Correctly formats identifiers (event_id, session_id, tool_call_id, reply_token)

~40 test cases.

### Level 2 (Interactive)

Everything in Level 1, plus tests verifying:

- Producer emits `agent.awaiting.confirmation` before irreversible actions
- Producer blocks until reply arrives or timeout elapses
- `default_decision` follows the safety rule (irreversible+high → reject)
- Producer correctly applies default_decision on timeout
- Subscriber sends valid `confirmation.reply` messages
- Subscriber sends valid `clarification.reply` messages
- Reply tokens are single-use
- Subscriber and producer handle multiple concurrent confirmations correctly

~80 test cases.

### Level 3 (Negotiated)

Everything in Levels 1 and 2, plus tests verifying:

- Producer responds to `subscription.request` with `subscription.accepted` or `subscription.rejected`
- `honored_capabilities` is not more permissive than the request
- Producer honors `max_events_per_second` (backpressure)
- Producer respects `event_filters` (include/exclude patterns)
- Producer honors `coalesce_boundaries`
- Critical events bypass rate limits and filters
- Signed manifests (when required) validate cryptographically
- Subscription renegotiation works
- Multiple concurrent subscriptions are handled correctly

~120 test cases.

---

## Reports

The suite produces two output formats:

### JSON report (`conformance-report.json`)

Machine-readable, suitable for CI pipelines:

```json
{
  "aaep_version": "1.0.0",
  "conformance_level": 2,
  "endpoint": "http://localhost:8080/agent",
  "started_at": "2026-06-30T14:22:00Z",
  "completed_at": "2026-06-30T14:24:18Z",
  "result": "PASS",
  "pass_rate": 0.98,
  "tests_run": 120,
  "tests_passed": 118,
  "tests_failed": 2,
  "tests_skipped": 0,
  "failures": [
    {
      "test_id": "L2-CONF-007",
      "description": "Producer blocks on confirmation timeout with default_decision=reject",
      "expected": "default_decision applied at 300.0s",
      "actual": "default_decision applied at 298.7s (1.3s early)",
      "severity": "warning"
    }
  ]
}
```

### HTML report (`conformance-report.html`)

Human-readable, suitable for product documentation. Shows pass/fail by category with drill-down to individual test cases.

### Publishing the report

Once your implementation passes, publish the report alongside your product's accessibility documentation. Recommended format:

> *Product Name X.Y.Z supports AAEP v1.0.0 at Conformance Level 2. Verified 2026-09-15 against `aaep-conformance` 1.0.0. Full report: [link]*

---

## Running in CI

Add to your `.github/workflows/`:

```yaml
name: AAEP Conformance
on: [push, pull_request]

jobs:
  conformance:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install aaep-conformance
      - run: |
          # Start your producer in background
          python my_agent.py --serve --port 8080 &
          sleep 5
          aaep-conformance producer --endpoint http://localhost:8080/agent --level 2 --fail-on-warning
```

The `--fail-on-warning` flag causes the suite to exit nonzero on any warning, blocking PR merges that introduce regressions.

---

## Interpreting failures

| Failure type | Meaning | Action |
|---|---|---|
| **error** | Hard spec violation | Fix before claiming conformance |
| **warning** | Spec ambiguity or recommended-not-required violation | Investigate; may indicate a real bug |
| **info** | Behavior worth noting but not a violation | No action required |

A run with zero `error` failures and pass_rate ≥ 0.95 conforms at the claimed level.

---

## Architecture

```
conformance/
├── README.md                          ← this file
├── pyproject.toml                     ← package config
├── setup.py                           ← legacy entry
├── aaep_conformance/
│   ├── __init__.py
│   ├── cli.py                         ← main CLI entry point
│   ├── runner.py                      ← test orchestration
│   ├── reporter.py                    ← report generation
│   ├── level_1.py                     ← Level 1 test suite
│   ├── level_2.py                     ← Level 2 test suite
│   ├── level_3.py                     ← Level 3 test suite
│   ├── checks/
│   │   ├── __init__.py
│   │   ├── envelope.py                ← envelope structure checks
│   │   ├── lifecycle.py               ← session lifecycle checks
│   │   ├── tools.py                   ← tool invocation checks
│   │   ├── streaming.py               ← output streaming checks
│   │   ├── confirmation.py            ← confirmation flow checks
│   │   ├── handshake.py               ← subscription handshake checks
│   │   └── safety.py                  ← safety rule enforcement
│   └── fixtures/
│       ├── valid/                     ← known-valid AAEP events
│       └── invalid/                   ← known-invalid AAEP events
└── tests/                             ← tests for the suite itself
```

The suite is itself tested (it would be ironic if the conformance suite had bugs). Run `pytest` in this directory to verify the suite's own correctness.

---

## Contributing new test cases

If you find AAEP behavior that ought to be tested but isn't, contribute a test case:

1. Identify what level the test belongs to (1, 2, or 3)
2. Open `aaep_conformance/level_N.py` and add your test function
3. Use the helpers in `aaep_conformance/checks/`
4. Add a fixture in `aaep_conformance/fixtures/` if needed
5. Update this README with the new test count
6. Submit a PR

Test cases are reviewed by the AAEP maintainers and other contributors. The bar: a test must verify a specific normative requirement in the spec and must be precise enough that "pass" and "fail" are unambiguous.

---

## See also

- [`../spec/09-conformance.md`](../spec/09-conformance.md) — normative conformance criteria
- [`../guides/IMPLEMENTERS_GUIDE.md`](../guides/IMPLEMENTERS_GUIDE.md) — what implementations should do
- [`../guides/SUBSCRIBERS_GUIDE.md`](../guides/SUBSCRIBERS_GUIDE.md) — what subscribers should do
- [`../tools/aaep-validate/`](../tools/aaep-validate/) — lightweight standalone validator
