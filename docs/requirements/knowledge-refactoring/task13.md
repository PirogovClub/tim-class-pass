Yes — here is the **full detailed description for Task 13**.

I’m treating Task 13 as:

# Task 13 — Prepare the Data Model for Future ML

**Confidence: High**

This is the natural next step after Tasks 10–12, because by now the pipeline already has:

* atomic knowledge (`KnowledgeEvent`)
* linked evidence (`EvidenceRef`)
* normalized rules (`RuleCard`)
* provenance
* confidence
* concept graph

Task 13 should make those artifacts **ML-ready**, without turning the pipeline into a full training system yet.

---

## Goal

Prepare the structured outputs so they can later support **supervised or weakly supervised ML workflows** for chart-pattern recognition and rule-based labeling.

This task must ensure the pipeline can support future work like:

* selecting positive/negative examples for a rule
* building training manifests from screenshots / frames / rule ids
* defining candidate features for algorithmic detection
* capturing labeling guidance for humans or models
* distinguishing:

  * positive examples
  * negative examples
  * ambiguous examples
  * supporting illustrations

Task 13 should **not** train a model and should **not** build the full labeling UI yet.

It should make the data model and outputs ready for that future work.

---

## Why this task exists

Your end goal is not just a readable RAG.

You want a pipeline that can help build:

* algorithms for level detection / rating
* training sets for ML
* pattern recognition workflows

By Task 5, the pipeline already produces `RuleCard`s.
By Task 4, it already links evidence.
By Task 11, provenance is preserved.
That is enough to start preparing the outputs for future ML.

Without Task 13, you would later have to reverse-engineer:

* which evidence refs are positives
* which are counterexamples
* what rule a screenshot belongs to
* what features the algorithm should try to compute
* what instructions a human labeler should follow

Task 13 avoids that future rework.

---

## Deliverables

Create:

* `pipeline/component2/ml_prep.py`
* `tests/test_ml_prep.py`

Update:

* `schemas.py`
* `rule_reducer.py`
* `evidence_linker.py`
* optionally `exporters.py`
* `contracts.py`
* `main.py`

Optional output files:

* `output_intermediate/<lesson>.ml_manifest.json`
* `output_intermediate/<lesson>.labeling_manifest.json`

---

## Scope

Task 13 should prepare the data model for future ML in **three layers**:

### 1. Schema readiness

Ensure `RuleCard` and related objects contain the right ML-oriented fields.

### 2. Population logic

Populate those fields conservatively from current structured data.

### 3. Manifest generation

Optionally generate lightweight machine-readable manifests for future labeling or training pipelines.

Task 13 should **not**:

* train models
* compute image embeddings
* generate real numeric market features from OHLC yet
* build a dataset UI
* create global cross-lesson training sets

---

## Core design principles

### 1. ML-readiness, not ML-completeness

This task should prepare the ground, not finish the ML system.

### 2. Rule-centered supervision

The basic supervision unit should be:

* a `RuleCard`
* linked to `EvidenceRef`s
* optionally linked to screenshots / frame ids
* labeled by example role

### 3. Deterministic first

Use the outputs already produced by earlier tasks:

* example roles from Task 4
* evidence linkage from Task 4
* rule cards from Task 5
* provenance from Task 11
* concept graph from Task 12 if helpful

Do not add an LLM as the primary ML-labeling engine.

### 4. Conservative labeling

Only populate training-related fields when the data clearly supports them.

If uncertain:

* leave a field empty
* mark an example ambiguous
* do not force fake labels

### 5. Preserve explainability

Future ML datasets should remain traceable back to:

* rule id
* source events
* evidence refs
* frame ids
* screenshots

---

## What Task 13 should add conceptually

Task 13 should prepare four things:

### A. Candidate features

Each rule should be able to carry a list of future measurable features, such as:

* reaction count
* price zone width
* time above level
* rejection magnitude

### B. Example partitions

Each rule should carry:

* `positive_example_refs`
* `negative_example_refs`
* `ambiguous_example_refs`

### C. Labeling guidance

Each rule should be able to carry concise instructions for a future human or automated labeler.

### D. ML manifests

The pipeline should optionally emit a machine-readable manifest per lesson showing:

* rule → evidence → screenshot/frame mapping
* example roles
* concept/subconcept
* confidence
* provenance

---

## Required schema updates

The earlier RuleCard design already anticipated some of this, but Task 13 should now make it explicit and operational.

### `RuleCard` fields to support and populate

These should exist in `schemas.py`:

* `candidate_features: list[str]`
* `positive_example_refs: list[str]`
* `negative_example_refs: list[str]`
* `ambiguous_example_refs: list[str]`
* `labeling_guidance: str | None`

