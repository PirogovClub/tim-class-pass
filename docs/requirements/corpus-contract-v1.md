# Corpus Contract v1.0.0

This document specifies the **stable v1 corpus contract** for all corpus-level exports produced by `pipeline/corpus/`. Downstream consumers (embedding pipelines, vector DBs, retrieval APIs) should depend only on the interfaces documented here.

## Schema Versions

All version strings are stored in `schema_versions.json` inside the output directory:

| Key | Value | Governs |
|---|---|---|
| `knowledge_schema_version` | `1.0.0` | `KnowledgeEvent` fields |
| `rule_schema_version` | `1.0.0` | `RuleCard` fields |
| `evidence_schema_version` | `1.0.0` | `EvidenceRef` fields |
| `concept_graph_version` | `1.0.0` | `ConceptNode`, `ConceptRelation` fields |
| `corpus_contract_version` | `1.0.0` | This document and `CorpusMetadata` |

A bump to any version indicates a breaking change in that schema.

## Global ID Format

Every entity in the corpus receives a deterministic global ID:

| Entity | Pattern | Example |
|---|---|---|
| Knowledge event | `event:<lesson_slug>:<local_event_id>` | `event:lesson_2_levels_part_1:ke_lesson2_0_rule_statement_0` |
| Rule card | `rule:<lesson_slug>:<local_rule_id>` | `rule:lesson_2_levels_part_1:rule_lesson2_levels_0` |
| Evidence ref | `evidence:<lesson_slug>:<local_evidence_id>` | `evidence:lesson_2_levels_part_1:ev_lesson2_0` |
| Concept node | `node:<slugified_concept_name>` | `node:uroven` |
| Relation | `rel:<source_node>:<relation_type>:<target_node>` | `rel:node:uroven:has_subconcept:node:uroven_reytinga` |

Properties:
- **Deterministic**: Same input always produces same ID.
- **Stable**: Adding a new lesson does not change existing IDs.
- **Compositional**: The ID encodes its type and provenance.

## Artifact Catalog

### Per-Lesson Input Artifacts (source)

Located in `data/<lesson_dir>/output_intermediate/`:

| File | Model | Required |
|---|---|---|
| `knowledge_events.json` | `KnowledgeEventCollection` | Yes |
| `rule_cards.json` | `RuleCardCollection` | Yes |
| `evidence_index.json` | `EvidenceIndex` | Yes |
| `concept_graph.json` | `ConceptGraph` | No (warning if missing) |

### Corpus Output Artifacts

Located in `<output_root>/`:

| File | Format | Description |
|---|---|---|
| `corpus_metadata.json` | `CorpusMetadata` (JSON) | Aggregate counts, versions, build timestamp |
| `lesson_registry.json` | `list[LessonRecord]` (JSON) | One entry per discovered lesson |
| `schema_versions.json` | `dict[str,str]` (JSON) | Copy of canonical version strings |
| `validation_report.json` | JSON | Per-lesson and cross-lesson validation results |
| `corpus_knowledge_events.jsonl` | JSONL | One globalized `KnowledgeEvent` dict per line |
| `corpus_rule_cards.jsonl` | JSONL | One globalized `RuleCard` dict per line |
| `corpus_evidence_index.jsonl` | JSONL | One globalized `EvidenceRef` dict per line |
| `corpus_lessons.jsonl` | JSONL | One `LessonRecord` dict per line |
| `corpus_concept_graph.json` | `ConceptGraph` (JSON) | Merged cross-lesson concept graph |
| `concept_alias_registry.json` | JSON | Canonical concept → aliases + source lessons |
| `concept_frequencies.json` | JSON | Per-concept rule/event/evidence/lesson counts |
| `concept_rule_map.json` | JSON | Concept → list of global rule IDs |
| `rule_family_index.json` | JSON | Rules grouped by normalized concept+subconcept |
| `concept_overlap_report.json` | JSON | Which lessons share concept families |

## Core Models

### KnowledgeEvent

