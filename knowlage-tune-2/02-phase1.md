Yes. Use this as the **exact implementation brief for the agent**.

**Confidence: High**

---

## Agent brief: close Phase 1 properly

Your goal is to make **final exports hard-gated** so invalid rules cannot leak into `rule_cards.json`, `ml_manifest.json`, or `labeling_manifest.json`.

This is required because the target design says rule cards must preserve provenance, especially `source_event_ids`, and ML-ready fields should not be populated aggressively when the data does not support them.
The current outputs still show invalid ML guidance derived from `"No rule text extracted."` with empty `source_event_ids`, so the export path is still leaking bad rules.

### Core diagnosis

* `rule_reducer.py` already rejects invalid rule cards during initial build.
* But `main.py` later re-saves `rule_cards.json` after ML enrichment.
* `ml_prep.py` enriches every rule without checking export validity.
* `schemas.py` has good validators, but they are helper functions, not hard export gates.
* `provenance.py` reports warnings, but those warnings are not enforced during export.

---

# 1. `schemas.py`

### File reference

* `validate_rule_card()` is already present around lines **205–228**
* `validate_evidence_ref()` is already present around lines **231–245**
* placeholder helpers already exist around lines **47–72**

### Change required

Add **strict export-level validators**. Do not replace the current helpers; add stricter ones.

### Implement

Add these functions near the existing validators:

```python
def validate_rule_card_for_export(rule: RuleCard) -> list[str]:
    errors = list(validate_rule_card(rule))

    if not (rule.lesson_id or "").strip():
        errors.append("lesson_id must not be empty for final export")

    if not (rule.concept or "").strip():
        errors.append("concept must not be empty for final export")

    if rule.labeling_guidance and is_placeholder_text(rule.rule_text):
        errors.append("labeling_guidance must be empty for placeholder rule_text")

    return dedupe_preserve_order(errors)


def validate_rule_card_collection_for_export(
    collection: RuleCardCollection,
) -> tuple[RuleCardCollection, list[dict]]:
    valid_rules: list[RuleCard] = []
    debug_rows: list[dict] = []

    for rule in collection.rules:
        errors = validate_rule_card_for_export(rule)
        if errors:
            debug_rows.append({
                "stage": "export_validation",
                "entity_type": "rule_card",
                "entity_id": rule.rule_id,
                "rule_id": rule.rule_id,
                "reason_rejected": errors,
                "source_event_ids": list(rule.source_event_ids or []),
                "concept": rule.concept,
                "subconcept": rule.subconcept,
            })
            continue
        valid_rules.append(rule)

    return (
        RuleCardCollection(
            schema_version=collection.schema_version,
            lesson_id=collection.lesson_id,
            rules=valid_rules,
        ),
        debug_rows,
    )
```

Also add a tiny helper:

```python
def dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out
```

### Why

Current schema helpers already reject placeholder `rule_text` and missing `source_event_ids`, but only if callers explicitly use them. 
We need one reusable export-safe validator.

---

# 2. `ml_prep.py`

### File reference

* `build_labeling_guidance()` is around lines **236–262**
* `enrich_rule_card_for_ml()` is around lines **268–286**
* `enrich_rule_card_collection_for_ml()` is around lines **289–305**
* `build_ml_manifest()` is around lines **311–368**

### Change required

Make ML enrichment **defensive**. Invalid rules must not receive:

* `labeling_guidance`
* `candidate_features`
* `positive_example_refs`
* `negative_example_refs`
* `ambiguous_example_refs`

### Implement

#### 2.1 Update imports

At the top, import:

```python
from pipeline.schemas import (
    EvidenceIndex,
    EvidenceRef,
    RuleCard,
    RuleCardCollection,
    is_placeholder_text,
    validate_rule_card_for_export,
)
```

#### 2.2 Guard `build_labeling_guidance()`

At the top of the function, add:

```python
errors = validate_rule_card_for_export(rule)
if errors:
    return None
```

Then keep the current template logic.

#### 2.3 Guard `infer_candidate_features()`

At the top of the function, add:

