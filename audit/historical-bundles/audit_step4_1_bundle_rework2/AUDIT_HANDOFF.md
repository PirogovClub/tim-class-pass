# Step 4.1 Explorer Backend Audit Handoff

## A. Summary

Step 4.1 is complete for the backend read-model layer:

- read-only explorer repository over existing RAG and corpus artifacts
- browser-friendly contracts and deterministic result cards
- mounted FastAPI `/browser/*` endpoints
- rule, evidence, concept, lesson, neighbor, and facets payloads
- explorer tests plus Step 3.1 regression protection
- real saved browser API JSON outputs
- manifest and design/contracts docs

Intentionally deferred for later steps:

- frontend UI
- write-back or annotation flows
- auth and multi-user concerns
- deployment packaging
- Step 5 ML work
- export workflows beyond the audit artifacts in this bundle

## B. Files Changed

### Added

- `pipeline/explorer/__init__.py`
- `pipeline/explorer/contracts.py`
- `pipeline/explorer/loader.py`
- `pipeline/explorer/views.py`
- `pipeline/explorer/service.py`
- `pipeline/explorer/api.py`
- `tests/explorer/__init__.py`
- `tests/explorer/conftest.py`
- `tests/explorer/test_service.py`
- `tests/explorer/test_views.py`
- `tests/explorer/test_api.py`
- `docs/step4_explorer_contracts.md`
- `docs/step4_explorer_notes.md`
- `RUN_BROWSER_API.md`
- `AUDIT_HANDOFF.md`
- `explorer_build_manifest.json`
- `browser_routes.txt`
- `browser_api_samples/health.json`
- `browser_api_samples/search_empty.json`
- `browser_api_samples/search_stop_loss_example.json`
- `browser_api_samples/search_timeframe_rules.json`
- `browser_api_samples/search_daily_level.json`
- `browser_api_samples/search_concept_heavy.json`
- `browser_api_samples/search_support_policy.json`
- `browser_api_samples/search_support_policy_transcript.json`
- `browser_api_samples/search_lesson_constrained.json`
- `browser_api_samples/search_empty_results.json`
- `browser_api_samples/rule_detail_stop_loss.json`
- `browser_api_samples/evidence_detail_stop_loss.json`
- `browser_api_samples/concept_detail_node_stop_loss.json`
- `browser_api_samples/concept_neighbors_node_stop_loss.json`
- `browser_api_samples/lesson_detail_stop_loss_lesson.json`
- `browser_api_samples/facets.json`
- `browser_api_samples/errors/unknown_rule.json`
- `browser_api_samples/errors/wrong_unit_type_rule.json`
- `browser_api_samples/errors/unknown_concept.json`
- `browser_api_samples/errors/unknown_lesson.json`
- `browser_api_samples/errors/bad_search_request.json`
- `pytest_output.txt`

### Modified

- `pipeline/rag/api.py`
- `pyproject.toml`
- `tests/test_pipeline_integration.py`
- `tests/test_pipeline_invariants.py`
- `tests/test_pipeline_optional_live.py`
- `tests/test_pipeline_regression.py`
- `ui/tests/e2e/test_operator_ui.py`

The non-explorer test edits above were made only to make the full-suite audit run robust in this environment:

- root tests now import `tests.conftest` explicitly instead of ambiguous `from conftest import ...`
- the Playwright e2e test now skips cleanly when `playwright` is not installed
- pytest now ignores `audit_step4_1_bundle/` during collection so the packaged audit copy does not shadow the live repo tests

## C. Commands Run

### Full test suite

```powershell
pytest -q 2>&1 | Tee-Object -FilePath "pytest_output.txt"
```

Final result:

- `747 passed`
- `5 skipped`

### Sample / manifest / route generation

Browser samples, `explorer_build_manifest.json`, and `browser_routes.txt` were generated from the mounted FastAPI app in-process by:

1. creating `cfg = RAGConfig()`
2. calling `init_app(cfg)`
3. using `TestClient(app)` to hit the real `/browser/*` routes
4. saving JSON responses to `browser_api_samples/`

This was run from the repo root in PowerShell via inline `python -` scripts so the saved files are produced from the actual initialized API surface, not hand-authored JSON.

### Manual API startup command

```powershell
python -m pipeline.rag.cli serve --rag-root output_rag --corpus-root output_corpus --host 127.0.0.1 --port 8000
```

## D. Data Roots Used

- RAG root: `H:\GITS\tim-class-pass\output_rag`
- Corpus root: `H:\GITS\tim-class-pass\output_corpus`

## E. IDs Used In Sample Generation

- Rule doc id: `rule:2025_09_29_sviatoslav_chornyi:rule_2025_09_29_sviatoslav_chornyi_stop_loss_technical_stop_loss_5`
- Evidence doc id: `evidence:2025_09_29_sviatoslav_chornyi:evcand_2025-09-29-sviatoslav-chornyi_0_0`
- Concept id: `node:stop_loss`
- Lesson id: `2025-09-29-sviatoslav-chornyi`

Sample filename note:

- The detail sample filenames use stable descriptive aliases, not raw ids:
- `browser_api_samples/rule_detail_stop_loss.json`
- `browser_api_samples/evidence_detail_stop_loss.json`
- `browser_api_samples/lesson_detail_stop_loss_lesson.json`

Use the ids above to map those samples exactly.

## F. Known Limitations

- Explorer directly loads `retrieval_docs_all.jsonl` plus corpus metadata/graph exports. It does not directly load the per-unit retrieval JSONL files.
- Individual retrieval JSONL files and corpus JSONL exports are present and listed in `explorer_build_manifest.json`, but they are informative inputs for audit verification rather than direct Step 4.1 repository dependencies.
- `GET /browser/facets` computes counts over the full filtered explorer set. The embedded `facets` field inside `POST /browser/search` remains page-scoped to the returned cards.
- Query-mode filtering is post-retrieval. The explorer relies on the accepted `HybridRetriever` for candidate generation.
- `search_support_policy.json` is the q023 visual-evidence policy case. `search_support_policy_transcript.json` is extra q022 transcript-policy proof.
- Endpoint names match the scoped Step 4.1 design exactly. Only some sample filenames use descriptive aliases instead of literal ids.
- No artifact formats were changed for Step 4.1. The explorer consumes existing Step 3 outputs as read-only inputs.
