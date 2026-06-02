"""
locale_data.py — Locale-aware data and helpers.

Provides per-language metadata that producers and subscribers need beyond
raw translations: speech-rate hints, script identification, pluralization
rules, and tone-mark verification.
"""

from __future__ import annotations

import unicodedata
from typing import Literal


# === Speech rate recommendations ===

# Recommended pace_wpm ranges for each language.
# Tonal languages (Yoruba, Igbo) get slower defaults because tone perception
# requires more processing time; syllable-timed Hausa gets a faster default.
# English reference range included for comparison.
PACE_WPM: dict[str, dict[str, int]] = {
    "yo": {"min": 110, "max": 150, "default": 130},
    "ha": {"min": 130, "max": 170, "default": 150},
    "ig": {"min": 110, "max": 150, "default": 130},
    "en": {"min": 140, "max": 180, "default": 160},
}


def recommended_pace(language: str) -> dict[str, int]:
    """
    Return the recommended pace_wpm range for a language.

    Returns a dict with 'min', 'max', and 'default' keys.
    Falls back to English range for unrecognized languages.
    """
    return PACE_WPM.get(language, PACE_WPM["en"])


# === Script identification ===

Script = Literal["latin", "ajami"]

_DEFAULT_SCRIPTS: dict[str, Script] = {
    "yo": "latin",
    "ha": "latin",   # Boko (Latin) is the modern standard for Hausa
    "ig": "latin",
}

# Hausa supports both Latin (Boko) and Arabic (Ajami) scripts.
_AVAILABLE_SCRIPTS: dict[str, tuple[Script, ...]] = {
    "yo": ("latin",),
    "ha": ("latin", "ajami"),
    "ig": ("latin",),
}


def script_for_language(language: str) -> Script:
    """Return the default script for a language. Defaults to 'latin'."""
    return _DEFAULT_SCRIPTS.get(language, "latin")


def available_scripts(language: str) -> tuple[Script, ...]:
    """Return all scripts available for a language."""
    return _AVAILABLE_SCRIPTS.get(language, ("latin",))


# === Tone mark handling ===

# Unicode combining diacritic ranges relevant to these languages.
_COMBINING_DIACRITICS = range(0x0300, 0x036F + 1)

# Precomposed characters with dot-below (Igbo: ị ọ ụ; Yoruba: ẹ ọ ṣ)
_DOT_BELOW_CHARS = frozenset({
    "ị", "Ị", "ọ", "Ọ", "ụ", "Ụ",  # Igbo
    "ẹ", "Ẹ", "ṣ", "Ṣ",            # Yoruba
})


def has_tone_marks(text: str) -> bool:
    """
    Detect whether a string contains tone marks or relevant diacritics.

    Returns True if any character has a combining diacritic in the relevant
    Unicode range, or if any character is one of the precomposed letters
    Yoruba and Igbo orthographies depend on.
    """
    for char in text:
        if ord(char) in _COMBINING_DIACRITICS:
            return True
        if char in _DOT_BELOW_CHARS:
            return True
        # Decomposed form check
        decomposed = unicodedata.normalize("NFD", char)
        for ch in decomposed:
            if ord(ch) in _COMBINING_DIACRITICS:
                return True
    return False


def preserve_tone_marks(text: str, *, normalize_to: str = "NFC") -> str:
    """
    Normalize a string to the specified Unicode form, preserving diacritics.

    NFC (default) is the recommended form for storage and display: composed
    characters where available, combining diacritics where not. NFD produces
    fully decomposed form, which some TTS engines prefer.

    This function does NOT strip diacritics — it just normalizes their form.
    Subscribers MUST NOT strip diacritics from Yoruba or Igbo text.
    """
    if normalize_to not in {"NFC", "NFD", "NFKC", "NFKD"}:
        raise ValueError(f"Unsupported normalization form: {normalize_to!r}")
    return unicodedata.normalize(normalize_to, text)


def strip_tone_marks(text: str) -> str:
    """
    Remove tone marks from a string (LOSSY: meaning may be lost).

    Use only when targeting a TTS engine that cannot handle Unicode
    diacritics. The result should be marked with
    `localization_hints.fallback_applied = true`.

    Returns text with combining diacritics removed and dot-below characters
    mapped to their plain forms.
    """
    # Decompose, then drop combining marks
    decomposed = unicodedata.normalize("NFD", text)
    no_combining = "".join(
        ch for ch in decomposed
        if unicodedata.category(ch) != "Mn"
    )
    # Map remaining precomposed dot-below characters
    plain_map = str.maketrans({
        "ị": "i", "Ị": "I",
        "ọ": "o", "Ọ": "O",
        "ụ": "u", "Ụ": "U",
        "ẹ": "e", "Ẹ": "E",
        "ṣ": "s", "Ṣ": "S",
    })
    return no_combining.translate(plain_map)


# === Pluralization ===

def pluralize(noun: str, count: int, *, language: str) -> str:
    """
    Apply language-specific pluralization rules.

    Yoruba and Igbo do not change noun form for plural; quantity is
    expressed through numerals or context. Hausa has multiple plural
    patterns (including broken plurals); we provide a minimal interface
    that returns the noun unchanged with a count, letting callers compose
    the surrounding phrase naturally.

    For English fallback, applies a naive "+s" rule.
    """
    if language in ("yo", "ig"):
        # No grammatical plural marker; numeric context conveys quantity
        return noun
    if language == "ha":
        # Hausa has rich plural morphology that depends on the noun's
        # phonological pattern. A full implementation needs a noun-class
        # lookup. For this reference impl, return the noun unchanged
        # and document this limitation.
        return noun
    if language == "en":
        if count == 1:
            return noun
        # Naive English: handle common irregulars + simple +s
        irregulars = {
            "child": "children", "person": "people", "man": "men",
            "woman": "women", "foot": "feet", "tooth": "teeth",
        }
        if noun.lower() in irregulars:
            return irregulars[noun.lower()]
        if noun.endswith(("s", "x", "z", "ch", "sh")):
            return noun + "es"
        if noun.endswith("y") and len(noun) > 1 and noun[-2] not in "aeiou":
            return noun[:-1] + "ies"
        return noun + "s"
    return noun
