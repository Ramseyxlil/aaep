# Chapter 11 — Internationalization

*Status: Normative*

---

This chapter specifies how AAEP handles **language, locale, character encoding, text direction, and culturally-sensitive content**. The requirements in this chapter are mandatory at all conformance levels.

Internationalization is treated as a first-class concern in AAEP. Most prior accessibility standards have been developed with English as the implicit default, with internationalization treated as an add-on. This produces uneven results for the more than 7,000 languages spoken globally and disproportionately disadvantages disabled users in non-English-speaking regions. AAEP corrects this by making language declaration mandatory on all events carrying human-readable text, by negotiating language preferences during subscription handshake, and by providing extension hooks for languages that require richer metadata than the core specification provides.

## 11.1 Language declaration

Every AAEP event whose payload contains human-readable strings (any `summary_*` field, `description`, `question`, `chunk`, `error_message`, or any other text field intended for user announcement) MUST be accompanied by a language declaration. The declaration appears in the envelope's `localization_hints` object.

### 11.1.1 Structure of `localization_hints`

```json
{
  "localization_hints": {
    "primary_language": "en-US",
    "text_direction": "ltr",
    "available_languages": ["en-US", "es-419", "yo-NG"],
    "fallback_chain": ["en-US", "en"],
    "script": "Latn",
    "calendar": "gregorian"
  }
}
```

| Field | Type | Description |
|---|---|---|
| `primary_language` | string (BCP 47 tag) | The language in which the event's human-readable strings are written. REQUIRED on events with human-readable payload. |
| `text_direction` | string | One of `"ltr"`, `"rtl"`, `"auto"`. Defaults to `"ltr"` if absent. |
| `available_languages` | array of strings | Other languages the producer could provide for this event if requested. OPTIONAL. |
| `fallback_chain` | array of strings | If the subscriber cannot use `primary_language`, the languages to try in order. OPTIONAL. |
| `script` | string (ISO 15924) | Script the text is written in. OPTIONAL; defaults are inferred from the language tag where possible. |
| `calendar` | string | Preferred calendar system for date/time formatting (`"gregorian"`, `"islamic"`, `"hebrew"`, etc.). OPTIONAL. |

### 11.1.2 BCP 47 language tags

The `primary_language`, `available_languages`, and `fallback_chain` values MUST use [BCP 47] / [RFC 5646] language tags. BCP 47 is the established standard for identifying languages, regions, scripts, and variants.

[BCP 47]: https://www.rfc-editor.org/info/bcp47
[RFC 5646]: https://www.rfc-editor.org/rfc/rfc5646

Examples of well-formed BCP 47 tags:

| Tag | Meaning |
|---|---|
| `en` | English (any region) |
| `en-US` | English as used in the United States |
| `en-GB` | English as used in the United Kingdom |
| `es-419` | Spanish as used in Latin America and the Caribbean |
| `es-MX` | Spanish as used in Mexico |
| `yo-NG` | Yoruba as used in Nigeria |
| `ha-NG` | Hausa as used in Nigeria |
| `ig-NG` | Igbo as used in Nigeria |
| `sw-KE` | Swahili as used in Kenya |
| `ar-SA` | Arabic as used in Saudi Arabia |
| `zh-Hans` | Simplified Chinese |
| `zh-Hant-TW` | Traditional Chinese as used in Taiwan |
| `he-IL` | Hebrew as used in Israel |
| `ja-JP` | Japanese as used in Japan |
| `pt-BR` | Portuguese as used in Brazil |

Subscribers MUST handle both region-qualified tags (`en-US`) and bare language tags (`en`). When a subscriber requests `en` and the producer offers `en-US`, the match is positive.

### 11.1.3 Tag matching rules

When matching a subscriber's requested languages against a producer's available languages, the following rules apply in order:

1. **Exact match.** A request for `en-US` matches a producer offering `en-US`.
2. **Region fallback.** A request for `en-US` matches a producer offering `en` if no `en-US` is available.
3. **Script fallback.** A request for `zh-Hant` matches a producer offering `zh` if no `zh-Hant` is available.
4. **Subscriber fallback chain.** If no match is found, the next language in the subscriber's `languages` capability list is tried.
5. **Producer fallback chain.** If still no match, the producer applies its own `fallback_chain` from the event's `localization_hints`.
6. **No match.** If no language matches, the producer emits the event in its `primary_language` and the subscriber MUST handle it gracefully (announce in available form, possibly using a translation service if configured).

## 11.2 Language negotiation in the subscription handshake

The subscriber declares its supported languages in the `languages` capability of `subscription.request` (Chapter 5 §5.3.1.3). The producer's `subscription.accepted` honors the declared languages by setting `honored_capabilities.languages` to the subset the producer can actually serve.

