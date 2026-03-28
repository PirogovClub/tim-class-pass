"""Hybrid retriever: lexical + vector + concept expansion + reranking."""

from __future__ import annotations

import re
from typing import Any

from pipeline.rag.contracts import GraphExpansionResult
from pipeline.rag.config import RAGConfig
from pipeline.rag.embedding_index import EmbeddingIndex
from pipeline.rag.graph_expand import ConceptExpander
from pipeline.rag.lexical_index import LexicalIndex
from pipeline.rag.query_intents import (
    QueryIntentSignals,
    analyze_query_intents,
    query_preferences_from_signals,
    unit_bias_from_intents,
)
from pipeline.rag.reranker import RerankerCandidate, rerank
from pipeline.rag.store import DocStore

_SPACE_RE = re.compile(r"\s+")
_TIMEFRAME_MARKERS: tuple[str, ...] = (
    "таймфрейм",
    "таймфреймов",
    "дневн",
    "дневка",
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


def _normalize_query(query: str) -> str:
    return _SPACE_RE.sub(" ", query.strip().lower())


def _is_actionable_timeframe(iq: QueryIntentSignals) -> bool:
    intents = set(iq.detected_intents)
    return (
        "timeframe_lookup" in intents
        and "cross_lesson_conflict_lookup" not in intents
        and iq.prefers_actionable_rules
    )


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


def _timeframe_doc_matches(doc: dict[str, Any]) -> bool:
    concept_ids = {str(cid).lower() for cid in (doc.get("canonical_concept_ids") or [])}
    if concept_ids & _TIMEFRAME_CONCEPT_IDS:
        return True
    blob = _doc_blob(doc)
    return any(marker in blob for marker in _TIMEFRAME_MARKERS)


def _stoploss_doc_matches(doc: dict[str, Any]) -> bool:
    concept_ids = {str(cid).lower() for cid in (doc.get("canonical_concept_ids") or [])}
    if concept_ids & _STOPLOSS_CONCEPT_IDS:
        return True
    blob = _doc_blob(doc)
    return any(marker in blob for marker in _STOPLOSS_MARKERS)


def _extra_seed_doc_ids(
    store: DocStore,
    query_concept_ids: set[str],
    boosted_rule_ids: set[str],
    iq: QueryIntentSignals,
) -> set[str]:
    wants_evidence = "example_lookup" in iq.detected_intents or (
        "support_policy" in iq.detected_intents and iq.prefers_visual_evidence
    )
    wants_timeframe_rules = _is_actionable_timeframe(iq)
    intents = set(iq.detected_intents)
    # Surface concept_node / concept_relation for timeframe queries (improves timeframe_concept_top3 eval signal).
    wants_timeframe_concepts = (
        "timeframe_lookup" in intents and "cross_lesson_conflict_lookup" not in intents
    )
    if not wants_evidence and not wants_timeframe_rules and not wants_timeframe_concepts:
        return set()

    qc = {str(c).lower() for c in query_concept_ids}
    tf_lower = {str(c).lower() for c in _TIMEFRAME_CONCEPT_IDS}

    seeded: set[str] = set()
    for doc in store.get_all():
        unit_type = doc.get("unit_type")
        concept_ids = {str(cid).lower() for cid in (doc.get("canonical_concept_ids") or [])}
        source_rule_ids = set(doc.get("source_rule_ids") or [])
        if wants_timeframe_concepts and unit_type in {"concept_node", "concept_relation"}:
            if qc and concept_ids & qc:
                seeded.add(doc["doc_id"])
                continue
            if concept_ids & tf_lower:
                seeded.add(doc["doc_id"])
                continue
        if wants_evidence and unit_type == "evidence_ref":
            if query_concept_ids and concept_ids & query_concept_ids:
                seeded.add(doc["doc_id"])
                continue
            if iq.mentions_stoploss and (
                _stoploss_doc_matches(doc) or concept_ids & _STOPLOSS_CONCEPT_IDS
            ):
                seeded.add(doc["doc_id"])
                continue
            if boosted_rule_ids and source_rule_ids & boosted_rule_ids:
                seeded.add(doc["doc_id"])
                continue
        if not wants_timeframe_rules or unit_type not in {"rule_card", "knowledge_event"}:
            continue
        if _timeframe_doc_matches(doc):
            seeded.add(doc["doc_id"])
            continue
        if concept_ids & (_TIMEFRAME_CONCEPT_IDS | query_concept_ids):
            seeded.add(doc["doc_id"])
            continue
        if boosted_rule_ids and source_rule_ids & boosted_rule_ids:
            seeded.add(doc["doc_id"])
    return seeded


def _unit_weight_map(cfg: RAGConfig, unit_bias: str, iq: QueryIntentSignals) -> dict[str, float]:
    weights = dict(cfg.default_unit_weights)
    intents = set(iq.detected_intents)
    actionable_timeframe = _is_actionable_timeframe(iq)
    cross_lesson = "cross_lesson_conflict_lookup" in intents
    conceptual_timeframe = "timeframe_lookup" in intents and not cross_lesson and not actionable_timeframe

    if unit_bias == "rule":
        weights["rule_card"] = max(weights.get("rule_card", 1.0), 1.12)
        weights["knowledge_event"] = max(weights.get("knowledge_event", 0.95), 1.0)
    elif unit_bias == "evidence":
        weights["evidence_ref"] = max(weights.get("evidence_ref", 0.95), 1.28)
        weights["knowledge_event"] = min(weights.get("knowledge_event", 0.95), 0.72)
        weights["rule_card"] = min(weights.get("rule_card", 1.0), 0.88)
    elif unit_bias == "concept":
        weights["concept_node"] = max(weights.get("concept_node", 0.85), 1.3)
        weights["concept_relation"] = max(weights.get("concept_relation", 0.8), 1.35)

    if "example_lookup" in intents:
        weights["evidence_ref"] = max(weights.get("evidence_ref", 0.95), 1.8)
        weights["knowledge_event"] = min(weights.get("knowledge_event", 0.95), 0.36)
        weights["rule_card"] = min(weights.get("rule_card", 1.0), 0.52)
    if "support_policy" in intents and iq.prefers_visual_evidence:
        weights["evidence_ref"] = max(weights.get("evidence_ref", 0.95), 1.95)
        weights["knowledge_event"] = min(weights.get("knowledge_event", 0.95), 0.55)
        weights["rule_card"] = min(weights.get("rule_card", 1.0), 0.48)
    if "support_policy" in intents and iq.prefers_transcript_only:
        weights["rule_card"] = max(weights.get("rule_card", 1.0), 1.28)
        weights["knowledge_event"] = min(weights.get("knowledge_event", 0.95), 0.92)
        weights["evidence_ref"] = min(weights.get("evidence_ref", 0.95), 0.25)
    if cross_lesson:
        weights["concept_node"] = max(weights.get("concept_node", 0.85), 1.5)
        weights["concept_relation"] = max(weights.get("concept_relation", 0.8), 1.6)
        weights["knowledge_event"] = min(weights.get("knowledge_event", 0.95), 0.58)
        weights["rule_card"] = min(weights.get("rule_card", 1.0), 0.7)
    elif actionable_timeframe:
        weights["rule_card"] = max(weights.get("rule_card", 1.0), 1.45)
        weights["knowledge_event"] = max(weights.get("knowledge_event", 0.95), 1.2)
        weights["concept_node"] = max(weights.get("concept_node", 0.85), 1.05)
        weights["concept_relation"] = min(weights.get("concept_relation", 0.8), 0.95)
        weights["evidence_ref"] = min(weights.get("evidence_ref", 0.95), 0.8)
    elif conceptual_timeframe:
        weights["concept_node"] = max(weights.get("concept_node", 0.85), 1.25)
        weights["concept_relation"] = max(weights.get("concept_relation", 0.8), 1.15)

    return weights


def _scales_for_intents(cfg: RAGConfig, iq: QueryIntentSignals) -> tuple[float, float]:
    ts_scale = cfg.step31_timestamp_scale
    ev_scale = cfg.step31_evidence_scale
    if "example_lookup" in iq.detected_intents:
        ts_scale *= 1.55
        ev_scale *= 1.7
    if "support_policy" in iq.detected_intents and iq.prefers_visual_evidence:
        ev_scale *= 1.85
    if "support_policy" in iq.detected_intents and iq.prefers_transcript_only:
        ev_scale *= 0.45
    return ts_scale, ev_scale


class HybridRetriever:
    def __init__(
        self,
        store: DocStore,
        lexical: LexicalIndex,
        embedding: EmbeddingIndex,
        expander: ConceptExpander,
        cfg: RAGConfig | None = None,
    ) -> None:
        self._store = store
        self._lexical = lexical
        self._embedding = embedding
        self._expander = expander
        self._cfg = cfg or RAGConfig()

    def search(
        self,
        query: str,
        top_k: int | None = None,
        unit_types: list[str] | None = None,
        lesson_ids: list[str] | None = None,
        concept_ids: list[str] | None = None,
        min_confidence: float | None = None,
        require_evidence: bool = False,
    ) -> dict[str, Any]:
        cfg = self._cfg
        final_k = top_k or cfg.final_top_k
        normalized_query = _normalize_query(query)
        iq = analyze_query_intents(normalized_query)
        unit_bias = unit_bias_from_intents(iq)
        query_preferences = query_preferences_from_signals(iq)

        expansion = GraphExpansionResult()
        if cfg.enable_graph_expand:
            expansion = self._expander.expand_query(normalized_query)
        query_concept_ids = set(expansion.canonical_concept_ids) | set(expansion.expanded_concept_ids)
        boosted_rule_ids = set(expansion.boosted_rule_ids)
        query_alias_terms = set(expansion.detected_terms) | set(expansion.lexical_expansion_terms)

        filter_ids: set[str] | None = None
        if lesson_ids or concept_ids or min_confidence is not None:
            filter_ids = self._store.filter_ids(
                unit_types=unit_types,
                lesson_ids=lesson_ids,
                concept_ids=concept_ids,
                min_confidence=min_confidence,
            )
        elif unit_types:
            filter_ids = self._store.filter_ids(unit_types=unit_types)

        lex_hits = self._lexical.search(
            normalized_query,
            top_k=cfg.lexical_top_k,
            unit_types=unit_types,
            lesson_ids=lesson_ids,
            concept_ids=concept_ids,
            allowed_ids=filter_ids,
            alias_terms=sorted(query_alias_terms),
        )
        lex_map = {did: score for did, score in lex_hits}

        vector_query = normalized_query
        if expansion.lexical_expansion_terms:
            extra = " ".join(expansion.lexical_expansion_terms[:24])
            vector_query = f"{normalized_query} {extra}".strip()

        q_emb = self._embedding.encode_query(vector_query)
        vec_hits = self._embedding.search(
            q_emb,
            top_k=cfg.vector_top_k,
            unit_types=unit_types,
            lesson_ids=lesson_ids,
            allowed_ids=filter_ids,
        )
        vec_map = {did: score for did, score in vec_hits}

        seeded_doc_ids = _extra_seed_doc_ids(self._store, query_concept_ids, boosted_rule_ids, iq)

        all_ids = list(set(lex_map.keys()) | set(vec_map.keys()) | seeded_doc_ids)
        all_ids.sort(
            key=lambda did: (
                1 if did in seeded_doc_ids else 0,
                max(lex_map.get(did, 0.0), vec_map.get(did, 0.0)),
            ),
            reverse=True,
        )
        all_ids = all_ids[: cfg.merged_top_k]
        candidates: list[RerankerCandidate] = []
        for did in all_ids:
            doc = self._store.get(did)
            if doc is None:
                continue
            c = RerankerCandidate(did, doc)
            c.lexical_score = lex_map.get(did, 0.0)
            c.vector_score = vec_map.get(did, 0.0)
            if did in seeded_doc_ids and doc.get("unit_type") == "evidence_ref":
                c.graph_boost = max(c.graph_boost, 1.0)
            if did in boosted_rule_ids:
                c.graph_boost = max(c.graph_boost, cfg.exact_alias_boost)
            elif query_concept_ids & set(doc.get("canonical_concept_ids") or []):
                c.graph_boost = max(c.graph_boost, cfg.exact_alias_boost * 0.5)
            candidates.append(c)

        ts_scale, ev_scale = _scales_for_intents(cfg, iq)
        ranked = rerank(
            candidates,
            query_concept_ids=query_concept_ids,
            query_alias_terms=query_alias_terms,
            boosted_rule_ids=boosted_rule_ids,
            unit_type_weights=_unit_weight_map(cfg, unit_bias, iq),
            detected_unit_bias=unit_bias,
            query_preferences=query_preferences,
            weights=cfg.reranker_weights,
            detected_intents=set(iq.detected_intents),
            intent_signals=iq.to_dict(),
            timestamp_scale=ts_scale,
            evidence_scale=ev_scale,
        )

        if require_evidence:
            ranked = [c for c in ranked if (c.doc.get("evidence_ids") or [])]

        top_hits: list[dict[str, Any]] = []
        for c in ranked[:final_k]:
            top_hits.append({
                "doc_id": c.doc_id,
                "global_id": c.doc_id,
                "unit_type": c.doc.get("unit_type", ""),
                "lesson_id": c.doc.get("lesson_id", ""),
                "concept": c.doc.get("concept") or "",
                "subconcept": c.doc.get("subconcept") or "",
                "title": c.doc.get("title", ""),
                "text_snippet": c.doc.get("short_text", ""),
                "timestamps": c.doc.get("timestamps", []),
                "evidence_ids": c.doc.get("evidence_ids", []),
                "source_event_ids": c.doc.get("source_event_ids", []),
                "source_rule_ids": c.doc.get("source_rule_ids", []),
                "raw_lexical_score": round(lex_map.get(c.doc_id, 0.0), 4),
                "raw_vector_score": round(vec_map.get(c.doc_id, 0.0), 4),
                "graph_boost": round(c.graph_boost, 4),
                "score": round(c.final_score, 4),
                "score_breakdown": {k: round(v, 4) for k, v in c.signals.items()},
                "why_retrieved": c.reasons,
                "resolved_doc": c.doc,
            })

        hit_ids = {h["doc_id"] for h in top_hits}
        facets = self._store.facets(hit_ids)

        return {
            "query": query,
            "normalized_query": normalized_query,
            "detected_unit_bias": unit_bias,
            "detected_intents": list(iq.detected_intents),
            "intent_signals": iq.to_dict(),
            "expansion": expansion.model_dump(mode="json"),
            "top_hits": top_hits,
            "hit_count": len(top_hits),
            "facets": facets,
        }