If any of these fields are missing or only partially defined, Task 13 should formalize them.

### Optional supporting fields in `EvidenceRef`

You may also consider optional fields like:

* `ml_candidate: bool`
* `labeling_notes: str | None`

But these are optional for V1.

---

## Functional requirements

## 1. Create `pipeline/component2/ml_prep.py`

This module should be the shared ML-readiness layer.

It should be responsible for:

* deriving candidate features from rules
* distributing evidence refs into positive/negative/ambiguous buckets
* generating labeling guidance
* building optional lesson-level ML manifests
* validating ML-readiness coverage

---

## 2. Add candidate-feature inference

Implement logic that derives candidate algorithmic features from a rule’s concept, subconcept, rule text, conditions, invalidations, and comparisons.

### Goal

For each `RuleCard`, generate a conservative list of possible future measurable features.

### Example

For a rule about `level_rating`, candidate features might include:

* `reaction_count`
* `reaction_magnitude`
* `price_zone_width`
* `time_between_reactions`

For a rule about `false_breakout`, candidate features might include:

* `time_beyond_level`
* `max_distance_beyond_level`
* `reversal_speed`
* `failed_retest_flag`

### Important

This is not numeric feature computation yet.
This is only **feature naming / candidate definition**.

---

## 3. Add evidence-role distribution into ML buckets

Task 4 already assigns evidence roles like:

* `positive_example`
* `counterexample`
* `negative_example`
* `ambiguous_example`
* `illustration`

Task 13 should standardize how those map into `RuleCard` ML fields.

### Mapping

* `positive_example` → `positive_example_refs`
* `negative_example` / `counterexample` → `negative_example_refs`
* `ambiguous_example` → `ambiguous_example_refs`
* `illustration` → usually do not treat as training-positive by default

### Important

Do not blindly convert every evidence ref into a training example.

Illustrations and vague visuals should not become training positives automatically.

---

## 4. Add labeling-guidance generation

Each `RuleCard` should be able to carry a compact instruction for future labeling.

### Example

For `level_rating`:

> Label as positive only when multiple reactions occur within the same clustered price zone and the reactions are visually distinct.

For `false_breakout`:

> Label as positive only when price crosses beyond the level, fails to hold beyond it, and returns through the level.

### Important

This guidance should be:

* short
* operational
* based on rule text + invalidation + examples
* not a long paragraph

This can be generated deterministically from structured fields, or with an optional controlled LLM pass later.
For V1, deterministic templating is preferred.

---

## 5. Add ML manifest generation

Create optional lesson-level ML manifests.

### Suggested outputs

* `output_intermediate/<lesson>.ml_manifest.json`
* `output_intermediate/<lesson>.labeling_manifest.json`

You can use one file if you prefer, but the purpose should be clear.

### Suggested contents

For each rule:

* rule id
* concept
* subconcept
* confidence
* candidate features
* labeling guidance
* positive example refs
* negative example refs
* ambiguous example refs

For each example ref:

* evidence id
* frame ids
* screenshot paths
* timestamps
* example role
* source event ids

This manifest should make it easy to later build:

* a frame/screenshot dataset
* a labeling export
* a future training subset

---

## 6. Add ML-readiness validation

The pipeline should be able to report how ready each lesson is for future ML.

### Example coverage questions

* how many rules have at least one positive example?
* how many rules have candidate features?
* how many rules have labeling guidance?
* how many evidence refs have screenshots?
* how many rules only have ambiguous evidence?

This does not change outputs, but it gives strong QA value.

---

## 7. Integrate into `rule_reducer.py`

Task 13 should update Task 5 rule building so that when a `RuleCard` is finalized, it also gets ML-ready fields populated.

### Specifically

After building a `RuleCard`:

* infer `candidate_features`
* distribute example refs
* generate `labeling_guidance`

This is the cleanest place to do it, because Task 5 is where the final rule meaning is assembled.

---

## 8. Integrate into `main.py`

Add an optional ML-prep stage after Task 5 rule cards.

### Conceptual flow

```text
knowledge events
→ evidence linking
→ rule cards
→ ML prep
→ concept graph / exporters
```

Or:

```text
knowledge events
→ evidence linking
→ rule cards
→ concept graph
→ ML prep
→ exporters
```

Either is acceptable, but I would usually place ML prep after rule cards and before exporters.

### Feature flag

Add:

* `enable_ml_prep`

Safe default:

* `False`

When enabled:

* enrich rule cards with ML-ready fields if not already done
* optionally write `ml_manifest.json`

---

## 9. Update `contracts.py`

Add path helpers if they do not already exist:

* `ml_manifest_path(<lesson>)`
* `labeling_manifest_path(<lesson>)`

These should probably live under:

* `output_intermediate/`

