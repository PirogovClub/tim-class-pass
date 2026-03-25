Yes. In **my fix plan**, **Phase 1 = stabilize schemas and validity gates**. It is the step that prevents garbage records from reaching final artifacts.

The need is very concrete: your current `rule_cards.json` contains multiple final rules with `rule_text: "No rule text extracted."`, empty `source_event_ids`, and generated labeling guidance based on that placeholder, which means invalid records are already leaking into downstream artifacts.
Also, the original redesign requires explicit JSON schemas, JSON-first extraction, and preserved provenance for rules and evidence, so Phase 1 should enforce those invariants at the schema boundary.

**Confidence: High — grounded in the current lesson outputs and your redesign spec.**

## What to change in Phase 1

### 1. `pipeline/component2/schemas.py`

This is the main file for Phase 1.

Add or tighten these models:

#### `KnowledgeEvent`

Required:

* `event_id: str`
* `lesson_id: str`
* `event_type: Literal[...]`
* `raw_text: str`
* `normalized_text: str`
* `evidence_refs: list[str] = []`
* `source_event_ids: list[str] = []`
* `metadata: dict = {}`
* `confidence: Literal["low","medium","high"] | None`
* `confidence_score: float | None`

Optional but strongly preferred:

* `section`
* `subsection`
* `timestamp_start`
* `timestamp_end`
* `concept`
* `subconcept`
* `ambiguity_notes`

Validation rules:

* `event_id`, `lesson_id`, `event_type`, `normalized_text` must not be empty
* reject placeholder text like:

  * `"No rule text extracted."`
  * `"N/A"`
  * `"unknown"`
* normalize whitespace
* `confidence_score` must be `0.0 <= x <= 1.0` if present

#### `RuleCard`

Required:

* `rule_id: str`
* `lesson_id: str`
* `rule_text: str`
* `source_event_ids: list[str]`
* `evidence_refs: list[str]`
* `conditions/context/invalidation/exceptions/comparisons/algorithm_notes: list[str]`
* `candidate_features/positive_example_refs/negative_example_refs/ambiguous_example_refs: list[str]`
* `metadata: dict = {}`

Validation rules:

* reject if `rule_text` is empty
* reject if `rule_text == "No rule text extracted."`
* reject if `source_event_ids` is empty
* reject if all of these are empty:

  * `rule_text`
  * `conditions`
  * `invalidation`
  * `exceptions`
  * `comparisons`
  * `algorithm_notes`
* if `visual_summary` exists and `evidence_refs` is empty, emit validation warning
* `labeling_guidance` must be empty or omitted if the rule is invalid

This directly fixes the bad records currently present in your final rule cards.

#### `EvidenceRef`

Required:

* `evidence_id: str`
* `lesson_id: str`
* `example_role: Literal["positive_example","negative_example","counterexample","ambiguous_example","illustration"]`
* `frame_ids: list[str]`
* `raw_visual_event_ids: list[str]`
* `linked_rule_ids: list[str]`
* `source_event_ids: list[str]`
* `compact_visual_summary: str | None`

Validation rules:

* reject if `lesson_id` missing
* reject if both `frame_ids` and `raw_visual_event_ids` are empty
* `linked_rule_ids` may be empty only in pre-reduction artifacts
* `compact_visual_summary` max length cap, for example 240–300 chars
* reject summaries that look like long narration

This aligns with the spec that visuals should be stored as evidence with compact summaries, not verbose narrative.

### 2. Add shared validation helpers in `schemas.py`

Create these exact functions:

```python
PLACEHOLDER_TEXTS = {
    "",
    "no rule text extracted.",
    "n/a",
    "unknown",
    "none",
}

def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(value.strip().split())

def is_placeholder_text(value: str | None) -> bool:
    return normalize_text(value).lower() in PLACEHOLDER_TEXTS

def is_compact_summary(value: str | None, max_len: int = 300) -> bool:
    if value is None:
        return True
    text = normalize_text(value)
    return len(text) <= max_len
```

And model-facing validators:

```python
def validate_knowledge_event(event) -> list[str]: ...
def validate_rule_card(rule) -> list[str]: ...
def validate_evidence_ref(evidence, allow_unlinked_rules: bool = True) -> list[str]: ...
```

These should return warning/error lists, not only booleans.

---

### 3. `pipeline/component2/knowledge_builder.py`

Phase 1 change here is not to improve semantic extraction yet.
It is to stop invalid `KnowledgeEvent`s from being emitted.

Make these exact changes:

#### Before creating a `KnowledgeEvent`

* run `normalize_text()` on `raw_text` and `normalized_text`
* if `normalized_text` is placeholder or empty, do **not** emit final event
* send it to `knowledge_debug.json` with:

  * `candidate_text`
  * `reason_rejected`
  * `chunk_index`
  * `section`
  * `timestamp_start`
  * `timestamp_end`

#### When creating a valid event

* always populate:

  * `lesson_id`
  * `event_id`
  * `event_type`
  * `normalized_text`
  * `evidence_refs=[]`
  * `source_event_ids=[]`
* attach compact metadata with chunk/timing fields, not raw blobs

This matches the original requirement that `knowledge_builder.py` be JSON-first and emit atomic statements with timestamps and evidence ids attached.

#### Add a small builder result object

Example:

```python
@dataclass
class KnowledgeBuildResult:
    events: list[KnowledgeEvent]
    debug_rows: list[dict]
    rejected_count: int
```