After the handshake, the producer SHOULD emit events whose `localization_hints.primary_language` is one of the negotiated languages. If a particular event cannot be expressed in any negotiated language, the producer MUST still emit it (possibly with translation guidance via `fallback_chain`) rather than silently dropping the event.

### 11.2.1 Multilingual subscribers

Subscribers serving multilingual users (a common case in many parts of the world) MAY declare a primary language plus one or more fallbacks:

```json
{
  "capabilities": {
    "languages": ["yo-NG", "en-NG", "en-US", "en"]
  }
}
```

This subscriber prefers Yoruba (Nigerian variant), but accepts Nigerian English, then US English, then any English variant. The producer emits Yoruba when possible and falls back along the chain.

### 11.2.2 Dynamic language switching

A subscriber MAY change its language preference mid-session via `subscription.renegotiate` (Chapter 5 §5.7). The producer MUST apply the new language preference to events emitted after the renegotiation is accepted.

## 11.3 Unicode and character encoding

### 11.3.1 Encoding

All AAEP events MUST be encoded as UTF-8 (Chapter 3 §3.8). Implementations MUST NOT use UTF-16, UTF-32, ISO-8859-x, GBK, Shift-JIS, or any other character encoding.

UTF-8 is the universal standard for modern protocols and supports all Unicode characters including the languages and scripts AAEP must serve.

### 11.3.2 Unicode normalization

Implementations SHOULD normalize human-readable strings to Unicode Normalization Form C (NFC) before emitting events. NFC is the form most software expects and is the basis for comparison and search across platforms.

Subscribers MUST accept any Unicode-valid input regardless of normalization form, and MAY normalize internally for their own purposes. Subscribers MUST NOT reject events because their text is in NFD, NFKC, or NFKD form.

### 11.3.3 Combining characters and grapheme clusters

Many languages use combining characters (Hebrew vowel points, Arabic harakat, tonal marks in Yoruba, Vietnamese diacritics). Subscribers presenting AAEP text MUST handle combining characters correctly:

- Speech subscribers MUST pass the combined grapheme cluster to text-to-speech without splitting characters.
- Braille subscribers MUST translate via grapheme-cluster-aware translation tables.
- Visual subscribers MUST render combining characters at correct positions.

Producers SHOULD avoid emitting "bare" combining characters (combining characters without their base) in human-readable fields.

## 11.4 Text direction and bidirectional text

### 11.4.1 Direction declaration

The `text_direction` field in `localization_hints` indicates the writing direction of the event's text:

