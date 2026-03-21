"""Hybrid retriever: lexical + vector + concept expansion + reranking."""

from __future__ import annotations

from typing import Any

from pipeline.rag.config import RAGConfig
from pipeline.rag.embedding_index import EmbeddingIndex
from pipeline.rag.graph_expand import ConceptExpander
from pipeline.rag.lexical_index import LexicalIndex
from pipeline.rag.reranker import RerankerCandidate, rerank
from pipeline.rag.store import DocStore


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

        expansion = self._expander.expand_query(query)
        query_concept_ids = set(expansion["all_concept_ids"])
        boosted_rule_ids = set(expansion["boosted_rule_ids"])

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
            query, top_k=cfg.lexical_top_k,
            unit_types=unit_types, allowed_ids=filter_ids,
        )
        lex_map = {did: score for did, score in lex_hits}

        q_emb = self._embedding.encode_query(query)
        vec_hits = self._embedding.search(
            q_emb, top_k=cfg.vector_top_k,
            unit_types=unit_types, allowed_ids=filter_ids,
        )
        vec_map = {did: score for did, score in vec_hits}

        all_ids = set(lex_map.keys()) | set(vec_map.keys())
        candidates: list[RerankerCandidate] = []
        for did in all_ids:
            doc = self._store.get(did)
            if doc is None:
                continue
            c = RerankerCandidate(did, doc)
            c.lexical_score = lex_map.get(did, 0.0)
            c.vector_score = vec_map.get(did, 0.0)
            candidates.append(c)

        query_alias_terms: set[str] = set()
        for det in expansion["detected_concepts"]:
            query_alias_terms.add(det["matched_term"].lower())

        ranked = rerank(
            candidates,
            query_concept_ids=query_concept_ids,
            query_alias_terms=query_alias_terms,
            boosted_rule_ids=boosted_rule_ids,
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
                "score": round(c.final_score, 4),
                "score_breakdown": {k: round(v, 4) for k, v in c.signals.items()},
                "why_retrieved": c.reasons,
            })

        hit_ids = {h["doc_id"] for h in top_hits}
        facets = self._store.facets(hit_ids)

        return {
            "query": query,
            "expansion": expansion,
            "top_hits": top_hits,
            "hit_count": len(top_hits),
            "facets": facets,
        }
