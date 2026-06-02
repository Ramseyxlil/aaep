# Multilingual African Languages Extension

A canonical AAEP extension demonstrating first-class support for **Yoruba**, **Hausa**, and **Igbo** — three of the most widely-spoken African languages, together used by approximately 150 million people across West Africa and the diaspora.

This extension serves two purposes:

1. **Practical:** Enable AAEP agents to communicate with assistive technology in Yoruba, Hausa, and Igbo, not just English.
2. **Demonstrative:** Show the AAEP extension mechanism in a worked example that other communities can model their own language extensions on.

Referenced from Specification Chapter 7 §7.7.1 and Chapter 11 as the canonical multilingual extension example.

---

## Why this extension exists

AAEP's core specification is canonical-English by convention (matching W3C and IETF practice). But the protocol's stated purpose — making AI agents accessible to everyone — would fail if accessibility tooling could only speak English to Yoruba grandmothers, Hausa traders, or Igbo students.

The standard pattern for accessibility specs is: launch in English, accept patches for other languages over years. We do better. This extension ships in v1.0.0 alongside the core specification, treating these three languages as **first-class from launch**, not as afterthoughts to be retrofitted.

The pattern this extension establishes is reusable. A Swahili, Wolof, Amharic, or any-other-language extension follows the same shape.

---

## What the extension provides

### 1. Language identifiers and metadata

Standard BCP 47 language tags with our extension namespace:

| Language | Tag | Native name | Estimated speakers |
|---|---|---|---|
| Yoruba | `yo` | Yorùbá | ~50 million |
| Hausa | `ha` | Hausa | ~80 million |
| Igbo | `ig` | Asụsụ Igbo | ~30 million |

### 2. Translated summary strings for canonical AAEP events

For each event type, the extension provides idiomatic translations of the `summary_normal`, `summary_terse`, and `summary_detailed` fields. Producers can opt-in to multilingual output by setting:

```json
{
  "language": "yo",
  "summary_normal": "Mò ń mú orúkọ rẹ wá",
  "summary_terse": "Ìpadàbọ̀",
  "summary_detailed": "Mò ń mú orúkọ tó wà ní ìwé àkọsílẹ̀ rẹ wá",
  "localization_hints": {
    "primary_language": "yo",
    "available_languages": ["yo", "en"]
  }
}
```

The extension provides the canonical translation tables in `translations/` so producers don't have to translate from scratch.

### 3. Locale-aware speech-rate hints

Different languages have different natural speaking rates. The extension provides recommended `pace_wpm` ranges:

| Language | Recommended pace_wpm range | Notes |
|---|---|---|
| Yoruba | 110–150 | Tonal language; slower pace aids comprehension of tone marks |
| Hausa | 130–170 | Faster, syllable-timed |
| Igbo | 110–150 | Tonal; similar to Yoruba |
| English (reference) | 140–180 | Stress-timed |

Subscribers can use these as defaults when negotiating with producers (see Capability Negotiation in Chapter 5).

### 4. Tone-mark preservation rules

Yoruba and Igbo are tonal languages where diacritics are not optional decorations — they encode meaning. The extension defines normative rules:

- Producers MUST emit text with proper Unicode combining diacritics (e.g., `ọ` not `o`)
- Subscribers MUST NOT strip tone marks before passing text to TTS engines that support them
- Subscribers that route to TTS engines without tone support SHOULD fall back to the closest-meaning rendering and signal this via `localization_hints.fallback_applied = true`

### 5. Pluralization rules

These three languages handle pluralization differently from English:

- **Yoruba and Igbo:** No grammatical plural marker on most nouns; quantity expressed through numerals or context
- **Hausa:** Multiple plural patterns including broken plurals (similar to Arabic influence)

The extension includes `pluralize()` helper functions that apply the correct rules per language.

### 6. Right-to-left awareness

All three languages are typically written left-to-right in modern usage. However, Hausa has historical use in **Ajami** (Arabic script, right-to-left). The extension acknowledges this and reserves `localization_hints.script` values:

- `latin` — default for all three languages
- `ajami` — for Hausa in Arabic script (RTL); sets `text_direction: "rtl"`

---

## Installation

```bash
cd examples/extensions/multilingual-african-languages
pip install -e .
```

Requires Python 3.10 or newer. Runtime dependencies are minimal (`aaep-minimal-producer` for the emitter API).

---

## Usage

### Producer side

```python
from aaep_minimal_producer.emitter import AAEPEmitter
from aaep_ext_african_languages import translate_summary, recommended_pace

emitter = AAEPEmitter(send_event=my_transport, agent_id="my-agent")

session_id = emitter.start_session(
    summary_normal=translate_summary("session.started", language="yo"),
    request_text="Mo nilo iranlowo pẹlu owó-mi",
    localization_hints={
        "primary_language": "yo",
        "available_languages": ["yo", "en"],
        "pace_wpm": recommended_pace("yo"),
    },
)
```

