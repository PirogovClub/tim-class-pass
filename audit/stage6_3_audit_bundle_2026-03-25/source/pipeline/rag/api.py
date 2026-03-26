"""FastAPI app for hybrid RAG retrieval."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI

from pipeline.adjudication.api_errors import AdjudicationApiError, adjudication_api_error_handler
from pipeline.adjudication.api_routes import adjudication_router, init_adjudication
from pipeline.explorer.api import explorer_router, get_explorer_service_optional, init_explorer
from pipeline.rag.config import RAGConfig
from pipeline.rag.embedding_index import EmbeddingIndex
from pipeline.rag.graph_expand import ConceptExpander
from pipeline.rag.lexical_index import LexicalIndex
from pipeline.rag.rag_routes import (
    get_rag_health_payload,
    init_rag_runtime,
    load_rag_aux_metadata,
    rag_router,
)
from pipeline.rag.retriever import HybridRetriever
from pipeline.rag.store import InMemoryDocStore

app = FastAPI(title="Tim Class Pass RAG", version="0.1.0")
app.add_exception_handler(AdjudicationApiError, adjudication_api_error_handler)
app.include_router(explorer_router)
app.include_router(adjudication_router)
app.include_router(rag_router)


def init_app(cfg: RAGConfig) -> None:
    """Load all indexes into memory and wire up the retriever."""
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

    retriever = HybridRetriever(_store, lex, emb, expander, cfg)
    embedding_manifest, build_metadata = load_rag_aux_metadata(cfg)
    init_rag_runtime(retriever, _store, cfg, embedding_manifest=embedding_manifest, build_metadata=build_metadata)
    init_explorer(cfg, retriever)
    adj_db = Path(os.environ.get("ADJUDICATION_DB_PATH", "var/adjudication.db"))
    init_adjudication(adj_db, get_explorer_service_optional())


@app.get("/health")
def health() -> dict[str, Any]:
    return get_rag_health_payload()
