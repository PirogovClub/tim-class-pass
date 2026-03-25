# Pipeline structure and features

This document describes the **current pipeline layout**, **output contracts**, and **optional features** implemented from the knowledge-refactoring work (Tasks 7–12). It complements [README.md](../README.md), [pipeline.md](pipeline.md), and [FRAMEWORK_MODULES.md](FRAMEWORK_MODULES.md).

---

## 1. Output layout (single source of truth)

All paths are defined in **`pipeline/contracts.py`** via `PipelinePaths`. No code should build output paths manually; use `PipelinePaths` and its methods.

### 1.1 Directories

| Directory | Purpose |
|-----------|---------|
| `output_intermediate/` | Chunks, Pass 1 markdown, LLM/reducer debug, and all structured JSON (knowledge_events, evidence_index, rule_cards, debug files). |
| `output_review/` | Exporter output: `*.review_markdown.md`, review render debug, `*.export_manifest.json`. |
| `output_rag_ready/` | Legacy reducer output (`*.md`) and exporter output (`*.rag_ready.md`), plus RAG render debug. |

`PipelinePaths.ensure_output_dirs()` creates these three directories when needed.

### 1.2 Per-lesson artifacts (by lesson name)

For a lesson name derived from the VTT stem (e.g. `"Lesson 2. Levels part 1"`):

| Artifact | Path (method) | When present |
|----------|----------------|--------------|
| Chunks | `lesson_chunks_path(lesson_name)` → `*.chunks.json` | After parse & sync |
| Pass 1 markdown | `pass1_markdown_path(lesson_name)` → `*.md` | After legacy markdown synthesis |
| LLM debug | `llm_debug_path(lesson_name)` → `*.llm_debug.json` | After Pass 1 |
| Reducer usage | `reducer_usage_path(lesson_name)` → `*.reducer_usage.json` | After Pass 2 |
| Knowledge events | `knowledge_events_path(lesson_name)` → `*.knowledge_events.json` | With `--enable-knowledge-events` |
| Knowledge debug | `knowledge_debug_path(lesson_name)` → `*.knowledge_debug.json` | With knowledge extraction |
| Evidence index | `evidence_index_path(lesson_name)` → `*.evidence_index.json` | With `--enable-evidence-linking` |
| Evidence debug | `evidence_debug_path(lesson_name)` → `*.evidence_debug.json` | With evidence linking |
| Rule cards | `rule_cards_path(lesson_name)` → `*.rule_cards.json` | With `--enable-rule-cards` |
| Rule debug | `rule_debug_path(lesson_name)` → `*.rule_debug.json` | With rule cards |
| Concept graph | `concept_graph_path(lesson_name)` → `*.concept_graph.json` | With `--enable-concept-graph` |
| Concept graph debug | `concept_graph_debug_path(lesson_name)` → `*.concept_graph_debug.json` | With concept graph |
| Review markdown | `review_markdown_path(lesson_name)` → `*.review_markdown.md` | With `--enable-exporters` |
| RAG ready (legacy) | `rag_ready_markdown_path(lesson_name)` → `*.md` | After legacy reducer |
| RAG ready (export) | `rag_ready_export_path(lesson_name)` → `*.rag_ready.md` | With `--enable-exporters` |
| Export manifest | `export_manifest_path(lesson_name)` → `*.export_manifest.json` | With exporters |

Root-level paths:

- `filtered_visuals_path` → `filtered_visual_events.json`
- `filtered_visuals_debug_path` → `filtered_visual_events.debug.json`
- `inspection_report_path()` → `pipeline_inspection.json`

**Legacy vs new RAG files:** Legacy final markdown is `output_rag_ready/<lesson>.md`. The exporter writes `output_rag_ready/<lesson>.rag_ready.md`. Both coexist; the pipeline does not overwrite the legacy file with the new one.

---

## 2. Stage registry and inspection

**`pipeline/stage_registry.py`** holds a machine-readable list of pipeline stages (`StageSpec`: stage_id, description, callable_path, required_inputs, outputs). It is used by:

