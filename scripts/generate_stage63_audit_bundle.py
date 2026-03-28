#!/usr/bin/env python3
"""Assemble ``audit/stage6_3_audit_bundle_<UTC-timestamp>/`` and zip for Stage 6.3 handoff.

Each run uses a new timestamped folder and zip; previous bundles are left in place.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _copy_rag_package(repo: Path, dest: Path) -> None:
    src = repo / "pipeline" / "rag"
    for p in sorted(src.rglob("*")):
        if p.is_dir():
            continue
        if "__pycache__" in p.parts or p.suffix not in {".py", ".md"}:
            continue
        rel = p.relative_to(src)
        out = dest / "pipeline" / "rag" / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, out)


def _copy_tests_rag(repo: Path, dest: Path) -> None:
    d = repo / "tests" / "rag"
    for p in sorted(d.glob("*.py")):
        out = dest / "tests" / "rag" / p.name
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, out)
    for name in ("conftest.py",):
        p = d / name
        if p.exists():
            shutil.copy2(p, dest / "tests" / "rag" / name)
    root_test = repo / "tests" / "test_rag.py"
    if root_test.exists():
        out_root = dest / "tests" / "test_rag.py"
        out_root.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root_test, out_root)


def _copy_audit_support_files(repo: Path, dest: Path) -> None:
    """Dependency manifest + project metadata for auditors."""
    req = repo / "audit" / "requirements-rag-audit.txt"
    if req.exists():
        d = dest / "requirements-rag-audit.txt"
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(req, d)
    pyproject = repo / "pyproject.toml"
    if pyproject.exists():
        out = dest / "pyproject.toml"
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(pyproject, out)


def _copy_ui_snippets(repo: Path, dest: Path) -> None:
    ui = repo / "ui" / "explorer" / "src"
    pairs = [
        ui / "lib" / "api" / "rag.ts",
        ui / "pages" / "RagSearchPage.tsx",
        ui / "pages" / "RagSearchPage.test.tsx",
        ui / "app" / "router.tsx",
        ui / "components" / "layout" / "TopBar.tsx",
        repo / "ui" / "explorer" / "vite.config.ts",
    ]
    for p in pairs:
        if not p.exists():
            continue
        rel = p.relative_to(repo)
        out = dest / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, out)


def _run_pytest(repo: Path, out_txt: Path) -> int:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/rag", "tests/test_rag.py", "-q"],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    out_txt.write_text(proc.stdout + "\n" + proc.stderr, encoding="utf-8")
    return proc.returncode


def _zip_dir(src_dir: Path, zip_path: Path) -> None:
    if zip_path.exists():
        raise FileExistsError(f"Refusing to overwrite existing zip: {zip_path}")
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(src_dir.rglob("*")):
            if p.is_file():
                arc = p.relative_to(src_dir.parent).as_posix()
                zf.write(p, arc)


def main() -> int:
    repo = _repo_root()
    root_str = str(repo)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
    bundle_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S_%f")
    bundle = repo / "audit" / f"stage6_3_audit_bundle_{bundle_ts}"
    examples = bundle / "examples"
    source = bundle / "source"
    bundle.mkdir(parents=True)
    examples.mkdir(parents=True)

    rc = _run_pytest(repo, bundle / "test_output.txt")

    _copy_rag_package(repo, source)
    _copy_tests_rag(repo, source)
    _copy_audit_support_files(repo, source)
    _copy_ui_snippets(repo, source)
    for script in ("generate_stage63_audit_bundle.py", "rag_eval_runner.py"):
        sp = repo / "scripts" / script
        if sp.exists():
            dest = source / "scripts" / script
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(sp, dest)

    corpus = repo / "output_corpus"
    has_built = (repo / "output_rag" / "retrieval_docs_all.jsonl").exists()
    use_existing = os.environ.get(
        "STAGE63_USE_EXISTING_RAG",
        "1" if has_built else "0",
    ) == "1"
    rag_root = repo / "output_rag" if use_existing else bundle / "_staging_rag"

    examples_note: dict[str, Any] = {"note": "", "generated": False}
    can_generate_examples = corpus.exists() and (
        (use_existing and (rag_root / "retrieval_docs_all.jsonl").exists())
        or (not use_existing)
    )
    if can_generate_examples:
        try:
            from fastapi.testclient import TestClient

            from pipeline.rag.api import app, init_app
            from pipeline.rag.cli import run_build, run_eval
            from pipeline.rag.config import RAGConfig

            cfg = RAGConfig(corpus_root=corpus, rag_root=rag_root)
            if not use_existing:
                run_build(cfg)
            # Always regenerate eval artifacts so examples/ match current CURATED_QUERIES in source snapshot.
            run_eval(cfg, None)
            init_app(cfg)
            client = TestClient(app)

            search = client.post(
                "/rag/search",
                json={
                    "query": "stop loss placement",
                    "top_k": 5,
                    "unit_types": [],
                    "filters": {"lesson_ids": [], "concept_ids": [], "min_confidence_score": None},
                    "return_summary": True,
                    "require_evidence": False,
                },
            )
            (examples / "rag_search_response.json").write_text(
                json.dumps(search.json(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

            explain_body = {
                "query": "stop loss placement",
                "top_k": 5,
                "unit_types": [],
                "filters": {"lesson_ids": [], "concept_ids": [], "min_confidence_score": None},
                "return_summary": True,
                "require_evidence": False,
            }
            explain = client.post("/rag/search/explain", json=explain_body)
            if explain.status_code == 200:
                (examples / "rag_search_explain_response.json").write_text(
                    json.dumps(
                        {"request": explain_body, "status_code": explain.status_code, "response": explain.json()},
                        indent=2,
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )

            emb_manifest = cfg.index_dir / "embedding_manifest.json"
            if emb_manifest.exists():
                shutil.copy2(emb_manifest, examples / "sample_embedding_manifest.json")

            # Pick first rule_card and evidence from health/doc count via search hits
            hits = search.json().get("top_hits") or []
            rule_id = next((h.get("doc_id") for h in hits if h.get("unit_type") == "rule_card"), None)
            ev_id = next((h.get("doc_id") for h in hits if h.get("unit_type") == "evidence_ref"), None)

            if rule_id:
                item = client.get(f"/rag/item/rule_card/{rule_id}")
                if item.status_code == 200:
                    (examples / "rag_item_rule.json").write_text(
                        json.dumps(item.json(), indent=2, ensure_ascii=False),
                        encoding="utf-8",
                    )
                rel = client.get(f"/rag/related/rule_card/{rule_id}")
                if rel.status_code == 200:
                    (examples / "rag_related_rule.json").write_text(
                        json.dumps(rel.json(), indent=2, ensure_ascii=False),
                        encoding="utf-8",
                    )
            if ev_id:
                item_e = client.get(f"/rag/item/evidence_ref/{ev_id}")
                if item_e.status_code == 200:
                    (examples / "rag_item_evidence.json").write_text(
                        json.dumps(item_e.json(), indent=2, ensure_ascii=False),
                        encoding="utf-8",
                    )
            if not (examples / "rag_item_evidence.json").exists():
                from pipeline.rag.store import InMemoryDocStore

                st = InMemoryDocStore.load(cfg.rag_root / "retrieval_docs_all.jsonl")
                for d in st.get_by_unit("evidence_ref"):
                    did = d.get("doc_id")
                    if not did:
                        continue
                    item_e = client.get(f"/rag/item/evidence_ref/{did}")
                    if item_e.status_code == 200:
                        (examples / "rag_item_evidence.json").write_text(
                            json.dumps(item_e.json(), indent=2, ensure_ascii=False),
                            encoding="utf-8",
                        )
                        break

            eq = cfg.eval_dir / "rag_eval_queries.json"
            er = cfg.eval_dir / "rag_eval_report.json"
            if eq.exists():
                shutil.copy2(eq, examples / "rag_eval_queries.json")
            if er.exists():
                shutil.copy2(er, examples / "rag_eval_report.json")
            ev_res = cfg.eval_dir / "eval_results.json"
            if ev_res.exists():
                shutil.copy2(ev_res, examples / "rag_eval_results.json")

            eval_sync: dict[str, Any] = {}
            if er.exists():
                rep = json.loads(er.read_text(encoding="utf-8"))
                eq_path = examples / "rag_eval_queries.json"
                queries_in_examples: list[Any] = []
                if eq_path.exists():
                    raw_q = json.loads(eq_path.read_text(encoding="utf-8"))
                    queries_in_examples = raw_q if isinstance(raw_q, list) else []
                eval_sync = {
                    "eval_report_query_count": rep.get("query_count"),
                    "examples_queries_len": len(queries_in_examples),
                    "eval_generated_at": rep.get("generated_at"),
                    "sync_note": "Eval regenerated during bundle build; report query_count must equal len(rag_eval_queries.json).",
                }
                if rep.get("query_count") != len(queries_in_examples):
                    eval_sync["sync_warning"] = "MISMATCH: report query_count != examples query list length"

            sample_sqlite = cfg.rag_root / "rag_metadata.sqlite"
            dest_sql = examples / "sample_rag_metadata.sqlite"
            if sample_sqlite.exists():
                shutil.copy2(sample_sqlite, dest_sql)
            elif corpus.exists():
                from pipeline.rag.corpus_loader import load_corpus_and_build_docs
                from pipeline.rag.metadata_sqlite import write_retrieval_metadata_sqlite

                store = load_corpus_and_build_docs(cfg)
                meta = json.loads((corpus / "corpus_metadata.json").read_text(encoding="utf-8"))
                sv_blob: dict[str, Any] = {}
                sv_path = corpus / "schema_versions.json"
                if sv_path.exists():
                    raw_sv = json.loads(sv_path.read_text(encoding="utf-8"))
                    if isinstance(raw_sv, dict):
                        sv_blob = raw_sv
                write_retrieval_metadata_sqlite(
                    store,
                    dest_sql,
                    corpus_contract_version=str(meta.get("corpus_contract_version", "unknown")),
                    schema_versions_blob=sv_blob,
                    embedding_model_version=cfg.embedding_model,
                )

            examples_note = {
                "generated": True,
                "rag_root": str(cfg.rag_root),
                "eval_artifact_sync": eval_sync,
            }
        except Exception as exc:  # noqa: BLE001
            examples_note = {"generated": False, "error": str(exc)}
    else:
        examples_note = {
            "generated": False,
            "reason": "output_corpus or RAG artifacts missing; set STAGE63_USE_EXISTING_RAG=1 with a built output_rag",
        }

    (examples / "examples_manifest.json").write_text(
        json.dumps(examples_note, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    changed = "\n".join(
        sorted(
            str(p.relative_to(repo)).replace("\\", "/")
            for p in (repo / "pipeline" / "rag").rglob("*.py")
        )
    )
    _write(bundle / "changed_files.txt", changed + "\n")

    _write(
        bundle / "README.md",
        f"""# Stage 6.3 audit bundle ({bundle_ts} UTC)

