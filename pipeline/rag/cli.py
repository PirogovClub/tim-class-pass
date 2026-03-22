"""Click CLI for the RAG pipeline: build, search, serve, eval."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from pipeline.rag.config import RAGConfig


@click.group()
def main() -> None:
    """Tim Class Pass – Hybrid RAG retrieval system."""


def _build_runtime(cfg: RAGConfig):
    from pipeline.rag.embedding_index import EmbeddingIndex, SentenceTransformerBackend
    from pipeline.rag.graph_expand import ConceptExpander
    from pipeline.rag.lexical_index import LexicalIndex
    from pipeline.rag.retriever import HybridRetriever
    from pipeline.rag.store import InMemoryDocStore

    store = InMemoryDocStore.load(cfg.rag_root / "retrieval_docs_all.jsonl")
    lex = LexicalIndex.load_from_store(store.get_all(), cfg.index_dir)
    try:
        emb = EmbeddingIndex.load(cfg.index_dir)
    except Exception:
        backend = SentenceTransformerBackend(
            model_name=cfg.embedding_model,
            batch_size=cfg.embedding_batch_size,
        )
        emb = EmbeddingIndex.build(store.get_all(), backend=backend)
        emb.save(cfg.index_dir)
    expander = ConceptExpander.from_corpus(
        cfg.corpus_root,
        max_hops=cfg.max_expansion_hops,
        max_expanded=cfg.max_graph_expansion,
    )
    return HybridRetriever(store, lex, emb, expander, cfg)


def run_build(cfg: RAGConfig) -> dict[str, object]:
    from pipeline.rag.corpus_loader import build_and_persist
    from pipeline.rag.embedding_index import EmbeddingIndex, SentenceTransformerBackend
    from pipeline.rag.lexical_index import LexicalIndex
    from pipeline.rag.store import InMemoryDocStore

    meta = build_and_persist(cfg)
    store = InMemoryDocStore.load(cfg.rag_root / "retrieval_docs_all.jsonl")
    lex = LexicalIndex.build(store.get_all())
    lex.save(cfg.index_dir)
    backend = SentenceTransformerBackend(
        model_name=cfg.embedding_model,
        batch_size=cfg.embedding_batch_size,
    )
    emb = EmbeddingIndex.build(store.get_all(), backend=backend)
    emb.save(cfg.index_dir)
    return {
        "meta": meta,
        "embedding_doc_count": emb.doc_count,
        "embedding_dim": emb.dim,
    }


def run_search(cfg: RAGConfig, query: str, top_k: int) -> dict[str, object]:
    from pipeline.rag.answer_builder import build_answer

    retriever = _build_runtime(cfg)
    result = retriever.search(query, top_k=top_k)
    return build_answer(result)


def run_eval(cfg: RAGConfig, queries: str | None) -> dict[str, object]:
    from pipeline.rag.eval import run_eval as run_eval_impl

    retriever = _build_runtime(cfg)
    return run_eval_impl(retriever, cfg, queries_path=queries)


@main.command()
@click.option("--corpus-root", default="output_corpus", type=click.Path(path_type=Path), help="Path to Step 2 corpus outputs.")
@click.option("--rag-root", default="output_rag", type=click.Path(path_type=Path), help="Output directory for RAG artifacts.")
@click.option("--config", "config_path", default=None, type=click.Path(path_type=Path), help="Optional YAML config path.")
def build(corpus_root: Path, rag_root: Path, config_path: Path | None) -> None:
    """Build retrieval docs and indexes from the corpus."""
    cfg = RAGConfig.from_sources(config_path=config_path, corpus_root=corpus_root, rag_root=rag_root)

    click.echo(f"Loading corpus from {cfg.corpus_root} ...")
    result = run_build(cfg)
    meta = result["meta"]
    click.echo(f"  Retrieval docs: {meta['total_retrieval_docs']}")
    click.echo("  Lexical index saved.")
    click.echo(f"  Embedding index saved ({result['embedding_doc_count']} docs, {result['embedding_dim']}d).")

    click.echo("Done.")


@main.command()
@click.option("--rag-root", default="output_rag", type=click.Path(path_type=Path), help="RAG artifacts directory.")
@click.option("--corpus-root", default="output_corpus", type=click.Path(path_type=Path), help="Path to Step 2 corpus outputs.")
@click.option("--config", "config_path", default=None, type=click.Path(path_type=Path), help="Optional YAML config path.")
@click.option("--query", required=True, help="Search query.")
@click.option("--top-k", default=10, type=int, help="Number of results.")
def search(rag_root: Path, corpus_root: Path, config_path: Path | None, query: str, top_k: int) -> None:
    """One-shot search against the RAG index."""
    cfg = RAGConfig.from_sources(config_path=config_path, corpus_root=corpus_root, rag_root=rag_root)
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    answer = run_search(cfg, query, top_k)
    click.echo(json.dumps(answer, indent=2, ensure_ascii=False))


@main.command()
@click.option("--rag-root", default="output_rag", type=click.Path(path_type=Path), help="RAG artifacts directory.")
@click.option("--corpus-root", default="output_corpus", type=click.Path(path_type=Path), help="Path to Step 2 corpus outputs.")
@click.option("--config", "config_path", default=None, type=click.Path(path_type=Path), help="Optional YAML config path.")
@click.option("--host", default="127.0.0.1", help="Bind host.")
@click.option("--port", default=8000, type=int, help="Bind port.")
def serve(rag_root: Path, corpus_root: Path, config_path: Path | None, host: str, port: int) -> None:
    """Start the FastAPI RAG server."""
    cfg = RAGConfig.from_sources(config_path=config_path, corpus_root=corpus_root, rag_root=rag_root)

    from pipeline.rag.api import app, init_app

    click.echo(f"Initializing RAG from {cfg.rag_root} ...")
    init_app(cfg)

    import uvicorn

    click.echo(f"Serving on http://{host}:{port}")
    uvicorn.run(app, host=host, port=port)


@main.command("eval")
@click.option("--rag-root", default="output_rag", type=click.Path(path_type=Path), help="RAG artifacts directory.")
@click.option("--corpus-root", default="output_corpus", type=click.Path(path_type=Path), help="Path to Step 2 corpus outputs.")
@click.option("--config", "config_path", default=None, type=click.Path(path_type=Path), help="Optional YAML config path.")
@click.option("--queries", default=None, help="Path to eval queries JSON (default: built-in).")
def eval_cmd(rag_root: Path, corpus_root: Path, config_path: Path | None, queries: str | None) -> None:
    """Run the evaluation harness."""
    cfg = RAGConfig.from_sources(config_path=config_path, corpus_root=corpus_root, rag_root=rag_root)
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    report = run_eval(cfg, queries)
    click.echo(json.dumps(report, indent=2, ensure_ascii=False))
