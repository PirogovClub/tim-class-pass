# Gemini Batch Orchestration -- Overview

This is the top-level context document for adding Gemini native Batch API
support to the tim-class-pass multimodal video-processing framework. It
describes the current repo state and the additive batch layer architecture.
Implementation details live in the companion files `01-*` through `09-*`.

---

## Authoritative documentation

| Document | Governs |
|----------|---------|
| [pipeline.md](../../pipeline.md) | End-to-end Step 0-3 flow, data-flow Mermaid, per-step artifact lifecycle |
| [pipeline_structure_and_features.md](../../pipeline_structure_and_features.md) | Canonical output-path contract (`PipelinePaths`), feature flags, stage registry |
| [FRAMEWORK_MODULES.md](../../FRAMEWORK_MODULES.md) | Module/function responsibility map, trigger tables |
| [framework_file_function_reference.md](../../framework_file_function_reference.md) | Flat function/file lookup index |
| [corpus-contract-v1.md](../corpus-contract-v1.md) | Frozen v1 per-lesson input contract, global ID patterns, referential integrity |
| [step2_corpus_build_notes.md](../../step2_corpus_build_notes.md) | Corpus merge CLI (`pipeline/corpus/`), enrichment, validation |

> **"Step 2" naming collision:** The main pipeline calls dense frame analysis
> "Step 2" (`pipeline/dense_analyzer.py`). The corpus docs call the multi-lesson
> merge "Step 2" (`pipeline/corpus/`). These files always qualify which is meant.

---

## Current repo state

### Path contract

All lesson artifact paths are defined in `pipeline/contracts.py` via the frozen
dataclass `PipelinePaths`. Every path method takes a `lesson_name` argument and
returns a lesson-prefixed file, for example:

- `knowledge_events_path(lesson_name)` -> `output_intermediate/<lesson>.knowledge_events.json`
- `evidence_index_path(lesson_name)` -> `output_intermediate/<lesson>.evidence_index.json`
- `rule_cards_path(lesson_name)` -> `output_intermediate/<lesson>.rule_cards.json`

`PipelinePaths` currently ends at `ensure_output_dirs()` which creates three
directories: `output_intermediate/`, `output_review/`, `output_rag_ready/`.
There are **no** batch-related path helpers today. The `batch_*` methods
proposed in `02-paths-and-client.md` are new additions.

### Sync Gemini client

`helpers/clients/gemini_client.py` provides `get_client()` (cached `genai.Client`),
`generate_content_result()` with 3-attempt retry, `generate_content_stream_result()`,
and model resolution via `get_model_for_step()`. It is the shared transport for all
Gemini sync calls. Batch lifecycle (upload, create job, poll, download) does not
exist in this module and will live in a new file.

### Dense vision analysis (main pipeline Step 2)

`pipeline/dense_analyzer.py` owns frame-level analysis. Key reusable seams:

| Symbol | Purpose |
|--------|---------|
| `_parse_json_from_response(text)` | Strip markdown fences, parse JSON with truncation recovery |
| `_encode_image(path)` | Read file, return base64 string |
| `get_batch_prompt(entries, video_dir, prev_state)` | Build production prompt for sequential frame batch |
| `get_batch_prompt_independent(entries, video_dir)` | Same prompt without previous-state (parallel) |
| `run_analysis(video_id, ...)` | Full Step 2 orchestration (IDE/API/merge-only/chunk modes) |
| `PRODUCTION_PROMPT` | Canonical vision extraction prompt text |

Batch spool emission must reuse the prompt builders and parser, not duplicate them.

### Component 2 LLM processor (Step 3 knowledge + render)

`pipeline/component2/llm_processor.py` owns knowledge extraction and markdown
render LLM calls. Key reusable seams:

| Symbol | Purpose |
|--------|---------|
| `build_knowledge_extract_prompt(...)` | Build extraction prompt for one adapted chunk |
| `parse_knowledge_extraction(payload)` | Parse response into `ChunkExtractionResult` |
| `build_markdown_render_prompt(...)` | Build render prompt from rule cards + evidence |
| `parse_markdown_render_result(payload)` | Parse response into `MarkdownRenderResult` |
| `process_chunks_knowledge_extract(...)` | Async per-chunk extraction with concurrency cap |
| `process_rule_cards_markdown_render(...)` | Sync rule-card render call |
| `_call_provider_for_mode(...)` | Generic provider dispatch with retry on truncation |
| `KNOWLEDGE_EXTRACT_SYSTEM_PROMPT` | System prompt for knowledge extraction mode |
| `MARKDOWN_RENDER_SYSTEM_PROMPT` | System prompt for markdown render mode |