| Field | Type | Notes |
|---|---|---|
| `event_id` | `str` | Local ID; becomes global ID in corpus export |
| `event_type` | `EventType` | One of: definition, rule_statement, condition, invalidation, exception, comparison, example, warning, process_step, algorithm_hint, observation |
| `raw_text` | `str` | Original extracted text |
| `normalized_text` | `str` | Cleaned, single-line text |
| `concept` | `str?` | Human-readable concept label |
| `subconcept` | `str?` | Human-readable subconcept label |
| `concept_id` | `str?` | Canonical concept ID |
| `subconcept_id` | `str?` | Canonical subconcept ID |
| `lesson_id` | `str` | Source lesson identifier |
| `source_language` | `str` | `"ru"` default |
| `normalized_text_ru` | `str?` | Russian text (populated when source is Russian) |
| `concept_label_ru` | `str?` | Russian concept label |
| `subconcept_label_ru` | `str?` | Russian subconcept label |

_(Additional fields: evidence_refs, confidence, transcript_anchors, timestamp_*, metadata, etc.)_

### RuleCard

| Field | Type | Notes |
|---|---|---|
| `rule_id` | `str` | Local ID; becomes global ID in corpus export |
| `concept` | `str` | Required, non-empty |
| `subconcept` | `str?` | |
| `rule_text` | `str` | Required, non-empty |
| `conditions` | `list[str]` | |
| `invalidation` | `list[str]` | |
| `exceptions` | `list[str]` | |
| `evidence_refs` | `list[str]` | Local evidence IDs |
| `source_event_ids` | `list[str]` | Local event IDs |
| `rule_text_ru` | `str?` | Russian rule text |
| `concept_label_ru` | `str?` | Russian concept label |
| `subconcept_label_ru` | `str?` | Russian subconcept label |

### EvidenceRef

| Field | Type | Notes |
|---|---|---|
| `evidence_id` | `str` | Local ID; becomes global ID in corpus export |
| `visual_type` | `VisualType` | annotated_chart, plain_chart, hand_drawing, etc. |
| `example_role` | `ExampleRole` | positive_example, negative_example, etc. |
| `linked_rule_ids` | `list[str]` | Local rule IDs |
| `compact_visual_summary` | `str?` | Raw visual summary (any language) |
| `summary_primary` | `str?` | Canonical summary text |
| `summary_language` | `str?` | Detected language: "ru", "en", or null |
| `summary_ru` | `str?` | Only populated when detected as Russian |
| `summary_en` | `str?` | Only populated when detected as English |

### ConceptNode

| Field | Type | Notes |
|---|---|---|
| `concept_id` | `str` | Cross-lesson: `node:<slug>` |
| `name` | `str` | Human-readable name |
| `type` | `ConceptNodeType` | concept, subconcept, condition, etc. |
| `aliases` | `list[str]` | All surface forms across lessons |
| `source_rule_ids` | `list[str]` | Global rule IDs that reference this concept |

### ConceptRelation

| Field | Type | Notes |
|---|---|---|
| `relation_id` | `str` | `rel:<src>:<type>:<dst>` |
| `source_id` | `str` | Global node ID |
| `target_id` | `str` | Global node ID |
| `relation_type` | `str` | has_subconcept, has_condition, has_invalidation, has_exception, co_occurs_with |
| `source_rule_ids` | `list[str]` | Provenance: which global rules support this relation |

## Referential Integrity Rules

1. Every `source_event_ids` entry in a `RuleCard` must reference an existing `event_id` in the corpus.
2. Every `evidence_refs` entry in a `RuleCard` must reference an existing `evidence_id` in the corpus.
3. Every `linked_rule_ids` entry in an `EvidenceRef` must reference an existing `rule_id` in the corpus.
4. Every `source_id` and `target_id` in a `ConceptRelation` must reference an existing `concept_id` in the node set.
5. No duplicate global IDs within the same entity type.

## Backward Compatibility

- Fields may be added as `Optional` without a version bump.
- Removing or renaming a field requires a version bump.
- Changing a field's type or semantics requires a version bump.
- The `corpus_contract_version` field in `CorpusMetadata` identifies which contract version was used to build the corpus.
