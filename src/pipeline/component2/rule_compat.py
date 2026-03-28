"""Task 17: Rule direction inference and positive-example compatibility checks.

Deterministic, keyword-based helpers — no LLM calls.
"""

from __future__ import annotations

import re
from typing import Any

_BULLISH_KEYWORDS = re.compile(
    r"(?:выше|above|бычий|bullish|покупк|buy|лонг|long|рост|growth|вверх|upward|отскок\s*вверх|bounce\s*up)",
    re.IGNORECASE,
)
_BEARISH_KEYWORDS = re.compile(
    r"(?:ниже|below|медвежий|bearish|продаж|sell|шорт|short|падени|decline|вниз|downward|отскок\s*вниз|bounce\s*down)",
    re.IGNORECASE,
)
_BREAKOUT_UP_KEYWORDS = re.compile(
    r"(?:пробой\s*вверх|breakout\s*up|пробой\s*уровня\s*сверху|break\s*above)",
    re.IGNORECASE,
)
_BREAKOUT_DOWN_KEYWORDS = re.compile(
    r"(?:пробой\s*вниз|breakout\s*down|пробой\s*уровня\s*снизу|break\s*below)",
    re.IGNORECASE,
)
_REVERSAL_UP_KEYWORDS = re.compile(
    r"(?:разворот\s*вверх|reversal\s*up|бычий\s*разворот|bullish\s*reversal)",
    re.IGNORECASE,
)
_REVERSAL_DOWN_KEYWORDS = re.compile(
    r"(?:разворот\s*вниз|reversal\s*down|медвежий\s*разворот|bearish\s*reversal)",
    re.IGNORECASE,
)
_NEUTRAL_KEYWORDS = re.compile(
    r"(?:флет|flat|боковик|sideways|консолидация|consolidation|range)",
    re.IGNORECASE,
)

OPPOSITE_PAIRS: set[frozenset[str]] = {
    frozenset({"bullish_above", "bearish_below"}),
    frozenset({"breakout_up", "breakout_down"}),
    frozenset({"reversal_up", "reversal_down"}),
    frozenset({"bullish_above", "breakout_down"}),
    frozenset({"bullish_above", "reversal_down"}),
    frozenset({"bearish_below", "breakout_up"}),
    frozenset({"bearish_below", "reversal_up"}),
}


def _collect_text_fields(rule: dict) -> str:
    """Concatenate textual fields from a rule dict for keyword scanning."""
    parts: list[str] = []
    for key in ("rule_text", "rule_text_ru", "concept_id", "subconcept_id"):
        val = rule.get(key)
        if val:
            parts.append(str(val))
    for list_key in ("conditions", "invalidation"):
        for item in rule.get(list_key, []) or []:
            if item:
                parts.append(str(item))
    return " ".join(parts)


def infer_rule_direction(rule: dict) -> str:
    """Return a directional tag for a rule using deterministic keyword matching.

    Possible values: bullish_above, bearish_below, breakout_up, breakout_down,
    reversal_up, reversal_down, neutral, unknown.
    """
    text = _collect_text_fields(rule)
    if not text.strip():
        return "unknown"

    hits: list[str] = []
    if _BREAKOUT_UP_KEYWORDS.search(text):
        hits.append("breakout_up")
    if _BREAKOUT_DOWN_KEYWORDS.search(text):
        hits.append("breakout_down")
    if _REVERSAL_UP_KEYWORDS.search(text):
        hits.append("reversal_up")
    if _REVERSAL_DOWN_KEYWORDS.search(text):
        hits.append("reversal_down")

    if not hits and _BULLISH_KEYWORDS.search(text):
        hits.append("bullish_above")
    if not hits and _BEARISH_KEYWORDS.search(text):
        hits.append("bearish_below")
    if not hits and _NEUTRAL_KEYWORDS.search(text):
        hits.append("neutral")

    if len(hits) == 1:
        return hits[0]
    if len(hits) > 1:
        if _has_conflict(hits):
            return "unknown"
        return hits[0]
    return "unknown"


def _has_conflict(directions: list[str]) -> bool:
    for i, a in enumerate(directions):
        for b in directions[i + 1:]:
            if frozenset({a, b}) in OPPOSITE_PAIRS:
                return True
    return False


def are_directions_conflicting(dir_a: str, dir_b: str) -> bool:
    """True if two direction tags are semantically opposite."""
    if dir_a == dir_b:
        return False
    if "unknown" in (dir_a, dir_b):
        return True
    return frozenset({dir_a, dir_b}) in OPPOSITE_PAIRS


def is_positive_example_compatible(
    rule: dict,
    evidence: dict,
    all_rules_by_id: dict[str, dict],
) -> bool:
    """Return True only if evidence can safely be a positive example for this rule.

    Returns False (block) when evidence is linked to multiple rules with
    conflicting directional meaning. Single-rule evidence is always compatible
    (no contradiction possible).
    """
    linked_rule_ids = evidence.get("linked_rule_ids", []) or []

    if len(linked_rule_ids) <= 1:
        return True

    rule_dir = infer_rule_direction(rule)

    for other_id in linked_rule_ids:
        if other_id == rule.get("rule_id"):
            continue
        other_rule = all_rules_by_id.get(other_id)
        if other_rule is None:
            continue
        other_dir = infer_rule_direction(other_rule)
        if are_directions_conflicting(rule_dir, other_dir):
            return False

    if rule_dir == "unknown":
        return False

    return True


def is_evidence_safe_for_ml(
    evidence: dict,
    all_rules_by_id: dict[str, dict],
) -> bool:
    """Return True only if evidence has no cross-rule directional conflicts.

    Single-rule evidence is always safe (no contradiction possible).
    Multi-rule evidence is blocked if any pair of linked rules has
    conflicting directions or if direction cannot be resolved.
    """
    linked_rule_ids = evidence.get("linked_rule_ids", []) or []
    if not linked_rule_ids:
        return False

    directions: list[str] = []
    for rid in linked_rule_ids:
        rule = all_rules_by_id.get(rid)
        if rule is None:
            continue
        directions.append(infer_rule_direction(rule))

    if not directions:
        return False

    if len(directions) == 1:
        return True

    for i, a in enumerate(directions):
        for b in directions[i + 1:]:
            if are_directions_conflicting(a, b):
                return False

    if any(d == "unknown" for d in directions):
        return False

    return True
