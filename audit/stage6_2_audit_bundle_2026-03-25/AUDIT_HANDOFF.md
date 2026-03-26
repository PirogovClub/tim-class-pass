# Stage 6.2 — AUDIT_HANDOFF (gap closure 2026-03-25)

## 1. What was implemented

- **Registry-only ingestion path (with programmatic fallback):** `build_corpus` always resolves lessons via Stage 6.1 `lesson_registry.json`. If `lesson_registry_path` is omitted (e.g. UI worker), an ephemeral v1 registry is written under the output directory (`_lesson_registry.ingest.v1.json`) using `build_registry_v1(..., validate=False)`.
- **`build_registry_v1` fix:** when `validate=False`, lessons with all four artifacts are marked `status=valid` so they are not incorrectly excluded from ingestion.
- **Explicit corpus / source IDs** on globalized rows (`adapters.py`): `corpus_event_id`, `source_event_id`, `corpus_rule_id`, `source_rule_id`, `corpus_evidence_id`, `source_evidence_id` (alongside existing `global_id`).
- **Source artifact paths** on corpus rows (relative to corpus root): `source_knowledge_events_json`, `source_rule_cards_json`, `source_evidence_index_json`, `source_concept_graph_json` (nodes and relations).
- **Validator hardening (`corpus_validation.py`):** ISO-8601 check for `corpus_metadata.generated_at`; provenance/id-policy checks; registry replay aligned with builder skip rules (`valid` and `validation_status != failed`); registry **record_counts** roll-up vs corpus row counts; optional concept graph provenance fields required when validating graph content.
- **CLI:** `build` requires **`--corpus-root` / `--input-root`** and **`--lesson-registry`** (both mandatory for the command-line entrypoint).
- **Documentation:** `corpus_contract_v1.md` updated; **`corpus_id_policy.py`** added as a thin policy re-export module.
- **Tests:** registry lesson-order invariance; registry count mismatch; skipped lessons with `validation_status=failed`.

## 2. Definition of done checklist

- [x] unified corpus builder implemented
- [x] stable corpus IDs implemented
- [x] required corpus outputs produced
- [x] required corpus entities present
- [x] corpus enrichments implemented
- [x] provenance preserved
- [x] corpus validator implemented
- [x] tests run
- [x] audit zip created

## 3. Corpus ID policy

- See `pipeline/corpus/corpus_id_policy.py` and `corpus_contract_v1.md`.
- `global_id` remains the primary stable key; `corpus_*_id` duplicates it for explicit typing; `source_*_id` holds lesson-local ids.

## 4. Corpus entity/output contract

- See `pipeline/corpus/corpus_contract_v1.md`.

## 5. Enrichment rules

- Unchanged from prior 6.2 slice (frequencies, rule families, overlap, alias registry, etc.).

## 6. Validator behavior

- Structural, uniqueness, cross-ref, and provenance checks on JSONL + concept graph.
- With `--lesson-registry`: ingestible-lesson replay + summed `record_counts` vs corpus row counts.
- `corpus_metadata.generated_at` must parse as ISO-8601 when metadata file exists.

## 7. Commands run

- `python -m pytest tests/corpus tests/test_corpus.py tests/contracts/test_lesson_registry.py -q`
- `python -m pipeline.corpus.cli build --corpus-root ... --lesson-registry ... --output-root ...`
- `python -m pipeline.corpus.cli validate --output-root ... --lesson-registry ... --report ...`

## 8. Tests run

- `tests/corpus/test_corpus_builder.py`
- `tests/corpus/test_corpus_ids.py`
- `tests/corpus/test_corpus_enrichment.py`
- `tests/corpus/test_corpus_validation.py`
- `tests/corpus/test_corpus_contract_examples.py`
- `tests/test_corpus.py`
- `tests/contracts/test_lesson_registry.py`

## 9. Example outputs produced

- `examples/corpus_output/*` (full build tree)
- `examples/corpus_{rule_cards,knowledge_events,evidence_index}.jsonl` and `examples/corpus_concept_graph.json` (copies at bundle root for quick review)
- `examples/corpus_validation_report.json`

## 10. Known limitations

- Ephemeral registries skip per-lesson contract validation (`validate=False`); production flows should pass an explicit Stage 6.1 registry built with validation enabled.
- Concept-graph node/relation counts are not rolled up against registry `record_counts["concept_graph"]` (that field counts nodes per lesson file; merged corpus nodes may dedupe).

## 11. Deferred work

- Vector DB, embeddings, retrieval API, hybrid RAG storage, analyst UI, ML (out of scope for 6.2).

## 12. Exact location of final zip contents

- Folder: `audit/stage6_2_audit_bundle_2026-03-25/`
- Zip: `audit/archives/stage6_2_audit_bundle_2026-03-25.zip`