```python
if validate_rule_card_for_export(rule):
    return []
```

This keeps ML fields conservative, which matches your own Task 13 requirement.

#### 2.4 Guard `enrich_rule_card_for_ml()`

Replace the function body with this pattern:

```python
def enrich_rule_card_for_ml(
    rule: RuleCard,
    evidence_refs: list[EvidenceRef],
) -> RuleCard:
    errors = validate_rule_card_for_export(rule)
    if errors:
        return rule.model_copy(update={
            "candidate_features": [],
            "positive_example_refs": [],
            "negative_example_refs": [],
            "ambiguous_example_refs": [],
            "labeling_guidance": None,
        })

    feature_list = infer_candidate_features(rule)
    example_buckets = distribute_example_refs_for_ml(rule, evidence_refs)
    labeling_guidance = build_labeling_guidance(rule)

    return rule.model_copy(update={
        "candidate_features": feature_list,
        "positive_example_refs": example_buckets["positive_example_refs"],
        "negative_example_refs": example_buckets["negative_example_refs"],
        "ambiguous_example_refs": example_buckets["ambiguous_example_refs"],
        "labeling_guidance": labeling_guidance,
    })
```

#### 2.5 Filter manifest rows

Inside `build_ml_manifest()`, skip invalid rules entirely:

```python
for rule in rule_cards.rules:
    if validate_rule_card_for_export(rule):
        debug_rows.append({
            "rule_id": rule.rule_id,
            "skipped_from_manifest": True,
            "reason": validate_rule_card_for_export(rule),
        })
        continue
```

Do the same in `build_labeling_manifest()`:

* skip invalid rules
* do not emit labeling tasks for them

### Why

Your current ML output shows placeholder-derived guidance and empty provenance in manifest rows.

---

# 3. `main.py`

### File reference

* Rule-card build/save block is around lines **294–314**
* ML-prep block is around lines **329–374**

### Change required

Add one **central final validation pass** after:

1. `build_rule_cards(...)`
2. `enrich_rule_card_collection_for_ml(...)`

This is the main fix.

### Implement

#### 3.1 Update imports

Add to the import section:

```python
from pipeline.schemas import (
    RuleCardCollection,
    validate_rule_card_collection_for_export,
)
from pipeline.component2.provenance import validate_rule_card_provenance
```

#### 3.2 Add helper near `require_artifact()`

Add:

```python
def _merge_rule_debug_rows(
    base_rows: list[dict],
    extra_rows: list[dict],
) -> list[dict]:
    if not base_rows:
        return list(extra_rows)
    if not extra_rows:
        return list(base_rows)
    return [*base_rows, *extra_rows]
```

#### 3.3 Validate after `build_rule_cards(...)`

In the Step 4b block, after:

```python
rule_cards, rule_debug = build_rule_cards(...)
```

insert:

```python
validated_rule_cards, export_rejects = validate_rule_card_collection_for_export(rule_cards)

# also promote provenance warnings to export rejects for final rules
final_rules: list = []
provenance_rejects: list[dict] = []
for rule in validated_rule_cards.rules:
    prov_warnings = validate_rule_card_provenance(rule)
    if prov_warnings:
        provenance_rejects.append({
            "stage": "export_validation",
            "entity_type": "rule_card",
            "entity_id": rule.rule_id,
            "rule_id": rule.rule_id,
            "reason_rejected": prov_warnings,
            "source_event_ids": list(rule.source_event_ids or []),
            "concept": rule.concept,
            "subconcept": rule.subconcept,
        })
        continue
    final_rules.append(rule)

rule_cards = RuleCardCollection(
    schema_version=validated_rule_cards.schema_version,
    lesson_id=validated_rule_cards.lesson_id,
    rules=final_rules,
)

rule_debug = _merge_rule_debug_rows(rule_debug, export_rejects)
rule_debug = _merge_rule_debug_rows(rule_debug, provenance_rejects)
```

Then save only the filtered `rule_cards`.

#### 3.4 Validate again after ML prep

In the Step 13 block, after:

