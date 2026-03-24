# Step 4 Explorer Notes

## Scope

Step 4.1 implements a read-only explorer backend on top of the accepted RAG stack. It does not add UI, write-back flows, auth, persistence beyond existing artifacts, or new retrieval experiments.

## Data flow

### Retrieval docs

The explorer uses `output_rag/retrieval_docs_all.jsonl` as the primary browser read-model source. This gives the explorer a single normalized document store that already contains:

- `rule_card`
- `knowledge_event`
- `evidence_ref`
- `concept_node`
- `concept_relation`

The repository loads this file into `InMemoryDocStore`, then builds read-oriented lookup maps for concept keys, source rules, and source events.

### Corpus exports

The explorer enriches retrieval docs with corpus-level metadata from:

- `output_corpus/corpus_concept_graph.json`
- `output_corpus/concept_alias_registry.json`
- `output_corpus/concept_rule_map.json`
- `output_corpus/rule_family_index.json`
- `output_corpus/lesson_registry.json`
- `output_corpus/corpus_metadata.json`

These files are used for alias lookup, graph traversal, related-rule lookup, lesson metadata, and corpus contract version reporting.

### Concept graph

Concept neighbors are computed from `corpus_concept_graph.json` relations. For each relation:

- the source concept gets an `outgoing` neighbor entry
- the target concept gets an `incoming` neighbor entry

The service returns these as lightweight `ConceptNeighbor` objects with `concept_id`, `relation`, `direction`, and `weight`.

### Lesson registry

Lesson summaries use `lesson_registry.json` to surface `lesson_title` and to validate lesson existence even when a lesson currently has no explorer docs.

## Search behavior

### Non-empty query

When `query` is non-empty, `ExplorerService.search()`:

1. calls the existing `HybridRetriever.search()`
2. consumes `top_hits[*].resolved_doc`
3. applies browser-specific post-filters
4. converts filtered hits into `BrowserResultCard`
5. computes groups and page-scoped facets for the returned cards

This keeps Step 4.1 retrieval-driven while separating browser contracts from raw retrieval internals.

### Empty query

When `query` is empty, the explorer enters browse mode:

1. list all docs from the repository
2. sort deterministically by unit priority, then confidence, then lesson id, then doc id
3. apply browser filters
4. return browser cards only

Browse ordering priority:

1. `rule_card`
2. `knowledge_event`
3. `evidence_ref`
4. `concept_node`
5. `concept_relation`

## Detail behavior

### Rule detail

Rule detail is assembled from:

- the base `rule_card` doc
- linked evidence docs via `evidence_ids` and `source_rule_ids`
- source events via `source_event_ids`
- related rules via concept overlap, rule-family index, and source-rule references

### Evidence detail

Evidence detail is assembled from:

- the base `evidence_ref` doc
- linked source rules via `source_rule_ids`
- linked source events via `source_event_ids`

### Concept detail

Concept detail combines:

- aliases from `concept_alias_registry.json`
- neighbors from `corpus_concept_graph.json`
- top rules and events from repository concept lookups
- total rule/event/evidence counts from the full concept doc set
- lesson coverage from graph metadata and matched docs

### Lesson detail

Lesson detail is computed from all docs matching a `lesson_id` and includes:

- counts by unit type
- counts by support basis
- top concepts by frequency
- top rule cards
- top evidence refs

## Filtering

Supported browser filters:

- `lesson_ids`
- `concept_ids`
- `unit_types`
- `support_basis`
- `evidence_requirement`
- `teaching_mode`
- `min_confidence_score`

Filtering behavior:

- query mode: retrieval first, browser post-filter second
- browse mode: repository listing first, browser filter second
- the `facets` field inside `/browser/search` reflects the current returned card set
- `/browser/facets` computes counts over the full filtered explorer set, not only the current page

## Notes on contracts

- Search returns browser cards, not raw retrieval docs.
- Detail responses expose selected structured fields only.
- Explorer contracts intentionally avoid leaking `resolved_doc`, score breakdown internals, or full raw metadata blobs as top-level API shape.
