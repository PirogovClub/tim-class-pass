"""Click CLI for the RAG pipeline: build, search, serve, eval, export-audit."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any

import click

from pipeline.rag.config import RAGConfig


@click.group()
def main() -> None:
    """Tim Class Pass – Hybrid RAG retrieval system."""


CLI_AUDIT_SAMPLES: list[tuple[str, str]] = [
    ("q001", "q001_stop_loss_level"),
    ("q003", "q003_bpu_price_action"),
    ("q012", "q012_accumulation_example"),
    ("q017", "q017_levels_and_stop_loss"),
    ("q020", "q020_daily_level"),
    ("q022", "q022_transcript_only_rules"),
    ("q024", "q024_stop_loss_placement_rules"),
    ("q027", "q027_retest_after_breakout"),
]

API_AUDIT_SAMPLES: list[dict[str, Any]] = [
    {"query_id": "q024", "slug": "search_stop_loss_rules", "unit_types": ["rule_card", "knowledge_event", "evidence_ref"]},
    {"query_id": "q012", "slug": "search_accumulation_example", "unit_types": ["evidence_ref", "rule_card", "knowledge_event"]},
    {"query_id": "q009", "slug": "search_concept_comparison", "unit_types": ["rule_card", "concept_relation", "concept_node"]},
    {"query_id": "q023", "slug": "search_support_policy", "unit_types": ["evidence_ref", "rule_card"]},
    {"query_id": "q027", "slug": "search_retest_alias", "unit_types": ["rule_card", "concept_node", "knowledge_event"]},
]

AUDIT_CORPUS_FILES: tuple[str, ...] = (
    "corpus_rule_cards.jsonl",
    "corpus_knowledge_events.jsonl",
    "corpus_evidence_index.jsonl",
    "corpus_concept_graph.json",
    "concept_alias_registry.json",
    "concept_rule_map.json",
    "rule_family_index.json",
    "corpus_metadata.json",
)

AUDIT_DOC_FILES: tuple[str, ...] = (
    "step3_hybrid_rag_notes.md",
    "rag_query_examples.md",
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_audit_queries(cfg: RAGConfig) -> dict[str, dict[str, Any]]:
    from pipeline.rag.eval import CURATED_QUERIES

    eval_queries_path = cfg.eval_dir / "eval_queries.json"
    if eval_queries_path.exists():
        queries = json.loads(eval_queries_path.read_text(encoding="utf-8"))
    else:
        queries = CURATED_QUERIES
    return {query["query_id"]: query for query in queries}


def _zip_sources(zip_path: Path, sources: list[tuple[Path, str]]) -> None:
    if zip_path.exists():
        zip_path.unlink()
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for src, arcname in sources:
            if src.is_dir():
                for child in sorted(src.rglob("*")):
                    if child.is_file():
                        relative = child.relative_to(src).as_posix()
                        archive.write(child, f"{arcname}/{relative}")
            elif src.is_file():
                archive.write(src, arcname)


def _run_pytest_capture(output_path: Path) -> Path:
    repo_root = _repo_root()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/rag", "tests/test_rag.py", "-q"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    combined_output = proc.stdout
    if proc.stderr:
        combined_output = f"{combined_output}{proc.stderr}"
    output_path.write_text(combined_output, encoding="utf-8")
    if proc.returncode != 0:
        raise click.ClickException(
            f"pytest failed with exit code {proc.returncode}. See {output_path}."
        )
    return output_path


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
    from pipeline.rag.contracts import RAGBuildResult
    from pipeline.rag.corpus_loader import build_and_persist, write_build_metadata
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
    meta["lexical_manifest_path"] = cfg.index_dir / "lexical_index_manifest.json"
    meta["embedding_manifest_path"] = cfg.index_dir / "embedding_manifest.json"
    write_build_metadata(
        cfg.rag_root / "rag_build_metadata.json",
        RAGBuildResult.model_validate(meta),
    )
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


def export_audit_bundle(
    cfg: RAGConfig,
    audit_root: Path,
    zip_path: Path | None = None,
    pytest_output_path: Path | None = None,
) -> dict[str, str]:
    from fastapi.testclient import TestClient

    from pipeline.rag.answer_builder import build_answer
    from pipeline.rag.api import app, init_app
    from pipeline.rag.store import InMemoryDocStore

    repo_root = _repo_root()
    audit_root.mkdir(parents=True, exist_ok=True)
    cli_dir = audit_root / "cli_samples"
    api_dir = audit_root / "api_samples"
    cli_dir.mkdir(parents=True, exist_ok=True)
    api_dir.mkdir(parents=True, exist_ok=True)

    queries = _load_audit_queries(cfg)
    retriever = _build_runtime(cfg)

    for query_id, slug in CLI_AUDIT_SAMPLES:
        query_text = queries[query_id]["query_text"]
        response = build_answer(retriever.search(query=query_text, top_k=5))
        _write_json(
            cli_dir / f"{slug}.json",
            {
                "query_id": query_id,
                "query": query_text,
                "top_k": 5,
                "response": response,
            },
        )

    init_app(cfg)
    client = TestClient(app)
    _write_json(
        api_dir / "health.json",
        {
            "method": "GET",
            "path": "/health",
            "status_code": 200,
            "response": client.get("/health").json(),
        },
    )

    sampled_doc_ids: list[str] = []
    sampled_concept_ids: list[str] = []
    for sample in API_AUDIT_SAMPLES:
        query_text = queries[sample["query_id"]]["query_text"]
        body = {
            "query": query_text,
            "top_k": 5,
            "unit_types": sample["unit_types"],
            "filters": {"lesson_ids": [], "concept_ids": [], "min_confidence_score": None},
            "return_summary": True,
        }
        response = client.post("/rag/search", json=body)
        payload = response.json()
        for concept_id in payload.get("query_analysis", {}).get("detected_concepts", []) or []:
            if concept_id and concept_id not in sampled_concept_ids:
                sampled_concept_ids.append(concept_id)
        for hit in payload.get("top_hits") or []:
            doc_id = hit.get("doc_id")
            if doc_id and doc_id not in sampled_doc_ids:
                sampled_doc_ids.append(doc_id)
            if len(sampled_doc_ids) >= 2:
                break
        _write_json(
            api_dir / f"{sample['slug']}.json",
            {
                "method": "POST",
                "path": "/rag/search",
                "request": body,
                "status_code": response.status_code,
                "response": payload,
            },
        )

    if not sampled_doc_ids:
        raise ValueError("Could not select a document sample from audit search responses.")

    for index, doc_id in enumerate(sampled_doc_ids[:2], start=1):
        doc_response = client.get(f"/rag/doc/{doc_id}")
        doc_payload = doc_response.json()
        _write_json(
            api_dir / f"doc_sample_{index}.json",
            {
                "method": "GET",
                "path": f"/rag/doc/{doc_id}",
                "status_code": doc_response.status_code,
                "response": doc_payload,
            },
        )
        for concept_id in doc_payload.get("canonical_concept_ids") or []:
            if concept_id and concept_id not in sampled_concept_ids:
                sampled_concept_ids.append(concept_id)
            if len(sampled_concept_ids) >= 2:
                break
        if len(sampled_concept_ids) >= 2:
            break

    if len(sampled_concept_ids) < 2:
        store = InMemoryDocStore.load(cfg.rag_root / "retrieval_docs_all.jsonl")
        for concept_id in store.concept_ids():
            if concept_id and concept_id not in sampled_concept_ids:
                sampled_concept_ids.append(concept_id)
            if len(sampled_concept_ids) >= 2:
                break

    if not sampled_concept_ids:
        raise ValueError("Could not select concept samples from sampled document responses.")

    for index, concept_id in enumerate(sampled_concept_ids[:2], start=1):
        concept_response = client.get(f"/rag/concept/{concept_id}")
        _write_json(
            api_dir / f"concept_sample_{index}.json",
            {
                "method": "GET",
                "path": f"/rag/concept/{concept_id}",
                "status_code": concept_response.status_code,
                "response": concept_response.json(),
            },
        )

    copied_pytest_output: Path | None = None
    if pytest_output_path is not None:
        copied_pytest_output = audit_root / "pytest_output.txt"
        if pytest_output_path.resolve() != copied_pytest_output.resolve():
            shutil.copy2(pytest_output_path, copied_pytest_output)
        else:
            copied_pytest_output = pytest_output_path

    zip_target = zip_path or Path(f"{audit_root}.zip")
    sample_manifest = {
        "audit_root": str(audit_root),
        "zip_path": str(zip_target),
        "cli_query_ids": [query_id for query_id, _ in CLI_AUDIT_SAMPLES],
        "api_query_ids": [sample["query_id"] for sample in API_AUDIT_SAMPLES],
        "doc_sample_ids": sampled_doc_ids[:2],
        "concept_sample_ids": sampled_concept_ids[:2],
        "included_docs": [doc_name for doc_name in AUDIT_DOC_FILES if (repo_root / "docs" / doc_name).exists()],
    }
    _write_json(audit_root / "sample_manifest.json", sample_manifest)

    zip_sources: list[tuple[Path, str]] = [
        (repo_root / "pipeline" / "rag", "pipeline/rag"),
        (repo_root / "tests" / "rag", "tests/rag"),
        (repo_root / "tests" / "test_rag.py", "tests/test_rag.py"),
        (cfg.rag_root, "output_rag"),
        (api_dir, "api_samples"),
        (cli_dir, "cli_samples"),
        (audit_root / "sample_manifest.json", "sample_manifest.json"),
    ]
    if copied_pytest_output is not None and copied_pytest_output.exists():
        zip_sources.append((copied_pytest_output, "pytest_output.txt"))
    for filename in AUDIT_CORPUS_FILES:
        src = cfg.corpus_root / filename
        if src.exists():
            zip_sources.append((src, f"output_corpus/{filename}"))
    for filename in AUDIT_DOC_FILES:
        src = repo_root / "docs" / filename
        if src.exists():
            zip_sources.append((src, f"docs/{filename}"))
    _zip_sources(zip_target, zip_sources)

    return {
        "audit_root": str(audit_root),
        "zip_path": str(zip_target),
        "doc_sample_ids": ",".join(sampled_doc_ids[:2]),
        "concept_sample_ids": ",".join(sampled_concept_ids[:2]),
    }


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


@main.command("export-audit")
@click.option("--rag-root", default="output_rag", type=click.Path(path_type=Path), help="RAG artifacts directory.")
@click.option("--corpus-root", default="output_corpus", type=click.Path(path_type=Path), help="Path to Step 2 corpus outputs.")
@click.option("--config", "config_path", default=None, type=click.Path(path_type=Path), help="Optional YAML config path.")
@click.option("--audit-root", default="audit_step3_real_v2", type=click.Path(path_type=Path), help="Directory for generated audit samples.")
@click.option("--zip-path", default=None, type=click.Path(path_type=Path), help="Optional zip path for the audit bundle.")
@click.option("--pytest-output", "pytest_output_path", default=None, type=click.Path(path_type=Path), help="Optional existing pytest output text file to include.")
@click.option("--refresh-build/--no-refresh-build", default=True, help="Rebuild Step 3 artifacts before packaging.")
@click.option("--refresh-eval/--no-refresh-eval", default=True, help="Regenerate eval outputs before packaging.")
@click.option("--run-pytest/--skip-pytest", default=True, help="Run the Step 3 pytest suite and include raw output.")
def export_audit_cmd(
    rag_root: Path,
    corpus_root: Path,
    config_path: Path | None,
    audit_root: Path,
    zip_path: Path | None,
    pytest_output_path: Path | None,
    refresh_build: bool,
    refresh_eval: bool,
    run_pytest: bool,
) -> None:
    """Generate UTF-8-safe audit samples and package a Step 3 bundle."""
    cfg = RAGConfig.from_sources(config_path=config_path, corpus_root=corpus_root, rag_root=rag_root)
    if refresh_build:
        click.echo(f"Refreshing build outputs from {cfg.corpus_root} ...")
        run_build(cfg)
    if refresh_eval:
        click.echo("Refreshing eval outputs ...")
        run_eval(cfg, queries=None)
    if run_pytest:
        pytest_output_path = _run_pytest_capture(audit_root / "pytest_output.txt")
        click.echo(f"Saved pytest output to {pytest_output_path}")
    result = export_audit_bundle(cfg, audit_root=audit_root, zip_path=zip_path, pytest_output_path=pytest_output_path)
    click.echo(f"Audit samples saved to {result['audit_root']}")
    click.echo(f"Audit bundle saved to {result['zip_path']}")
