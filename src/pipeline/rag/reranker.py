"""Deterministic weighted reranker with explainable score breakdown."""

from __future__ import annotations

from typing import Any

from pipeline.rag.query_intents import (
    INTENT_CONCEPT_COMPARISON,
    INTENT_CROSS_LESSON_CONFLICT,
    INTENT_EXAMPLE_LOOKUP,
    INTENT_SUPPORT_POLICY,
    INTENT_TIMEFRAME,
)


class RerankerCandidate:
    __slots__ = (
        "doc_id",
        "doc",
        "lexical_score",
        "vector_score",
        "graph_boost",
        "signals",
        "final_score",
        "reasons",
    )

    def __init__(self, doc_id: str, doc: dict[str, Any]) -> None:
        self.doc_id = doc_id
        self.doc = doc
        self.lexical_score: float = 0.0
        self.vector_score: float = 0.0
        self.graph_boost: float = 0.0
        self.signals: dict[str, float] = {}
        self.final_score: float = 0.0
        self.reasons: list[str] = []


_TIMEFRAME_MARKERS: tuple[str, ...] = (
    "таймфрейм",
    "таймфреймов",
    "дневн",
    "дневка",
    "дневной уровень",
    "уровень с дневки",
    "часов",
    "часовик",
    "старш",
    "младш",
    "локальн",
    "htf",
)
_TIMEFRAME_CONCEPT_IDS: frozenset[str] = frozenset(
    {
        "node:analiz_taymfreymov",
        "node:soglasovannost_taymfreymov",
        "node:vybor_urovney",
        "node:adaptatsiya_urovney",
        "node:taymfreym",
        "node:taymfreymy",
    }
)
_STOPLOSS_MARKERS: tuple[str, ...] = (
    "стоп-лосс",
    "стоп лосс",
    "стоп-лосса",
    "стоп лосса",
    "stop loss",
    "stop-loss",
    "технический стоп",
    "technical stop",
    "размер стопа",
)
_STOPLOSS_CONCEPT_IDS: frozenset[str] = frozenset(
    {
        "node:stop_loss",
        "node:technical_stop_loss",
        "node:tekhnicheskiy_stop_loss",
        "node:raschetnyy_stop_loss",
        "node:razmer_stop_lossa",
        "node:vliyanie_na_stop_loss",
    }
)


def _normalize_scores(candidates: list[RerankerCandidate], attr: str) -> None:
    """Normalize a score attribute without exaggerating small raw-score gaps."""
    vals = [getattr(c, attr) for c in candidates]
    lo, hi = min(vals, default=0), max(vals, default=0)
    if hi <= 0:
        for c in candidates:
            setattr(c, attr, 0.0)
        return

    # When candidates are already close, divide by max instead of stretching to 0/1.
    if lo >= 0 and hi > 0 and (hi - lo) / hi < 0.35:
        for c in candidates:
            setattr(c, attr, getattr(c, attr) / hi)
        return

    span = hi - lo if hi > lo else 1.0
    for c in candidates:
        setattr(c, attr, (getattr(c, attr) - lo) / span)


def _evidence_requirement_signal(
    doc: dict[str, Any],
    detected_intents: set[str],
    intent_signals: dict[str, Any],
) -> float:
    er = (doc.get("evidence_requirement") or "").lower()
    if not er:
        return 0.0
    score = 0.0
    if INTENT_EXAMPLE_LOOKUP in detected_intents:
        if er == "required":
            score = max(score, 1.0)
        elif er == "optional":
            score = max(score, 0.55)
    if INTENT_SUPPORT_POLICY in detected_intents and intent_signals.get("prefers_visual_evidence"):
        if er == "required":
            score = max(score, 1.0)
        elif er == "optional":
            score = max(score, 0.45)
    if INTENT_SUPPORT_POLICY in detected_intents and intent_signals.get("prefers_transcript_only"):
        score = max(score, 0.35)
    if score == 0.0 and er:
        score = 0.2
    return min(score, 1.0)


def _example_role_signal(doc: dict[str, Any]) -> float:
    unit_type = doc.get("unit_type", "")
    if unit_type == "evidence_ref":
        role = (doc.get("example_role") or "").lower()
        detail = ((doc.get("metadata") or {}).get("evidence_role_detail") or "").lower()
        if role in {"positive_example", "negative_example", "counterexample", "example"}:
            return 1.0
        if detail in {"positive_example", "negative_example", "counterexample"}:
            return 1.0
        if role in {"illustration", "supporting_example"}:
            return 0.75
        if role or detail:
            return 0.55
    if unit_type == "knowledge_event":
        if (doc.get("event_type") or "").lower() == "example":
            return 0.75
        candidate_types = ((doc.get("metadata") or {}).get("candidate_example_types") or [])
        if candidate_types:
            return 0.6
    if unit_type == "rule_card":
        if doc.get("visual_summary"):
            return 0.35
    return 0.0


