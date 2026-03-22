"""Hybrid retriever: lexical + vector + concept expansion + reranking."""

from __future__ import annotations

import re
from typing import Any

from pipeline.rag.contracts import GraphExpansionResult
from pipeline.rag.config import RAGConfig
from pipeline.rag.embedding_index import EmbeddingIndex
from pipeline.rag.graph_expand import ConceptExpander
from pipeline.rag.lexical_index import LexicalIndex
from pipeline.rag.reranker import RerankerCandidate, rerank
from pipeline.rag.store import DocStore

_SPACE_RE = re.compile(r"\s+")


def _normalize_query(query: str) -> str:
    return _SPACE_RE.sub(" ", query.strip().lower())


def _detect_unit_bias(query: str) -> str:
    if any(term in query for term in ("example", "examples", "evidence", "покажи", "пример", "визу")):
        return "evidence"
    if any(term in query for term in ("difference", "compare", "comparison", "разница", "сравн")):
        return "concept"
    if any(term in query for term in ("rule", "invalid", "condition", "правил", "отмен", "услов")):
        return "rule"
    return "mixed"


def _query_preferences(query: str) -> dict[str, bool]:
    return {
        "prefers_examples": any(term in query for term in ("example", "examples", "покажи", "пример", "визу")),
        "prefers_theory": any(term in query for term in ("what is", "difference", "theory", "что такое", "разница", "объясни")),
    }


def _unit_weight_map(cfg: RAGConfig, unit_bias: str) -> dict[str, float]:
    weights = dict(cfg.default_unit_weights)
    if unit_bias == "rule":
        weights["rule_card"] = 1.15
        weights["knowledge_event"] = max(weights.get("knowledge_event", 0.95), 1.0)
    elif unit_bias == "evidence":
        weights["evidence_ref"] = 1.20
    elif unit_bias == "concept":
        weights["concept_node"] = 1.20
        weights["concept_relation"] = 1.10
    return weights


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
    ) -> dict[str, Any]:
        cfg = self._cfg
        final_k = top_k or cfg.final_top_k
        normalized_query = _normalize_query(query)
        unit_bias = _detect_unit_bias(normalized_query)
        query_preferences = _query_preferences(normalized_query)

        expansion = GraphExpansionResult()
        if cfg.enable_graph_expand:
            expansion = self._expander.expand_query(normalized_query)
        query_concept_ids = set(expansion.canonical_concept_ids) | set(expansion.expanded_concept_ids)
        boosted_rule_ids = set(expansion.boosted_rule_ids)
        query_alias_terms = set(expansion.detected_terms)

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
            alias_terms=list(query_alias_terms),
        )
        lex_map = {did: score for did, score in lex_hits}

        q_emb = self._embedding.encode_query(normalized_query)
        vec_hits = self._embedding.search(
            q_emb,
            top_k=cfg.vector_top_k,
            unit_types=unit_types,
            lesson_ids=lesson_ids,
            allowed_ids=filter_ids,
        )
        vec_map = {did: score for did, score in vec_hits}

        all_ids = list(set(lex_map.keys()) | set(vec_map.keys()))
        all_ids.sort(key=lambda did: max(lex_map.get(did, 0.0), vec_map.get(did, 0.0)), reverse=True)
        all_ids = all_ids[:cfg.merged_top_k]
        candidates: list[RerankerCandidate] = []
        for did in all_ids:
            doc = self._store.get(did)
            if doc is None:
                continue
            c = RerankerCandidate(did, doc)
            c.lexical_score = lex_map.get(did, 0.0)
            c.vector_score = vec_map.get(did, 0.0)
            if did in boosted_rule_ids:
                c.graph_boost = cfg.exact_alias_boost
            elif query_concept_ids & set(doc.get("canonical_concept_ids") or []):
                c.graph_boost = cfg.exact_alias_boost * 0.5
            candidates.append(c)

        ranked = rerank(
            candidates,
            query_concept_ids=query_concept_ids,
            query_alias_terms=query_alias_terms,
            boosted_rule_ids=boosted_rule_ids,
            unit_type_weights=_unit_weight_map(cfg, unit_bias),
            detected_unit_bias=unit_bias,
            query_preferences=query_preferences,
            weights=cfg.reranker_weights,
        )

        top_hits: list[dict[str, Any]] = []
        for c in ranked[:final_k]:
            top_hits.append({
                "doc_id": c.doc_id,
                "unit_type": c.doc.get("unit_type", ""),
                "lesson_id": c.doc.get("lesson_id", ""),
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
            "expansion": expansion.model_dump(mode="json"),
            "top_hits": top_hits,
            "hit_count": len(top_hits),
            "facets": facets,
        }