That gives you clean debugging without polluting final JSON.

---

### 4. `pipeline/component2/rule_reducer.py`

Phase 1 change here is **not** the full dedup rewrite yet.
It is a validity gate before any `RuleCard` is written.

Add this exact flow:

```python
candidate_rule = build_rule_card_candidate(...)

warnings = validate_rule_card(candidate_rule)

if warnings:
    rule_debug_rows.append({
        "rule_id": candidate_rule.rule_id,
        "reason_rejected": warnings,
        "source_event_ids": candidate_rule.source_event_ids,
        "concept": candidate_rule.concept,
        "subconcept": candidate_rule.subconcept,
    })
    continue

final_rules.append(candidate_rule)
```

Also add these rules:

* if `rule_text` is placeholder, do not export
* if `source_event_ids` is empty, do not export
* if `labeling_guidance` contains `"No rule text extracted."`, blank it and quarantine the rule
* do not auto-fill medium confidence for invalid rules

This is required because your current final rules violate provenance and quality expectations.

---

### 5. `pipeline/component2/evidence_linker.py`

Phase 1 here is again about validity, not smart semantic linking yet.

Make these exact changes:

#### When building an `EvidenceRef`

* always populate:

  * `evidence_id`
  * `lesson_id`
  * `source_event_ids`
  * `frame_ids`
  * `raw_visual_event_ids`
  * `linked_rule_ids=[]`
* build `compact_visual_summary`
* cap the summary length
* reject if both `frame_ids` and `raw_visual_event_ids` are empty

#### Add pre-reduction vs final validation mode

* pre-reduction artifact: `linked_rule_ids=[]` allowed
* final artifact after reduction: empty `linked_rule_ids` should become warning or rejection, depending on config

This is needed because the current evidence index shows many entries with `linked_rule_ids: []`, broad source-event attachment, and counterexample labeling even for intro/example visuals. Phase 1 should at least stop structurally bad evidence records from being treated as healthy.

---

### 6. `contracts.py` or shared pipeline types

Add a strict export contract so each stage knows what can be finalized.

Recommended:

```python
@dataclass
class ValidationPolicy:
    allow_unlinked_evidence_pre_reduction: bool = True
    reject_placeholder_rule_text: bool = True
    require_rule_source_event_ids: bool = True
    require_event_normalized_text: bool = True
```

Then pass this into builder/reducer/exporter.

That makes the behavior explicit instead of hidden in scattered `if` statements.

---

### 7. `main.py` / orchestration

Add one validation checkpoint before writing artifacts.

Exact pattern:

```python
knowledge_events = ...
evidence_refs = ...
rule_cards = ...

valid_events, invalid_events = split_valid_events(knowledge_events)
valid_evidence, invalid_evidence = split_valid_evidence(evidence_refs)
valid_rules, invalid_rules = split_valid_rules(rule_cards)

write_json(valid_events, "knowledge_events.json")
write_json(valid_evidence, "evidence_index.json")
write_json(valid_rules, "rule_cards.json")

write_json(invalid_events, "knowledge_debug.json")
write_json(invalid_evidence, "evidence_debug.json")
write_json(invalid_rules, "rule_debug.json")
```

Do **not** let invalid rows flow into `rule_cards.json` just because the pipeline completed.

---

### 8. Add one new debug convention

Each rejected row should include:

* `stage`
* `entity_type`
* `entity_id`
* `warnings`
* `source_event_ids`
* `chunk_index` or timestamps if available

That will make the next phases much faster to debug.

---

### 9. Tests to add in Phase 1

Create a dedicated test file, for example:

`tests/test_phase1_validation.py`

Add these exact tests:

#### `test_reject_placeholder_rule_card`

Input:

* `RuleCard(rule_text="No rule text extracted.", source_event_ids=[])`

Expected:

* validation errors
* not written to final rules

#### `test_accept_minimal_valid_rule_card`

Input:

* rule with real `rule_text`
* non-empty `source_event_ids`

Expected:

* passes validation

#### `test_reject_empty_knowledge_event_text`

Input:

* event with empty `normalized_text`

Expected:

* rejected

#### `test_reject_evidence_with_no_frames_and_no_raw_visual_ids`

Expected:

* rejected

#### `test_allow_unlinked_evidence_pre_reduction`

Expected:

* passes with warning only

#### `test_blank_labeling_guidance_for_invalid_rule`

Expected:

* invalid placeholder rule does not emit guidance

These tests are fully aligned with the redesign requirement for explicit schemas, structured artifacts, and production-safe behavior.

## What should be true after Phase 1

When Phase 1 is done:

* `rule_cards.json` has **zero** `"No rule text extracted."` rows
* `rule_cards.json` has **zero** final rules with empty `source_event_ids`
* `knowledge_events.json` has no empty `normalized_text`
* `evidence_index.json` has no structurally broken evidence rows
* invalid rows still exist, but only in debug artifacts

That is the real purpose of this phase: **make final artifacts trustworthy enough that later dedup and evidence logic are not working on garbage**.

## My recommendation

Implement Phase 1 in this order:

1. `schemas.py`
2. `knowledge_builder.py`
3. `rule_reducer.py`
4. `evidence_linker.py`
5. `main.py`
6. tests

If you want, I’ll turn this into a **copy-paste coding task for Cursor** with exact file-by-file instructions.