def _evidence_strength_signal(doc: dict[str, Any]) -> float:
    raw = (doc.get("evidence_strength") or "").lower()
    if not raw:
        meta = doc.get("metadata") or {}
        raw = (meta.get("evidence_strength") or "").lower()
    if raw in ("strong",):
        return 1.0
    if raw in ("moderate", "medium"):
        return 0.65
    if raw in ("weak", "low"):
        return 0.35
    return 0.0


def _timeframe_doc_signal(doc: dict[str, Any]) -> float:
    return _timeframe_specificity_signal(doc)


def _doc_blob(doc: dict[str, Any]) -> str:
    return " ".join(
        [
            str(doc.get("title", "")),
            str(doc.get("text", "")),
            str(doc.get("short_text", "")),
            " ".join(str(k) for k in (doc.get("keywords") or [])),
            " ".join(str(a) for a in (doc.get("alias_terms") or [])),
        ]
    ).lower()


def _timeframe_specificity_signal(doc: dict[str, Any]) -> float:
    blob = _doc_blob(doc)
    concept_ids = {str(cid).lower() for cid in (doc.get("canonical_concept_ids") or [])}
    if concept_ids & _TIMEFRAME_CONCEPT_IDS:
        return 1.0
    marker_hits = sum(1 for marker in _TIMEFRAME_MARKERS if marker in blob)
    if marker_hits >= 2:
        return 1.0
    if marker_hits == 1:
        return 0.75
    return 0.0


def _stoploss_specificity_signal(doc: dict[str, Any]) -> float:
    blob = _doc_blob(doc)
    concept_ids = {str(cid).lower() for cid in (doc.get("canonical_concept_ids") or [])}
    if concept_ids & _STOPLOSS_CONCEPT_IDS:
        return 1.0
    marker_hits = sum(1 for marker in _STOPLOSS_MARKERS if marker in blob)
    if marker_hits >= 2:
        return 1.0
    if marker_hits == 1:
        return 0.75
    return 0.0


def _cross_lesson_unit_signal(doc: dict[str, Any]) -> float:
    ut = doc.get("unit_type", "")
    if ut == "concept_relation":
        return 1.2
    if ut == "concept_node":
        src = doc.get("source_lessons") or (doc.get("metadata") or {}).get("source_lessons")
        if isinstance(src, list) and len(src) > 1:
            return 1.0
    return 0.0


def _intent_evidence_priority_boost(
    doc: dict[str, Any],
    detected_intents: set[str],
    intent_signals: dict[str, Any],
) -> float:
    """Strong boost for evidence_ref when the query explicitly asks for examples or visual proof."""
    wants_evidence = False
    if INTENT_EXAMPLE_LOOKUP in detected_intents:
        wants_evidence = True
    if INTENT_SUPPORT_POLICY in detected_intents and intent_signals.get("prefers_visual_evidence"):
        wants_evidence = True
    if not wants_evidence:
        return 0.0
    return 1.0 if doc.get("unit_type") == "evidence_ref" else 0.0


def _intent_evidence_mismatch_penalty(
    doc: dict[str, Any],
    detected_intents: set[str],
    intent_signals: dict[str, Any],
) -> float:
    wants_evidence = INTENT_EXAMPLE_LOOKUP in detected_intents or (
        INTENT_SUPPORT_POLICY in detected_intents and intent_signals.get("prefers_visual_evidence")
    )
    if not wants_evidence:
        return 0.0
    unit_type = doc.get("unit_type")
    if unit_type == "evidence_ref":
        return 0.0
    if unit_type == "knowledge_event":
        return -0.75
    if unit_type == "rule_card":
        return -0.9
    return -0.55


def _intent_transcript_policy_signal(
    doc: dict[str, Any],
    detected_intents: set[str],
    intent_signals: dict[str, Any],
) -> float:
    if INTENT_SUPPORT_POLICY not in detected_intents or not intent_signals.get("prefers_transcript_only"):
        return 0.0
    support_basis = doc.get("support_basis")
    unit_type = doc.get("unit_type")
    if support_basis == "transcript_primary":
        return 1.25
    if support_basis == "transcript_plus_visual":
        return -1.25
    if unit_type == "evidence_ref":
        return -1.25
    if support_basis:
        return -0.65
    return -0.3