because they are structured machine artifacts, not final human-facing outputs.

---

## 10. Optionally surface ML hints in review markdown

This is optional.

For example, review markdown could later include:

```markdown
**Candidate features**
- reaction_count
- price_zone_width

**Labeling guidance**
- Label positive only when multiple reactions occur within the same zone.
```

### Recommendation

* okay in review markdown
* do not include in RAG markdown by default

But Task 13 does not require exporter changes unless easy.

---

# Suggested public functions

In `ml_prep.py`, expose at least:

```python id="1mxtdb"
def infer_candidate_features(rule: RuleCard) -> list[str]:
    ...

def distribute_example_refs_for_ml(rule: RuleCard, evidence_refs: list[EvidenceRef]) -> dict[str, list[str]]:
    ...

def build_labeling_guidance(rule: RuleCard) -> str | None:
    ...

def enrich_rule_card_for_ml(rule: RuleCard, evidence_refs: list[EvidenceRef]) -> RuleCard:
    ...

def build_ml_manifest(
    lesson_id: str,
    rule_cards: RuleCardCollection,
    evidence_index: EvidenceIndex,
) -> tuple[dict, list[dict]]:
    ...

def save_ml_manifest(payload: dict, output_path: Path) -> None:
    ...
```

Optional:

```python id="2tfvxy"
def compute_ml_readiness_coverage(...)
```

---

# Suggested candidate-feature inference logic

This should be heuristic and rule-family-based.

### Example mapping ideas

#### `level`

Possible features:

* `price_zone_width`
* `local_extrema_density`
* `touch_count`

#### `level_recognition`

Possible features:

* `touch_count`
* `extrema_cluster_count`
* `reaction_spacing`

#### `level_rating`

Possible features:

* `reaction_count`
* `reaction_magnitude`
* `zone_width`
* `higher_timeframe_alignment`

#### `break_confirmation`

Possible features:

* `time_beyond_level`
* `close_beyond_level_count`
* `distance_beyond_level`
* `retest_success_flag`

#### `false_breakout`

Possible features:

* `max_distance_beyond_level`
* `time_beyond_level`
* `reversal_speed`
* `return_through_level_flag`
* `failed_acceptance_flag`

#### `trend_break_level`

Possible features:

* `trendline_touch_count`
* `post_break_hold_time`
* `retest_behavior`

This mapping can begin as a simple dictionary / heuristic switch.

---

# Suggested labeling-guidance principles

A good labeling guidance string should:

* mention the positive condition
* mention a key invalidation or exclusion if available
* be short enough for later UI use
* not become a long essay

### Template examples

#### If rule has conditions + invalidation

> Label positive only when {top conditions}. Do not label positive when {top invalidation}.

#### If rule has only rule text

> Label positive only when the setup clearly matches this rule: {rule_text}

#### If rule has ambiguity or low confidence

You may optionally soften it:

> Use manual review when the setup is visually unclear or only partially matches the rule.

---

# Suggested ML manifest structure

Example:

```json id="zvb0w8"
{
  "lesson_id": "lesson_2",
  "rules": [
    {
      "rule_id": "rule_lesson2_level_level_rating_0",
      "concept": "level",
      "subconcept": "level_rating",
      "confidence": "high",
      "confidence_score": 0.88,
      "candidate_features": [
        "reaction_count",
        "reaction_magnitude",
        "price_zone_width"
      ],
      "labeling_guidance": "Label positive only when multiple reactions occur within the same clustered price zone.",
      "positive_example_refs": ["evid_1"],
      "negative_example_refs": ["evid_2"],
      "ambiguous_example_refs": ["evid_3"]
    }
  ],
  "examples": [
    {
      "evidence_id": "evid_1",
      "example_role": "positive_example",
      "frame_ids": ["000120", "000122"],
      "screenshot_paths": [".../frame_000120.jpg"],
      "timestamp_start": "120.0",
      "timestamp_end": "128.0",
      "source_event_ids": ["ke_1", "ke_2"]
    }
  ]
}
```

---

# Tests to implement

Create `tests/test_ml_prep.py`.

## Required tests

### 1. Candidate features inferred

Given a `RuleCard` with concept/subconcept for `level_rating`, verify expected feature names appear.

### 2. Example refs distributed correctly

Given evidence refs with roles:

* positive
* negative/counterexample
* ambiguous
* illustration

verify only the correct ones populate ML buckets.

### 3. Labeling guidance generated

Verify a rule with conditions and invalidation produces useful compact guidance.

### 4. Rule enrichment preserves provenance

When enriching a rule for ML, ensure:

* `source_event_ids` unchanged
* `evidence_refs` unchanged

### 5. ML manifest serialization

Ensure generated manifest writes clean JSON.

### 6. ML readiness coverage

