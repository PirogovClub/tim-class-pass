# Step 2: Corpus Build — Implementation Notes

## Overview

Step 2 freezes the per-lesson output schema as **v1** and introduces a new `pipeline/corpus/` package that merges all lesson-level artifacts into a unified corpus with deterministic global IDs, validated referential integrity, and concept enrichments.

## New Modules

| Module | Purpose |
|---|---|
| `pipeline/corpus/__init__.py` | Package init |
| `pipeline/corpus/contracts.py` | Frozen v1 Pydantic models (`LessonRecord`, `CorpusMetadata`), re-exports of `KnowledgeEvent`, `RuleCard`, `EvidenceRef`, `ConceptNode`, `ConceptRelation`, `ConceptGraph` |
| `pipeline/corpus/schema_versions.json` | Canonical version strings for all schemas |
| `pipeline/corpus/id_utils.py` | Deterministic global ID generation: `slugify_lesson_id`, `make_global_id`, `make_global_node_id`, `make_global_relation_id` |
| `pipeline/corpus/adapters.py` | Load lesson JSON artifacts into Pydantic models; convert local IDs to global IDs without mutating source files |
| `pipeline/corpus/lesson_registry.py` | Scan `data/` for processed lessons, count artifacts, compute SHA-256 hashes, build `lesson_registry.json` |
| `pipeline/corpus/validator.py` | Per-lesson validation (schema, IDs, file existence) and cross-lesson validation (ID collisions, referential integrity, graph consistency) |
| `pipeline/corpus/corpus_builder.py` | Main orchestrator: discover → validate → merge → enrich → export |
| `pipeline/corpus/cli.py` | Click CLI entry point |
| `pipeline/corpus/__main__.py` | Enables `python -m pipeline.corpus.build` |

## Output Folder Structure

```
output_corpus/
├── corpus_metadata.json          # aggregate counts, version, timestamp
├── lesson_registry.json          # one entry per discovered lesson
├── schema_versions.json          # copy of canonical version strings
├── validation_report.json        # per-lesson + cross-lesson results
├── corpus_knowledge_events.jsonl # one globalized event per line
├── corpus_rule_cards.jsonl       # one globalized rule per line
├── corpus_evidence_index.jsonl   # one globalized evidence ref per line
├── corpus_lessons.jsonl          # one LessonRecord per line
├── corpus_concept_graph.json     # merged cross-lesson concept graph
├── concept_alias_registry.json   # canonical concept → aliases + lessons
├── concept_frequencies.json      # per-concept counts
├── concept_rule_map.json         # concept → global rule IDs
├── rule_family_index.json        # rules grouped by concept+subconcept
└── concept_overlap_report.json   # concepts shared across lessons
```

## How Global IDs Work

Every entity receives a deterministic, compositional ID:

- **Events**: `event:<lesson_slug>:<local_event_id>`
- **Rules**: `rule:<lesson_slug>:<local_rule_id>`
- **Evidence**: `evidence:<lesson_slug>:<local_evidence_id>`
- **Concept nodes**: `node:<slugified_concept_name>` (cross-lesson)
- **Relations**: `rel:<source_node>:<type>:<target_node>`

Adding new lessons does not change existing IDs. Rerunning always produces the same output.

## How to Run

### Build the corpus

```bash
python -m pipeline.corpus --input-root data --output-root output_corpus
```

### With strict validation (warnings become errors)

```bash
python -m pipeline.corpus --input-root data --output-root output_corpus --strict
```

### Run tests

```bash
python -m pytest tests/test_corpus.py -v
```

## Validation

The validator runs two passes:

1. **Per-lesson**: checks each lesson's artifacts against the v1 contract (file existence, JSON parsing, Pydantic schema, non-empty IDs, intra-lesson referential integrity)
2. **Cross-lesson**: checks the merged corpus (no global ID collisions, no duplicate lessons, all relation endpoints exist, rule→event/evidence and evidence→rule references resolve)

In `--strict` mode, warnings are promoted to errors and the build aborts.

## Concept Enrichments

The builder produces five enrichment files:

- **concept_alias_registry.json**: Maps each canonical concept to all surface-form aliases and the lessons they appear in
- **concept_frequencies.json**: Per-concept counts of rules, events, evidence, and lessons
- **concept_rule_map.json**: Maps each concept to its list of global rule IDs
- **rule_family_index.json**: Groups rules by normalized `concept__subconcept` key
- **concept_overlap_report.json**: Lists concepts that appear in multiple lessons, sorted by overlap degree

## Known Limitations

- No LLM calls: concept aliasing relies on string normalization and Cyrillic transliteration
- No embeddings or vector DB (deferred to Step 3)
- Concept graph merging uses exact name matching after normalization; near-duplicates require manual alias registration
- The builder does not handle incremental updates — it rebuilds the full corpus each time

## What Step 3 Consumes

The hybrid RAG database (Step 3) will consume:

- `corpus_knowledge_events.jsonl` — for embedding and retrieval
- `corpus_rule_cards.jsonl` — for structured rule lookup
- `corpus_concept_graph.json` — for graph-based traversal
- `concept_alias_registry.json` — for query expansion
- `corpus_metadata.json` — for version tracking
