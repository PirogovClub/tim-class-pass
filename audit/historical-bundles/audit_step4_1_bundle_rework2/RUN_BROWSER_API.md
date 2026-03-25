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

## Notes

- The browser API is mounted by `pipeline/rag/api.py`.
- Startup initializes the normal RAG retriever first, then initializes the explorer repository and service from the same config roots.