def _intent_concept_priority_signal(
    doc: dict[str, Any],
    detected_intents: set[str],
    query_concept_ids: set[str],
    intent_signals: dict[str, Any],
) -> float:
    unit_type = doc.get("unit_type")
    concept_ids = set(doc.get("canonical_concept_ids") or [])
    concept_overlap = 1.0 if concept_ids & query_concept_ids else 0.0
    timeframe_specificity = _timeframe_specificity_signal(doc)
    stoploss_specificity = _stoploss_specificity_signal(doc)

    if INTENT_EXAMPLE_LOOKUP in detected_intents and intent_signals.get("mentions_stoploss"):
        if unit_type == "evidence_ref":
            if stoploss_specificity and concept_overlap:
                return 1.35
            if stoploss_specificity or concept_overlap:
                return 1.05
            return 0.35
        if unit_type == "rule_card":
            if stoploss_specificity or concept_overlap:
                return 0.45
            return -0.2
        if unit_type == "knowledge_event":
            if stoploss_specificity or concept_overlap:
                return 0.2
            return -0.35
        return -0.15

    if INTENT_CROSS_LESSON_CONFLICT in detected_intents:
        if unit_type == "concept_relation":
            return 1.2 if concept_overlap else 0.95
        if unit_type == "concept_node":
            return 1.05 if concept_overlap else 0.8
        if unit_type == "rule_card":
            return 0.1 if concept_overlap else -0.55
        if unit_type == "knowledge_event":
            return 0.05 if concept_overlap else -0.65
        return -0.35

    if INTENT_TIMEFRAME in detected_intents:
        actionable_timeframe = bool(intent_signals.get("prefers_actionable_rules"))
        prefers_explicit_rules = bool(intent_signals.get("prefers_explicit_rules"))
        if actionable_timeframe:
            if unit_type == "rule_card":
                if timeframe_specificity:
                    return 1.5 if prefers_explicit_rules else 1.35
                return (1.0 if prefers_explicit_rules else 0.85) if concept_overlap else (
                    0.4 if prefers_explicit_rules else 0.25
                )
            if unit_type == "knowledge_event":
                if timeframe_specificity:
                    return 1.05 if prefers_explicit_rules else 1.15
                return (0.6 if prefers_explicit_rules else 0.7) if concept_overlap else (
                    0.05 if prefers_explicit_rules else 0.15
                )
            if unit_type == "concept_node":
                return 0.65 if (timeframe_specificity or concept_overlap) else 0.25
            if unit_type == "concept_relation":
                if timeframe_specificity and concept_overlap:
                    return 0.25
                if timeframe_specificity:
                    return 0.05
                return -0.55
            return -0.3

        if unit_type == "concept_relation":
            if timeframe_specificity:
                return 0.95
            return 0.75 if concept_overlap else 0.55
        if unit_type == "concept_node":
            if timeframe_specificity:
                return 0.9
            return 0.8 if concept_overlap else 0.6
        if unit_type == "rule_card":
            if timeframe_specificity:
                return 0.55
            return 0.2 if concept_overlap else -0.15
        if unit_type == "knowledge_event":
            if timeframe_specificity:
                return 0.45
            return 0.15 if concept_overlap else -0.2
        return -0.15

    if INTENT_CONCEPT_COMPARISON in detected_intents:
        if unit_type == "concept_relation":
            return 1.2 if concept_overlap else 0.95
        if unit_type == "concept_node":
            return 1.05 if concept_overlap else 0.8
        if unit_type == "rule_card":
            return 0.1 if concept_overlap else -0.55
        if unit_type == "knowledge_event":
            return 0.05 if concept_overlap else -0.65
        return -0.35

    return 0.0


