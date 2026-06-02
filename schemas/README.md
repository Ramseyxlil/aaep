# AAEP JSON Schemas

This directory contains the **machine-readable definitions** of every AAEP event type, handshake message, and capability shape. Together with the prose specification in [`../spec/`](../spec/), these schemas form the canonical definition of the protocol.

## What's in this directory

```
schemas/
├── README.md                                ← this file
├── envelope.schema.json                     ← the base envelope every event carries
├── context/
│   └── aaep-v1.jsonld                       ← JSON-LD context document
├── core/                                    ← schemas for the 12 core event types
│   ├── agent.session.started.schema.json
│   ├── agent.session.completed.schema.json
│   ├── agent.session.errored.schema.json
│   ├── agent.session.cancelled.schema.json
│   ├── agent.state.changed.schema.json
│   ├── agent.progress.updated.schema.json
│   ├── agent.tool.invoked.schema.json
│   ├── agent.tool.completed.schema.json
│   ├── agent.output.streaming.schema.json
│   ├── agent.awaiting.confirmation.schema.json
│   ├── agent.awaiting.clarification.schema.json
│   └── agent.handoff.requested.schema.json
└── handshake/                               ← schemas for handshake and reply messages
    ├── subscription.request.schema.json
    ├── subscription.accepted.schema.json
    ├── subscription.rejected.schema.json
    └── confirmation.reply.schema.json
```

## Schema dialect

All AAEP schemas declare conformance to **JSON Schema 2020-12**:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema"
}
```

This is the current stable dialect of JSON Schema and is supported by all major schema validators (ajv for Node.js, jsonschema for Python, jsonschema-rs for Rust, NJsonSchema for .NET, github.com/santhosh-tekuri/jsonschema for Go, and others).

## Canonical URIs

Once the project website is established, each schema will be reachable at a stable canonical URL of the form:

```
https://aaep-protocol.org/schemas/v1/envelope.schema.json
https://aaep-protocol.org/schemas/v1/core/agent.session.started.schema.json
https://aaep-protocol.org/schemas/v1/handshake/subscription.request.schema.json
...
```

These URLs MUST resolve to the byte-identical content of the corresponding files in this directory at the matching specification version. Until the website is live, the canonical source is this Git repository at the tag corresponding to the spec version.

The `$id` field in each schema points to its canonical URL. The `$ref` fields point to canonical URLs of referenced schemas. Validators that operate offline can substitute local file paths.

## Relationship to the prose specification

The prose specification in [`../spec/`](../spec/) and these schemas express the same protocol from different angles:

- The prose specification is the human-readable canonical definition. It describes **what the protocol means** and includes rationale, examples, and design context.
- The schemas are the machine-readable canonical definition. They describe **the structural rules** that determine whether a JSON object is a valid AAEP message.

In any conflict between prose and schemas, **the prose specification takes precedence** and the schema MUST be corrected in a subsequent patch release. This rule exists because schemas can encode the structure of fields but cannot encode all semantic requirements (e.g., "default_decision MUST be 'reject' for irreversible high-risk actions" is a semantic rule expressed in [Chapter 6 §6.4.1](../spec/06-confirmation-protocol.md), not in the schema itself).

The conformance test suite in [`../conformance/`](../conformance/) verifies both: structural conformance via schema validation, and semantic conformance via additional test logic.

## Using the schemas

### Validating events programmatically

**Python (using `jsonschema`):**

```python
import json
from jsonschema import validate, ValidationError

# Load the envelope schema
with open('schemas/envelope.schema.json') as f:
    envelope_schema = json.load(f)

# Load an event-specific schema
with open('schemas/core/agent.tool.invoked.schema.json') as f:
    tool_invoked_schema = json.load(f)

event = {
    "@context": "https://aaep-protocol.org/context/v1",
    "type": "aaep:agent.tool.invoked",
    "event_id": "evt_abc123",
    "session_id": "sess_def456",
    "timestamp": "2026-05-24T14:22:11.342Z",
    "producer": { "agent_id": "test-agent" },
    "tool": "fetch_balance",
    "summary_normal": "Checking your balance.",
    "risk_level": "low",
    "irreversible": false
}

try:
    validate(instance=event, schema=tool_invoked_schema)
    print("Valid AAEP event.")
except ValidationError as e:
    print(f"Invalid: {e.message}")