If implemented, verify counts are correct for a small sample.

### 7. Feature-flag-safe integration

When `enable_ml_prep=False`, pipeline behavior remains unchanged.

---

# Important implementation rules

## Do

* keep ML-prep deterministic and lightweight
* use rule cards and evidence refs as the source
* populate only fields clearly supported by data
* preserve provenance and confidence
* keep manifests machine-friendly

## Do not

* do not build a real training pipeline yet
* do not invent numeric values for features
* do not force illustrations into positive examples
* do not use an LLM as the main labeler
* do not break existing structured artifacts

---

# Definition of done

Task 13 is complete when:

1. `pipeline/component2/ml_prep.py` exists
2. `RuleCard` ML-ready fields are populated consistently
3. candidate features can be inferred for major rule families
4. evidence refs are distributed into positive/negative/ambiguous buckets
5. compact labeling guidance can be generated
6. optional ML manifest can be written
7. pipeline can run this behind `enable_ml_prep`
8. tests validate core ML-prep behavior

---

# Copy-paste instruction for the coding agent

```text id="n59h9n"
Implement Task 13 only: Prepare the Data Model for Future ML.

Create:
- pipeline/component2/ml_prep.py
- tests/test_ml_prep.py

Update:
- schemas.py
- rule_reducer.py
- evidence_linker.py
- contracts.py
- main.py
- optionally exporters.py

Goal:
Make structured outputs ML-ready without building a full ML system yet.

Requirements:
1. Ensure RuleCard supports:
   - candidate_features
   - positive_example_refs
   - negative_example_refs
   - ambiguous_example_refs
   - labeling_guidance
2. Implement deterministic candidate-feature inference from concept/subconcept/rule content
3. Map EvidenceRef example roles into ML buckets conservatively
4. Generate compact labeling guidance for each rule
5. Add optional ML manifest generation:
   - output_intermediate/<lesson>.ml_manifest.json
   - optional labeling_manifest.json
6. Preserve provenance and confidence in ML-prep outputs
7. Add feature flag:
   - enable_ml_prep
8. Do not train models or compute numeric features yet
9. Do not force illustrations into positive examples
10. Do not use an LLM as the primary ML labeling engine
```

Yes — below is a **detailed implementation addendum for Task 13**.

**Confidence: High**

The goal is to make Task 13 concrete enough that the coding agent can implement it without guessing how ML-ready fields should be populated.

---

# `pipeline/component2/ml_prep.py`

## 1. Imports and small constants

```python
from __future__ import annotations

from pathlib import Path
from typing import Any
import json
import re

from pipeline.schemas import (
    RuleCard,
    RuleCardCollection,
    EvidenceRef,
    EvidenceIndex,
)
```

I would also define a small feature vocabulary map up front.

```python
FEATURE_HINTS_BY_CONCEPT = {
    "level": [
        "price_zone_width",
        "touch_count",
        "extrema_cluster_count",
    ],
    "level_recognition": [
        "touch_count",
        "extrema_cluster_count",
        "reaction_spacing",
    ],
    "level_rating": [
        "reaction_count",
        "reaction_magnitude",
        "price_zone_width",
        "higher_timeframe_alignment",
    ],
    "break_confirmation": [
        "time_beyond_level",
        "close_beyond_level_count",
        "distance_beyond_level",
        "retest_success_flag",
    ],
    "false_breakout": [
        "max_distance_beyond_level",
        "time_beyond_level",
        "reversal_speed",
        "return_through_level_flag",
        "failed_acceptance_flag",
    ],
    "trend_break_level": [
        "trendline_touch_count",
        "post_break_hold_time",
        "retest_behavior",
    ],
}
```

I would also add a few text cue maps so rules can infer features from wording even if concept/subconcept is sparse.

```python
FEATURE_CUES = {
    "reaction": ["reaction_count", "reaction_magnitude"],
    "multiple reactions": ["reaction_count"],
    "touch": ["touch_count"],
    "zone": ["price_zone_width"],
    "cluster": ["extrema_cluster_count"],
    "hold above": ["time_beyond_level", "close_beyond_level_count"],
    "hold below": ["time_beyond_level", "close_beyond_level_count"],
    "retest": ["retest_success_flag", "retest_behavior"],
    "fails to hold": ["failed_acceptance_flag", "reversal_speed"],
    "returns below": ["return_through_level_flag"],
    "returns through": ["return_through_level_flag"],
    "distance beyond": ["distance_beyond_level", "max_distance_beyond_level"],
}
```

---

## 2. Basic text helpers

```python
def normalize_text(text: str | None) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        value = normalize_text(item)
        if not value:
            continue
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def normalize_feature_name(name: str) -> str:
    text = normalize_text(name).lower()
    text = text.replace("/", "_")
    text = re.sub(r"[^a-z0-9_]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text
```