def rerank(
    candidates: list[RerankerCandidate],
    query_concept_ids: set[str],
    query_alias_terms: set[str],
    boosted_rule_ids: set[str],
    unit_type_weights: dict[str, float] | None = None,
    detected_unit_bias: str = "mixed",
    query_preferences: dict[str, bool] | None = None,
    weights: dict[str, float] | None = None,
    *,
    detected_intents: set[str] | None = None,
    intent_signals: dict[str, Any] | None = None,
    timestamp_scale: float = 1.0,
    evidence_scale: float = 1.0,
) -> list[RerankerCandidate]:
    if not candidates:
        return []

    intents = detected_intents or set()
    isignals = intent_signals or {}
    prefs = query_preferences or {}
    unit_weights = unit_type_weights or {}
    w = weights or {
        "lexical_score": 0.26,
        "vector_score": 0.26,
        "graph_boost": 0.14,
        "concept_exact_match": 0.12,
        "alias_match": 0.05,
        "unit_type_relevance": 0.06,
        "support_basis_relevance": 0.04,
        "teaching_mode_relevance": 0.03,
        "evidence_requirement_relevance": 0.04,
        "evidence_strength_relevance": 0.03,
        "confidence_score": 0.04,
        "evidence_available": 0.06,
        "timestamp_available": 0.05,
        "provenance_richness": 0.04,
        "lesson_diversity_bonus": 0.02,
        "groundedness": 0.04,
        "intent_cross_lesson_boost": 0.12,
        "intent_timeframe_boost": 0.14,
        "intent_evidence_priority_boost": 0.34,
        "example_role_relevance": 0.06,
        "intent_evidence_mismatch_penalty": 0.18,
        "intent_transcript_policy_signal": 0.28,
        "intent_concept_priority_signal": 0.38,
    }

    _normalize_scores(candidates, "lexical_score")
    _normalize_scores(candidates, "vector_score")

    lesson_seen_count: dict[str, int] = {}

    for c in candidates:
        doc = c.doc
        signals: dict[str, float] = {
            "lexical_score": c.lexical_score,
            "vector_score": c.vector_score,
            "graph_boost": max(0.0, min(c.graph_boost, 1.0)),
        }

        concept_ids = set(doc.get("canonical_concept_ids") or [])
        signals["concept_exact_match"] = 1.0 if concept_ids & query_concept_ids else 0.0

        aliases = set(a.lower() for a in (doc.get("alias_terms") or []))
        signals["alias_match"] = 1.0 if aliases & query_alias_terms else 0.0

        conf = doc.get("confidence_score")
        signals["confidence_score"] = min(conf, 1.0) if conf and conf > 0 else 0.0

        ev = doc.get("evidence_ids") or []
        signals["evidence_available"] = (1.0 if ev else 0.0) * max(evidence_scale, 0.0)

        ts = doc.get("timestamps") or []
        signals["timestamp_available"] = (1.0 if ts else 0.0) * max(timestamp_scale, 0.0)

        prov = doc.get("provenance") or {}
        prov_count = sum(1 for v in prov.values() if v is not None and v != "" and v != [])
        signals["provenance_richness"] = min(prov_count / 3.0, 1.0)

        unit_type = doc.get("unit_type", "")
        signals["unit_type_relevance"] = unit_weights.get(unit_type, 0.75)

        support_basis = doc.get("support_basis")
        signals["support_basis_relevance"] = 0.0
        if isignals.get("prefers_transcript_only") and INTENT_SUPPORT_POLICY in intents:
            if support_basis == "transcript_primary":
                signals["support_basis_relevance"] = 1.0
            elif support_basis == "transcript_plus_visual":
                signals["support_basis_relevance"] = 0.15
            elif support_basis:
                signals["support_basis_relevance"] = 0.25
        elif isignals.get("prefers_visual_evidence") and INTENT_SUPPORT_POLICY in intents:
            if support_basis == "transcript_plus_visual":
                signals["support_basis_relevance"] = 1.0
            elif support_basis == "transcript_primary":
                signals["support_basis_relevance"] = 0.35
            elif support_basis:
                signals["support_basis_relevance"] = 0.45
        elif prefs.get("prefers_theory"):
            if support_basis == "transcript_primary":
                signals["support_basis_relevance"] = 1.0
            elif support_basis == "transcript_plus_visual":
                signals["support_basis_relevance"] = 0.7
        elif support_basis:
            signals["support_basis_relevance"] = 0.4

        teaching_mode = doc.get("teaching_mode")
        signals["teaching_mode_relevance"] = 0.0
        if INTENT_EXAMPLE_LOOKUP in intents or (
            prefs.get("prefers_examples") and INTENT_SUPPORT_POLICY not in intents
        ):
            if teaching_mode == "example":
                signals["teaching_mode_relevance"] = 1.0
            elif teaching_mode == "mixed":
                signals["teaching_mode_relevance"] = 0.75
            elif teaching_mode == "theory":
                signals["teaching_mode_relevance"] = 0.2
        elif prefs.get("prefers_examples"):
            if teaching_mode == "example":
                signals["teaching_mode_relevance"] = 1.0
            elif teaching_mode == "mixed":
                signals["teaching_mode_relevance"] = 0.7
            elif teaching_mode:
                signals["teaching_mode_relevance"] = 0.4
        elif prefs.get("prefers_theory"):
            if teaching_mode == "theory":
                signals["teaching_mode_relevance"] = 1.0
            elif teaching_mode == "mixed":
                signals["teaching_mode_relevance"] = 0.6
            elif teaching_mode:
                signals["teaching_mode_relevance"] = 0.4
        elif teaching_mode:
            signals["teaching_mode_relevance"] = 0.4

        signals["evidence_requirement_relevance"] = _evidence_requirement_signal(doc, intents, isignals)
        signals["evidence_strength_relevance"] = (
            _evidence_strength_signal(doc) if doc.get("unit_type") == "evidence_ref" else 0.0
        )
        signals["example_role_relevance"] = _example_role_signal(doc)

        signals["intent_timeframe_boost"] = (
            _timeframe_doc_signal(doc) if INTENT_TIMEFRAME in intents else 0.0
        )
        signals["intent_cross_lesson_boost"] = (
            _cross_lesson_unit_signal(doc) if INTENT_CROSS_LESSON_CONFLICT in intents else 0.0
        )
        signals["intent_evidence_priority_boost"] = _intent_evidence_priority_boost(doc, intents, isignals)
        signals["intent_evidence_mismatch_penalty"] = _intent_evidence_mismatch_penalty(doc, intents, isignals)
        signals["intent_transcript_policy_signal"] = _intent_transcript_policy_signal(doc, intents, isignals)
        signals["intent_concept_priority_signal"] = _intent_concept_priority_signal(
            doc,
            intents,
            query_concept_ids,
            isignals,
        )

        grounded_signals = [
            1.0 if ev or doc.get("unit_type") == "evidence_ref" else 0.0,
            1.0 if ts else 0.0,
            min(prov_count / 3.0, 1.0),
            1.0 if support_basis and support_basis != "inferred" else 0.0,
        ]
        signals["groundedness"] = sum(grounded_signals) / len(grounded_signals)
        signals["lesson_diversity_bonus"] = 0.0

        if doc.get("doc_id") in boosted_rule_ids:
            signals["concept_exact_match"] = max(signals["concept_exact_match"], 0.8)
            c.reasons.append("boosted_by_concept_rule_map")
            c.graph_boost = max(c.graph_boost, 1.0)

        score = sum(signals.get(k, 0.0) * w.get(k, 0.0) for k in w)
        c.signals = signals
        c.final_score = score

        if signals["concept_exact_match"] > 0:
            c.reasons.append("concept_match")
        if signals["alias_match"] > 0:
            c.reasons.append("alias_match")
        if c.lexical_score > 0.5:
            c.reasons.append("strong_lexical")
        if c.vector_score > 0.5:
            c.reasons.append("strong_vector")
        if unit_weights.get(unit_type, 0.75) >= 1.0 and detected_unit_bias != "mixed":
            c.reasons.append("unit_bias_match")
        if signals["teaching_mode_relevance"] > 0.6:
            c.reasons.append("example_mode_match")
        if signals["support_basis_relevance"] > 0.6:
            c.reasons.append("support_basis_match")
        if signals["groundedness"] > 0.6:
            c.reasons.append("well_grounded")
        if signals["evidence_requirement_relevance"] > 0.55:
            c.reasons.append("evidence_requirement_match")
        if signals["intent_timeframe_boost"] > 0:
            c.reasons.append("timeframe_intent_match")
        if signals["intent_cross_lesson_boost"] > 0:
            c.reasons.append("cross_lesson_intent_match")
        if signals["intent_evidence_priority_boost"] > 0:
            c.reasons.append("evidence_intent_priority")
        if signals["intent_concept_priority_signal"] > 0.6:
            c.reasons.append("concept_intent_priority")
        if signals["intent_evidence_mismatch_penalty"] < 0:
            c.reasons.append("evidence_intent_mismatch")
        if signals["intent_transcript_policy_signal"] > 0.6:
            c.reasons.append("transcript_primary_match")
        elif signals["intent_transcript_policy_signal"] < -0.6:
            c.reasons.append("transcript_policy_mismatch")

    candidates.sort(key=lambda c: c.final_score, reverse=True)

    for c in candidates:
        lesson_id = c.doc.get("lesson_id") or "corpus"
        seen = lesson_seen_count.get(lesson_id, 0)
        c.signals["lesson_diversity_bonus"] = 1.0 if seen == 0 else 0.0
        c.final_score += c.signals["lesson_diversity_bonus"] * w.get("lesson_diversity_bonus", 0.0)
        lesson_seen_count[lesson_id] = seen + 1

    return candidates