- `"ltr"` (left-to-right): English, Spanish, most European and African languages.
- `"rtl"` (right-to-left): Arabic, Hebrew, Persian, Urdu.
- `"auto"`: Determined by Unicode Bidirectional Algorithm ([UAX #9]) on the actual text content.

[UAX #9]: https://www.unicode.org/reports/tr9/

Subscribers MUST honor the declared direction when presenting visual text (braille, large-print displays, captioning). Speech subscribers MAY ignore direction since speech is inherently linear.

### 11.4.2 Mixed-direction text

Bidirectional text (e.g., English names embedded in Arabic prose) MUST be presented using Unicode bidirectional formatting characters where the producer expects specific visual ordering, or with `text_direction: "auto"` for the subscriber to apply the algorithm.

Producers MUST NOT depend on subscribers applying any particular bidirectional rendering beyond the Unicode standard.

## 11.5 Multiple languages within a single event

A single AAEP event MAY contain content in multiple languages. The patterns are:

### 11.5.1 Per-field language override

A specific field MAY override the envelope's `primary_language` by using a language-tagged variant. For example, when a multilingual subscriber prefers content in both Yoruba and English:

```json
{
  "summary_normal": "Calculating retirement projections.",
  "summary_normal_yo": "Mo ń ṣírò àbáwọn àkànkàn fífí ìfẹ̀hìn-tì-iṣẹ́ silẹ̀."
}
```

The `_yo` suffix indicates the Yoruba variant. Subscribers select the variant matching their preferred language.

### 11.5.2 Inline mixed language

A field MAY include inline mixed-language content with HTML `<span>` or equivalent markup indicating the language of substrings. This is less common in AAEP and SHOULD be avoided in favor of per-field variants.

### 11.5.3 Streaming output language

For `agent.output.streaming` events, the producer MAY indicate per-chunk language via the optional `language` field:

```json
{
  "type": "aaep:agent.output.streaming",
  "chunk": "Bonjour, je m'appelle Anaïs.",
  "language": "fr-FR",
  "position": 0,
  "complete": false
}
```

Subscribers use the per-chunk `language` to select appropriate text-to-speech voices and braille tables. The chunk's language MAY differ from the envelope's `primary_language` for genuinely multilingual content.

## 11.6 Culturally sensitive verbosity

Verbosity preferences interact with cultural conventions. Different languages and cultures have different norms about:

- Formality (use of honorifics, indirect speech).
- Length (some languages convey more in fewer words; others require more elaboration for the same meaning).
- Directness (some cultures expect explicit instructions; others prefer suggestion).
- Number and date formatting.

AAEP does not standardize these. Producers SHOULD adapt the content of `summary_*` fields to be culturally appropriate for the declared `primary_language`. A literal translation that ignores cultural conventions is inferior to a localized rendering.

Producers serving multiple cultures SHOULD work with native speakers and cultural advisors to ensure announcements are appropriate in each. This is particularly important for confirmation events involving irreversible actions, where misunderstanding has high cost.

## 11.7 Number, date, and currency formatting

AAEP does not standardize number, date, or currency formatting. The producer formats values according to its own logic; subscribers MAY re-format if they have richer locale information than the producer used.

For high-precision domains (finance, medical, scientific), producers SHOULD include both a formatted human-readable value AND a machine-readable raw value in event payloads:

```json
{
  "summary_normal": "Transferring ₦240,000 to your savings account.",
  "amount_raw": 240000,
  "currency": "NGN",
  "amount_formatted_ng": "₦240,000.00",
  "amount_formatted_en_us": "$155.42",
  "fx_rate": 1545.13,
  "fx_rate_source": "central_bank_of_nigeria"
}
```

The subscriber selects the formatted variant matching the user's locale, with the raw value as fallback if no formatted variant matches.

## 11.8 Extension hooks for richer language support

Some languages and writing systems have requirements that exceed what `localization_hints` can express. AAEP's extension mechanism supports these via extension namespaces.

### 11.8.1 Worked example: multilingual African languages

The Multilingual African Languages extension (referenced in [Chapter 7 §7.7.1](07-extensions.md) and at [`examples/extensions/multilingual-african-languages/`](../examples/extensions/multilingual-african-languages/)) adds:

- **Tonal mark preservation.** Tonal languages (Yoruba, Igbo, Lingala) carry meaning in tonal marks; the extension specifies how tonal marks are preserved or transformed by subscribers.
- **Transliteration variants.** When users prefer reading their language in Latin script vs native script (e.g., Hausa in Latin vs Ajami script), the extension declares the user's preference and lets the producer emit either form.
- **Dominant-language signaling.** Multilingual users in code-switching contexts (English-Yoruba, Swahili-English) often switch dominant language mid-conversation; the extension carries dominant-language hints.
- **Native-name pronunciation.** Personal and place names from the user's culture should be pronounced in the native form even when text is in English; the extension provides pronunciation hints.

This extension is a reference template for any language community with similar needs. Communities for indigenous languages, regional dialects, and language-revitalization projects are invited to publish similar extensions for their languages.

### 11.8.2 Other potential extensions

Examples of language/region extensions that could be published in the future:

- **Right-to-left enhancement extension.** Richer support for Arabic and Hebrew with bidirectional algorithm hints, RTL number formatting, calligraphic preferences.
- **Sign language interface extension.** When the subscriber is a sign-language renderer, the producer emits semantic-level structured content rather than spoken-language transcripts.
- **Plain language extension.** For users with cognitive disabilities or for whom the primary language is a second language, the producer offers simplified vocabulary and shorter sentences.
- **Dialect and accent extension.** When the user prefers a specific regional dialect or accent for text-to-speech.

These are not yet published; they are listed here as examples of the range of internationalization extensions AAEP's mechanism supports.

## 11.9 Implementer guidance

### 11.9.1 Producer guidance

Producers building AAEP support should:

1. Declare `localization_hints.primary_language` on every event with human-readable text.
2. Provide multiple language variants when feasible (`available_languages`).
3. Work with native speakers for any language being supported, especially for confirmation event wording.
4. Use UTF-8 throughout the producer's codebase.
5. Test with at least one non-Latin script language to surface assumptions about character handling.
6. Adopt the Multilingual African Languages extension (or similar regional extensions) for any deployment serving multilingual users in those regions.

### 11.9.2 Subscriber guidance

Subscribers building AAEP support should:

1. Honor the user's preferred languages declared at runtime (do not hardcode English).
2. Implement BCP 47 tag matching correctly, including fallback rules.
3. Test with right-to-left languages and bidirectional text.
4. Test with combining characters and grapheme clusters.
5. Use locale-appropriate text-to-speech voices and braille translation tables.
6. Provide user controls for language selection and switching.
7. Surface unhandled-language situations gracefully rather than failing silently.

## 11.10 Where to go next

Readers should now proceed to [Chapter 12 (Versioning and evolution)](12-versioning.md), which specifies how AAEP changes over time and what implementers can rely on across versions.

Implementers building multilingual AAEP support should additionally consult the [Multilingual African Languages extension](../examples/extensions/multilingual-african-languages/) as a worked example.
