# Stage 6.1 — AUDIT_HANDOFF (2026-03-26, gaps closed)

## 1. What was implemented

- Frozen `pipeline/contracts/schema_versions.json` and corpus loader wiring.
- Package `pipeline/contracts/`: versioning, models, `corpus_validator.py`, `lesson_registry.py`, CLI, `lesson_contract_v1.md`.
- **Gap closure (post-audit):**
  - **Timestamps (§10.2):** `_check_timestamps_contract_v1` — events cited by `rule_cards.source_event_ids` must have non-empty `timestamp_start`/`timestamp_end`; evidence with `frame_ids`, `screenshot_paths`, or `linked_rule_ids` must have both timestamps.
  - **Registry replay (§10.4):** `validate_registry_v1` calls `validate_lesson_record_v1` on each row (when `validation_status` is `passed` or `failed`) and emits `validation_status_mismatch` if stale.
  - **Example corpus (§16):** `examples/corpus_example/lesson_minimal/output_intermediate/` with all four JSON artifacts.
  - **Backward compatibility / per-file schema note:** documented in `lesson_contract_v1.md` §6.
  - **Lint artifact:** `lint_output.txt` from `python -m compileall` (no Ruff in `pyproject.toml`).
- Fixtures: `concept_graph.json` + `evidence_index.json` timestamps for contract tests.
- `lesson_record_from_registry_entry` exported for reuse/testing.

## 2. Definition of done checklist

- [x] schema/contracts frozen and versioned
- [x] stable lesson export contract documented
- [x] `lesson_registry.json` produced
- [x] corpus validator implemented
- [x] provenance validation enforced
- [x] summary_ru cleanup finalized or documented
- [x] tests run
- [x] audit zip created
- [x] prior audit gaps addressed (timestamps §10.2, registry replay §10.4, example corpus §16, compileall §15)

## 3. Schema version policy

Canonical map: `pipeline/contracts/schema_versions.json`. Registry rows echo frozen semantic versions. Per-file `"schema_version": "1.0"` in JSON exports is documented as legacy; tooling uses frozen keys.

## 4. Lesson registry contract

See `pipeline/contracts/registry_models.py` — paths relative to corpus root, hashes, counts, `validation_status`, `validation_errors`.

## 5. Validator behavior

- **Strict (default):** missing artifacts, bad JSON/Pydantic, provenance keys, `summary_ru`/`summary_language`, **timestamp contract**, promoted warnings → fail.
- **Lenient:** fewer promoted errors; version map mismatch optional.
- **Registry check:** paths, SHA-256, counts, version fields, **live replay** vs `validation_status`.

## 6. Commands run

- `python -m pytest tests/contracts -q` → 26 passed (`test_output.txt`)
- `python -m compileall -q pipeline/contracts tests/contracts` (`lint_output.txt`)
- `python -m pipeline.contracts.cli registry examples/corpus_example -o examples/lesson_registry.json`
- `python -m pipeline.contracts.cli validate examples/corpus_example -r examples/validator_report.json --registry examples/lesson_registry.json`

## 7. Tests run

`tests/contracts/test_*.py` — schema versions, registry, validator (incl. timestamp + `validation_status_mismatch`), contract examples, `summary_ru`.

## 8. Example outputs produced

- `examples/schema_versions.json`
- `examples/lesson_registry.json`
- `examples/validator_report.json`
- `examples/lesson_contract_v1.md`
- `examples/corpus_example/lesson_minimal/output_intermediate/*.json`

## 9. Known limitations

- Discovery still uses suffix-based filenames under `output_intermediate/` (`discover_lessons`).
- Cross-lesson global corpus checks remain out of scope for 6.1.
- No Ruff/Black in repo; only `compileall` captured for static pass.

## 10. Deferred work

Corpus DB, merger, JSONL exports, hybrid RAG, retrieval API, embeddings, rule browser, ML (per roadmap).

## 11. Exact location of final zip contents

- **Folder:** `audit/stage6_1_audit_bundle_2026-03-26/`
- **Zip:** `audit/archives/stage6_1_audit_bundle_2026-03-26.zip`
