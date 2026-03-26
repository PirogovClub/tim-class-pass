# Rerun audit checks

Assumptions: Python 3.12+, repo root, optional `uv` or venv with project deps.

## Backend unit tests
```bash
python -m pytest tests/rag tests/test_rag.py -q
```

## Build RAG from corpus (6.2 outputs)
```bash
python -m pipeline.rag.cli build --corpus-root output_corpus --rag-root output_rag
```

## Evaluation harness
```bash
python scripts/rag_eval_runner.py --rag-root output_rag --corpus-root output_corpus
```
Outputs: `output_rag/eval/eval_report.json`, `rag_eval_report.json`, `rag_eval_queries.json` (34+ curated queries including Stage 6.3 §15.1 representative phrasing).

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
Open `/rag` for hybrid search page; Vite proxies `/rag` to the API.

## Regenerate this bundle
```bash
python scripts/generate_stage63_audit_bundle.py
```
Use `STAGE63_USE_EXISTING_RAG=1` to skip rebuild when `output_rag` is already populated.
