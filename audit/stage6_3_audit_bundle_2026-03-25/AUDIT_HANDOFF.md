# Stage 6.3 — Audit handoff (2026-03-25)

## 1. What was implemented

- Hybrid RAG ingestion from Stage 6.2 corpus JSONL/JSON into typed retrieval units (rules, events, evidence, concept nodes/relations).
- SQLite metadata mirror (`rag_metadata.sqlite`) plus JSONL docs and file-based lexical/vector indexes.
- Hybrid retrieval: BM25 + embeddings + concept expansion + deterministic reranking.
- FastAPI routes under `/rag` including `POST /rag/search`, `POST /rag/search/explain`, `GET /rag/item/...`, `GET /rag/related/...`, `GET /rag/explore/lesson/...`, eval and facets.
- Minimal explorer page at `/rag` in `ui/explorer` calling the retrieval API.
- Evaluation harness with `rag_eval_queries.json` / `rag_eval_report.json` mirrors.
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

See `examples/` (`rag_search_response.json`, `rag_search_explain_response.json`, `sample_embedding_manifest.json`, `sample_rag_metadata.sqlite`, etc.) when generation succeeded; else `examples/examples_manifest.json` explains gaps.

## 12. Known limitations

- No Postgres/pgvector in default path; vectors are local numpy archives.
- Full corpus embedding build requires `sentence-transformers` model download on first run.

## 13. Deferred work

- Incremental upsert; pgvector adapter; LLM reranking; richer analyst workflows.

## 14. Zip location

`audit/stage6_3_audit_bundle_2026-03-25.zip` (sibling of this folder).