Hybrid RAG database and retrieval API (Stage 6.2 corpus → retrieval units → BM25 + vectors + rerank).

Bundle id suffix is `YYYY-MM-DD_HHMMSS_microseconds` (UTC). Each script run creates a **new** folder and zip; existing bundles are not deleted or overwritten.

- **Source snapshot**: `source/` (RAG module, tests including `tests/test_rag.py`, `requirements-rag-audit.txt`, `pyproject.toml`).
- **Examples**: `examples/` (API JSON + eval artifacts regenerated on each bundle build).
- **Tests**: see `test_output.txt`.
- **Reproducibility**: read `REPRODUCIBILITY.md` (tests require full repo + deps, not `source/` alone).

Zip: `../stage6_3_audit_bundle_{bundle_ts}.zip`  
Duplicate: `../archives/stage6_3_audit_bundle_{bundle_ts}.zip`
""",
    )

    _write(
        bundle / "REPRODUCIBILITY.md",
        """# Audit bundle reproducibility

## What the zip is for

- `source/pipeline/rag/` is a **code snapshot** for review (diff against your checkout).
- `examples/` is **evidence** produced by the bundle script from the **same** repo revision (eval is re-run so query counts match `eval.py`).
- The snapshot is **not** a standalone Python package: `pipeline.rag.api` imports `pipeline.adjudication` and `pipeline.explorer`, which are **not** vendored in this zip.

