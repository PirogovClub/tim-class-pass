"""Deterministic global ID generation for corpus-level exports.

IDs are compositional (prefix:lesson:local), stable across reruns, and
independent of iteration order or the addition of unrelated lessons.
"""

from __future__ import annotations

import re
import unicodedata


def _transliterate_char(ch: str) -> str:
    _MAP = {
        "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo",
        "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
        "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
        "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch",
        "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
    }
    low = ch.lower()
    return _MAP.get(low, ch)


def _slugify(text: str) -> str:
    """Lowercase, transliterate Cyrillic, collapse non-alnum to underscores."""
    text = unicodedata.normalize("NFKC", text.strip().lower())
    out: list[str] = []
    for ch in text:
        out.append(_transliterate_char(ch))
    text = "".join(out)
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return re.sub(r"_+", "_", text).strip("_")


def slugify_lesson_id(lesson_id: str) -> str:
    """Convert a human-readable lesson ID into a stable slug."""
    return _slugify(lesson_id)


def make_global_id(kind: str, lesson_slug: str, local_id: str) -> str:
    """Build a global ID like 'event:lesson_slug:local_id'."""
    return f"{kind}:{lesson_slug}:{local_id}"


def make_global_node_id(concept_name: str) -> str:
    """Concept nodes are cross-lesson, keyed by normalized concept name."""
    return f"node:{_slugify(concept_name)}"


def make_global_relation_id(source_id: str, relation_type: str, target_id: str) -> str:
    """Deterministic relation ID from endpoints and type."""
    return f"rel:{source_id}:{relation_type}:{target_id}"