---

## 3. Concept resolution helper for ML prep

The rule may have both `concept` and `subconcept`. For ML-prep, I would prefer subconcept first, then concept.

```python
def get_rule_family_key(rule: RuleCard) -> str | None:
    if normalize_text(rule.subconcept):
        return normalize_feature_name(rule.subconcept)
    if normalize_text(rule.concept):
        return normalize_feature_name(rule.concept)
    return None
```

---

## 4. Candidate feature inference

This is the first main function.

## Exact behavior

It should combine:

* concept-based defaults
* subconcept-based defaults
* text-cue-based additions
* optional condition/invalidation hints

It should stay conservative.

```python
def infer_candidate_features(rule: RuleCard) -> list[str]:
    features: list[str] = []

    family_key = get_rule_family_key(rule)
    concept_key = normalize_feature_name(rule.concept) if normalize_text(rule.concept) else None
    subconcept_key = normalize_feature_name(rule.subconcept) if normalize_text(rule.subconcept) else None

    for key in [subconcept_key, concept_key, family_key]:
        if key and key in FEATURE_HINTS_BY_CONCEPT:
            features.extend(FEATURE_HINTS_BY_CONCEPT[key])

    all_text_parts = [
        rule.rule_text,
        *(rule.conditions or []),
        *(rule.invalidation or []),
        *(rule.exceptions or []),
        *(rule.comparisons or []),
        *(rule.algorithm_notes or []),
        rule.visual_summary or "",
    ]
    combined = " ".join(normalize_text(x).lower() for x in all_text_parts if normalize_text(x))

    for cue, hinted_features in FEATURE_CUES.items():
        if cue in combined:
            features.extend(hinted_features)

    features = [normalize_feature_name(f) for f in features]
    return dedupe_preserve_order(features)
```

### Example results

For a rule like:

* concept = `level`
* subconcept = `level_rating`
* rule_text = “A level becomes stronger when price reacts to it multiple times.”

The output should likely be:

```python
[
    "reaction_count",
    "reaction_magnitude",
    "price_zone_width",
    "higher_timeframe_alignment",
]
```

---

## 5. Evidence lookup helpers

You need a fast way to map `rule.evidence_refs` to actual `EvidenceRef` objects.

```python
def build_evidence_lookup(evidence_index: EvidenceIndex) -> dict[str, EvidenceRef]:
    return {evidence.evidence_id: evidence for evidence in evidence_index.evidence}


def get_linked_evidence_for_rule(rule: RuleCard, evidence_lookup: dict[str, EvidenceRef]) -> list[EvidenceRef]:
    evidence_refs = rule.evidence_refs or []
    return [evidence_lookup[eid] for eid in evidence_refs if eid in evidence_lookup]
```

---

## 6. Example-role distribution

This is the second main function.

## Exact behavior

Map evidence roles into ML buckets conservatively.

```python
def distribute_example_refs_for_ml(
    rule: RuleCard,
    evidence_refs: list[EvidenceRef],
) -> dict[str, list[str]]:
    positive: list[str] = []
    negative: list[str] = []
    ambiguous: list[str] = []

    for evidence in evidence_refs:
        role = normalize_text(evidence.example_role).lower()

        if role == "positive_example":
            positive.append(evidence.evidence_id)
        elif role in {"negative_example", "counterexample"}:
            negative.append(evidence.evidence_id)
        elif role == "ambiguous_example":
            ambiguous.append(evidence.evidence_id)
        elif role == "illustration":
            # keep out of positive by default
            continue
        else:
            continue

    return {
        "positive_example_refs": dedupe_preserve_order(positive),
        "negative_example_refs": dedupe_preserve_order(negative),
        "ambiguous_example_refs": dedupe_preserve_order(ambiguous),
    }
```

### Important

Do **not** put `illustration` into positives automatically.

That would contaminate later datasets.

---

## 7. Labeling guidance generation

This is the third main function.

I would make it deterministic and template-based.

### Helper functions

```python
def pick_top_items(items: list[str], limit: int = 2) -> list[str]:
    cleaned = [normalize_text(x) for x in items if normalize_text(x)]
    cleaned = dedupe_preserve_order(cleaned)
    return cleaned[:limit]


def sentence_join(items: list[str]) -> str:
    items = [normalize_text(x) for x in items if normalize_text(x)]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return f"{', '.join(items[:-1])}, and {items[-1]}"
```

### Main guidance builder

