# Chapter 7 — Extensions

*Status: Normative*

---

This chapter specifies the **extension mechanism**: how third parties extend AAEP with new event types, additional fields on existing events, new capabilities, and new transport bindings, without breaking interoperability with core implementations.

The extension mechanism is what makes AAEP future-proof. The twelve core event types defined in [Chapter 4](04-core-event-types.md) cannot anticipate every domain that will eventually need accessibility primitives. Medical AI agents need patient privacy markers. Educational agents need learning-objective annotations. Financial agents need regulatory-compliance fields. Multilingual deployments need richer language metadata than the core spec defines. Spatial-audio assistants need 3D positioning. Each of these is legitimate; none of them belong in the core.

Rather than refuse extensions (causing fragmentation as vendors invent incompatible private formats) or admit everything into the core (causing the core to become unwieldy and slow to evolve), AAEP follows the pattern that has worked for HTTP, ARIA, ActivityStreams, and the broader Linked Data ecosystem: a small rigid core, a published extension mechanism with clear rules, and a registry of known extensions.

## 7.1 What extensions can add

Extensions MAY add the following to a producer-subscriber exchange:

1. **New event types** in a non-`aaep:` namespace, with their own payload schemas.
2. **Additional fields on existing core events**, placed in the namespaced `extensions` object of the event envelope (§3.4.3).
3. **Additional capability fields** in the subscription handshake's `capabilities` object, placed under a namespaced key (§5.3.2).
4. **Additional reply message kinds**, for protocols that require new blocking interactions beyond confirmation and clarification.
5. **Additional transport bindings**, describing how AAEP messages may be carried over transports not enumerated in [Chapter 8](08-transports.md).
6. **Additional profile requirements**, in published profile documents that select extensions for a domain (see §7.10).

## 7.2 What extensions MUST NOT do

Extensions MUST NOT:

1. **Modify the envelope structure.** All required and reserved envelope fields specified in [Chapter 3](03-event-envelope.md) retain their meaning. Extensions cannot redefine `event_id`, `session_id`, `timestamp`, `type`, `@context`, or any other envelope field.

2. **Modify the semantics of core event types.** The twelve core event types defined in [Chapter 4](04-core-event-types.md) retain their meaning. Extensions cannot redefine `agent.tool.invoked` to mean something different. Extensions can only add fields under the `extensions` object of core events.

3. **Modify the subscription handshake message types.** The `subscription.request`, `subscription.accepted`, `subscription.rejected`, `subscription.renegotiate`, and `subscription.close` message types retain their meaning.

4. **Modify the confirmation protocol.** The `confirmation.reply` and `clarification.reply` message types retain their meaning. Extensions MAY add new blocking interaction types (with their own reply messages) but cannot redefine existing ones.

5. **Add fields at the envelope level that are not in the `extensions` object.** Extensions live inside `extensions`, namespaced by prefix. Adding raw fields at the top level of an event is non-conforming.

6. **Claim to be the AAEP standard.** Extension documents MUST be clearly identified as extensions of AAEP, not as competing or successor specifications. Extension URIs MUST NOT be in the `aaep:` namespace.

An extension that violates any of these rules is not a conforming AAEP extension and SHOULD NOT be adopted by implementers.

## 7.3 The namespace mechanism

Extensions are identified by a **namespace URI**. The namespace URI is:

- A URI controlled by the extension's publisher.
- Resolvable (RECOMMENDED) to a published specification document.
- Versioned in the URI path (RECOMMENDED) for clarity.

Examples of well-formed namespace URIs:

- `https://example.org/medai/context/v1`
- `https://aaep-protocol.org/extensions/multilingual-african-languages/v1`
- `https://my-company.com/aaep-extensions/finance/v1`

Each extension MUST also define a **prefix** that producers and subscribers use to compactly reference the namespace in JSON. The prefix is a short identifier (typically 3-12 characters) declared in the `@context`:

```json
{
  "@context": [
    "https://aaep-protocol.org/context/v1",
    "https://example.org/medai/context/v1"
  ]
}
```

When this `@context` is in effect, the prefix `medai` (defined in the medai context document) can be used in events:

```json
{
  "type": "medai:patient.consulted",
  "extensions": {
    "medai": {
      "patient_data_accessed": true
    }
  }
}
```

### 7.3.1 Prefix collisions

If two extensions chosen by the same subscription declare the same prefix, the producer MUST reject the subscription with `reason_code: "capabilities_incompatible"` and `reason_message` identifying the colliding prefix. Subscribers MUST then renegotiate with the conflict resolved (typically by aliasing one prefix to a different value).