- **Inspection:** `pipeline/inspection.py` builds a report of resolvable stages and artifact checks, written to `pipeline_inspection.json` (path from `PipelinePaths.inspection_report_path()`).

Stages include Step 0–2, Step 3 (invocation filter, parse/sync, markdown LLM, reducer), and the optional structured steps:

- `step3_2b_knowledge_events` → `*.knowledge_events.json`
- `step4_evidence_linking` → `*.evidence_index.json`
- `step4b_rule_cards` → `*.rule_cards.json`
- `step12_concept_graph` → `*.concept_graph.json`, `*.concept_graph_debug.json`
- `step5_exporters` → `output_review/*.review_markdown.md`, `output_rag_ready/*.rag_ready.md`

---

## 3. Optional features (Component 2)

The Component 2 + Step 3 pipeline (`pipeline/component2/main.py`) supports optional stages controlled by flags. Default behavior is **legacy only**: invalidation filter, parse/sync, Pass 1 markdown, Pass 2 reducer, writing `output_intermediate/*.md` and `output_rag_ready/*.md`.

### 3.1 Feature flags (CLI / `run_component2_pipeline`)

| Flag | Effect |
|------|--------|
| `--enable-knowledge-events` | Run knowledge extraction from chunks → write `*.knowledge_events.json` and `*.knowledge_debug.json`. |
| `--enable-evidence-linking` | Link visual evidence to knowledge events (requires knowledge_events) → write `*.evidence_index.json` and `*.evidence_debug.json`. |
| `--enable-rule-cards` | Build rule cards from knowledge_events + evidence_index → write `*.rule_cards.json` and `*.rule_debug.json`. |
| `--enable-concept-graph` | Build lesson-level concept graph from rule_cards (Task 12) → write `*.concept_graph.json` and `*.concept_graph_debug.json`. Requires rule_cards. |
| `--enable-exporters` | Render from rule_cards + evidence_index → write `*.review_markdown.md`, `*.rag_ready.md`, and `*.export_manifest.json`. |
| `--no-preserve-legacy-markdown` | Skip legacy Pass 1 + Pass 2 markdown synthesis (Steps 3.3–3.5). |
| `--enable-new-markdown-render` | Alternative render path from rule_cards + evidence (writes to `output_intermediate/*.review.md`). |
| `--use-llm-review-render` / `--use-llm-rag-render` | Use LLM for review/RAG markdown when exporters are enabled (default: deterministic templates). |

### 3.2 Dependency order

- Evidence linking requires knowledge events (from run or existing file).
- Rule cards require knowledge events and evidence index.
- Concept graph (Task 12) requires rule cards (from run or existing file).
- Exporters require rule cards and evidence index. When concept graph exists, review markdown can optionally include a "Concept relationships" section.

The pipeline skips a stage with a clear message and hint if a required artifact is missing.

---

## 4. File writing and manifest

- **Atomic writes:** All stage outputs are written via **`pipeline/io_utils.py`** (`atomic_write_text`, `atomic_write_json`, `write_artifact_manifest`) so that readers never see half-written files.
- **Export manifest:** When exporters run, the pipeline builds a manifest with `build_export_manifest()` (only **existing** artifact paths are included). That payload is written with `write_artifact_manifest()` to `paths.export_manifest_path(lesson_name)`.

---

## 5. Where to read more

- **Step-by-step flow:** [pipeline.md](pipeline.md) (main pipeline and Component 2; Step 3 diagram still shows legacy outputs; structured steps are additive).
- **Module/function reference:** [FRAMEWORK_MODULES.md](FRAMEWORK_MODULES.md).
- **Path and flag definitions:** `pipeline/contracts.py`, `pipeline/stage_registry.py`.
- **Task specs and addenda:** [`docs/requirements/knowledge-refactoring/`](requirements/knowledge-refactoring/) (task7–task11, step_3_new_tune, task-1 for inspection).
