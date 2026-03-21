# 17-task10 Implementation Note: Correctness Hardening Pass

## Summary

Five narrow correctness fixes applied without redesigning the pipeline, broadening ML eligibility, or changing extraction prompts.

---

## Part 1 -- Contradictory positive-example assignment

**Problem:** A single evidence row could become a `positive_example` for two rules with opposite directional meaning (e.g., one bullish, one bearish).

**Fix:** New module `pipeline/component2/rule_compat.py` with two deterministic helpers:

- `infer_rule_direction(rule)` -- keyword matching on `rule_text`, `concept_id`, `subconcept_id`, conditions, and invalidations. Returns one of: `bullish_above`, `bearish_below`, `breakout_up`, `breakout_down`, `reversal_up`, `reversal_down`, `neutral`, `unknown`.
- `is_positive_example_compatible(rule, evidence, all_rules_by_id)` -- blocks positive attachment when the evidence is linked to multiple rules with conflicting directions.

**Wiring:** Compatibility gate inserted in `distribute_example_refs_for_ml`, `attach_rule_example_refs`, `build_ml_examples`, and `build_labeling_manifest` in `ml_prep.py`. Single-rule evidence is always compatible (no contradiction possible).

---

## Part 2 -- ML output gating hardened

**Problem:** ML outputs were active before contradictory assignment was fully resolved.

**Fix:** `is_evidence_safe_for_ml(evidence, all_rules_by_id)` added to `rule_compat.py`. Returns `False` when evidence is linked to 2+ rules with conflicting or unresolvable directions. Wired as an additional gate into all ML manifest and labeling manifest builders.

**Result:** Lesson 2 produces 0 ML examples / 0 labeling tasks (conservative). Sviatoslav produces 1 ML example / 1 labeling task (only the one with clear, non-conflicting direction).

---

## Part 3 -- Russian `*_ru` fields populated

**Problem:** The new multilingual schema fields existed conceptually but were never created or filled.

**Fix:** Added to `pipeline/schemas.py`:
- `KnowledgeEvent`: `normalized_text_ru`, `concept_label_ru`, `subconcept_label_ru`
- `RuleCard`: `rule_text_ru`, `concept_label_ru`, `subconcept_label_ru`
- `EvidenceRef`: `summary_ru`

Backfill logic added in:
- `knowledge_builder.py` -- populates `*_ru` from Russian source fields during event creation
- `rule_reducer.py` -- populates `*_ru` during rule card creation
- `evidence_linker.py` -- populates `summary_ru` from `compact_visual_summary`

Existing knowledge events JSON patched via `scripts/patch_ke_ru_fields.py`. All legacy fields (`normalized_text`, `rule_text`, `concept`, `subconcept`, `compact_visual_summary`) remain unchanged.

---

## Part 4 -- Concept graph provenance tightened

**Problem:** Many graph relations had empty `source_rule_ids`, making them untrustworthy.

**Fix:**
1. `create_parent_child_relations` now emits a single `has_subconcept` instead of mirrored `parent_of`/`child_of` pairs.
2. Post-filter `_filter_provenance_backed` in `build_concept_graph` drops any relation with empty `source_rule_ids` or a type not in the allowed set: `{has_subconcept, has_condition, has_invalidation, has_exception, co_occurs_with}`.

**Result:** Lesson 2 went from many unprovenance-backed relations to 38 provenance-backed. Sviatoslav: 186. All relations have non-empty `source_rule_ids`. Relation types like `related_to`, `precedes`, `contrasts_with`, `depends_on`, `supports` are filtered out.

---

## Part 5 -- RAG timestamps restored

**Problem:** `rag_ready.md` had no `[MM:SS]` timestamps.

**Fix:** New helper `resolve_rule_timestamp(rule, events_by_id)` in `exporters.py`:
1. Collects source events via `rule.source_event_ids`
2. Finds the earliest non-None `timestamp_start` (excluding `00:00`)
3. Formats as `MM:SS`

Wired into `_rag_rule_block` and `render_rag_markdown_deterministic`. Timestamp is prepended to the rule line: `[MM:SS] Rule: ...`. If no timestamp can be derived, no prefix is added.

**Result:** Lesson 2: 44 timestamps. Sviatoslav: 174 timestamps. No fabricated `[00:00]`.

---

## Test coverage

34 new tests added (438 total, all passing):
- Contradictory positive example blocking (5 tests)
- ML safety under ambiguity (5 tests)
- Direction inference (9 tests)
- Direction conflict detection (4 tests)
- Russian `*_ru` backfill (6 tests)
- Graph provenance and allowed types (3 tests)
- RAG timestamp rendering (2 tests)

Existing concept graph tests updated to reflect `has_subconcept` (replacing `parent_of`/`child_of`) and provenance filtering.

---

## Files changed

| File | Change |
|------|--------|
| `pipeline/component2/rule_compat.py` | NEW: direction inference, compatibility checks |
| `pipeline/component2/ml_prep.py` | Wired safety gates into ML manifest builders |
| `pipeline/schemas.py` | Added `*_ru` fields to KnowledgeEvent, RuleCard, EvidenceRef |
| `pipeline/component2/knowledge_builder.py` | Backfill `*_ru` fields during event creation |
| `pipeline/component2/rule_reducer.py` | Backfill `*_ru` fields during rule card creation |
| `pipeline/component2/evidence_linker.py` | Backfill `summary_ru` during evidence creation |
| `pipeline/component2/concept_graph.py` | `has_subconcept` replaces `parent_of`/`child_of`; provenance post-filter |
| `pipeline/component2/exporters.py` | Timestamp resolution and rendering in RAG markdown |
| `tests/test_rule_compat.py` | NEW: 29 tests for Parts 1-3 |
| `tests/test_concept_graph.py` | Updated + 3 new tests for Part 4 |
| `tests/test_exporters.py` | 2 new tests for Part 5 |
