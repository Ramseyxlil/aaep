# ACP-0002: Canonical Multilingual African Languages Extension

| Field | Value |
|---|---|
| **ACP Number** | 0002 |
| **Title** | Canonical Multilingual African Languages Extension |
| **Author(s)** | Abdulrafiu Izuafa <Abdulrafiu@izusoft.tech> |
| **Status** | Final |
| **Type** | Standards Track |
| **Category** | Extension |
| **Created** | 2026-06-30 |
| **Updated** | 2026-06-30 |
| **Requires** | ACP-0001 |
| **Replaces** | none |
| **Discussion-URL** | https://github.com/Ramseyxlil/aaep/pull/2 |
| **Implementation** | [`examples/extensions/multilingual-african-languages/`](../../examples/extensions/multilingual-african-languages/) |

---

## Abstract

This ACP formally registers the `aaep-ext-african-languages` extension as a canonical AAEP extension shipped with v1.0.0. The extension provides first-class translation support for Yoruba, Hausa, and Igbo — three of West Africa's most widely-spoken languages, together used by approximately 150 million people. It demonstrates the **content extension pattern** as the canonical model for non-English language extensions.

---

## Motivation

AAEP's stated purpose is to make AI agents accessible to everyone, not just English speakers. The canonical specification is in English by W3C convention, but launching with only English summary fields would fail the protocol's stated purpose for the majority of the world's potential AT users.

Three specific gaps motivated this extension:

1. **No accessibility specification has shipped with Yoruba/Hausa/Igbo as first-class.** All major accessibility specs launched English-only and added other languages later, often years later. This extension reverses that pattern.

2. **Tonal language handling is poorly served by generic i18n.** Yoruba and Igbo tone marks encode meaning; stripping them in TTS pipelines changes what the text says. A canonical extension can specify normative tone-mark preservation rules.

3. **A working multilingual extension is needed as a template.** Future language extensions (Swahili, Arabic, Hindi, Mandarin) need a worked example to model on. Without a canonical first one, every subsequent extension would re-invent decisions about schema additions, fallback chains, and capability signaling.

---

## Specification

### Extension manifest

The extension manifest is defined in [`examples/extensions/multilingual-african-languages/extension.json`](../../examples/extensions/multilingual-african-languages/extension.json).

Key fields:

| Field | Value |
|---|---|
| `extension_id` | `aaep-ext-african-languages` |
| `namespace` | `ext_african_languages` |
| `version` | `1.0.0` |
| `conformance_class` | `informational` |
| `supported_aaep_versions` | `>=1.0.0`, `<2.0.0` |
| `capability_signal` | `aaep-ext-african-languages-1.0` |

### Schema additions

No envelope changes. No new event types. Only optional capability fields:

```json
{
  "ext_african_languages.preferred_dialect": "string",
  "ext_african_languages.tone_marks": "boolean"
}
```

### Translation file format

Each language has a JSON file in `translations/` mapping AAEP event types to summary translations with format-string interpolation:

```json
{
  "language": "yo",
  "name_native": "Yorùbá",
  "events": {
    "aaep:agent.awaiting.confirmation": {
      "summary_terse": "Béèrè ìfọwọ́sí",
      "summary_normal": "Ṣé kí n ṣe {action}?",
      "summary_detailed": "Mò ń béèrè ìfọwọ́sí rẹ kí n tó ṣe {action}. {consequence}"
    }
  }
}
```

### Helper functions (Python reference implementation)

Reference implementation provides 5 helpers:

```python
from aaep_ext_african_languages import (
    translate_summary,       # Look up translation
    select_summary,           # Pick best language with fallback
    recommended_pace,         # Locale-aware pace_wpm
    preserve_tone_marks,      # Unicode NFC normalization
    pluralize,                # Language-specific plural rules
)
```

### Normative behavior

- Producers using this extension MUST emit text with proper Unicode combining diacritics
- Subscribers using this extension MUST NOT strip tone marks before TTS output
- Subscribers that route to TTS engines without tone support SHOULD signal `localization_hints.fallback_applied = true`

---

## Backward compatibility

This extension introduces no breaking changes. Implementations that don't recognize the `ext_african_languages` namespace simply ignore the optional capability fields, per AAEP's standard "ignore unknown fields" rule.

---

## Accessibility implications

