# Step 4 Explorer Contracts

## Overview

Step 4.3 extends the accepted Step 4 explorer into a read-only analyst surface with:

- search and browse over explorer cards
- rule, evidence, concept, and lesson detail pages
- rule-to-rule comparison
- lesson-to-lesson comparison
- related-rules traversal
- concept-anchored traversal into all linked rules and all linked lessons

The explorer still reads from the same Step 4.1 data roots:

- `output_rag/retrieval_docs_all.jsonl`
- `output_corpus/corpus_concept_graph.json`
- `output_corpus/concept_alias_registry.json`
- `output_corpus/concept_rule_map.json`
- `output_corpus/rule_family_index.json`
- `output_corpus/lesson_registry.json`
- `output_corpus/corpus_metadata.json`

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/browser/health` | Explorer readiness, doc count, and corpus contract version |
| `POST` | `/browser/search` | Query or browse mode over browser result cards |
| `GET` | `/browser/rule/{doc_id}` | Rule detail view with linked evidence, events, and related rules |
| `GET` | `/browser/evidence/{doc_id}` | Evidence detail view with linked rules and events |
| `GET` | `/browser/concept/{concept_id}` | Concept detail view with aliases, neighbors, rules, and events |
| `GET` | `/browser/concept/{concept_id}/neighbors` | Lightweight concept graph traversal payload |
| `GET` | `/browser/lesson/{lesson_id}` | Lesson summary with counts, top concepts, rules, and evidence |
| `GET` | `/browser/facets` | Facet counts for the current filtered explorer result set |
| `POST` | `/browser/compare/rules` | Side-by-side rule comparison workflow |
| `POST` | `/browser/compare/lessons` | Side-by-side lesson comparison workflow |
| `GET` | `/browser/rule/{doc_id}/related` | Grouped related-rule traversal from a source rule |
| `GET` | `/browser/concept/{concept_id}/rules` | Full concept-linked rule list |
| `GET` | `/browser/concept/{concept_id}/lessons` | Full concept-linked lesson list |

## Core shared cards

`BrowserResultCard` remains the common lightweight entity card returned by search results and linked lists. Each card includes:

- `doc_id`
- `unit_type`
- `lesson_id`
- `title`
- `subtitle`
- `snippet`
- `concept_ids`
- `support_basis`
- `evidence_requirement`
- `teaching_mode`
- `confidence_score`
- `timestamps`
- `evidence_count`
- `related_rule_count`
- `related_event_count`
- `score`
- `why_retrieved`

## Search and detail contracts

### Search

`POST /browser/search` accepts:

- `query`
- `top_k`
- `filters.lesson_ids`
- `filters.concept_ids`
- `filters.unit_types`
- `filters.support_basis`
- `filters.evidence_requirement`
- `filters.teaching_mode`
- `filters.min_confidence_score`
- `return_groups`

`BrowserSearchResponse` returns:

- `query`
- `cards`
- `groups`
- `facets`
- `hit_count`

### Detail responses

`RuleDetailResponse` exposes:

- rule identity and lesson metadata
- concept and subconcept labels
- canonical concept ids
- RU-first and normalized rule text
- conditions, invalidation, exceptions, and comparisons
- visual summary and `frame_ids`
- support / evidence / teaching metadata
- timestamps
- linked `evidence_refs`
- linked `source_events`
- linked `related_rules`

`EvidenceDetailResponse` exposes:

- evidence identity
- lesson id
- title and snippet
- timestamps
- support basis and confidence
- evidence strength and role detail
- visual summary and `frame_ids`
- linked `source_rules`
- linked `source_events`

`ConceptDetailResponse` exposes:

- `concept_id`
- `aliases`
- `top_rules`
- `top_events`
- `lessons`
- `neighbors`
- `rule_count`
- `event_count`
- `evidence_count`

`LessonDetailResponse` exposes:

- `lesson_id`
- `lesson_title`
- `rule_count`
- `event_count`
- `evidence_count`
- `concept_count`
- `support_basis_counts`
- `top_concepts`
- `top_rules`
- `top_evidence`

## Comparison contracts

### Rule comparison

`POST /browser/compare/rules` accepts:

- `rule_ids: string[]`
- `include_related_context: boolean`

`RuleCompareResponse` returns:

- `rules: RuleCompareItem[]`
- `summary: ComparisonSummary`

Each `RuleCompareItem` exposes:

- rule identity and lesson metadata
- concept / subconcept labels
- canonical concept ids
- RU-first and normalized rule text
- conditions, invalidation, exceptions, and comparisons
- visual summary and `frame_ids`
- support / evidence / teaching metadata
- timestamps
- `linked_evidence_count`
- `linked_source_event_count`
- `related_rule_count`
- optional preview `related_rules`

`ComparisonSummary` exposes:

- `shared_concepts`
- `shared_lessons`
- `shared_support_basis`
- `differences`
- `possible_relationships`

The comparison summary is deterministic and field-based. It does not use fuzzy matching or LLM-generated text.

### Lesson comparison

`POST /browser/compare/lessons` accepts:

- `lesson_ids: string[]`

`LessonCompareResponse` returns:

- `lessons: LessonCompareItem[]`
- `shared_concepts`
- `unique_concepts`
- `shared_rule_families`

Each `LessonCompareItem` exposes:

- `lesson_id`
- `lesson_title`
- `unit_type_counts`
- `support_basis_counts`
- `top_concepts`
- `top_rules`
- `top_evidence`
- `rule_count`
- `event_count`
- `evidence_count`
- `concept_count`

## Traversal contracts

### Related rules

`GET /browser/rule/{doc_id}/related` returns `RelatedRulesResponse`:

- `source_doc_id`
- `groups`

Each group key is a deterministic relation reason:

- `same_concept`
- `same_family`
- `same_lesson`
- `linked_by_evidence`
- `cross_lesson_overlap`

Each `RelatedRuleItem` exposes:

- `card`
- `relation_reason`

### Concept lists

`GET /browser/concept/{concept_id}/rules` returns `ConceptRuleListResponse`:

- `concept_id`
- `rules`
- `total`

`GET /browser/concept/{concept_id}/lessons` returns `ConceptLessonListResponse`:

- `concept_id`
- `lessons`
- `lesson_details`
- `total`

## Error behavior

- `GET /browser/rule/{doc_id}` returns `404` for unknown ids and `400` when the id exists but is not a `rule_card`.
- `GET /browser/evidence/{doc_id}` returns `404` for unknown ids and `400` when the id exists but is not an `evidence_ref`.
- `GET /browser/concept/{concept_id}` returns `404` for unknown concept ids.
- `GET /browser/lesson/{lesson_id}` returns `404` for unknown lesson ids.
- `POST /browser/compare/rules` returns `400` for fewer than two ids, more than four ids, or duplicate ids.
- `POST /browser/compare/lessons` returns `400` for fewer than two ids, more than four ids, or duplicate ids.
- traversal list endpoints return `404` when the source rule or concept does not exist.
- `POST /browser/search` uses FastAPI/Pydantic request validation and returns `422` for malformed payloads.
