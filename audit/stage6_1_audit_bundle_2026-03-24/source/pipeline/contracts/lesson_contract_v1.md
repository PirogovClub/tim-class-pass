# Lesson export contract v1

## 1. Purpose

This document freezes **lesson-level export contract v1** for the knowledge pipeline. Downstream work (corpus builder, hybrid RAG ingestion, ML prep) must treat these artifacts and rules as stable.

Goals:

- Lock schema/version semantics before corpus DB or retrieval infrastructure.
- Make manifests (`lesson_registry.json`) and validation reproducible.
- Keep **JSON** as the source of truth; markdown remains derived.

## 2. Artifact inventory

### 2.1 Required primary artifacts (per processed lesson)

All must exist under the lesson’s `output_intermediate/` directory (actual filenames use the pipeline suffix pattern, e.g. `{lesson_id}.knowledge_events.json`):

| Logical name | Typical suffix | Description |
|----------------|----------------|-------------|
| `knowledge_events.json` | `.knowledge_events.json` | Extracted knowledge events |
| `rule_cards.json` | `.rule_cards.json` | Normalized rules |
| `evidence_index.json` | `.evidence_index.json` | Visual/transcript evidence refs |
| `concept_graph.json` | `.concept_graph.json` | Lesson concept nodes and relations |

If any required artifact is **missing**, contract validation **fails**.

### 2.2 Optional derived artifacts

These may exist alongside the lesson root (see `PipelinePaths`):

- **Review markdown**: `output_review/{lesson_id}.review_markdown.md`
- **RAG-ready export**: `output_rag_ready/{lesson_id}.rag_ready.md`

They are **derived only** from structured JSON (rules + evidence + graph), not alternate sources of truth.

## 3. Field definitions (high level)

Detailed Pydantic shapes live in `pipeline/schemas.py` and `pipeline/corpus/contracts.py`. Contract v1 additionally requires:

### 3.1 `rule_cards.json` — provenance keys (per rule object)

Each rule **object** in the `rules` array must contain these **JSON keys** (not only inferred defaults):

- `lesson_id` (string)
- `source_event_ids` (array; may be empty)
- `evidence_refs` (array; may be empty)

### 3.2 `evidence_index.json` — `summary_ru` consistency

If `summary_language` is `"en"`, then `summary_ru` must be empty or absent. Russian summaries belong in `summary_ru` when `summary_language` is `"ru"` (see `pipeline/component2/evidence_linker.py`).

### 3.3 `concept_graph.json`

Must parse as `ConceptGraph`: `lesson_id`, `nodes`, `relations`, optional `stats`.

## 4. Provenance rules

- Every rule must remain attributable to its lesson and source events (`source_event_ids`).
- `evidence_refs` on rules must either list valid evidence IDs from `evidence_index.json` or be an explicit empty list when none apply.
- Evidence entries should link to rules where applicable (`linked_rule_ids`); broken references are reported as **warnings** in lenient mode, or **errors** in strict mode when those warnings are promoted.

## 5. Derived markdown rule

Markdown exports are **not** primary artifacts. Ingestion and auditing should prefer JSON; markdown is a human-facing or RAG convenience layer built from JSON.

## 6. Versioning policy

- Frozen version strings live in `pipeline/contracts/schema_versions.json`.
- **Patch** bump: compatible additions (new optional fields).
- **Minor/Major** bump: renamed/removed required fields, semantic changes — treated as a **new contract version**.
- Registry and each lesson entry record: `lesson_contract_version`, per-schema versions (`knowledge_schema_version`, …), and `registry_version`.

## 7. Validation rules (failure conditions)

The corpus validator (`pipeline/contracts/corpus_validator.py`) **fails** a lesson when:

1. Any required artifact is missing or not valid JSON.
2. Top-level models fail Pydantic validation.
3. Any rule object lacks `lesson_id`, `source_event_ids`, or `evidence_refs` **keys**.
4. `summary_language == "en"` while `summary_ru` is non-empty.
5. In **strict** mode, selected **warnings** (empty artifacts, version stamp drift vs frozen file, integrity warnings) are promoted to errors.

**Lenient** mode keeps warnings separate; default for freeze work is **strict**.

## 8. Registry (`lesson_registry.json`)

Root object (v1):

- `registry_version`, `lesson_contract_version`, `generated_at`
- `lessons`: array of entries with artifact **paths relative to corpus root**, hashes, record counts, validation status, and errors.

See `pipeline/contracts/registry_models.py`.

## 9. ID stability (lesson scope)

Within a lesson, IDs must remain stable across rebuilds unless content identity changes:

- `lesson_id`, `event_id`, `rule_id`, `evidence_id`, `concept_id`, `relation_id`

Global corpus IDs are out of scope for v1 but must compose from these lesson-level IDs.
