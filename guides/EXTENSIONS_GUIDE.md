# AAEP Extensions Guide

**How to design, publish, and maintain an AAEP extension.**

This guide explains how to extend AAEP for a domain the core specification doesn't cover. By the end you'll know how to define new event types, capabilities, and fields without breaking the core protocol or harming interoperability with implementations that don't know about your extension.

If you're just trying to use AAEP, this guide is not what you need. See the [Implementer's Guide](IMPLEMENTERS_GUIDE.md) or [Subscribers' Guide](SUBSCRIBERS_GUIDE.md).

---

## Table of contents

1. [When you should write an extension](#1-when-you-should-write-an-extension)
2. [What extensions can and cannot do](#2-what-extensions-can-and-cannot-do)
3. [The namespace mechanism](#3-the-namespace-mechanism)
4. [Designing your extension](#4-designing-your-extension)
5. [Writing the extension specification](#5-writing-the-extension-specification)
6. [Defining JSON Schemas for extension events](#6-defining-json-schemas-for-extension-events)
7. [Registering your extension](#7-registering-your-extension)
8. [Publishing your extension](#8-publishing-your-extension)
9. [Versioning](#9-versioning)
10. [Worked example: multilingual African languages extension](#10-worked-example-multilingual-african-languages-extension)
11. [Common extension patterns](#11-common-extension-patterns)
12. [Getting feedback](#12-getting-feedback)

---

## 1. When you should write an extension

Write an extension when:

- Your domain has events the core doesn't model (e.g., medical extensions emit `patient.consulted` and `prescription.suggested`)
- Your platform has subscriber capabilities not in the core (e.g., haptic feedback intensity, refreshable-braille cell count)
- Your industry has compliance requirements that need to be visible in events (e.g., HIPAA audit trail IDs)
- Your community speaks languages the core doesn't address explicitly (e.g., Yoruba tonal marks, Hausa diacritics)

Don't write an extension when:

- The core already supports your use case (always check first)
- You only need to add free-form metadata (use the existing `extensions` envelope field)
- Your need is product-specific rather than industry-wide (use product-internal logging instead)
- You're trying to weaken a core safety rule (extensions cannot override the core)

---

## 2. What extensions can and cannot do

### 2.1 What extensions CAN do

- Define new event types in their own namespace
- Add new fields to events under their namespace prefix
- Declare new capability fields in the subscription handshake
- Recommend additional transport bindings
- Publish profile documents (combinations of conformance levels with extension requirements)
- Suggest additional default values for core fields
- Define stricter constraints on core fields (e.g., a healthcare extension might require `risk_level` to never be `low`)

### 2.2 What extensions CANNOT do

The core specification's safety rules are inviolable. Specifically, extensions MUST NOT:

- Override the rule that irreversible+high-risk actions MUST have `default_decision: reject`
- Allow `agent.awaiting.confirmation` to have urgency other than `critical`
- Permit producers to skip emitting `agent.tool.invoked` before side effects
- Loosen the blocking contract (a producer MUST always wait for confirmation reply or timeout)
- Hide or suppress critical-urgency events
- Skip required envelope fields

These rules exist because users' safety depends on them. An "extension" that softened them would be incompatible with the core and rejected by conformance tests.

---

## 3. The namespace mechanism

Every extension claims a URI namespace. The namespace appears in three places:

### 3.1 In `@context`

```json
{
  "@context": [
    "https://aaep-protocol.org/context/v1",
    "https://example.org/medai/context/v1"
  ]
}
```

The AAEP core context MUST be first. Your extension's context follows.

### 3.2 In compact event types

Once the namespace is declared in `@context`, you can use the prefix in event types:

```json
{
  "type": "medai:patient.consulted"
}
```

The producer and subscriber both know that `medai:` resolves to `https://example.org/medai/context/v1` because the context document says so.

### 3.3 In the `extensions` object

Per-event extension data lives in the envelope's `extensions` object, keyed by prefix:

```json
{
  "extensions": {
    "medai": {
      "patient_data_accessed": true,
      "phi_categories": ["medications", "medical_history"],
      "audit_trail_id": "audit_9c4a2b1e7d3f"
    }
  }
}
```

### 3.4 Picking your namespace URI

Use a URI you control. Reverse-DNS is the convention:

- `https://yourorganization.com/aaep-extensions/your-extension-name/v1`
- `https://github.com/your-org/your-extension/spec/v1`
- `https://aaep-protocol.org/extensions/your-extension/v1` (if your extension is added to the official registry)

Your namespace URI does not need to resolve to anything during early development. Once you publish, it should resolve to your context document at minimum.

---

## 4. Designing your extension

Before writing the specification, answer these questions:

1. **Who is your audience?** Producers, subscribers, or both? An extension that defines new event types is for producers; one that defines new capabilities is for subscribers.

2. **What's the minimum viable extension?** Resist scope creep. A focused extension with 2-3 new event types and 1-2 new fields is easier to adopt than one with 20.

3. **How does it compose with the core?** Your extension events should fit alongside core events in a session, not replace them. If your domain needs a session lifecycle different from the core's, you may be building a different protocol, not an extension.

4. **What does conformance to your extension mean?** Define a separate conformance level for extension support. A producer can be AAEP Level 2 conforming + your-extension Level 1 conforming.

5. **What happens when a subscriber doesn't know your extension?** All core fields still work. Extension-specific data in the `extensions` envelope field is gracefully ignored. The user still gets the AAEP-conforming experience minus the extension-specific value-add.

---

## 5. Writing the extension specification

Your extension specification should follow the same structure as the core spec at a smaller scale:

```
your-extension/
├── README.md
├── spec/
│   ├── 01-introduction.md
│   ├── 02-event-types.md
│   ├── 03-capabilities.md
│   ├── 04-conformance.md
│   └── 05-versioning.md
├── schemas/
│   ├── context/
│   │   └── your-extension-v1.jsonld
│   ├── events/
│   │   ├── your-namespace.event-type-1.schema.json
│   │   └── your-namespace.event-type-2.schema.json
│   └── handshake/
│       └── capability-extensions.schema.json
├── examples/
└── LICENSE (CC-BY-4.0 is recommended for spec material)
```

Required sections in `spec/`:

- **Introduction** — what your extension addresses, who it's for, how it relates to the core
- **Event types** — every event type your extension defines, with required and optional fields
- **Capabilities** — any new subscription capabilities
- **Conformance** — what it means to conform to your extension
- **Versioning** — your extension's SemVer scheme

You may add optional sections (transport bindings, security considerations, profile documents).

---

## 6. Defining JSON Schemas for extension events

Each extension event type needs a schema following the same conventions as core schemas. The key difference: your schema's `$id` points to your namespace.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://example.org/medai/schemas/v1/patient.consulted.schema.json",
  "title": "MedAI Extension Event: patient.consulted",
  "description": "Emitted when the agent has consulted a patient record.",

  "allOf": [
    { "$ref": "https://aaep-protocol.org/schemas/v1/envelope.schema.json" }
  ],

  "type": "object",
  "required": ["type", "patient_id", "data_categories", "summary_normal"],

  "properties": {
    "type": { "const": "medai:patient.consulted" },
    "patient_id": { "type": "string", "minLength": 1 },
    "data_categories": {
      "type": "array",
      "items": { "type": "string" },
      "uniqueItems": true,
      "minItems": 1
    },
    "summary_normal": { "type": "string", "minLength": 1 },
    "summary_detailed": { "type": "string" }
  }
}
```

The pattern is:
- `allOf` references the core envelope (so all envelope rules apply)
- `type` is constrained to your specific event identifier
- Your extension-specific fields are defined with their own constraints

---

## 7. Registering your extension

Registration is optional. AAEP has no central authority that approves extensions.

To make your extension discoverable, submit a pull request to [governance/EXTENSIONS_REGISTRY.md](../governance/EXTENSIONS_REGISTRY.md) adding an entry:

```markdown
### Your Extension Name

- **Namespace:** `https://example.org/your-extension/v1`
- **Prefix:** `your-prefix`
- **Maintainer:** Your Name / Your Organization
- **Repository:** https://github.com/your-org/your-extension
- **Status:** experimental | stable | mature
- **Scope:** Brief one-line description
```

Registration provides:

- Visibility (other implementers can find your extension)
- Coordination (no two extensions accidentally claim the same prefix)
- Quality signal (registered extensions are reviewed for basic standards compliance)

Registration does NOT provide:

- Endorsement (AAEP doesn't endorse specific extensions)
- Stability guarantees (your extension's stability is your responsibility)
- Compliance review (only structural checks; correctness is your responsibility)

---

## 8. Publishing your extension

A complete extension publication consists of:

1. **Your repository** — public Git repository containing the spec, schemas, examples, and license
2. **Your context document** — JSON-LD context file resolvable at your namespace URI
3. **Your schemas** — JSON Schema files resolvable at their `$id` URLs
4. **Your README** — explaining how to use the extension
5. **(Optional) Your conformance suite** — test cases verifying implementations of your extension

The AAEP core team can provide GitHub Pages hosting at `aaep-protocol.org/extensions/<your-name>/` for extensions that are added to the official registry.

---

## 9. Versioning

Extensions follow Semantic Versioning 2.0.0, just like the core specification.

- **MAJOR.MINOR.PATCH** in your extension's version string
- **Backward-compatible additions** are MINOR releases
- **Breaking changes** are MAJOR releases (and the namespace URI's path version increments, e.g., `/v1/` → `/v2/`)
- **Errata corrections** are PATCH releases

Your extension's version is independent of the AAEP core version. Your extension v1.4.0 can target AAEP v1.0.0, v1.1.0, or v1.2.0 — declare which in your spec.

---

## 10. Worked example: multilingual African languages extension

The most complete extension example is the multilingual African languages extension at [`../examples/extensions/multilingual-african-languages/`](../examples/extensions/multilingual-african-languages/). It demonstrates every pattern in this guide.

### 10.1 What it does

Adds first-class support for African languages with structured tonal mark handling, transliteration options, and culturally-specific date/calendar formatting. Targets Yoruba, Hausa, Igbo, Swahili, Amharic, Zulu, Xhosa, and other widely-spoken African languages.

### 10.2 Namespace and prefix

- Namespace: `https://aaep-protocol.org/extensions/multilingual-african-languages/v1`
- Prefix: `azlearn` (named after the AzureLearn AI community that maintains it)

### 10.3 New capability fields

Under `capabilities.azlearn`:

```json
{
  "capabilities": {
    "azlearn": {
      "tonal_marks": "preserve",
      "transliteration": "native",
      "calendar_systems": ["gregorian", "ethiopian", "islamic-hijri"],
      "preferred_naming_conventions": ["yoruba-traditional", "anglicized"]
    }
  }
}
```

These tell the producer how to render African-language content.

### 10.4 New envelope extension fields

Under `extensions.azlearn`:

```json
{
  "extensions": {
    "azlearn": {
      "tonal_marks_applied": true,
      "transliteration_method": "iso-9985",
      "original_orthography": "Ẹ ku àárọ̀"
    }
  }
}
```

### 10.5 New event types

The extension adds three event types specific to African-language scenarios:

- `azlearn:translation.confidence_changed` — when the agent transitions between languages and confidence in translation changes
- `azlearn:cultural_context.invoked` — when the agent applies culturally-specific reasoning (e.g., Yoruba name-day calculations)
- `azlearn:tone_correction.suggested` — for educational use cases where the agent suggests tonal corrections to learner output

### 10.6 Conformance levels

The extension defines two levels:

- **Level 1:** Producer renders content in the requested African language with correct orthography (tones, diacritics).
- **Level 2:** Producer additionally handles capability negotiation for tonal marks, transliteration method, and calendar systems.

### 10.7 Why this extension matters

Africa has 1.4 billion people speaking ~2,000 languages. Most existing accessibility infrastructure assumes English (or at most, the top 10 European languages). An open extension that treats Yoruba, Hausa, Igbo, and Swahili as first-class — not afterthought — is critical for making AAEP genuinely useful outside the Global North.

This extension is maintained by the AzureLearn AI community in Lagos.

---

## 11. Common extension patterns

### 11.1 Domain-specific compliance metadata

Many regulated industries need audit trails visible in events. The pattern:

```json
{
  "extensions": {
    "your-prefix": {
      "compliance_framework": "HIPAA",
      "audit_trail_id": "audit_abc123",
      "data_classification": "PHI",
      "access_justification": "Treatment"
    }
  }
}
```

This is metadata only; it doesn't change AAEP's behavior. But it gives compliance officers what they need to verify the system.

### 11.2 Risk-stratified action descriptions

Some domains need finer-grained risk classification than the core's `[low, medium, high]`. The pattern:

```json
{
  "risk_level": "high",
  "extensions": {
    "your-prefix": {
      "domain_risk_level": "FDA-Class-III",
      "risk_factors": ["irreversible", "patient-safety-critical", "regulated"]
    }
  }
}
```

Your extension carries the domain-specific risk vocabulary; the core's `risk_level` ensures cross-domain interoperability.

### 11.3 New transport bindings

Your domain may need a transport AAEP doesn't normatively specify. Document a transport binding in your extension spec; it then becomes a recommendation that AAEP-compatible implementations may follow.

### 11.4 New conformance profiles

A profile combines a conformance level with extension requirements. For example:

> **Healthcare AAEP Profile, Level 2:** Implements core AAEP Level 2, plus the HIPAA extension, plus the FDA-classification extension. Required for all clinical decision support systems.

Profiles make it easier for users and procurement officers to specify what they need.

---

## 12. Getting feedback

Before publishing your extension as stable, get feedback from:

- The AAEP community on the project discussion forum
- Domain experts in your target area
- Representative users from your domain
- At least one implementer who will adopt the extension

A good extension is one your users actually want, not just one you find interesting.

---

## Where to go from here

- For reference extension implementations, see [`../examples/extensions/`](../examples/extensions/)
- For the core specification, see [`../spec/SPEC.md`](../spec/SPEC.md)
- For the extensions registry, see [`../governance/EXTENSIONS_REGISTRY.md`](../governance/EXTENSIONS_REGISTRY.md)
- For governance and contribution guidance, see [`../governance/CONTRIBUTING.md`](../governance/CONTRIBUTING.md)

The strength of AAEP depends on its extensions. Every domain that builds one makes the protocol more useful for everyone.
