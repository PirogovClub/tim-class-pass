# Corpus contract v1 (Stage 6.2)

## Purpose

This contract defines the unified corpus store generated from Stage 6.1 lesson exports.
It is the ingestion boundary for later retrieval / hybrid-RAG layers.

## Required outputs

- `corpus_rule_cards.jsonl`
- `corpus_knowledge_events.jsonl`
- `corpus_evidence_index.jsonl`
- `corpus_concept_graph.json`

Additional enrichment outputs currently emitted:

- `concept_frequencies.json`
- `concept_rule_map.json`
- `concept_overlap_report.json`
- `concept_alias_registry.json`
- `rule_family_index.json`
- `corpus_metadata.json`
- `validation_report.json`

## Required corpus entities

- lessons
- knowledge events
- rule cards
- evidence refs
- concept nodes
- concept relations

## Stable ID policy

- Deterministic IDs only; no random UUIDs.
- Event/rule/evidence IDs preserve lesson-local IDs under namespaced global keys:
  - `event:<lesson_slug>:<local_event_id>`
  - `rule:<lesson_slug>:<local_rule_id>`
  - `evidence:<lesson_slug>:<local_evidence_id>`
- Concept nodes are canonicalized across lessons:
  - `node:<slugified_concept_name>`
- Concept relations are deterministic from endpoints and relation type:
  - `rel:<source_node_id>:<relation_type>:<target_node_id>`

Given unchanged inputs, repeated builds must produce identical IDs and content.

## Provenance rules

Corpus rows retain:

- source `lesson_id`
- lesson-local identifiers (via namespaced global ids)
- `source_event_ids`
- `evidence_refs`
- timestamps where present in lesson artifacts

## Enrichment rules

- **Concept frequencies**: lesson / rule / event / evidence counts by canonical concept node.
- **Rule families**: rules grouped by normalized `concept(+subconcept)` key.
- **Concept-to-rule mappings**: reverse index from concept node id to corpus rule IDs.
- **Cross-lesson concept overlap**: concepts appearing in more than one lesson.
- **Concept alias registry**: canonical node names + aliases + source lesson support.

## Validation rules

Validation checks include:

- required output file existence
- parseability of JSON/JSONL outputs
- uniqueness of corpus global IDs
- cross-reference integrity (rule->events/evidence, evidence->rules)
- provenance presence on rule/evidence rows
- optional Stage 6.1 registry replay inclusion checks

## Versioning

- Lesson schemas remain pinned by `pipeline/contracts/schema_versions.json`.
- Corpus output compatibility for this contract is `corpus_contract_version = 1.0.0`.
- Breaking changes (required field removals/renames or semantics changes) require a new corpus contract version.

## Deferred to Stage 6.3+

- vector DB / embeddings
- retrieval API / reranking
- storage backends and serving infrastructure
- analyst UI / rule browser