Batch materialization must call the same parsers (`parse_knowledge_extraction`,
`parse_markdown_render_result`) and downstream writers (`save_knowledge_events`,
`build_knowledge_events_from_extraction_results`, etc.) so that downstream stages
(evidence linker, rule reducer, concept graph, exporters) receive identical
artifact shapes.

### Existing Component 2 orchestrator (preflight only)

`pipeline/component2/orchestrator.py` already exists. It contains
`Component2RunConfig`, `Component2RunArtifacts`, and `prepare_component2_run()`
which writes the `pipeline_inspection.json` preflight report. This is **not** the
batch orchestrator. The new `pipeline/orchestrator/` package proposed in
`01-state-store.md` is a separate top-level package for multi-video batch
lifecycle management.

### CLI entrypoints

| Entrypoint | Module | Framework |
|------------|--------|-----------|
| `uv run tim-class-pass` | `pipeline/main.py` | Click |
| `uv run python -m pipeline.component2.main` | `pipeline/component2/main.py` | Click |
| `python -m pipeline.corpus` | `pipeline/corpus/__main__.py` -> `cli.py` | Click |

Click is already a dependency in `pyproject.toml` (`click>=8.0.0`). The new
batch CLI should use Click for consistency.

### Feature flags

`pipeline/contracts.py` defines `PipelineFeatureFlags` with defaults:

- `preserve_legacy_markdown = True`
- `enable_knowledge_events = False`
- `enable_rule_cards = False`
- `enable_evidence_index = False`
- `enable_concept_graph = False`
- `enable_exporters = False`
- `enable_ml_prep = False`

These flags gate optional structured stages in `run_component2_pipeline()`.
Batch orchestration must respect them when planning stage runs.

### Stage order (Component 2)

From `docs/pipeline_structure_and_features.md` and `pipeline/component2/main.py`:

1. Invalidation filter (local, deterministic)
2. Parse VTT + sync chunks (local, deterministic)
3. Knowledge extraction (LLM -- batch-eligible)
4. Evidence linking (local, deterministic; requires knowledge events)
5. Rule cards (local, deterministic; requires knowledge + evidence)
6. Concept graph (local, deterministic; requires rule cards)
7. Exporters (local, deterministic; requires rule cards + evidence)
8. Legacy Pass 1 markdown (LLM -- batch-eligible)
9. Legacy Pass 2 reducer (LLM -- batch-eligible but single-doc; low priority)

Only stages marked **batch-eligible** will have spool/materialize support.
Deterministic stages remain local and consume the same saved artifacts.

### Existing tests

| Test file | Covers |
|-----------|--------|
| `tests/test_dense_analyzer.py` | Step 2 analysis, parsing, normalization |
| `tests/test_llm_processor.py` | LLM processor prompts, parsers, modes |
| `tests/test_component2_pipeline.py` | Full `run_component2_pipeline` with mocked providers |
| `tests/test_knowledge_builder.py` | `adapt_chunks`, `build_knowledge_events_from_extraction_results` |
| `tests/test_evidence_linker.py` | Evidence linking + candidate grouping |
| `tests/test_schemas.py` | Pydantic models + export validation |
| `tests/test_corpus.py` | Corpus discover, merge, validate |
| `tests/test_output_layout.py` | `PipelinePaths` path methods |
| `tests/test_pipeline_invariants.py` | Artifact shape invariants |
| `tests/test_pipeline_regression.py` | Regression guards for known outputs |
| `tests/integration/test_lesson2_artifact_regression.py` | Lesson 2 artifact structure, provenance, cross-file integrity |

None of these tests may regress. Batch tests are additive.

### Config

`helpers/config.py` loads `data/<video_id>/pipeline.yml`, merges defaults,
env vars, and CLI overrides. Batch-specific config keys (proposed in
`09-operations.md`) will be added here with safe defaults that do not
affect existing sync runs.

---

## Gemini native Batch API constraints

