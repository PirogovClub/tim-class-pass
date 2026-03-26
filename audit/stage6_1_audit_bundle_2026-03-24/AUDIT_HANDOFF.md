# Stage 6.1 — AUDIT_HANDOFF

## 1. What was implemented

- **Frozen versions:** `pipeline/contracts/schema_versions.json` (knowledge/rule/evidence/concept graph + `lesson_contract_version`, `registry_version`, `corpus_contract_version`).
- **Path module rename:** `pipeline/contracts.py` → `pipeline/path_contracts.py` so `pipeline/contracts/` can be a package; imports updated to `from pipeline.path_contracts import PipelinePaths`.
- **Contract package:** `pipeline/contracts/` — `versioning.py`, `contract_models.py`, `registry_models.py`, `corpus_validator.py`, `lesson_registry.py`, `cli.py`, `lesson_contract_v1.md`.
- **Registry v1:** `build_registry_v1` / `save_registry_v1` produce a machine-readable manifest with artifact paths (relative to corpus root), hashes, counts, validation status.
- **Validator v1:** Required four JSON artifacts; Pydantic validation; raw JSON key checks on rules (`lesson_id`, `source_event_ids`, `evidence_refs`); cross-file integrity warnings; `summary_ru` vs `summary_language` enforcement; optional registry cross-check.
- **Tests:** `tests/contracts/` (23 tests); fixtures gained `concept_graph.json` for `lesson_minimal` and `lesson_multi_concept`.
- **CLI:** `python -m pipeline.contracts.cli` and `lesson-contract` script in `pyproject.toml`.

## 2. Definition of done checklist

- [x] schema/contracts frozen and versioned
- [x] stable lesson export contract documented (`lesson_contract_v1.md`)
- [x] `lesson_registry.json` produced (see `examples/lesson_registry.json`)
- [x] corpus validator implemented
- [x] provenance validation enforced (rule keys + non-empty discipline via explicit keys)
- [x] summary_ru cleanup finalized or documented (exporter logic in `evidence_linker.py`; validator enforces `en` ⇒ empty `summary_ru`)
- [x] tests run (`test_output.txt`)
- [x] audit zip created (`audit/archives/stage6_1_audit_bundle_2026-03-24.zip`)

## 3. Schema version policy

- Source of truth: `pipeline/contracts/schema_versions.json`.
- `pipeline/corpus/contracts.py` loads versions from that file (`SCHEMA_VERSIONS`).
- Strict validation compares per-lesson and registry version fields to the frozen map; lenient mode allows mismatches to surface as non-fatal where implemented.

## 4. Lesson registry contract

- Pydantic models: `pipeline/contracts/registry_models.py`.
- Root object includes `registry_version`, `lesson_contract_version`, `generated_at`, `lessons[]`.
- Each lesson: artifact paths, `artifact_hashes`, `record_counts`, `validation_status`, `validation_errors`, schema version fields.

## 5. Validator behavior

- **Default:** strict (warnings promoted to errors where configured).
- **Lenient:** integrity/version warnings stay warnings; `validate_version_map(..., strict=False)` skips version mismatch errors.
- **Registry check:** `validate_registry_v1` — paths exist, SHA-256 hashes, record counts, root version fields.

## 6. Commands run

- `python -m pytest tests/contracts -q` → 23 passed (captured in `test_output.txt`).
- `python -m pipeline.contracts.cli registry audit/_tmp_stage6/corpus -o examples/lesson_registry.json`
- `python -m pipeline.contracts.cli validate audit/_tmp_stage6/corpus -r examples/validator_report.json --registry examples/lesson_registry.json`

## 7. Tests run

- `tests/contracts/test_schema_versions.py`
- `tests/contracts/test_lesson_registry.py`
- `tests/contracts/test_corpus_validator.py`
- `tests/contracts/test_contract_examples.py`
- `tests/contracts/test_summary_ru_tidyup.py`

## 8. Example outputs produced

- `examples/schema_versions.json`
- `examples/lesson_registry.json`
- `examples/validator_report.json`
- `examples/lesson_contract_v1.md`
- Fixture reference: `tests/fixtures/lesson_minimal` (with `concept_graph.json`)

## 9. Known limitations

- Discovery reuses `pipeline/corpus/lesson_registry.discover_lessons` (suffix-based filenames under `output_intermediate/`).
- Cross-lesson / global corpus checks are out of scope for 6.1.
- Markdown paths in registry use `PipelinePaths` conventions (`output_review`, `output_rag_ready`), not literal `review_markdown.md` in intermediate.

## 10. Deferred work

- Corpus DB, merger, global JSONL, hybrid RAG DB, retrieval API, embeddings, rule browser UI (per roadmap after Phase A).

## 11. Exact location of final zip contents

- **Folder:** `audit/stage6_1_audit_bundle_2026-03-24/`
- **Zip:** `audit/archives/stage6_1_audit_bundle_2026-03-24.zip`
