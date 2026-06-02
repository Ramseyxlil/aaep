"""
translations.py — Translation lookup and interpolation for AAEP events.

Loads JSON translation files from the translations/ directory and provides
functions to look up event summaries by language with format-string
interpolation of structured event fields.
"""

from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
from importlib.resources import files
from pathlib import Path
from typing import Any, Literal

logger = logging.getLogger("aaep_ext_african_languages.translations")


SUPPORTED_LANGUAGES = ("yo", "ha", "ig")
SummaryLevel = Literal["summary_terse", "summary_normal", "summary_detailed"]


# === Translation loading ===

@lru_cache(maxsize=8)
def load_translations(language: str) -> dict[str, Any]:
    """
    Load the translation table for a language.

    Looks first in the installed package's `translations/` directory, then
    falls back to a sibling `translations/` directory (development checkout).

    Raises FileNotFoundError if the language file doesn't exist.
    """
    if language not in SUPPORTED_LANGUAGES:
        raise ValueError(
            f"Unsupported language: {language!r}. "
            f"Supported: {SUPPORTED_LANGUAGES}"
        )

    # Try package resource first (works after pip install)
    try:
        resource = files("aaep_ext_african_languages").joinpath(
            "..", "translations", f"{language}.json"
        )
        if resource.is_file():
            return json.loads(resource.read_text(encoding="utf-8"))
    except (FileNotFoundError, AttributeError, ModuleNotFoundError):
        pass

    # Fallback: walk up to find translations/ in development checkout
    here = Path(__file__).resolve().parent
    candidates = [
        here.parent / "translations" / f"{language}.json",
        here.parent.parent / "translations" / f"{language}.json",
    ]
    for path in candidates:
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))

    raise FileNotFoundError(
        f"Translation file not found for language: {language}. "
        f"Looked in: {candidates}"
    )


# === Translation lookup ===

def translate_summary(
    event_type: str,
    *,
    language: str,
    level: SummaryLevel = "summary_normal",
    event_fields: dict[str, Any] | None = None,
) -> str:
    """
    Look up the translated summary for an event type in the given language.

    Format-string placeholders ({tool}, {action}, {consequence}, etc.) are
    interpolated from event_fields if provided.

    Returns an empty string if the event type is not translated (e.g.,
    streaming events which have no canonical summary).

    Raises ValueError if the language is unsupported.
    """
    translations = load_translations(language)
    events = translations.get("events", {})
    event_entry = events.get(event_type)
    if event_entry is None:
        logger.debug(
            "No translation for %s in %s; returning empty",
            event_type, language,
        )
        return ""

    template = event_entry.get(level, "")
    if not template:
        # Fall back through levels if requested level is empty
        for fallback in ("summary_normal", "summary_terse", "summary_detailed"):
            template = event_entry.get(fallback, "")
            if template:
                break

    if event_fields:
        return interpolate(template, event_fields)
    return template


def select_summary(
    event: dict[str, Any],
    *,
    preferred_languages: list[str],
    level: SummaryLevel = "summary_normal",
) -> str:
    """
    Pick the best available summary for an event given a subscriber's
    preferred languages.

    Selection algorithm:
        1. If event already has summary in a preferred language, use it.
        2. Otherwise, look up translation for the highest-preference
           supported language.
        3. Fall back to the event's existing summary_normal in English.

    Returns the chosen summary string, with interpolation applied.
    """
    existing_summary = event.get(level, "") or event.get("summary_normal", "")
    event_language = event.get("language", "en")

    # If the event is already in a preferred language, use it
    if event_language in preferred_languages and existing_summary:
        return existing_summary

    # Try translation for each preferred language in order
    event_type = event.get("type", "")
    for lang in preferred_languages:
        if lang not in SUPPORTED_LANGUAGES:
            continue
        try:
            translated = translate_summary(
                event_type,
                language=lang,
                level=level,
                event_fields=event,
            )
            if translated:
                return translated
        except FileNotFoundError:
            continue

    # Final fallback: return whatever the event provided
    return existing_summary


# === Interpolation ===

_PLACEHOLDER = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


def interpolate(template: str, fields: dict[str, Any]) -> str:
    """
    Replace {placeholder} markers in a template with field values.

    Differs from str.format() in that missing keys are replaced with an
    empty string instead of raising KeyError. This lets translations
    reference optional fields without strict requirements.

    Examples:

        >>> interpolate("Calling {tool}", {"tool": "send_email"})
        'Calling send_email'

        >>> interpolate("Calling {tool}", {})  # missing tool
        'Calling '
    """
    def _replace(match: re.Match[str]) -> str:
        key = match.group(1)
        value = fields.get(key, "")
        return str(value) if value is not None else ""

    return _PLACEHOLDER.sub(_replace, template)
