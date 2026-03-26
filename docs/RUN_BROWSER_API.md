# Run Browser API

## Purpose

Step 4.1 mounts the explorer backend on the existing FastAPI RAG service under `/browser/*`.

## Bootstrap

From the repo root:

```powershell
python -m pipeline.rag.cli serve --rag-root output_rag --corpus-root output_corpus --host 127.0.0.1 --port 8000
```

## Expected host and port

- Host: `127.0.0.1`
- Port: `8000`
- Base URL: `http://127.0.0.1:8000`

## Required env vars

- None required for local startup against existing `output_rag/` and `output_corpus/`.

## Optional env vars

- `HF_TOKEN`: optional only, suppresses anonymous Hugging Face rate-limit warnings during embedding model load.
- `ADJUDICATION_DB_PATH`: SQLite file for Stage 5 adjudication (default `var/adjudication.db`). The RAG app initializes this path on startup when `init_app` runs; the file is created on first use.

## Quick checks

```powershell
curl http://127.0.0.1:8000/browser/health
curl http://127.0.0.1:8000/browser/facets
```

Search example:

```powershell
curl -X POST http://127.0.0.1:8000/browser/search `
  -H "Content-Type: application/json" `
  -d "{\"query\":\"Пример постановки стоп-лосса\",\"top_k\":5,\"filters\":{\"lesson_ids\":[],\"concept_ids\":[],\"unit_types\":[],\"support_basis\":[],\"evidence_requirement\":[],\"teaching_mode\":[],\"min_confidence_score\":null},\"return_groups\":true}"
```

## Adjudication API (Stage 5)

Same FastAPI process also mounts **`/adjudication/*`** (review items, queues, tiers, proposals, metrics). Queues and tier endpoints need a **corpus index** built from the explorer repository; if the explorer failed to init, those routes may respond **503** `corpus_index_unavailable`.

Quick checks (after `serve` is up):

```powershell
curl http://127.0.0.1:8000/adjudication/tiers/counts
curl http://127.0.0.1:8000/adjudication/metrics/summary
```

Full route list and semantics: [`../pipeline/adjudication/docs.md`](../pipeline/adjudication/docs.md).

## Notes

- The browser API is mounted by `pipeline/rag/api.py`.
- The adjudication router is mounted by the same module (`adjudication_router`); metrics live under `/adjudication/metrics/`.
- Startup initializes the normal RAG retriever first, then initializes the explorer repository and service from the same config roots, then adjudication with `ADJUDICATION_DB_PATH`.
