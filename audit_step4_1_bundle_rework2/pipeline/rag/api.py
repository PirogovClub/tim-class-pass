"""FastAPI app for hybrid RAG retrieval."""

from __future__ import annotations

import json
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from pipeline.explorer.api import explorer_router, init_explorer
from pipeline.rag.answer_builder import build_answer
from pipeline.rag.contracts import SearchRequest, SearchResponse
from pipeline.rag.config import RAGConfig
from pipeline.rag.embedding_index import EmbeddingIndex
from pipeline.rag.graph_expand import ConceptExpander
from pipeline.rag.lexical_index import LexicalIndex
from pipeline.rag.retriever import HybridRetriever
from pipeline.rag.store import DocStore, InMemoryDocStore

app = FastAPI(title="Tim Class Pass RAG", version="0.1.0")
app.include_router(explorer_router)

_retriever: HybridRetriever | None = None
_store: DocStore | None = None
_cfg: RAGConfig | None = None
_embedding_manifest: dict[str, Any] = {}
_build_metadata: dict[str, Any] = {}


class EvalRunRequest(BaseModel):
    query_file: str | None = None


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
    global _retriever, _store, _cfg, _embedding_manifest, _build_metadata
    _cfg = cfg

    _store = InMemoryDocStore.load(cfg.rag_root / "retrieval_docs_all.jsonl")
    all_docs = _store.get_all()

    lex = LexicalIndex.load_from_store(all_docs, cfg.index_dir)
    try:
        emb = EmbeddingIndex.load(cfg.index_dir)
    except Exception:
        from pipeline.rag.embedding_index import SentenceTransformerBackend

        backend = SentenceTransformerBackend(
            model_name=cfg.embedding_model,
            batch_size=cfg.embedding_batch_size,
        )
        emb = EmbeddingIndex.build(all_docs, backend=backend)
        emb.save(cfg.index_dir)
    expander = ConceptExpander.from_corpus(
        cfg.corpus_root,
        max_hops=cfg.max_expansion_hops,
        max_expanded=cfg.max_graph_expansion,
    )

    _retriever = HybridRetriever(_store, lex, emb, expander, cfg)
    init_explorer(cfg, _retriever)
    embedding_manifest_path = cfg.index_dir / "embedding_manifest.json"
    if embedding_manifest_path.exists():
        _embedding_manifest = json.loads(embedding_manifest_path.read_text(encoding="utf-8"))
    build_meta_path = cfg.rag_root / "rag_build_metadata.json"
    if build_meta_path.exists():
        _build_metadata = json.loads(build_meta_path.read_text(encoding="utf-8"))


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "rag_ready": _retriever is not None,
        "doc_count": _store.doc_count if _store else 0,
        "embedding_model": _embedding_manifest.get("model_name", ""),
        "corpus_contract_version": _build_metadata.get("corpus_contract_version", "unknown"),
    }


@app.post("/rag/search", response_model=SearchResponse)
def rag_search(req: SearchRequest) -> dict[str, Any]:
    retriever = _get_retriever()
    result = retriever.search(
        query=req.query,
        top_k=req.top_k,
        unit_types=req.unit_types or None,
        lesson_ids=req.filters.lesson_ids or None,
        concept_ids=req.filters.concept_ids or None,
        min_confidence=req.filters.min_confidence_score,
    )
    answer = build_answer(result, return_summary=req.return_summary)
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
def rag_eval_run(req: EvalRunRequest) -> dict[str, Any]:
    from pipeline.rag.eval import run_eval

    retriever = _get_retriever()
    if _cfg is None:
        raise HTTPException(503, "RAG not initialized")
    return run_eval(retriever, _cfg, queries_path=req.query_file)


@app.get("/rag/facets")
def rag_facets(query: str | None = None) -> dict[str, Any]:
    retriever = _get_retriever()
    if not query:
        store = _get_store()
        return store.facets()
    result = retriever.search(query=query, top_k=20)
    hit_ids = {hit["doc_id"] for hit in result["top_hits"]}
    return _get_store().facets(hit_ids)
