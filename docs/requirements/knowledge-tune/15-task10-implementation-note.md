# Task 14 + Task 12 Implementation Note

## What changed

### Task 14: Regression tests finalized

Created a comprehensive regression test suite covering both canonical lessons with checks A through H:

- **A**: Structured artifact existence (knowledge_events, rule_cards, evidence_index, concept_graph, ml_manifest, labeling_manifest, rag_ready.md, review_markdown.md)
- **B**: Rule cards provenance (lesson_id, source_event_ids, no placeholder rule_text)
- **C**: Knowledge events cleanliness (non-empty normalized_text, Phase 2A fields present)
- **D**: Timestamp confidence rule (no `line` confidence with `anchor_span_width > 3`)
- **E**: Evidence backlink integrity (linked_rule_ids, source_event_ids populated)
- **F**: ML safety guard (no illustrations in ML examples, no weak-specificity evidence leakage)
- **G**: Markdown quality (no repetitive frame spam, timestamps not collapsed to `[00:00]`)
- **H**: Cross-file integrity (all references between events, rules, and evidence resolve)

### Task 12: Concept graph enhanced

Enhanced the existing concept graph builder to match the full specification:

**New node types added**: `condition`, `invalidation`, `exception` (extracted from `RuleCard.conditions`, `RuleCard.invalidation`, `RuleCard.exceptions`). Only short, reusable text (<=120 chars, non-placeholder) qualifies for node creation.

**New edge types added**:
- `has_condition`: concept/subconcept -> condition node
- `has_invalidation`: concept/subconcept -> invalidation node
- `has_exception`: concept/subconcept -> exception node
- `co_occurs_with`: between concept/subconcept pairs appearing together in >= 2 rules

**Integer weights on all edges**: Weights represent the number of supporting rules. When edges merge during deduplication, weights sum.

**`source_rule_ids` on nodes and relations**: Both track which rule_ids contribute to them.

**`stats` block added**: `{ node_count, edge_count }` matches actual list lengths.

**`graph_version` field added**: Set to `"1.0"`.

## How the concept graph is built

1. Extract concept and subconcept nodes from `rule_cards.json` (normalize labels, infer parent for subconcepts)
2. Extract condition/invalidation/exception nodes from rule card text fields (short text only)
3. Build relation edges: `parent_of`/`child_of`, `related_to` (siblings), `precedes` (chunk order), `depends_on` (dependency cues), `contrasts_with` (name pairs and comparison cues), `supports` (naming heuristic), `has_condition`/`has_invalidation`/`has_exception`, `co_occurs_with` (threshold >= 2)
4. Deduplicate nodes by `concept_id`, relations by `(source_id, relation_type, target_id)` with weight merging
5. Compute stats and serialize as `concept_graph.json`

No LLM calls. No markdown dependency. Purely deterministic from `rule_cards.json`.

## Tests added

**Unit tests** (tests/test_concept_graph.py): 24 tests total (was 9), covering:
- Condition, invalidation, exception node creation and filtering
- has_condition, has_invalidation, has_exception edges
- co_occurs_with threshold behavior
- Integer weight merging
- source_rule_ids tracking
- Stats accuracy
- graph_version presence
- No markdown dependency (structural test)

**Regression tests** (tests/regression_helpers.py + tests/integration/):
- `test_lesson2_artifact_regression.py`: Full A-H checks for Lesson 2
- `test_sviatoslav_regression.py`: 10 tests covering A-H + ML safety specifics + weak-specificity isolation

**Total tests: 361 passing** (2 expected skips).

## Files changed

| File | Change |
|------|--------|
| `pipeline/schemas.py` | Extended ConceptNodeType, ConceptNode (source_rule_ids), ConceptRelation (weight, source_rule_ids), ConceptGraph (graph_version, stats), new ConceptGraphStats |
| `pipeline/component2/concept_graph.py` | Added secondary node extraction, secondary edges, co_occurs_with, weight/source_rule_ids tracking, stats computation |
| `tests/conftest.py` | Added --enable-concept-graph and --enable-exporters to run_lesson2_pipeline |
| `tests/regression_helpers.py` | NEW: Shared assertion functions for A-H regression checks |
| `tests/test_concept_graph.py` | Extended from 9 to 24 tests |
| `tests/integration/test_lesson2_artifact_regression.py` | Rewritten with shared helpers, concept graph + markdown + cross-file checks |
| `tests/integration/test_sviatoslav_regression.py` | NEW: 10 regression tests for Sviatoslav lesson |

## Known limitations

- `pattern` node type is defined in schema but not yet extracted (no clear pattern field on RuleCard)
- Co-occurrence edges only count concept+subconcept co-occurrence within a single rule, not across evidence or markdown
- Secondary nodes (condition/invalidation/exception) use exact-match dedup, not fuzzy
- The `--enable-concept-graph` flag is still opt-in, not default