Source: [Batch API | Google AI for Developers](https://ai.google.dev/gemini-api/docs/batch-api)

- JSONL lines shaped as `{"key": "...", "request": {...}}`
- Uploaded input files for larger jobs; inline for totals under 20 MB
- Batch input files up to 2 GB; Files API storage up to 20 GB per project
- Create jobs with `client.batches.create(model=..., src=uploaded_file.name, ...)`
- Poll with `client.batches.get(name=...)`
- Download results from `batch_job.dest.file_name` via `client.files.download(...)`
- 50% of interactive cost; 24-hour turnaround target
- 48-hour file retention

---

## Non-negotiable constraints

- DO NOT rewrite the existing synchronous pipeline.
- DO NOT break existing single-video execution.
- ADD a new orchestration + batch layer that reuses existing stage logic.
- Preserve all existing parsing, normalization, schema validation, and artifact-writing logic.
- Keep batch support provider-specific to Gemini for now.
- Use native Gemini Batch format with per-line `key`, not a custom top-level `id`.
- Write per-lesson spool fragments, then assemble central batch files.
- SQLite stores orchestration metadata only. Heavy payloads remain on disk as JSONL and normal artifacts.
- CLI only. No web UI, no Streamlit, no curses.

---

## Architecture: sync flow vs. batch layer

```
Existing sync path (unchanged):
  run_component2_pipeline()
    -> filter -> parse -> [knowledge_extract LLM] -> evidence -> rules -> ...
    -> [legacy_markdown LLM] -> reducer

New batch layer (additive):
  batch_cli discover -> plan -> spool -> assemble -> submit -> poll -> download -> materialize
    |                                                                                |
    |  pipeline/orchestrator/ (new)                                                  |
    |  SQLite state in var/pipeline_state.db                                         |
    |                                                                                |
    +---> spool: calls same prompt builders from dense_analyzer / llm_processor      |
    +---> materialize: calls same parsers + artifact writers                     <---+
```

Key principle: spool and materialize wrap the existing modules; they never
duplicate prompt construction, response parsing, or artifact writing.

---

## Present-vs-proposed module map

| Existing module | Proposed new module | Relationship |
|-----------------|---------------------|--------------|
| `helpers/clients/gemini_client.py` | `helpers/clients/gemini_batch_client.py` | New file; may share `get_client()` |
| `pipeline/contracts.py` (PipelinePaths) | Same file, extended | Add `batch_*` path helpers |
| `pipeline/dense_analyzer.py` | Same file, extended | Add `emit_batch_spool_for_analysis()`, `materialize_batch_results_for_analysis()` |
| `pipeline/component2/llm_processor.py` | Same file, extended | Add `emit_batch_spool_for_knowledge_extract()`, `materialize_batch_results_for_knowledge_extract()`, `emit_batch_spool_for_markdown_render()`, `materialize_batch_results_for_markdown_render()` |
| `pipeline/component2/orchestrator.py` (preflight) | Unchanged | Naming collision: the new `pipeline/orchestrator/` package is separate |
| _(does not exist)_ | `pipeline/orchestrator/__init__.py` | New package |
| _(does not exist)_ | `pipeline/orchestrator/models.py` | Enums, request key helpers |
| _(does not exist)_ | `pipeline/orchestrator/state_store.py` | SQLite state store |
| _(does not exist)_ | `pipeline/orchestrator/discovery.py` | Multi-video discovery + planning |
| _(does not exist)_ | `pipeline/orchestrator/run_manager.py` | Submit, poll, download, retry |
| _(does not exist)_ | `pipeline/orchestrator/batch_assembler.py` | Merge spool fragments into batch files |
| _(does not exist)_ | `pipeline/orchestrator/status_service.py` | Status formatting |
| _(does not exist)_ | `pipeline/batch_cli.py` | Click CLI for batch workflow |

---

## Design rationale

**Per-lesson spool fragments first, central batch assembly second.** This is the
critical architectural choice. It matches the existing layout where lesson
artifacts have a strong home under `PipelinePaths`, and downstream stages expect
normal per-lesson artifacts rather than one global batch blob. It makes retry,
resume, and multi-video processing tractable.

**Batch scope limited to LLM-heavy stages only.** The framework has many
deterministic/local stages after LLM extraction -- evidence linking, rule
reduction, concept graph, exporters, validations -- and those must keep
consuming the same saved artifacts they already expect. This preserves the
current tests and artifact contracts documented in
`docs/pipeline_structure_and_features.md`.

**Naming isolation.** The new `pipeline/orchestrator/` package is intentionally
separate from the existing `pipeline/component2/orchestrator.py` (which handles
preflight inspection only). The batch CLI is `pipeline/batch_cli.py`, not mixed
into the existing `pipeline/main.py` or `pipeline/component2/main.py`.

---

## Companion files

| File | Contents |
|------|----------|
| `01-state-store.md` | Phase 1 + Phase 4: SQLite schema, models, request keys |
| `02-paths-and-client.md` | Phase 2 + Phase 3: PipelinePaths batch dirs, gemini_batch_client |
| `03-vision-batch.md` | Phase 5: dense_analyzer spool + materialize |
| `04-text-llm-batch.md` | Phase 6: llm_processor knowledge_extract + markdown_render |
| `05-assembler.md` | Phase 7: batch assembler |
| `06-submit-poll.md` | Phase 8: run_manager, status_service |
| `07-discovery-cli.md` | Phase 9 + Phase 10: discovery, planning, CLI commands |
| `08-testing.md` | Phase 13 + Lesson 2 comparison testing (3 layers) |
| `09-operations.md` | Phase 11 + 14 + 15 + 16: sync compat, config, acceptance, order |
