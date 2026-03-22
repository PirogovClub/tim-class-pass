"""Deterministic weighted reranker with explainable score breakdown."""

from __future__ import annotations

from typing import Any


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


def _normalize_scores(candidates: list[RerankerCandidate], attr: str) -> None:
    """Min-max normalize a score attribute across all candidates to [0, 1]."""
    vals = [getattr(c, attr) for c in candidates]
    lo, hi = min(vals, default=0), max(vals, default=0)
    span = hi - lo if hi > lo else 1.0
    for c in candidates:
        setattr(c, attr, (getattr(c, attr) - lo) / span)


def rerank(
    candidates: list[RerankerCandidate],
    query_concept_ids: set[str],
    query_alias_terms: set[str],
    boosted_rule_ids: set[str],
    unit_type_weights: dict[str, float] | None = None,
    detected_unit_bias: str = "mixed",
    query_preferences: dict[str, bool] | None = None,
    weights: dict[str, float] | None = None,
) -> list[RerankerCandidate]:
    if not candidates:
        return []

    prefs = query_preferences or {}
    unit_weights = unit_type_weights or {}
    w = weights or {
        "lexical_score": 0.30,
        "vector_score": 0.30,
        "concept_exact_match": 0.15,
        "alias_match": 0.05,
        "unit_type_relevance": 0.04,
        "support_basis_relevance": 0.02,
        "teaching_mode_relevance": 0.02,
        "confidence_score": 0.05,
        "evidence_available": 0.05,
        "timestamp_available": 0.05,
        "provenance_richness": 0.05,
        "lesson_diversity_bonus": 0.03,
        "groundedness": 0.04,
    }

    _normalize_scores(candidates, "lexical_score")
    _normalize_scores(candidates, "vector_score")

    lesson_seen_count: dict[str, int] = {}

    for c in candidates:
        doc = c.doc
        signals: dict[str, float] = {
            "lexical_score": c.lexical_score,
            "vector_score": c.vector_score,
        }

        concept_ids = set(doc.get("canonical_concept_ids") or [])
        signals["concept_exact_match"] = 1.0 if concept_ids & query_concept_ids else 0.0

        aliases = set(a.lower() for a in (doc.get("alias_terms") or []))
        signals["alias_match"] = 1.0 if aliases & query_alias_terms else 0.0

        conf = doc.get("confidence_score")
        signals["confidence_score"] = min(conf, 1.0) if conf and conf > 0 else 0.0

        ev = doc.get("evidence_ids") or []
        signals["evidence_available"] = 1.0 if ev else 0.0

        ts = doc.get("timestamps") or []
        signals["timestamp_available"] = 1.0 if ts else 0.0

        prov = doc.get("provenance") or {}
        prov_count = sum(1 for v in prov.values() if v is not None and v != "" and v != [])
        signals["provenance_richness"] = min(prov_count / 3.0, 1.0)

        unit_type = doc.get("unit_type", "")
        signals["unit_type_relevance"] = unit_weights.get(unit_type, 0.75)

        support_basis = doc.get("support_basis")
        signals["support_basis_relevance"] = 0.0
        if prefs.get("prefers_theory"):
            if support_basis == "transcript_primary":
                signals["support_basis_relevance"] = 1.0
            elif support_basis == "transcript_plus_visual":
                signals["support_basis_relevance"] = 0.7
        elif support_basis:
            signals["support_basis_relevance"] = 0.4

        teaching_mode = doc.get("teaching_mode")
        signals["teaching_mode_relevance"] = 0.0
        if prefs.get("prefers_examples"):
            if teaching_mode == "example":
                signals["teaching_mode_relevance"] = 1.0
            elif teaching_mode == "mixed":
                signals["teaching_mode_relevance"] = 0.7
        elif teaching_mode:
            signals["teaching_mode_relevance"] = 0.4

        grounded_signals = [
            1.0 if ev else 0.0,
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
            c.reasons.append("transcript_theory_match")
        if signals["groundedness"] > 0.6:
            c.reasons.append("well_grounded")

    candidates.sort(key=lambda c: c.final_score, reverse=True)

    for c in candidates:
        lesson_id = c.doc.get("lesson_id") or "corpus"
        seen = lesson_seen_count.get(lesson_id, 0)
        c.signals["lesson_diversity_bonus"] = 1.0 if seen == 0 else 0.0
        c.final_score += c.signals["lesson_diversity_bonus"] * w.get("lesson_diversity_bonus", 0.0)
        lesson_seen_count[lesson_id] = seen + 1

    return candidates