## How to rerun tests (required path)

Use a **full clone** of `tim-class-pass` at the commit under review.

```bash
cd /path/to/tim-class-pass
python -m venv .venv
.venv\\Scripts\\activate   # Windows
pip install -r audit/requirements-rag-audit.txt
# Optional full project:
pip install -e .
python -m pytest tests/rag tests/test_rag.py -q
```

Bundled copies for reference: `source/requirements-rag-audit.txt`, `source/pyproject.toml`, `source/tests/test_rag.py`.

Do **not** run pytest with cwd = `source/` only; imports will fail.

## Eval artifacts vs source

After any change to `pipeline/rag/eval.py` (`CURATED_QUERIES`), regenerate the bundle so `examples/rag_eval_queries.json`, `examples/rag_eval_report.json`, and `examples/rag_eval_results.json` match. The bundle script always runs `run_eval` before copying. Check `examples/examples_manifest.json` → `eval_artifact_sync` for query-count parity.

## Regenerate this bundle

```bash
python scripts/generate_stage63_audit_bundle.py
```

Each run creates a **new** UTC-timestamped folder under `audit/` and a matching zip (and archive copy). Older bundles are not removed or overwritten.
""",
    )

    _write(
        bundle / "RUN_AUDIT_TESTS.md",
        """# Rerun audit checks