```python
def build_labeling_guidance(rule: RuleCard) -> str | None:
    rule_text = normalize_text(rule.rule_text)
    conditions = pick_top_items(rule.conditions or [], limit=2)
    invalidation = pick_top_items(rule.invalidation or [], limit=1)

    if conditions and invalidation:
        return (
            f"Label positive only when {sentence_join(conditions)}. "
            f"Do not label positive when {sentence_join(invalidation)}."
        )

    if conditions:
        return f"Label positive only when {sentence_join(conditions)}."

    if invalidation and rule_text:
        return (
            f"Label positive only when the setup clearly matches this rule: {rule_text}. "
            f"Do not label positive when {sentence_join(invalidation)}."
        )

    if rule_text:
        return f"Label positive only when the setup clearly matches this rule: {rule_text}"

    return None
```

### Examples

For:

* conditions = `["multiple reactions occur near the same price zone"]`
* invalidation = `["a single isolated touch"]`

You get:

> Label positive only when multiple reactions occur near the same price zone. Do not label positive when a single isolated touch.

That is exactly the kind of future-labeling instruction you want.

---

## 8. Rule enrichment

This function should produce a new enriched rule, not mutate the original in place unless your codebase prefers mutation.

```python
def enrich_rule_card_for_ml(
    rule: RuleCard,
    evidence_refs: list[EvidenceRef],
) -> RuleCard:
    feature_list = infer_candidate_features(rule)
    example_buckets = distribute_example_refs_for_ml(rule, evidence_refs)
    labeling_guidance = build_labeling_guidance(rule)

    updated = rule.model_copy(update={
        "candidate_features": feature_list,
        "positive_example_refs": example_buckets["positive_example_refs"],
        "negative_example_refs": example_buckets["negative_example_refs"],
        "ambiguous_example_refs": example_buckets["ambiguous_example_refs"],
        "labeling_guidance": labeling_guidance,
    })
    return updated
```

### Important

This must preserve:

* `source_event_ids`
* `evidence_refs`
* confidence
* metadata
* provenance

Only ML-related fields should change.

---

## 9. Whole-collection enrichment

This is the main collection-level function you want for integration into `main.py` or `rule_reducer.py`.

```python
def enrich_rule_card_collection_for_ml(
    rules: RuleCardCollection,
    evidence_index: EvidenceIndex,
) -> RuleCardCollection:
    evidence_lookup = build_evidence_lookup(evidence_index)
    enriched_rules: list[RuleCard] = []

    for rule in rules.rules:
        linked_evidence = get_linked_evidence_for_rule(rule, evidence_lookup)
        enriched_rules.append(enrich_rule_card_for_ml(rule, linked_evidence))

    return RuleCardCollection(
        schema_version=rules.schema_version,
        lesson_id=rules.lesson_id,
        rules=enriched_rules,
    )
```

---

## 10. ML manifest builder

This should produce a clean machine-readable export, not a debug dump.

### Main function

```python
def build_ml_manifest(
    lesson_id: str,
    rule_cards: RuleCardCollection,
    evidence_index: EvidenceIndex,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    evidence_lookup = build_evidence_lookup(evidence_index)

    rules_payload: list[dict[str, Any]] = []
    examples_payload: list[dict[str, Any]] = []
    debug_rows: list[dict[str, Any]] = []

    used_evidence_ids: set[str] = set()

    for rule in rule_cards.rules:
        linked_evidence = get_linked_evidence_for_rule(rule, evidence_lookup)
        used_evidence_ids.update(e.evidence_id for e in linked_evidence)

        rules_payload.append({
            "rule_id": rule.rule_id,
            "concept": rule.concept,
            "subconcept": rule.subconcept,
            "confidence": rule.confidence,
            "confidence_score": rule.confidence_score,
            "candidate_features": rule.candidate_features or [],
            "labeling_guidance": rule.labeling_guidance,
            "positive_example_refs": rule.positive_example_refs or [],
            "negative_example_refs": rule.negative_example_refs or [],
            "ambiguous_example_refs": rule.ambiguous_example_refs or [],
            "source_event_ids": rule.source_event_ids or [],
        })

        debug_rows.append({
            "rule_id": rule.rule_id,
            "linked_evidence_count": len(linked_evidence),
            "positive_count": len(rule.positive_example_refs or []),
            "negative_count": len(rule.negative_example_refs or []),
            "ambiguous_count": len(rule.ambiguous_example_refs or []),
        })

    for evidence_id in sorted(used_evidence_ids):
        evidence = evidence_lookup[evidence_id]
        examples_payload.append({
            "evidence_id": evidence.evidence_id,
            "example_role": evidence.example_role,
            "frame_ids": evidence.frame_ids or [],
            "screenshot_paths": evidence.screenshot_paths or [],
            "timestamp_start": evidence.timestamp_start,
            "timestamp_end": evidence.timestamp_end,
            "source_event_ids": evidence.source_event_ids or [],
        })

    manifest = {
        "lesson_id": lesson_id,
        "rules": rules_payload,
        "examples": examples_payload,
    }
    return manifest, debug_rows
```

