"""FastAPI router for Stage 6.3 RAG retrieval API."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from pipeline.rag.answer_builder import build_answer
from pipeline.rag.config import ALL_UNIT_TYPES, RAGConfig
from pipeline.rag.contracts import SearchRequest, SearchResponse
from pipeline.rag.eval import run_eval
from pipeline.rag.rag_related import related_for_document
from pipeline.rag.retriever import HybridRetriever
from pipeline.rag.store import DocStore

rag_router = APIRouter(prefix="/rag", tags=["rag"])

_retriever: HybridRetriever | None = None
_store: DocStore | None = None
_cfg: RAGConfig | None = None
_embedding_manifest: dict[str, Any] = {}
_build_metadata: dict[str, Any] = {}


class EvalRunRequest(BaseModel):
    query_file: str | None = None


def init_rag_runtime(
    retriever: HybridRetriever,
    store: DocStore,
    cfg: RAGConfig,
    *,
    embedding_manifest: dict[str, Any] | None = None,
    build_metadata: dict[str, Any] | None = None,
) -> None:
    global _retriever, _store, _cfg, _embedding_manifest, _build_metadata
    _retriever = retriever
    _store = store
    _cfg = cfg
    _embedding_manifest = embedding_manifest or {}
    _build_metadata = build_metadata or {}


def clear_rag_runtime() -> None:
    """Reset module state (used by tests that assert 503 when RAG is not initialized)."""
    global _retriever, _store, _cfg, _embedding_manifest, _build_metadata
    _retriever = None
    _store = None
    _cfg = None
    _embedding_manifest = {}
    _build_metadata = {}


def _get_retriever() -> HybridRetriever:
    if _retriever is None:
        raise HTTPException(503, "RAG system not initialized. Run 'build' first.")
    return _retriever


def _get_store() -> DocStore:
    if _store is None:
        raise HTTPException(503, "RAG system not initialized. Run 'build' first.")
    return _store


def _get_cfg() -> RAGConfig:
    if _cfg is None:
        raise HTTPException(503, "RAG system not initialized. Run 'build' first.")
    return _cfg


@rag_router.post("/search", response_model=SearchResponse)
def rag_search(req: SearchRequest) -> dict[str, Any]:
    retriever = _get_retriever()
    result = retriever.search(
        query=req.query,
        top_k=req.top_k,
        unit_types=req.unit_types or None,
        lesson_ids=req.filters.lesson_ids or None,
        concept_ids=req.filters.concept_ids or None,
        min_confidence=req.filters.min_confidence_score,
        require_evidence=req.require_evidence,
    )
    return build_answer(result, return_summary=req.return_summary)


@rag_router.post("/search/explain")
def rag_search_explain(req: SearchRequest) -> dict[str, Any]:
    """Same as ``/rag/search`` plus a compact retrieval trace for debugging (Stage 6.3 optional API)."""
    retriever = _get_retriever()
    result = retriever.search(
        query=req.query,
        top_k=req.top_k,
        unit_types=req.unit_types or None,
        lesson_ids=req.filters.lesson_ids or None,
        concept_ids=req.filters.concept_ids or None,
        min_confidence=req.filters.min_confidence_score,
        require_evidence=req.require_evidence,
    )
    answer = build_answer(result, return_summary=req.return_summary)
    top_hits = result.get("top_hits") or []
    retrieval_trace = {
        "normalized_query": result.get("normalized_query"),
        "detected_unit_bias": result.get("detected_unit_bias"),
        "detected_intents": result.get("detected_intents"),
        "intent_signals": result.get("intent_signals"),
        "expansion": result.get("expansion"),
        "merged_hit_count": len(top_hits),
        "facets": result.get("facets"),
        "per_hit_scores": [
            {
                "doc_id": h.get("doc_id"),
                "unit_type": h.get("unit_type"),
                "score": h.get("score"),
                "raw_lexical_score": h.get("raw_lexical_score"),
                "raw_vector_score": h.get("raw_vector_score"),
                "graph_boost": h.get("graph_boost"),
            }
            for h in top_hits
        ],
    }
    return {"search_response": answer, "retrieval_trace": retrieval_trace}


@rag_router.get("/item/{unit_type}/{doc_id:path}")
def rag_item(unit_type: str, doc_id: str) -> dict[str, Any]:
    store = _get_store()
    if unit_type not in ALL_UNIT_TYPES:
        raise HTTPException(400, f"Invalid unit_type {unit_type!r}")
    doc = store.get(doc_id)
    if doc is None:
        raise HTTPException(404, f"Document {doc_id!r} not found")
    if doc.get("unit_type") != unit_type:
        raise HTTPException(
            400,
            detail={
                "message": "unit_type does not match document",
                "expected": doc.get("unit_type"),
                "requested": unit_type,
            },
        )
    return doc


@rag_router.get("/related/{unit_type}/{doc_id:path}")
def rag_related(unit_type: str, doc_id: str) -> dict[str, Any]:
    store = _get_store()
    if unit_type not in ALL_UNIT_TYPES:
        raise HTTPException(400, f"Invalid unit_type {unit_type!r}")
    payload = related_for_document(store, unit_type, doc_id)
    if not payload.get("found"):
        if payload.get("mismatch"):
            raise HTTPException(400, detail=payload)
        raise HTTPException(404, detail=payload)
    return payload


@rag_router.get("/explore/lesson/{lesson_id}")
def rag_explore_lesson(lesson_id: str) -> dict[str, Any]:
    store = _get_store()
    docs = store.get_by_lesson(lesson_id)
    if not docs:
        raise HTTPException(404, f"No retrieval units for lesson {lesson_id!r}")
    grouped: dict[str, list[dict[str, Any]]] = {}
    for d in docs:
        ut = d.get("unit_type", "unknown")
        grouped.setdefault(ut, []).append(
            {
                "doc_id": d.get("doc_id"),
                "global_id": d.get("doc_id"),
                "unit_type": ut,
                "title": d.get("title", ""),
                "short_text": d.get("short_text", ""),
                "evidence_ids": d.get("evidence_ids") or [],
                "timestamps": d.get("timestamps") or [],
                "canonical_concept_ids": d.get("canonical_concept_ids") or [],
            }
        )
    return {
        "lesson_id": lesson_id,
        "unit_counts": {k: len(v) for k, v in grouped.items()},
        "units_by_type": grouped,
    }


@rag_router.get("/doc/{doc_id:path}")
def rag_doc_legacy(doc_id: str) -> dict[str, Any]:
    """Backward-compatible alias for single-doc fetch by id only."""
    store = _get_store()
    doc = store.get(doc_id)
    if doc is None:
        raise HTTPException(404, f"Document {doc_id!r} not found")
    return doc


@rag_router.get("/lesson/{lesson_id}")
def rag_lesson_legacy(lesson_id: str) -> dict[str, Any]:
    store = _get_store()
    docs = store.get_by_lesson(lesson_id)
    return {"lesson_id": lesson_id, "doc_count": len(docs), "docs": docs}


@rag_router.get("/concept/{concept_id:path}")
def rag_concept_legacy(concept_id: str) -> dict[str, Any]:
    store = _get_store()
    docs = store.get_by_concept(concept_id)
    return {"concept_id": concept_id, "doc_count": len(docs), "docs": docs}


@rag_router.post("/eval/run")
def rag_eval_run(req: EvalRunRequest) -> dict[str, Any]:
    retriever = _get_retriever()
    cfg = _get_cfg()
    return run_eval(retriever, cfg, queries_path=req.query_file)


@rag_router.get("/facets")
def rag_facets(query: str | None = None) -> dict[str, Any]:
    retriever = _get_retriever()
    store = _get_store()
    if not query:
        return store.facets()
    result = retriever.search(query=query, top_k=20)
    hit_ids = {hit["doc_id"] for hit in result["top_hits"]}
    return store.facets(hit_ids)


def load_rag_aux_metadata(cfg: RAGConfig) -> tuple[dict[str, Any], dict[str, Any]]:
    embedding_manifest: dict[str, Any] = {}
    build_metadata: dict[str, Any] = {}
    embedding_manifest_path = cfg.index_dir / "embedding_manifest.json"
    if embedding_manifest_path.exists():
        embedding_manifest = json.loads(embedding_manifest_path.read_text(encoding="utf-8"))
    build_meta_path = cfg.rag_root / "rag_build_metadata.json"
    if build_meta_path.exists():
        build_metadata = json.loads(build_meta_path.read_text(encoding="utf-8"))
    return embedding_manifest, build_metadata


def get_rag_health_payload() -> dict[str, Any]:
    store = _store
    return {
        "status": "ok",
        "rag_ready": _retriever is not None,
        "doc_count": store.doc_count if store else 0,
        "embedding_model": _embedding_manifest.get("model_name", ""),
        "corpus_contract_version": _build_metadata.get("corpus_contract_version", "unknown"),
    }
