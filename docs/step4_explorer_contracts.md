# Step 4 Explorer Contracts

## Overview

Step 4.1 adds a read-only explorer layer on top of the accepted RAG system. The explorer consumes existing retrieval docs and corpus metadata, then exposes browser-friendly `/browser/*` endpoints that return structured cards and detail payloads instead of raw retrieval documents.

## Source artifacts

The Step 4.1 explorer repository directly reads from:

- `output_rag/retrieval_docs_all.jsonl`
- `output_corpus/corpus_concept_graph.json`
- `output_corpus/concept_alias_registry.json`
- `output_corpus/concept_rule_map.json`
- `output_corpus/rule_family_index.json`
- `output_corpus/lesson_registry.json`
- `output_corpus/corpus_metadata.json`

Additional retrieval artifacts such as `retrieval_docs_rule_cards.jsonl`, `retrieval_docs_knowledge_events.jsonl`, `retrieval_docs_evidence_refs.jsonl`, `retrieval_docs_concept_nodes.jsonl`, and `retrieval_docs_concept_relations.jsonl` remain available in `output_rag/`, but Step 4.1 does not load them directly. The explorer reads the consolidated retrieval document store from `retrieval_docs_all.jsonl`.

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

## Search request

`POST /browser/search` accepts:

- `query`: free-text query string; empty string activates browse mode
- `top_k`: max number of returned cards
- `filters.lesson_ids`
- `filters.concept_ids`
- `filters.unit_types`
- `filters.support_basis`
- `filters.evidence_requirement`
- `filters.teaching_mode`
- `filters.min_confidence_score`
- `return_groups`: include grouped card buckets for UI rendering

## Search response

`BrowserSearchResponse` returns:

- `query`
- `cards`: ordered `BrowserResultCard[]`
- `groups`: grouped cards by browser category (`rules`, `events`, `evidence`, `concepts`, `relations`)
- `facets`
- `hit_count`

`BrowserSearchResponse.facets` is page-scoped to the returned search cards. For full filtered-set facet counts across the explorer corpus, use `GET /browser/facets`.

Each `BrowserResultCard` includes:

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

## Detail payloads

### Rule detail

`RuleDetailResponse` exposes:

- rule identity and lesson metadata
- concept and subconcept labels
- canonical concept ids
- rule text in normalized and RU-first form
- conditions, invalidation, exceptions, comparisons
- visual summary
- support / evidence / teaching metadata
- timestamps
- linked `evidence_refs`
- linked `source_events`
- linked `related_rules`

### Evidence detail

`EvidenceDetailResponse` exposes:

- evidence identity
- lesson id
- title and snippet
- timestamps
- support basis
- confidence score
- evidence strength
- evidence role detail
- visual summary
- linked `source_rules`
- linked `source_events`

### Concept detail

`ConceptDetailResponse` exposes:

- `concept_id`
- `aliases`
- `top_rules`
- `top_events`
- `lessons`
- `neighbors`
- `rule_count` (full total, not preview length)
- `event_count` (full total, not preview length)
- `evidence_count`

Each `ConceptNeighbor` includes:

- `concept_id`
- `relation`
- `direction`
- `weight`

### Lesson detail

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

## Behavior notes

- Search mode calls the accepted `HybridRetriever` and then applies browser-specific post-filters.
- Browse mode is deterministic and sorts by unit priority first: `rule_card`, `knowledge_event`, `evidence_ref`, `concept_node`, `concept_relation`.
- The explorer never returns raw `resolved_doc` payloads directly.
- Concept navigation is lightweight in Step 4.1: aliases, counts, and neighbor traversal only.

## Error behavior

- `GET /browser/rule/{doc_id}` returns `404` for unknown ids and `400` when the id exists but is not a `rule_card`.
- `GET /browser/evidence/{doc_id}` returns `404` for unknown ids and `400` when the id exists but is not an `evidence_ref`.
- `GET /browser/concept/{concept_id}` returns `404` for unknown concept ids.
- `GET /browser/lesson/{lesson_id}` returns `404` for unknown lesson ids.
- `POST /browser/search` uses FastAPI/Pydantic request validation and returns `422` for malformed payloads.