All commands assume the **repository root** of a full `tim-class-pass` checkout (see `REPRODUCIBILITY.md`).

## Install dependencies

```bash
pip install -r audit/requirements-rag-audit.txt
# or full project:
pip install -e .
```

## Backend unit tests

```bash
python -m pytest tests/rag tests/test_rag.py -q
```

The bundle includes `source/tests/test_rag.py` as a mirror of `tests/test_rag.py` for review; pytest must still be run from **repo root** so `pipeline.*` resolves.

## Build RAG from corpus (6.2 outputs)

```bash
python -m pipeline.rag.cli build --corpus-root output_corpus --rag-root output_rag
```

## Evaluation harness (refreshes eval dir)

```bash
python scripts/rag_eval_runner.py --rag-root output_rag --corpus-root output_corpus
```

Outputs under `output_rag/eval/`: `eval_queries.json`, `eval_results.json`, `eval_report.json`, `rag_eval_queries.json`, `rag_eval_report.json` (and `examples/rag_eval_results.json` mirrors `eval_results.json` in the bundle). Query count must match `len(CURATED_QUERIES)` in `pipeline/rag/eval.py`.

## Explain search (debug trace)

```bash
curl -s -X POST http://127.0.0.1:8000/rag/search/explain -H "Content-Type: application/json" -d '{"query":"levels","top_k":5}'
```

## API server

```bash
python -m pipeline.rag.cli serve --rag-root output_rag --corpus-root output_corpus
```

## Explorer UI (optional)

```bash
cd ui/explorer && npm test && npm run dev
```

## Regenerate this audit zip

```bash
python scripts/generate_stage63_audit_bundle.py
```

`STAGE63_USE_EXISTING_RAG=1` (default when `output_rag` exists) skips corpus rebuild but still **re-runs eval** so examples stay aligned with `eval.py`.
""",
    )

    _write(
        bundle / "AUDIT_HANDOFF.md",
        f"""# Stage 6.3 — Audit handoff ({bundle_ts} UTC)

## 1. What was implemented