This extension benefits Yoruba, Hausa, and Igbo speakers using AT — a population currently underserved by accessibility tooling. Specific benefits:

- **Screen reader users in Nigeria, Benin, Niger, Ghana, and the African diaspora** receive agent announcements in their native language rather than English-only
- **Tonal language users** receive properly accented text that TTS engines with appropriate voices can pronounce correctly
- **AT users learning English as a second language** can hear agent context in their first language

No AT user group is disadvantaged by this extension. Implementations not adopting it continue to work as before.

The AT community has been consulted via informal channels with native-speaker reviewers. Formal community translation contributions are welcomed via the standard ACP process for future translations.

---

## Alternatives considered

**1. Single global multilingual extension.** Instead of separate language extensions, one extension supporting all languages. Rejected because: (a) different languages have different metadata needs (tone marks for Yoruba; broken plurals for Hausa; case marking for Slavic languages); (b) one monolithic extension would have an unbounded scope; (c) separate extensions allow incremental community contribution.

**2. Translation tables in the core spec.** Instead of an extension, translations could live in the core specification. Rejected because: (a) translations should evolve faster than the core protocol; (b) language community ownership is better served by extension-level governance; (c) core spec already commits to canonical English to avoid translation disputes affecting normative semantics.

**3. Defer multilingual support to v1.1 or later.** Could have shipped English-only at v1.0.0. Rejected because: (a) "we'll add multilingual later" is how every accessibility spec has historically deprioritized non-English; (b) shipping with three languages forces the design to handle multiple languages correctly from day one; (c) signals to global community that AAEP is multilingual by design.

---

## Rationale

The choice of Yoruba, Hausa, and Igbo (rather than, say, Spanish, French, Chinese) reflects three considerations:

1. **The protocol architect's authorship context.** Yoruba is the architect's native language and language he can reliably review translations for. Authorship credibility matters for canonical extensions.

2. **Underserved demographics.** Spanish, French, German, Japanese, and Mandarin already have extensive accessibility tooling. Yoruba, Hausa, and Igbo do not. Shipping canonical support for these three signals AAEP fills the gap that other specs leave open.

3. **Linguistic diversity.** The three languages cover tonal (Yoruba, Igbo) and non-tonal (Hausa), Latin script (all three) and historical Arabic script (Hausa Ajami). This forces the extension design to handle the variety of patterns future language extensions will need.

The decision to include normative rules about tone-mark preservation (not just translation content) was made because tone marks aren't decorative — they encode meaning. Allowing subscribers to strip them silently would create accessibility regression compared to producers emitting unmarked text.

---

## Reference implementation

The reference implementation ships with v1.0.0 at [`examples/extensions/multilingual-african-languages/`](../../examples/extensions/multilingual-african-languages/). It includes:

- `extension.json` — manifest
- `translations/yo.json`, `ha.json`, `ig.json` — full translations for all 12 core AAEP events
- `aaep_ext_african_languages/` — Python package with helper functions
- `pyproject.toml` — pip-installable as `aaep-ext-african-languages`

---

## Security considerations

This extension has no direct security implications. It adds optional content fields and helper functions; it does not modify authentication, authorization, or trust boundaries.

Translation files are loaded from the package's bundled data or filesystem. Malicious translation files could in principle inject control characters, but the redaction applied by subscribers (in medical contexts) and standard text-processing safeguards in TTS engines mitigate this.

---

## Privacy considerations

This extension has no direct privacy implications. Translated summaries follow the same privacy rules as English summaries — producers control what they emit.

In healthcare contexts (combining this extension with the medical-hipaa extension), translated PHI summaries are still PHI and require the same redaction.

---

## Open questions

(no open questions)

---

## References

- [Specification Chapter 7](../../spec/07-extensions.md) — Extension mechanism
- [Specification Chapter 9](../../spec/09-internationalization.md) — Internationalization
- [Reference implementation README](../../examples/extensions/multilingual-african-languages/README.md)
- [BCP 47](https://www.rfc-editor.org/bcp/bcp47) — Language tag conventions

---

## Acknowledgments

Translation review and idiomatic phrasing guidance came from the protocol architect's native fluency in Yoruba and educated competence in Hausa and Igbo. Community contribution of regional variants and dialect refinements is welcomed via the standard ACP process.

---

## Changelog

- **2026-06-30:** Created and Final at v1.0.0 launch