```

**TypeScript / Node.js (using `ajv`):**

```typescript
import Ajv from "ajv";
import addFormats from "ajv-formats";
import envelopeSchema from "./schemas/envelope.schema.json";
import toolInvokedSchema from "./schemas/core/agent.tool.invoked.schema.json";

const ajv = new Ajv({ schemas: [envelopeSchema] });
addFormats(ajv);
const validate = ajv.compile(toolInvokedSchema);

const event = { /* ... */ };

if (validate(event)) {
  console.log("Valid AAEP event.");
} else {
  console.log("Invalid:", validate.errors);
}
```

**Command-line (using the `aaep-validate` tool):**

```bash
aaep-validate --event-file my-event.json
```

See [`../tools/aaep-validate/`](../tools/aaep-validate/) for details.

### Generating typed code from the schemas

Many programming languages have tools to generate types or classes from JSON Schema. Examples:

- **TypeScript:** `json-schema-to-typescript` produces TypeScript interfaces.
- **Python:** `datamodel-code-generator` produces Pydantic models or dataclasses.
- **Rust:** `schemafy` or `typify` produces Rust structs with serde.
- **C#:** `NJsonSchema` produces C# classes.
- **Go:** `go-jsonschema` produces Go structs.

The AAEP project does not distribute pre-generated bindings; implementers generate bindings appropriate to their language and codebase from these schemas.

## Schema versioning

These schemas are versioned with the AAEP specification:

- **Major version** is in the `$id` URL path (`/v1/`, `/v2/`).
- **Minor version** corresponds to the spec version; minor versions are backward-compatible additions only.
- **Patch version** fixes typos or clarifies ambiguous constraints; no behavior change.

Each schema's `$id` carries the major version. To track minor and patch versions, consult [`../CHANGELOG.md`](../CHANGELOG.md).

## Schema design conventions

The schemas in this directory follow these conventions for clarity and validator efficiency:

1. **Strict `additionalProperties`.** Most schemas declare `"additionalProperties": false` to catch typos and unauthorized fields. Extensions go in the `extensions` sub-object, never directly at the envelope or payload level.

2. **`required` arrays.** Every required field is explicitly listed in `required`.

3. **Pattern constraints.** Identifier formats use `pattern` with regex matching the ABNF grammar in the spec (e.g., `event_id` matches `^evt_[A-Za-z0-9]{1,64}$`).

4. **Enum constraints.** Fields with fixed value sets (verbosity, urgency, status, decision) use `enum`.

5. **Format constraints.** `timestamp` fields use `"format": "date-time"`; URIs use `"format": "uri"`.

6. **Reference reuse.** The envelope schema is referenced by event-specific schemas via `$ref`, preventing duplication.

7. **Examples.** Each schema includes `examples` showing a valid instance, useful for documentation generators and IDE autocomplete.

## Schema validation in CI

The AAEP repository's CI workflows ([`.github/workflows/schema-validation.yml`](../.github/workflows/schema-validation.yml)) validate:

- Every schema is itself valid JSON Schema 2020-12.
- Every fixture in `../conformance/fixtures/valid/` validates against its claimed event type's schema.
- Every fixture in `../conformance/fixtures/invalid/` fails to validate against its target schema (with the expected error).

These checks run on every pull request. PRs that break schema validation are blocked from merge.

## Reporting schema issues

If you find that a schema contradicts the prose specification, or that a schema is overly permissive or restrictive in a way the spec does not justify, please open an issue on the AAEP repository:

- **Bug reports:** Use the bug template at [`../.github/ISSUE_TEMPLATE/bug.md`](../.github/ISSUE_TEMPLATE/bug.md).
- **Spec clarifications:** Use the spec-clarification template at [`../.github/ISSUE_TEMPLATE/spec-clarification.md`](../.github/ISSUE_TEMPLATE/spec-clarification.md).

Reports identifying genuine schema bugs are handled as PATCH-level errata.

## License

The schemas in this directory are licensed under [Creative Commons Attribution 4.0 International (CC-BY-4.0)](../LICENSE-CC-BY-4.0), per the split-license model in [LICENSE](../LICENSE). You may incorporate them into your own products with attribution.

## See also

- [`../spec/SPEC.md`](../spec/SPEC.md) — the canonical prose specification.
- [`../guides/IMPLEMENTERS_GUIDE.md`](../guides/IMPLEMENTERS_GUIDE.md) — framework-specific integration patterns.
- [`../conformance/`](../conformance/) — the conformance test suite that uses these schemas.
- [`../tools/aaep-validate/`](../tools/aaep-validate/) — command-line schema validator.
