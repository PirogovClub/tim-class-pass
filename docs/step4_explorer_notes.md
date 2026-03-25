# Step 4 Explorer Notes

## Scope

Step 4.3 keeps the Step 4 explorer read-only while adding comparison and traversal workflows. It still does not add:

- write-back or analyst annotations
- auth or multi-user state
- export bundle authoring beyond audit artifacts
- new retrieval experiments or ML inference

## Data flow

### Retrieval docs

The explorer still uses `output_rag/retrieval_docs_all.jsonl` as the browser read-model source. The repository loads that document store once, then builds read-oriented indexes for:

- concept keys
- source rules
- source events
- rule family relationships

### Corpus exports

The explorer enriches retrieval docs with corpus-level metadata from:

- `output_corpus/corpus_concept_graph.json`
- `output_corpus/concept_alias_registry.json`
- `output_corpus/concept_rule_map.json`
- `output_corpus/rule_family_index.json`
- `output_corpus/lesson_registry.json`
- `output_corpus/corpus_metadata.json`

These files power alias lookup, graph traversal, concept-to-rule traversal, concept-to-lesson traversal, rule family grouping, and lesson metadata validation.

## Search behavior

### Query mode

When `query` is non-empty, `ExplorerService.search()`:

1. calls the accepted `HybridRetriever.search()`
2. consumes `top_hits[*].resolved_doc`
3. applies browser-specific post-filters
4. converts filtered hits into `BrowserResultCard`
5. computes groups and page-scoped facets for the returned cards

The Step 3.1 search regressions remain protected. Step 4.3 adds only a narrow browser-layer post-processing rule so explicit timeframe rule queries stay rule-first in the explorer UI.

### Browse mode

When `query` is empty, the explorer enters deterministic browse mode:

1. list all docs from the repository
2. sort by unit priority, confidence, lesson id, then doc id
3. apply browser filters
4. return browser cards only

Browse ordering priority:

1. `rule_card`
2. `knowledge_event`
3. `evidence_ref`
4. `concept_node`
5. `concept_relation`

## Comparison behavior

### Rule comparison

Rule comparison validates two to four unique `rule_card` ids, preserves the requested order, and returns:

- one `RuleCompareItem` per selected rule
- a deterministic `ComparisonSummary`

The summary is field-based only. Shared concepts, shared lessons, shared support basis, differing fields, and possible relationships are all computed from explicit explorer fields.

### Lesson comparison

Lesson comparison validates two to four unique lesson ids, loads lesson metadata plus all lesson docs, and returns:

- one `LessonCompareItem` per selected lesson
- shared concepts across all lessons
- per-lesson unique concepts
- overlapping rule families when they exist

## Traversal behavior

### Related rules

Related rules are grouped by explicit deterministic reasons:

- `same_concept`
- `same_family`
- `same_lesson`
- `linked_by_evidence`
- `cross_lesson_overlap`

Groups are non-destructive and additive. A given related rule may appear in more than one group when it genuinely satisfies multiple traversal reasons.

### Concept traversal

Concept traversal now supports:

- `GET /browser/concept/{concept_id}/rules`
- `GET /browser/concept/{concept_id}/lessons`

Concept-linked rules come from the concept rule map plus normalized repository lookups. Concept-linked lessons are derived from those rule docs and concept metadata.

## UI notes

The Step 4.3 UI adds:

- shareable compare routes via `?ids=a,b`
- rule compare and lesson compare pages
- rule detail to related-rules navigation
- concept detail to all-rules / all-lessons navigation
- session-backed compare selection with a global launch bar

The compare launch bar is intentionally lightweight. Selection is capped at four ids and stored locally for the current browser session. The compare page URL remains the shareable canonical source of truth.

## Contract guardrails

- Search returns browser cards, never raw retrieval docs.
- Compare summaries are deterministic and non-generative.
- Traversal reasons are explicit strings, not fuzzy heuristics.
- Explorer contracts still avoid exposing raw `resolved_doc`, score breakdown internals, or opaque metadata blobs as top-level API surface.