```python
enriched_rule_cards = enrich_rule_card_collection_for_ml(rule_cards, evidence_index)
```

insert the same validation pass again.

Then:

* save only validated enriched rules to `rule_cards.json`
* append newly rejected enriched rows to `rule_debug.json`

Pattern:

```python
validated_enriched_rule_cards, ml_export_rejects = validate_rule_card_collection_for_export(enriched_rule_cards)

final_enriched_rules: list = []
ml_provenance_rejects: list[dict] = []
for rule in validated_enriched_rule_cards.rules:
    prov_warnings = validate_rule_card_provenance(rule)
    if prov_warnings:
        ml_provenance_rejects.append({
            "stage": "ml_export_validation",
            "entity_type": "rule_card",
            "entity_id": rule.rule_id,
            "rule_id": rule.rule_id,
            "reason_rejected": prov_warnings,
            "source_event_ids": list(rule.source_event_ids or []),
            "concept": rule.concept,
            "subconcept": rule.subconcept,
        })
        continue
    final_enriched_rules.append(rule)

enriched_rule_cards = RuleCardCollection(
    schema_version=validated_enriched_rule_cards.schema_version,
    lesson_id=validated_enriched_rule_cards.lesson_id,
    rules=final_enriched_rules,
)

existing_rule_debug = []
if paths.rule_debug_path(lesson_name).exists():
    existing_rule_debug = json.loads(paths.rule_debug_path(lesson_name).read_text(encoding="utf-8"))

combined_rule_debug = _merge_rule_debug_rows(existing_rule_debug, ml_export_rejects)
combined_rule_debug = _merge_rule_debug_rows(combined_rule_debug, ml_provenance_rejects)

save_rule_cards(enriched_rule_cards, paths.rule_cards_path(lesson_name))
save_rule_debug(combined_rule_debug, paths.rule_debug_path(lesson_name))
rule_cards = enriched_rule_cards
```

### Why

Your current Step 13 block follows the intended Task 13 integration and re-saves enriched rules, but that is exactly why a second hard validation pass is needed there.

---

# 4. `provenance.py`

### File reference

* `validate_evidence_ref_provenance()` is around lines **203–228**
* `validate_rule_card_provenance()` is around lines **231–250**
* `compute_provenance_coverage()` is around lines **253–289**

### Change required

Do not rewrite this file heavily. Add one helper that converts provenance warnings into export decisions.

### Implement

Add:

```python
def validate_rule_card_for_final_provenance(rule: Any) -> list[str]:
    warnings = validate_rule_card_provenance(rule)
    hard_errors: list[str] = []

    for warning in warnings:
        if warning in {
            "missing lesson_id",
            "missing source_event_ids",
            "missing concept",
            "visual_summary present but evidence_refs missing",
        }:
            hard_errors.append(warning)

    return hard_errors
```

Then use this helper in `main.py` instead of calling `validate_rule_card_provenance()` directly.

### Why

Task 11 says normalized rules must preserve provenance. That should be hard-enforced at final export, not only logged as QA.

---

# 5. `evidence_linker.py`

### File reference

* `infer_example_role()` is around lines **303–327**

### Change required

Fix the `false_breakout` bug.

Right now the heuristic treats any content containing `"false"` as a counterexample, which is wrong for valid false-breakout teaching examples.

### Implement

Replace:

```python
counter_indicators = ["failure", "false", "trap", "mistake", "invalid", "counter"]
```

with:

```python
counter_indicators = ["failure", "trap", "mistake", "invalid", "counter"]
```

Then rewrite the function logic to be conservative:

```python
def infer_example_role(
    candidate: VisualEvidenceCandidate,
    linked_events: list[KnowledgeEvent],
) -> str:
    content_lower = (
        (
            (candidate.compact_visual_summary or "")
            + " "
            + " ".join(candidate.concept_hints)
            + " "
            + " ".join(e.change_summary or "" for e in candidate.visual_events)
        )
        .lower()
        .strip()
    )

    event_types = [e.event_type for e in linked_events]

    if any(t in event_types for t in ("invalidation", "exception", "warning")):
        return "counterexample"

    if any(x in content_lower for x in ["failure", "trap", "mistake", "invalid", "counterexample"]):
        return "counterexample"

    if any(t in event_types for t in ("rule_statement", "condition")):
        return "positive_example"

    if any(t in event_types for t in ("definition", "comparison")):
        return "illustration"

    if not linked_events or all(t == "example" for t in event_types):
        return "ambiguous_example"

    return "illustration"
```