- Hybrid RAG ingestion from Stage 6.2 corpus JSONL/JSON into typed retrieval units (rules, events, evidence, concept nodes/relations).
- SQLite metadata mirror (`rag_metadata.sqlite`) plus JSONL docs and file-based lexical/vector indexes.
- Hybrid retrieval: BM25 + embeddings + concept expansion + deterministic reranking.
- FastAPI routes under `/rag` including `POST /rag/search`, `POST /rag/search/explain`, `GET /rag/item/...`, `GET /rag/related/...`, `GET /rag/explore/lesson/...`, eval and facets.
- Minimal explorer page at `/rag` in `ui/explorer` calling the retrieval API.
- Evaluation harness with `rag_eval_queries.json` / `rag_eval_report.json` / `rag_eval_results.json` mirrors.
- Contract: `pipeline/rag/rag_contract_v1.md`.

## 2. Definition of done checklist

- [x] corpus ingestion pipeline implemented
- [x] embedding job implemented
- [x] hybrid retrieval implemented
- [x] separate retrieval units indexed
- [x] retrieval API implemented
- [x] provenance/timestamps preserved
- [x] minimal explorer implemented
- [x] representative eval set implemented
- [x] tests run
- [x] audit zip created

## 3. Retrieval unit design

See `rag_contract_v1.md` in `source/pipeline/rag/`.

## 4. Metadata / vector storage

- JSONL: `retrieval_docs_all.jsonl`
- SQLite: `rag_metadata.sqlite` table `retrieval_unit`
- Indexes: `output_rag/index/` (BM25 manifest + embedding `.npy` + manifest JSON)

## 5. Hybrid retrieval and reranking

Lexical + vector candidate generation, merged and reranked with intent-aware unit weights and graph boosts (`retriever.py`, `reranker.py`).

## 6. API contract

Stable JSON shapes via Pydantic `SearchRequest` / `SearchResponse`; item and related endpoints return full or linked provenance payloads.

## 7. Explorer scope

Single **RAG search** page: query, optional “require evidence”, hit list with links into existing rule/evidence/concept routes.

## 8. Evaluation query set

Curated queries in `pipeline/rag/eval.py` (`CURATED_QUERIES`); written to `eval_queries.json` and `rag_eval_queries.json` on run.

## 9. Commands run

- `python -m pytest tests/rag tests/test_rag.py -q`
- Bundle script may run `run_build` / `run_eval` when corpus and env allow.

## 10. Tests run

See `test_output.txt` in this folder.

## 11. Example outputs

See `examples/` (`rag_search_response.json`, `rag_search_explain_response.json`, `sample_embedding_manifest.json`, `sample_rag_metadata.sqlite`, `rag_eval_results.json`, etc.). Eval files are **regenerated during bundle build** so `rag_eval_queries.json` row count matches `eval.py` `CURATED_QUERIES`. Verify `examples/examples_manifest.json` → `eval_artifact_sync` (no `sync_warning`).

## 12. Reproducibility

- `REPRODUCIBILITY.md` and `source/requirements-rag-audit.txt`: minimal deps (`rank-bm25`, `sentence-transformers`, etc.).
- Rerun pytest only from a **full repo checkout**, not from `source/` alone (`pipeline.rag.api` depends on adjudication + explorer).

## 13. Known limitations

- No Postgres/pgvector in default path; vectors are local numpy archives.
- Full corpus embedding build requires `sentence-transformers` model download on first run.

## 14. Deferred work

- Incremental upsert; pgvector adapter; LLM reranking; richer analyst workflows.

## 15. Zip location

`audit/stage6_3_audit_bundle_{bundle_ts}.zip` and `audit/archives/stage6_3_audit_bundle_{bundle_ts}.zip`.
""",
    )

    zip_path = repo / "audit" / f"stage6_3_audit_bundle_{bundle_ts}.zip"
    _zip_dir(bundle, zip_path)

    archives = repo / "audit" / "archives"
    archives.mkdir(parents=True, exist_ok=True)
    archive_copy = archives / zip_path.name
    shutil.copy2(zip_path, archive_copy)

    print(f"Bundle: {bundle}")
    print(f"Zip: {zip_path}")
    print(f"Archive copy: {archive_copy}")
    print(f"pytest exit code: {rc}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