---

## 11. Optional labeling manifest

If you want a second manifest more tailored to a future manual-labeling tool, you can generate a narrower version.

```python
def build_labeling_manifest(
    lesson_id: str,
    rule_cards: RuleCardCollection,
    evidence_index: EvidenceIndex,
) -> dict[str, Any]:
    evidence_lookup = build_evidence_lookup(evidence_index)

    tasks: list[dict[str, Any]] = []

    for rule in rule_cards.rules:
        for evidence_id in (
            (rule.positive_example_refs or [])
            + (rule.negative_example_refs or [])
            + (rule.ambiguous_example_refs or [])
        ):
            if evidence_id not in evidence_lookup:
                continue
            evidence = evidence_lookup[evidence_id]
            tasks.append({
                "rule_id": rule.rule_id,
                "concept": rule.concept,
                "subconcept": rule.subconcept,
                "expected_role": evidence.example_role,
                "labeling_guidance": rule.labeling_guidance,
                "evidence_id": evidence.evidence_id,
                "frame_ids": evidence.frame_ids or [],
                "screenshot_paths": evidence.screenshot_paths or [],
            })

    return {
        "lesson_id": lesson_id,
        "tasks": tasks,
    }
```

This is optional for V1, but useful.

---

## 12. ML readiness coverage

This is very useful and cheap to add.

```python
def compute_ml_readiness_coverage(
    rule_cards: RuleCardCollection,
    evidence_index: EvidenceIndex,
) -> dict[str, int]:
    rules = rule_cards.rules
    evidence_lookup = build_evidence_lookup(evidence_index)

    return {
        "rules_total": len(rules),
        "rules_with_candidate_features": sum(1 for r in rules if (r.candidate_features or [])),
        "rules_with_labeling_guidance": sum(1 for r in rules if normalize_text(r.labeling_guidance)),
        "rules_with_positive_examples": sum(1 for r in rules if (r.positive_example_refs or [])),
        "rules_with_negative_examples": sum(1 for r in rules if (r.negative_example_refs or [])),
        "rules_with_ambiguous_examples": sum(1 for r in rules if (r.ambiguous_example_refs or [])),
        "evidence_total": len(evidence_index.evidence),
        "evidence_with_screenshots": sum(1 for e in evidence_index.evidence if (e.screenshot_paths or [])),
        "evidence_with_frame_ids": sum(1 for e in evidence_index.evidence if (e.frame_ids or [])),
    }
```

This can go to:

* debug output
* manifest metadata
* optional review report

---

## 13. Save helpers

```python
def save_ml_manifest(payload: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
```

If Task 9’s atomic write helpers exist, use them instead.

---

# Integration by file

## `rule_reducer.py`

You have two options.

### Option A — enrich immediately in rule creation

After `RuleCard` is created, call ML enrichment.

### Option B — enrich as a separate post-step

I recommend **Option B**, because it keeps Task 5 focused and makes Task 13 optional via feature flag.

So in `main.py`:

```python
if feature_flags.enable_rule_cards:
    rule_cards, rule_debug = build_rule_cards(...)

if feature_flags.enable_ml_prep:
    evidence_index = load_evidence_index(paths.evidence_index_path(lesson_name))
    rule_cards = enrich_rule_card_collection_for_ml(rule_cards, evidence_index)
    save_rule_cards(rule_cards, paths.rule_cards_path(lesson_name))
```

That way:

* Task 5 still owns normalization
* Task 13 owns ML enrichment

---

## `contracts.py`

Add:

```python
def ml_manifest_path(self, lesson_name: str) -> Path:
    return self.output_intermediate_dir / f"{lesson_name}.ml_manifest.json"

def labeling_manifest_path(self, lesson_name: str) -> Path:
    return self.output_intermediate_dir / f"{lesson_name}.labeling_manifest.json"
```

---

## `main.py`

### Suggested integration block

```python
if feature_flags.enable_ml_prep:
    if require_artifact(
        paths.rule_cards_path(lesson_name),
        "step13_ml_prep",
        "Generate rule_cards.json first",
    ) and require_artifact(
        paths.evidence_index_path(lesson_name),
        "step13_ml_prep",
        "Generate evidence_index.json first",
    ):
        rule_cards = load_rule_cards(paths.rule_cards_path(lesson_name))
        evidence_index = load_evidence_index(paths.evidence_index_path(lesson_name))

        enriched_rule_cards = enrich_rule_card_collection_for_ml(rule_cards, evidence_index)
        save_rule_cards(enriched_rule_cards, paths.rule_cards_path(lesson_name))

        ml_manifest, ml_debug = build_ml_manifest(
            lesson_id=lesson_name,
            rule_cards=enriched_rule_cards,
            evidence_index=evidence_index,
        )
        save_ml_manifest(ml_manifest, paths.ml_manifest_path(lesson_name))
```

