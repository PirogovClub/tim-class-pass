"""Canonicalization utilities: normalize labels and generate language-neutral canonical IDs.

Canonical IDs are stable, deterministic slugs for machine automation.
They use the lexicon for known terms and fall back to transliteration/slugification.
"""

from __future__ import annotations

import re
import unicodedata

from pipeline.component2.canonical_lexicon import lookup_canonical

_CYRILLIC_TO_LATIN: dict[str, str] = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


def _transliterate(text: str) -> str:
    """Transliterate Cyrillic characters to Latin equivalents."""
    result: list[str] = []
    for ch in text:
        if ch in _CYRILLIC_TO_LATIN:
            result.append(_CYRILLIC_TO_LATIN[ch])
        elif ch.lower() in _CYRILLIC_TO_LATIN:
            mapped = _CYRILLIC_TO_LATIN[ch.lower()]
            result.append(mapped.capitalize() if ch.isupper() and mapped else mapped)
        else:
            result.append(ch)
    return "".join(result)


def normalize_label(text: str) -> str:
    """Lowercase, trim, collapse whitespace, strip punctuation noise."""
    text = text.strip().lower()
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"[^\w\s-]", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _slugify(text: str) -> str:
    """Convert normalized label to a slug: transliterate, lowercase, underscores."""
    text = _transliterate(text.lower())
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "unknown"


def make_canonical_id(kind: str, label: str) -> str:
    """Return e.g. 'concept:level', 'subconcept:false_breakout'.

    Lexicon lookup first, falls back to slugification of the normalized label.
    """
    normalized = normalize_label(label)
    slug = lookup_canonical(normalized)
    if slug is None:
        slug = _slugify(normalized)
    return f"{kind}:{slug}"


def canonicalize_concept(text: str | None) -> str | None:
    """Return canonical concept_id or None if text is empty/None."""
    if not text or not text.strip():
        return None
    return make_canonical_id("concept", text)


def canonicalize_subconcept(text: str | None) -> str | None:
    """Return canonical subconcept_id or None if text is empty/None."""
    if not text or not text.strip():
        return None
    return make_canonical_id("subconcept", text)


def canonicalize_short_statement(kind: str, text: str) -> str:
    """For conditions/invalidations/exceptions: return a canonical_id slug.

    Tries lexicon first, falls back to slugification of the full statement.
    """
    return make_canonical_id(kind, text)


EVENT_TYPE_TO_RULE_TYPE: dict[str, str] = {
    "definition": "definition",
    "rule_statement": "rule",
    "condition": "condition",
    "invalidation": "invalidation",
    "exception": "exception",
    "comparison": "comparison",
    "warning": "warning",
    "process_step": "process_step",
    "algorithm_hint": "algorithm_hint",
    "example": "example",
}


def classify_rule_type(event_type: str) -> str | None:
    """Map an event_type to its rule_type classification."""
    return EVENT_TYPE_TO_RULE_TYPE.get(event_type)