### Subscriber side

```python
from aaep_ext_african_languages import select_summary

def on_event(event):
    # Pick the best language for the user
    text = select_summary(event, preferred_languages=["yo", "en"])
    speak(text)
```

The helper functions handle the gritty work: choosing the right available language, applying fallback chains, preserving tone marks when supported.

---

## Translation files

The extension ships canonical translation tables in `translations/`:

```
translations/
├── yo.json          # Yoruba
├── ha.json          # Hausa
└── ig.json          # Igbo
```

Each file maps AAEP event type → translation block. Translators can contribute updates via the standard ACP process.

Example excerpt from `yo.json`:

```json
{
  "language": "yo",
  "name_native": "Yorùbá",
  "events": {
    "aaep:agent.session.started": {
      "summary_terse": "Ìbẹ̀rẹ̀",
      "summary_normal": "Mò ń bẹ̀rẹ̀ iṣẹ́ rẹ",
      "summary_detailed": "Mò ń bẹ̀rẹ̀ iṣẹ́ tó béèrè nípa..."
    },
    "aaep:agent.tool.invoked": {
      "summary_terse": "Lílo ohun-èlò",
      "summary_normal": "Mò ń lo {tool}",
      "summary_detailed": "Mò ń lo ohun-èlò {tool} pẹ̀lú àwọn àlàyé"
    },
    "aaep:agent.awaiting.confirmation": {
      "summary_terse": "Béèrè ìfọwọ́sí",
      "summary_normal": "Ṣé kí n ṣe {action}?",
      "summary_detailed": "Mò ń béèrè ìfọwọ́sí rẹ kí n tó ṣe {action}. {consequence}"
    }
  }
}
```

Producers use a simple format-string interpolation: `{tool}`, `{action}`, `{consequence}` get replaced from the event's structured fields.

---

## Translation quality and contributions

The translations shipped in v1.0.0 are reviewed by native speakers but should be considered **community-driven and iterable**. Contributions welcome:

- Improvements to existing translations
- Regional dialect variants (e.g., Lagos Yoruba vs. Oyo Yoruba)
- Audio pronunciation references
- Sign language equivalents

To contribute translations:

1. Read `governance/CONTRIBUTING.md` §7.1 on translation contributions
2. Fork the repository and edit the relevant `translations/<lang>.json`
3. Open a PR with:
   - The change you made
   - Your level of fluency
   - A second native-speaker review if available
   - Citation for any contested word choices

---

## Project layout

```
multilingual-african-languages/
├── README.md
├── extension.json              # Extension manifest
├── pyproject.toml
├── aaep_ext_african_languages/
│   ├── __init__.py
│   ├── translations.py         # Translation lookup + interpolation
│   └── locale_data.py          # Speech rates, scripts, pluralization
├── translations/
│   ├── yo.json
│   ├── ha.json
│   └── ig.json
└── tests/
    └── test_translations.py
```

---

## Conformance

This extension is non-normative (per AAEP Chapter 7 §7.3). Producers MAY implement it; subscribers MAY support it. The extension does not modify any normative requirement in core AAEP.

Conformance to the extension itself is signaled via the `supported_extensions` capability:

```json
{
  "supported_extensions": ["aaep-ext-african-languages-1.0"]
}
```

Producers and subscribers exchanging this in handshake know they can use the extension's features.

---

## Why this matters beyond the three languages

AAEP's success depends on serving users globally, not just English speakers. By shipping a worked multilingual extension in v1.0.0:

1. **We prove the extension mechanism works.** Future extensions (Swahili, Wolof, Arabic, Hindi, Mandarin, etc.) follow the same template.
2. **We surface the cultural-technical decisions early.** Tone marks, RTL scripts, locale-specific speech rates — these become design considerations from day one, not afterthoughts.
3. **We invite the global accessibility community in.** The translation infrastructure is open; native speakers can contribute without needing to understand AAEP's core machinery.
4. **We signal intent.** A protocol that ships with Yoruba, Hausa, and Igbo support is a protocol that takes global accessibility seriously, not as a marketing checkbox.

This extension is what the broader accessibility community needed but hasn't gotten from English-centric specs.

---

## See also

- [Specification Chapter 7](../../../spec/07-extensions.md) — extension mechanism
- [Specification Chapter 11](../../../spec/11-internationalization.md) — internationalization requirements
- [`../medical-hipaa/`](../medical-hipaa/) — sister extension for healthcare contexts
- [Extensions Guide](../../../guides/EXTENSIONS_GUIDE.md) — full extension authoring guide
- [CONTRIBUTING.md §7.1](../../../governance/CONTRIBUTING.md) — translation contribution guidelines
