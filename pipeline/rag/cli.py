"""Click CLI for the RAG pipeline: build, search, serve, eval."""

from __future__ import annotations

import json
import sys

import click

from pipeline.rag.config import RAGConfig


@click.group()
def main() -> None:
    """Tim Class Pass – Hybrid RAG retrieval system."""


@main.command()
@click.option("--corpus-root", default="output_corpus", help="Path to Step 2 corpus outputs.")
@click.option("--rag-root", default="output_rag", help="Output directory for RAG artifacts.")
def build(corpus_root: str, rag_root: str) -> None:
    """Build retrieval docs and indexes from the corpus."""
    cfg = RAGConfig(corpus_root=corpus_root, rag_root=rag_root)

    click.echo(f"Loading corpus from {cfg.corpus_root} ...")
    from pipeline.rag.corpus_loader import build_and_persist

    meta = build_and_persist(cfg)
    click.echo(f"  Retrieval docs: {meta['total_retrieval_docs']}")

    click.echo("Building lexical index ...")
    from pipeline.rag.store import DocStore
    from pipeline.rag.lexical_index import LexicalIndex

    store = DocStore.load(cfg.rag_root / "retrieval_docs_all.jsonl")
    lex = LexicalIndex.build(store.get_all())
    lex.save(cfg.index_dir)
    click.echo("  Lexical index saved.")

    click.echo("Building embedding index ...")
    from pipeline.rag.embedding_index import EmbeddingIndex

    emb = EmbeddingIndex.build(store.get_all(), model_name=cfg.embedding_model, batch_size=cfg.embedding_batch_size)
    emb.save(cfg.index_dir)
    click.echo(f"  Embedding index saved ({emb.doc_count} docs, {emb.dim}d).")

    click.echo("Done.")


@main.command()
@click.option("--rag-root", default="output_rag", help="RAG artifacts directory.")
@click.option("--corpus-root", default="output_corpus", help="Path to Step 2 corpus outputs.")
@click.option("--query", required=True, help="Search query.")
@click.option("--top-k", default=10, type=int, help="Number of results.")
def search(rag_root: str, corpus_root: str, query: str, top_k: int) -> None:
    """One-shot search against the RAG index."""
    cfg = RAGConfig(corpus_root=corpus_root, rag_root=rag_root)
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

    from pipeline.rag.store import DocStore
    from pipeline.rag.lexical_index import LexicalIndex
    from pipeline.rag.embedding_index import EmbeddingIndex
    from pipeline.rag.graph_expand import ConceptExpander
    from pipeline.rag.retriever import HybridRetriever
    from pipeline.rag.answer_builder import build_answer

    store = DocStore.load(cfg.rag_root / "retrieval_docs_all.jsonl")
    lex = LexicalIndex.build(store.get_all())
    emb = EmbeddingIndex.load(cfg.index_dir)
    expander = ConceptExpander.from_corpus(cfg.corpus_root)
    retriever = HybridRetriever(store, lex, emb, expander, cfg)

    result = retriever.search(query, top_k=top_k)
    answer = build_answer(result)

    click.echo(json.dumps(answer, indent=2, ensure_ascii=False))


@main.command()
@click.option("--rag-root", default="output_rag", help="RAG artifacts directory.")
@click.option("--corpus-root", default="output_corpus", help="Path to Step 2 corpus outputs.")
@click.option("--host", default="127.0.0.1", help="Bind host.")
@click.option("--port", default=8000, type=int, help="Bind port.")
def serve(rag_root: str, corpus_root: str, host: str, port: int) -> None:
    """Start the FastAPI RAG server."""
    cfg = RAGConfig(corpus_root=corpus_root, rag_root=rag_root)

    from pipeline.rag.api import app, init_app

    click.echo(f"Initializing RAG from {cfg.rag_root} ...")
    init_app(cfg)

    import uvicorn

    click.echo(f"Serving on http://{host}:{port}")
    uvicorn.run(app, host=host, port=port)


@main.command("eval")
@click.option("--rag-root", default="output_rag", help="RAG artifacts directory.")
@click.option("--corpus-root", default="output_corpus", help="Path to Step 2 corpus outputs.")
@click.option("--queries", default=None, help="Path to eval queries JSON (default: built-in).")
def eval_cmd(rag_root: str, corpus_root: str, queries: str | None) -> None:
    """Run the evaluation harness."""
    cfg = RAGConfig(corpus_root=corpus_root, rag_root=rag_root)
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

    from pipeline.rag.store import DocStore
    from pipeline.rag.lexical_index import LexicalIndex
    from pipeline.rag.embedding_index import EmbeddingIndex
    from pipeline.rag.graph_expand import ConceptExpander
    from pipeline.rag.retriever import HybridRetriever
    from pipeline.rag.eval import run_eval

    store = DocStore.load(cfg.rag_root / "retrieval_docs_all.jsonl")
    lex = LexicalIndex.build(store.get_all())
    emb = EmbeddingIndex.load(cfg.index_dir)
    expander = ConceptExpander.from_corpus(cfg.corpus_root)
    retriever = HybridRetriever(store, lex, emb, expander, cfg)

    report = run_eval(retriever, cfg, queries_path=queries)
    click.echo(json.dumps(report, indent=2, ensure_ascii=False))
