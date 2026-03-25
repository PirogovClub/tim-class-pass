# 16-task10 Implementation Note: Russian-First Canonical IDs

## Design Decision

All text stays Russian throughout the pipeline. No bilingual `_ru` / `_en` label fields.
Canonical IDs are added for machine automation only. Translation of final algorithm
output is a separate future step.

## Changes Made

### New Modules

1. **`pipeline/component2/canonical_lexicon.py`** — Registry mapping ~100 known Russian
   and English trading terms to stable canonical slugs (e.g. `"уровень" → "level"`,
   `"false breakout" → "false_breakout"`). Seeded from actual `concept` and `subconcept`
   values in both lesson datasets.

2. **`pipeline/component2/canonicalization.py`** — Normalization + canonical ID generation:
   - `normalize_label()` — lowercase, NFKC normalize, collapse whitespace
   - `make_canonical_id(kind, label)` — lexicon lookup first, falls back to Cyrillic→Latin
     transliteration + slugification. Returns `"concept:level"`, `"subconcept:false_breakout"`, etc.
   - `canonicalize_concept()` / `canonicalize_subconcept()` — convenience wrappers
   - `canonicalize_short_statement(kind, text)` — for conditions/invalidations/exceptions
   - `classify_rule_type(event_type)` — maps event types to rule_type classification

### Schema Extensions (`pipeline/schemas.py`)

All new fields have defaults for backward compatibility:

- **KnowledgeEvent**: `source_language="ru"`, `concept_id`, `subconcept_id`,
  `condition_ids`, `invalidation_ids`, `exception_ids`, `rule_type`, `pattern_tags`
- **RuleCard**: Same set of canonical ID fields
- **EvidenceRef**: `source_language="ru"`, `related_concept_ids`
- **ConceptNode**: `canonical_label` (English-like readable slug from lexicon)

### Pipeline Patches

- **`knowledge_builder.py`**: Populates `source_language`, `concept_id`, `subconcept_id`,
  `rule_type` on every `KnowledgeEvent` during extraction.
- **`rule_reducer.py`**: Populates `source_language`, `concept_id`, `subconcept_id`,
  `condition_ids`, `invalidation_ids`, `exception_ids`, `rule_type` on every `RuleCard`.
  Uses `Counter` to determine dominant `event_type` from primary events for `rule_type`.
- **`concept_graph.py`**: Populates `canonical_label` on every `ConceptNode` via lexicon
  lookup. Preserved through deduplication merges.

### Tests

- **`tests/test_canonicalization.py`** (42 tests): Comprehensive unit tests for
  `normalize_label`, `make_canonical_id`, lexicon lookup, transliteration fallback,
  `canonicalize_*` helpers, `classify_rule_type`, lexicon integrity, ASCII-only ID output.
- **`tests/regression_helpers.py`**: Added `assert_canonical_ids_on_events()`,
  `assert_canonical_ids_on_rules()`, `assert_canonical_ids_on_evidence()`.
- **Integration tests**: Both Lesson 2 and Sviatoslav regression tests now assert
  canonical ID fields are present and correctly structured (check I).

## Test Results

- **404 passed**, 2 skipped (pre-existing skip conditions)
- 42 new canonicalization unit tests
- Both lesson integration tests pass canonical ID assertions

## Files Changed

| File | Change |
|------|--------|
| `pipeline/component2/canonical_lexicon.py` | NEW: term → slug registry |
| `pipeline/component2/canonicalization.py` | NEW: normalization + ID generation |
| `pipeline/schemas.py` | Added canonical ID fields to 4 schema classes |
| `pipeline/component2/knowledge_builder.py` | Populate canonical fields on KnowledgeEvent |
| `pipeline/component2/rule_reducer.py` | Populate canonical fields on RuleCard |
| `pipeline/component2/concept_graph.py` | Populate canonical_label on ConceptNode |
| `tests/test_canonicalization.py` | NEW: 42 unit tests |
| `tests/regression_helpers.py` | Added canonical field assertion helpers |
| `tests/integration/test_lesson2_artifact_regression.py` | Added canonical ID checks |
| `tests/integration/test_sviatoslav_regression.py` | Added canonical ID test |

## Files NOT Changed

- `pipeline/component2/ml_prep.py` — ML gating untouched
- `pipeline/component2/evidence_linker.py` — evidence logic untouched
- `pipeline/component2/exporters.py` — text fields stay Russian as-is

## Limitations / Future Work

- Lexicon covers ~100 terms; new terms fall back to transliteration slugification
- `pattern_tags` field defined but not yet populated (future classifier step)
- `EvidenceRef.related_concept_ids` field defined but not yet populated (requires
  cross-referencing evidence with rule concept_ids at linking time)
- Translation of final algorithm outputs to English is deferred to a future task
