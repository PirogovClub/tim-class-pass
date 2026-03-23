"""Deterministic query intent analysis for Step 3.1 retrieval quality."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# Multi-label intent tags aligned with eval categories and roadmap modes.
INTENT_EXAMPLE_LOOKUP = "example_lookup"
INTENT_SUPPORT_POLICY = "support_policy"
INTENT_INVALIDATION = "invalidation_lookup"
INTENT_CONCEPT_COMPARISON = "concept_comparison"
INTENT_TIMEFRAME = "timeframe_lookup"
INTENT_CROSS_LESSON_CONFLICT = "cross_lesson_conflict_lookup"
INTENT_LESSON_COVERAGE = "lesson_coverage"
INTENT_DIRECT_RULE = "direct_rule_lookup"


@dataclass
class QueryIntentSignals:
    """Structured signals derived from the normalized query string."""

    detected_intents: list[str] = field(default_factory=list)
    prefers_transcript_only: bool = False
    prefers_visual_evidence: bool = False
    mentions_timeframe: bool = False
    mentions_cross_lesson: bool = False
    prefers_examples: bool = False
    prefers_theory: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "detected_intents": list(self.detected_intents),
            "prefers_transcript_only": self.prefers_transcript_only,
            "prefers_visual_evidence": self.prefers_visual_evidence,
            "mentions_timeframe": self.mentions_timeframe,
            "mentions_cross_lesson": self.mentions_cross_lesson,
            "prefers_examples": self.prefers_examples,
            "prefers_theory": self.prefers_theory,
        }


def analyze_query_intents(normalized_query: str) -> QueryIntentSignals:
    """Heuristic multi-label intent detection. Input must be lowercased normalized text."""
    q = normalized_query
    intents: list[str] = []

    example_terms = (
        "example",
        "examples",
        "покажи",
        "пример",
        "визуальн",
        "на графике",
        "chart",
        "screenshot",
        "illustrat",
    )
    prefers_examples = any(t in q for t in example_terms)

    theory_terms = (
        "what is",
        "difference",
        "compare",
        "comparison",
        "что такое",
        "разница",
        "сравн",
        "объясни",
        "versus",
        " vs ",
    )
    prefers_theory = any(t in q for t in theory_terms)

    invalidation_terms = (
        "invalid",
        "invalidate",
        "cancel",
        "cancellation",
        "exception",
        "when rule",
        "не работает",
        "отмен",
        "исключен",
        "условия отмены",
        "не сработает",
    )
    if any(t in q for t in invalidation_terms):
        intents.append(INTENT_INVALIDATION)

    support_policy_terms = (
        "transcript",
        "транскрипт",
        "visual proof",
        "визуальн доказательств",
        "доказательств",
        "support basis",
        "подтверждаются только",
        "только по transcript",
        "требуют визуальн",
    )
    prefers_transcript_only = any(
        t in q
        for t in (
            "only transcript",
            "только по transcript",
            "только transcript",
            "подтверждаются только по transcript",
            "transcript only",
        )
    )
    prefers_visual_evidence = any(
        t in q for t in ("визуальн", "visual", "график", "chart", "screenshot", "доказательств")
    )
    if any(t in q for t in support_policy_terms) or prefers_transcript_only:
        intents.append(INTENT_SUPPORT_POLICY)

    timeframe_terms = (
        "timeframe",
        "таймфрейм",
        "htf",
        "дневн",
        "daily",
        "hour",
        "часов",
        "higher timeframe",
        "старш",
    )
    mentions_timeframe = any(t in q for t in timeframe_terms)
    if mentions_timeframe:
        intents.append(INTENT_TIMEFRAME)

    cross_lesson_terms = (
        "cross lesson",
        "разные урок",
        "несколько урок",
        "общего между",
        "conflict",
        "противореч",
        "связан",
        "какие уроки",
        "уроки обсуждают",
    )
    mentions_cross_lesson = any(t in q for t in cross_lesson_terms)
    if mentions_cross_lesson or ("урок" in q and ("какие" in q or "что общего" in q or "обсужда" in q)):
        intents.append(INTENT_CROSS_LESSON_CONFLICT)
        mentions_cross_lesson = True

    lesson_coverage_terms = ("какие уроки", "уроки обсужда", "о чем рассказывал урок", "lesson cover")
    if any(t in q for t in lesson_coverage_terms):
        intents.append(INTENT_LESSON_COVERAGE)

    if prefers_examples:
        intents.append(INTENT_EXAMPLE_LOOKUP)

    if prefers_theory and INTENT_CONCEPT_COMPARISON not in intents:
        if any(t in q for t in ("разница", "difference", "compare", "сравн", "versus", " vs ")):
            intents.append(INTENT_CONCEPT_COMPARISON)

    rule_terms = (
        "rule",
        "правил",
        "правило",
        "placement",
        "стоп-лосс",
        "stop loss",
        "take profit",
        "тейк",
    )
    if any(t in q for t in rule_terms) and not intents:
        intents.append(INTENT_DIRECT_RULE)

    # De-duplicate preserving order
    seen: set[str] = set()
    ordered: list[str] = []
    for it in intents:
        if it not in seen:
            seen.add(it)
            ordered.append(it)

    return QueryIntentSignals(
        detected_intents=ordered,
        prefers_transcript_only=prefers_transcript_only,
        prefers_visual_evidence=prefers_visual_evidence,
        mentions_timeframe=mentions_timeframe,
        mentions_cross_lesson=mentions_cross_lesson,
        prefers_examples=prefers_examples,
        prefers_theory=prefers_theory,
    )


def unit_bias_from_intents(signals: QueryIntentSignals) -> str:
    """Map intent bundle to legacy detected_unit_bias for API compatibility."""
    if signals.prefers_transcript_only and INTENT_SUPPORT_POLICY in signals.detected_intents:
        return "rule"
    if INTENT_SUPPORT_POLICY in signals.detected_intents and signals.prefers_visual_evidence:
        return "evidence"
    if INTENT_EXAMPLE_LOOKUP in signals.detected_intents:
        return "evidence"
    if INTENT_CONCEPT_COMPARISON in signals.detected_intents or (
        signals.prefers_theory and not signals.prefers_examples
    ):
        return "concept"
    if INTENT_INVALIDATION in signals.detected_intents or INTENT_DIRECT_RULE in signals.detected_intents:
        return "rule"
    if INTENT_TIMEFRAME in signals.detected_intents or INTENT_CROSS_LESSON_CONFLICT in signals.detected_intents:
        return "concept"
    return "mixed"


def query_preferences_from_signals(signals: QueryIntentSignals) -> dict[str, bool]:
    return {
        "prefers_examples": signals.prefers_examples,
        "prefers_theory": signals.prefers_theory,
    }
