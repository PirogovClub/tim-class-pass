"""FastAPI app for hybrid RAG retrieval."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from pipeline.rag.answer_builder import build_answer
from pipeline.rag.config import RAGConfig
from pipeline.rag.embedding_index import EmbeddingIndex
from pipeline.rag.graph_expand import ConceptExpander
from pipeline.rag.lexical_index import LexicalIndex
from pipeline.rag.retriever import HybridRetriever
from pipeline.rag.store import DocStore

app = FastAPI(title="Tim Class Pass RAG", version="0.1.0")

_retriever: HybridRetriever | None = None
_store: DocStore | None = None
_cfg: RAGConfig | None = None


class SearchRequest(BaseModel):
    query: str
    top_k: int = 10
    unit_types: Optional[list[str]] = None
    lesson_ids: Optional[list[str]] = None
    concept_ids: Optional[list[str]] = None
    min_confidence: Optional[float] = None
    return_summary: bool = True


class SearchResponse(BaseModel):
    query: str
    hit_count: int = 0
    detected_concepts: list[dict[str, Any]] = Field(default_factory=list)
    expansion_trace: list[dict[str, Any]] = Field(default_factory=list)
    top_hits: list[dict[str, Any]] = Field(default_factory=list)
    grouped_results: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)
    answer_summary: Optional[str] = None
    citations: list[dict[str, Any]] = Field(default_factory=list)
    facets: dict[str, dict[str, int]] = Field(default_factory=dict)


def _get_retriever() -> HybridRetriever:
    if _retriever is None:
        raise HTTPException(503, "RAG system not initialized. Run 'build' first.")
    return _retriever


def _get_store() -> DocStore:
    if _store is None:
        raise HTTPException(503, "RAG system not initialized. Run 'build' first.")
    return _store


def init_app(cfg: RAGConfig) -> None:
    """Load all indexes into memory and wire up the retriever."""
    global _retriever, _store, _cfg
    _cfg = cfg

    _store = DocStore.load(cfg.rag_root / "retrieval_docs_all.jsonl")
    all_docs = _store.get_all()

    lex = LexicalIndex.build(all_docs)
    emb = EmbeddingIndex.load(cfg.index_dir)
    expander = ConceptExpander.from_corpus(cfg.corpus_root, max_hops=cfg.max_expansion_hops, max_expanded=cfg.max_expanded_per_concept)

    _retriever = HybridRetriever(_store, lex, emb, expander, cfg)


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "store_doc_count": _store.doc_count if _store else 0,
        "initialized": _retriever is not None,
    }


@app.post("/rag/search", response_model=SearchResponse)
def rag_search(req: SearchRequest) -> dict[str, Any]:
    retriever = _get_retriever()
    result = retriever.search(
        query=req.query,
        top_k=req.top_k,
        unit_types=req.unit_types,
        lesson_ids=req.lesson_ids,
        concept_ids=req.concept_ids,
        min_confidence=req.min_confidence,
    )
    answer = build_answer(result, return_summary=req.return_summary)
    answer["hit_count"] = result["hit_count"]
    return answer


@app.get("/rag/doc/{doc_id}")
def rag_doc(doc_id: str) -> dict[str, Any]:
    store = _get_store()
    doc = store.get(doc_id)
    if doc is None:
        raise HTTPException(404, f"Document {doc_id!r} not found")
    return doc


@app.get("/rag/concept/{concept_id}")
def rag_concept(concept_id: str) -> dict[str, Any]:
    store = _get_store()
    docs = store.get_by_concept(concept_id)
    return {"concept_id": concept_id, "doc_count": len(docs), "docs": docs}


@app.get("/rag/lesson/{lesson_id}")
def rag_lesson(lesson_id: str) -> dict[str, Any]:
    store = _get_store()
    docs = store.get_by_lesson(lesson_id)
    return {"lesson_id": lesson_id, "doc_count": len(docs), "docs": docs}


@app.post("/rag/eval/run")
def rag_eval_run() -> dict[str, Any]:
    from pipeline.rag.eval import run_eval

    retriever = _get_retriever()
    if _cfg is None:
        raise HTTPException(503, "RAG not initialized")
    return run_eval(retriever, _cfg)