Optional:

* also save a labeling manifest

---

# Tests

## `tests/test_ml_prep.py`

### Test 1 — candidate features inferred from subconcept

```python
def test_infer_candidate_features_level_rating():
    rule = RuleCard(
        rule_id="r1",
        lesson_id="lesson1",
        concept="level",
        subconcept="level_rating",
        rule_text="A level becomes stronger when price reacts to it multiple times.",
    )

    features = infer_candidate_features(rule)

    assert "reaction_count" in features
    assert "reaction_magnitude" in features
    assert "price_zone_width" in features
```

### Test 2 — example ref distribution

```python
def test_distribute_example_refs_for_ml():
    rule = RuleCard(
        rule_id="r1",
        lesson_id="lesson1",
        concept="level",
        rule_text="Rule",
    )
    evidence = [
        EvidenceRef(evidence_id="e1", lesson_id="lesson1", example_role="positive_example"),
        EvidenceRef(evidence_id="e2", lesson_id="lesson1", example_role="counterexample"),
        EvidenceRef(evidence_id="e3", lesson_id="lesson1", example_role="ambiguous_example"),
        EvidenceRef(evidence_id="e4", lesson_id="lesson1", example_role="illustration"),
    ]

    buckets = distribute_example_refs_for_ml(rule, evidence)

    assert buckets["positive_example_refs"] == ["e1"]
    assert buckets["negative_example_refs"] == ["e2"]
    assert buckets["ambiguous_example_refs"] == ["e3"]
```

### Test 3 — labeling guidance generated

```python
def test_build_labeling_guidance():
    rule = RuleCard(
        rule_id="r1",
        lesson_id="lesson1",
        concept="false_breakout",
        rule_text="A false breakout fails to hold beyond the level.",
        conditions=["price moves beyond the level", "price fails to hold beyond it"],
        invalidation=["price holds beyond the level"],
    )

    guidance = build_labeling_guidance(rule)

    assert guidance is not None
    assert "Label positive only when" in guidance
    assert "Do not label positive when" in guidance
```

### Test 4 — enrichment preserves provenance fields

```python
def test_enrich_rule_card_for_ml_preserves_provenance():
    rule = RuleCard(
        rule_id="r1",
        lesson_id="lesson1",
        concept="level",
        rule_text="A level matters.",
        evidence_refs=["e1"],
        source_event_ids=["ke1"],
        confidence="high",
        confidence_score=0.8,
    )
    evidence = [
        EvidenceRef(evidence_id="e1", lesson_id="lesson1", example_role="positive_example"),
    ]

    enriched = enrich_rule_card_for_ml(rule, evidence)

    assert enriched.source_event_ids == ["ke1"]
    assert enriched.evidence_refs == ["e1"]
    assert enriched.confidence == "high"
    assert "candidate_features" in enriched.model_dump()
```

### Test 5 — ML manifest serialization

```python
def test_build_ml_manifest():
    rule = RuleCard(
        rule_id="r1",
        lesson_id="lesson1",
        concept="level",
        rule_text="A level matters.",
        candidate_features=["touch_count"],
        positive_example_refs=["e1"],
        evidence_refs=["e1"],
        source_event_ids=["ke1"],
    )
    evidence = EvidenceRef(
        evidence_id="e1",
        lesson_id="lesson1",
        example_role="positive_example",
        frame_ids=["001"],
        screenshot_paths=["/tmp/frame_001.jpg"],
        source_event_ids=["ke1"],
    )

    manifest, debug_rows = build_ml_manifest(
        lesson_id="lesson1",
        rule_cards=RuleCardCollection(lesson_id="lesson1", rules=[rule]),
        evidence_index=EvidenceIndex(lesson_id="lesson1", evidence=[evidence]),
    )

    assert manifest["lesson_id"] == "lesson1"
    assert len(manifest["rules"]) == 1
    assert len(manifest["examples"]) == 1
    assert debug_rows
```

---

# One extra sentence I would explicitly add to Task 13

```text
ML-ready fields must be derived conservatively from structured rule and evidence data; absence of a positive example or candidate feature should leave the field empty rather than forcing a speculative value.
```

That protects the future dataset quality.

---

# My recommendation

Yes — for Task 13, I would absolutely include this level of detail.

The risk in Task 13 is not schema changes.
The risk is quietly producing ML metadata that looks precise but is actually speculative.

These implementations keep it:

* deterministic
* conservative
* provenance-preserving
* useful for future algorithm and ML work