Extensions SHOULD choose distinctive prefixes to minimize collision risk. Single-letter prefixes (`x:`, `e:`) are NOT RECOMMENDED.

### 7.3.2 Reserved prefixes

The following prefixes are reserved and MUST NOT be used by extensions:

- `aaep` — reserved for the core specification.
- `xsd`, `rdf`, `rdfs` — reserved for foundational JSON-LD/RDF vocabularies.
- `@`-prefixed names — reserved by JSON-LD itself.

## 7.4 New event types

An extension MAY define new event types using its own namespace. New event types MUST follow the conventions of core event types:

1. The `type` field uses the extension's prefix (or full URI), for example `"medai:patient.consulted"`.
2. The event carries the full envelope (Chapter 3 fields all apply).
3. The event payload is defined in a JSON Schema published alongside the extension.
4. The event has an assigned urgency convention (per the extension's spec).
5. Sequencing rules, if any, are documented.

### 7.4.1 Example: a custom event type

A hypothetical "Federated Learning" extension might add an event signaling that a model parameter update has been integrated:

```json
{
  "@context": [
    "https://aaep-protocol.org/context/v1",
    "https://example.org/fedlearn/context/v1"
  ],
  "type": "fedlearn:model.parameters.updated",
  "event_id": "evt_8a3f5b22",
  "session_id": "sess_2c91a7",
  "timestamp": "2026-05-24T14:22:11.342Z",
  "producer": { "agent_id": "fl-aggregator" },
  "urgency": "background",
  "round_number": 47,
  "participants_count": 12,
  "summary_normal": "Aggregated parameters from 12 participants in round 47."
}
```

Subscribers that recognize `fedlearn:model.parameters.updated` MAY interpret it and surface to users. Subscribers that do not recognize the type SHOULD fall back to a generic announcement using the `summary_normal` field. This graceful degradation is essential to interoperability.

## 7.5 Additional fields on core events

The most common form of extension is adding fields to existing core events. These fields live inside the event's `extensions` object, keyed by the extension's prefix.

### 7.5.1 Example: medical privacy markers

The "Medical AAEP Profile" might require that any tool invocation that accesses patient data be marked with PHI categories:

```json
{
  "@context": [
    "https://aaep-protocol.org/context/v1",
    "https://example.org/medai/context/v1"
  ],
  "type": "aaep:agent.tool.invoked",
  "event_id": "evt_8a3f5b22",
  "session_id": "sess_2c91a7",
  "timestamp": "2026-05-24T14:22:11.342Z",
  "producer": { "agent_id": "clinical-assistant" },
  "tool": "fetch_patient_record",
  "summary_normal": "Retrieving patient medical history.",
  "extensions": {
    "medai": {
      "patient_data_accessed": true,
      "phi_categories": ["medical_history", "medications"],
      "audit_trail_id": "audit_9c4a2b1e"
    }
  }
}
```

The event remains a valid core `aaep:agent.tool.invoked`. Subscribers that understand `medai` interpret the additional fields; subscribers that do not ignore the `extensions.medai` sub-object entirely.

### 7.5.2 Extension fields MUST be self-contained

An extension's fields under its prefix MUST be self-contained: they MUST NOT reference or depend on fields from other extensions or from non-namespaced parts of the event. This rule prevents transitive dependencies that fragment the ecosystem.

## 7.6 Additional capability fields

Subscribers MAY declare extension capabilities during the handshake, using the same namespace-prefix pattern (§5.3.2). The producer evaluates extension capabilities against its own supported extensions:

```json
{
  "capabilities": {
    "max_events_per_second": 5,
    "preferred_verbosity": "normal",
    "haptic": {
      "patterns_supported": ["pulse", "directional"],
      "body_locations": ["wrist"]
    }
  }
}
```

A producer that does not support the `haptic` extension ignores the `haptic` capability sub-object. A producer that does support `haptic` honors the declared sub-capabilities and emits `haptic:` extension data on events where appropriate.

## 7.7 Publishing an extension

Anyone may publish an AAEP extension. Publication does not require permission from AAEP maintainers. A well-formed extension publication includes:

1. **A namespace URI** under the publisher's control.
2. **A JSON-LD context document** at that URI (or referenced from a document at that URI) declaring the prefix and the vocabulary terms.
3. **JSON Schemas** for any new event types, capability shapes, or reply message types defined by the extension.
4. **A specification document** (typically Markdown) describing:
   - What the extension adds.
   - Why it adds those things (motivation and scope).
   - Required and optional fields.
   - Examples of events using the extension.
   - Conformance criteria (how an implementation knows it correctly supports the extension).
   - Versioning and compatibility commitments.
5. **A version identifier** in the namespace URI (e.g., `/v1`, `/v2`).
6. **A maintainer contact** for the extension.

### 7.7.1 Example minimal extension spec

A complete minimal extension specification document looks like:

```markdown
# Multilingual African Languages Extension for AAEP

**Namespace URI:** https://aaep-protocol.org/extensions/multilingual-african-languages/v1
**Prefix:** `azlearn`
**Version:** 1.0.0
**Maintainer:** AzureLearn AI Community

## Purpose

This extension adds rich language metadata for African languages where the
core AAEP `localization_hints` field is insufficient: handling of tonal
marks, transliteration variants, and bidirectional language preferences for
multilingual users in West and East Africa.

## Capability fields

### `azlearn.tonal_marks`
Whether the subscriber preserves tonal marks (booleán).

### `azlearn.transliteration`
"latin" or "native". Preferred transliteration of names for users who prefer
Latin script while reading native content.

## Event-level fields

### `extensions.azlearn.dominant_language`
The user's strongest declared language for this event, distinct from the
primary `localization_hints.primary_language`.

### `extensions.azlearn.fallback_chain`
Ordered array of language codes the subscriber should try in order if the
primary language is unavailable.

## Examples

(...examples here...)

## Conformance

An implementation conforms to this extension if it:
1. Honors `azlearn.tonal_marks` capability when set.
2. Resolves `azlearn.fallback_chain` correctly when the primary language fails.
3. Passes the extension's conformance fixtures published at
   https://aaep-protocol.org/extensions/multilingual-african-languages/v1/conformance/

## Versioning

This extension follows SemVer. The major version is in the namespace URI.
Backward-compatible additions increment the minor version of the spec
document; breaking changes require a new namespace URI (/v2).
```

Real-world extensions follow this pattern with more detail. The AAEP repository includes a worked example at [`examples/extensions/multilingual-african-languages/`](../examples/extensions/multilingual-african-languages/).

## 7.8 The Extensions Registry

The AAEP project maintains a public **Extensions Registry** at [governance/EXTENSIONS_REGISTRY.md](../governance/EXTENSIONS_REGISTRY.md). The registry is informational: registration is not required to publish an extension and registration does not confer official endorsement.

### 7.8.1 Why register

Registering an extension in the AAEP Extensions Registry:

- Helps implementers discover relevant extensions.
- Helps avoid prefix collisions across major extensions.
- Documents the contact and maintenance status of each extension.
- Allows the registry to flag deprecated or superseded extensions.

### 7.8.2 How to register

Open a pull request to [governance/EXTENSIONS_REGISTRY.md](../governance/EXTENSIONS_REGISTRY.md) adding a row with:

- Extension name.
- Namespace URI.
- Recommended prefix.
- Brief description.
- Maintainer contact.
- Specification URL.
- Status (`active`, `deprecated`, `experimental`).

Registry maintainers review and accept registrations on a non-discriminatory basis: extensions are accepted as long as they conform to the rules of this chapter (§7.2 in particular). Registry maintainers do NOT review extensions for quality, completeness, or usefulness; those judgments are left to implementers.

### 7.8.3 Removal and dispute

If an extension is found to violate §7.2 after registration, maintainers MAY mark it as `non-conforming` in the registry. If a dispute arises between extension maintainers (e.g., over prefix collisions or naming), the AAEP governance process (see [governance/GOVERNANCE.md](../governance/GOVERNANCE.md)) provides a path to resolution.

## 7.9 Extension versioning

Extensions SHOULD follow Semantic Versioning ([SemVer]):

- **Major version** is in the namespace URI (`/v1`, `/v2`). Major version changes are breaking and produce a new namespace.
- **Minor version** appears in the extension's spec document. Minor versions add backward-compatible features.
- **Patch version** is editorial; clarifications and bug fixes without semantic change.

[SemVer]: https://semver.org/spec/v2.0.0.html

Subscribers and producers SHOULD include the major version in the `@context` URI they declare. The minor and patch versions are not part of the URI.

### 7.9.1 Coexistence of major versions

Different major versions of the same extension can coexist in the same ecosystem. A subscriber that supports both `v1` and `v2` of an extension declares both in `supported_extensions`. Producers MAY emit events targeting whichever major version is appropriate to the producer's logic, and subscribers handle each by major version.

## 7.10 Profiles

A **profile** is a published document that selects a combination of core conformance level, specific extensions, and additional requirements appropriate to a domain. Profiles do not add new technical capabilities; they specify what an implementation must support to claim conformance to the profile.

### 7.10.1 Example: a hypothetical Medical Profile

```markdown
# Medical AAEP Profile

**Profile URI:** https://example.org/profiles/medai/v1
**Version:** 1.0.0
**Maintainer:** Medical AAEP Working Group

## Required base conformance

Implementations claiming conformance to this profile MUST:

1. Conform to AAEP at Level 2 or higher.
2. Implement the Medical AAEP extension at v1 or higher.
3. Implement the Multilingual extension at v1 with at least English, Spanish, and one local language.

## Additional requirements

In addition to the base requirements:

1. Tool invocations accessing patient data MUST include `medai.phi_categories`.
2. All confirmations involving patient communication MUST have `timeout_seconds >= 300`.
3. All sessions MUST emit a final `agent.handoff.requested` to a human clinician
   if any low-confidence reasoning occurred during the session.

## Conformance fixtures

Test fixtures verifying these additional requirements are published at:
https://example.org/profiles/medai/v1/conformance/
```

A producer or subscriber that wishes to advertise compliance with the Medical AAEP Profile must pass the profile's conformance fixtures in addition to the core AAEP conformance suite.

### 7.10.2 Profiles vs extensions

| Aspect | Extension | Profile |
|---|---|---|
| Adds new capabilities | Yes | No (selects existing ones) |
| Imposes additional requirements | No (purely additive) | Yes (constrains valid implementations) |
| Has its own JSON Schema | Yes | No (uses core and extension schemas) |
| Has its own conformance fixtures | Optional | Required |
| Identified by | Namespace URI | Profile URI |

Profiles and extensions are complementary. Profiles often specify which extensions must be supported for a domain, but the technical content of the extension is defined by the extension document, not the profile.

## 7.11 Compatibility matrix

The following table summarizes what extensions can and cannot do, as a quick reference.

| Capability | Permitted? |
|---|---|
| Define new event types in own namespace | Yes |
| Add fields to existing core events via `extensions` object | Yes |
| Add capability fields to subscription handshake | Yes |
| Define new blocking-reply message types | Yes |
| Add new transport bindings | Yes |
| Publish profiles that combine extensions | Yes |
| Redefine core envelope fields | No |
| Change semantics of core event types | No |
| Add fields directly at envelope level (outside `extensions`) | No |
| Modify subscription handshake message types | No |
| Modify confirmation/clarification reply types | No |
| Use the `aaep:` namespace | No |
| Use reserved prefixes (`aaep`, `xsd`, `rdf`, `@`-names) | No |

## 7.12 Worked example: the multilingual African languages extension

A complete worked extension example is included with the AAEP project at [`examples/extensions/multilingual-african-languages/`](../examples/extensions/multilingual-african-languages/). This extension:

- Adds rich language metadata for African languages.
- Adds a capability for declaring preferred fallback chains.
- Includes JSON Schemas for the additional fields.
- Includes example events demonstrating use.
- Includes conformance fixtures.

The example serves as a template for implementers who wish to publish their own extensions.

## 7.13 Implementation guidance

Implementers building producers should:

- Decide which extensions, if any, your domain requires.
- Choose existing extensions before inventing new ones.
- If you must invent a new extension, follow §7.7.
- Publish your extension publicly (your own URL, plus optionally the Extensions Registry).
- Provide example events and conformance fixtures.
- Maintain a contact for inquiries.

Implementers building subscribers should:

- Implement core AAEP first (Level 1, then Level 2, then Level 3 if applicable).
- Add extensions selectively based on what your subscribers' users need.
- Gracefully ignore extensions you do not understand.
- Avoid baking extension assumptions into core code paths.

The [Extensions Guide](../guides/EXTENSIONS_GUIDE.md) provides detailed implementation patterns for both authors and consumers of extensions.

## 7.14 Where to go next

Readers should now proceed to [Chapter 8 (Transports)](08-transports.md), which specifies the transport-agnostic requirements that any conforming transport must satisfy, plus a non-normative survey of recommended transports.

Implementers planning to publish an extension should additionally consult the [Extensions Guide](../guides/EXTENSIONS_GUIDE.md) for templates and review checklists.