### Why

Evidence is supposed to be supporting context, not noisy misclassification, and visuals should become compact evidence refs rather than misleading labels.

---

# 6. `contracts.py`

### File reference

* `ValidationPolicy` exists already around lines **14–22**

### Change required

Actually use it.

### Implement

Add two module-level constants:

```python
STRICT_FINAL_EXPORT_POLICY = ValidationPolicy(
    allow_unlinked_evidence_pre_reduction=True,
    reject_placeholder_rule_text=True,
    require_rule_source_event_ids=True,
    require_event_normalized_text=True,
)

RELAXED_PRE_REDUCTION_POLICY = ValidationPolicy(
    allow_unlinked_evidence_pre_reduction=True,
    reject_placeholder_rule_text=False,
    require_rule_source_event_ids=False,
    require_event_normalized_text=True,
)
```

Then thread `STRICT_FINAL_EXPORT_POLICY` into `main.py` export validation if you want one clear source of truth.

### Why

`ValidationPolicy` currently exists but is dead code. Using it makes the export behavior explicit.

---

# 7. `rule_reducer.py`

### File reference

* `build_rule_cards()` around lines **672–727**

### Change required

Very small.

This file is already doing the right thing by validating cards before initial export. Keep that logic.

Only add one debug field so later rejections are easier to analyze:

Inside the `warnings` branch, add:

```python
"provenance_warnings": validate_rule_card_provenance(card),
```

You do **not** need a bigger rewrite here for this step.

---

# 8. Tests to add

Create or update:

## `tests/test_phase1_export_validation.py`

Add these tests:

### A. placeholder rule is removed before final export

* Build `RuleCardCollection` with one valid rule and one placeholder rule.
* Run `validate_rule_card_collection_for_export()`.
* Assert only the valid rule remains.
* Assert one debug reject row exists.

### B. ML enrichment does not generate guidance for invalid rule

* Rule with `rule_text="No rule text extracted."`
* `source_event_ids=[]`
* Call `enrich_rule_card_for_ml()`
* Assert:

  * `labeling_guidance is None`
  * `candidate_features == []`
  * all ML example refs are empty

### C. ML manifest skips invalid rules

* Build collection with one invalid rule
* Run `build_ml_manifest()`
* Assert invalid rule is absent from `manifest["rules"]`

### D. false breakout is not auto-counterexample

* Create `VisualEvidenceCandidate` whose summary contains `"false breakout"`
* Link it to a `rule_statement`
* Assert `infer_example_role(...) != "counterexample"`

### E. main-style post-ML validation catches bad rules

* Simulate enriched collection containing one invalid rule
* Run export validation helper
* Assert invalid rule is quarantined

---

# 9. Acceptance criteria

Phase 1 is done only when all of this is true:

* `rule_cards.json` contains **zero** rules with `"No rule text extracted."`
* `rule_cards.json` contains **zero** rules with empty `source_event_ids`
* `ml_manifest.json` contains **zero** placeholder-derived `labeling_guidance` rows
* `labeling_manifest.json` contains no tasks for invalid rules
* new invalid rows appear only in `rule_debug.json`
* a legitimate `false_breakout` example is no longer auto-labeled `counterexample`

That matches both the provenance requirement and the “do not populate aggressively” ML guidance from your original design.

---

# 10. Short implementation order

Do it in this order:

1. `schemas.py`
2. `ml_prep.py`
3. `provenance.py`
4. `main.py`
5. `evidence_linker.py`
6. tests

That is the fastest path to actually closing the leak.

If you want, I can also turn this into a **single copy-paste Cursor task prompt** with no explanation text around it.
