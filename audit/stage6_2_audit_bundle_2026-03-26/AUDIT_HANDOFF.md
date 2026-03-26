# Stage 6.2 — AUDIT_HANDOFF

## 1. What was implemented

- Stage 6.2 corpus builder implemented in `pipeline/corpus/corpus_builder.py`.
- Registry-first ingestion wired: builder can ingest from Stage 6.1 `lesson_registry.json` (`--lesson-registry`) and skip invalid/failed lessons.
- Deterministic/stable IDs preserved via `pipeline/corpus/id_utils.py` and globalize adapters.
- Required corpus outputs produced:
  - `corpus_rule_cards.jsonl`
  - `corpus_knowledge_events.jsonl`
  - `corpus_evidence_index.jsonl`
  - `corpus_concept_graph.json`
- Required enrichments produced:
  - canonical concept frequencies
  - rule families
  - concept-to-rule map
  - cross-lesson concept overlap
  - concept alias registry
- Corpus output validator implemented: `pipeline/corpus/corpus_validation.py`.
- CLI supports build + validate:
  - `python -m pipeline.corpus.cli build ...`
  - `python -m pipeline.corpus.cli validate ...`
- Corpus contract doc added: `pipeline/corpus/corpus_contract_v1.md`.

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

- Event/rule/evidence global IDs are deterministic namespaced IDs derived from lesson slug + local ID.
- Concept node IDs are deterministic canonical IDs from normalized concept names.
- Relation IDs are deterministic from source+type+target.
- No random UUIDs are used.

## 4. Corpus entity/output contract

- See `pipeline/corpus/corpus_contract_v1.md`.
- Core corpus entities: lessons, knowledge events, rules, evidence refs, concept nodes, concept relations.
- Core output files listed above.

## 5. Enrichment rules

- Concept frequencies count lesson/rule/event/evidence support.
- Rule families group by normalized concept/subconcept.
- Concept->rule map is reverse index from canonical concept node ID.
- Concept overlap reports concepts appearing in multiple lessons.
- Alias registry stores canonical names + aliases + lesson support.

## 6. Validator behavior

- Structural checks: required output files, parseability, required IDs.
- Cross-reference checks: rule->event/evidence, evidence->rule, concept refs.
- Provenance checks: lesson IDs and source linkage fields.
- Registry replay checks: verifies valid lessons from Stage 6.1 registry are included in corpus output.
- Determinism helper: `corpus_output_fingerprints` for hash-based repeatability checks.

## 7. Commands run

- `python -m pytest tests/corpus tests/contracts -q`
- `python -m compileall -q pipeline/corpus tests/corpus`
- `python -m pipeline.contracts.cli registry ...`
- `python -m pipeline.corpus.cli build ...`
- `python -m pipeline.corpus.cli validate ...`

## 8. Tests run

- `tests/corpus/test_corpus_builder.py`
- `tests/corpus/test_corpus_ids.py`
- `tests/corpus/test_corpus_enrichment.py`
- `tests/corpus/test_corpus_validation.py`
- `tests/corpus/test_corpus_contract_examples.py`

## 9. Example outputs produced

- `examples/corpus_output/corpus_rule_cards.jsonl`
- `examples/corpus_output/corpus_knowledge_events.jsonl`
- `examples/corpus_output/corpus_evidence_index.jsonl`
- `examples/corpus_output/corpus_concept_graph.json`
- `examples/corpus_validation_report.json`
- `examples/lesson_registry.json`

## 10. Known limitations

- Validator currently focuses on output integrity and registry replay, not full semantic dedup quality scoring.
- Build strictness is inherited from existing corpus lesson/cross-lesson validator behavior.

## 11. Deferred work

- Vector DB, embeddings, retrieval API, reranking, storage backend wiring, analyst UI, ML components (all out-of-scope for 6.2).

## 12. Exact location of final zip contents

- Folder: `audit/stage6_2_audit_bundle_2026-03-26/`
- Zip: `audit/archives/stage6_2_audit_bundle_2026-03-26.zip`
