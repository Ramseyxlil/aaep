"""
Multilingual African Languages Extension for AAEP.

Provides idiomatic translations of AAEP event summaries into Yoruba, Hausa,
and Igbo, plus helper functions for locale-aware speech rates, tone-mark
handling, and pluralization.

Public API:

    from aaep_ext_african_languages import (
        translate_summary,    # Get a translated summary for one event
        select_summary,       # Pick the best language with fallback
        recommended_pace,     # Recommended pace_wpm range per language
        preserve_tone_marks,  # Verify Unicode diacritics intact
        pluralize,            # Language-specific plural rules
        SUPPORTED_LANGUAGES,  # ('yo', 'ha', 'ig')
    )

See README.md for usage examples and the canonical translation table.
"""

from __future__ import annotations

__version__ = "1.0.0"
__author__ = "Abdulrafiu Izuafa"
__email__ = "Abdulrafiu@izusoft.tech"
__license__ = "MIT"
__aaep_spec_version__ = "1.0.0"
__extension_id__ = "aaep-ext-african-languages"


from aaep_ext_african_languages.translations import (
    SUPPORTED_LANGUAGES,
    interpolate,
    load_translations,
    select_summary,
    translate_summary,
)
from aaep_ext_african_languages.locale_data import (
    PACE_WPM,
    pluralize,
    preserve_tone_marks,
    recommended_pace,
    script_for_language,
)


__all__ = [
    "__version__",
    "__author__",
    "__email__",
    "__license__",
    "__aaep_spec_version__",
    "__extension_id__",
    # Translations API
    "SUPPORTED_LANGUAGES",
    "translate_summary",
    "select_summary",
    "interpolate",
    "load_translations",
    # Locale data API
    "PACE_WPM",
    "recommended_pace",
    "preserve_tone_marks",
    "pluralize",
    "script_for_language",
]
