Yes — here is **Task 10** formulated in the same style.

**Confidence: High**

---

# Task 10 — Add Confidence Scoring

## Goal

Standardize **confidence scoring** across the structured pipeline so that:

* each `KnowledgeEvent` gets a consistent confidence label and score
* each `RuleCard` gets a consistent confidence label and score
* confidence is based on **deterministic, explainable heuristics**
* confidence can later be used for:

  * QA and review
  * filtering weak rules out of RAG
  * prioritizing manual validation
  * future ML dataset selection

This task must **not** replace the extracted content.
It adds a **reliability layer** on top of structured artifacts.

---

# Why this task exists

By Task 5, the pipeline already produces:

* `knowledge_events.json`
* `evidence_index.json`
* `rule_cards.json`

But not all extracted knowledge is equally strong.

Some rules are:

* clearly and explicitly stated by the instructor
* well-supported by evidence
* easy to map to a clean concept

Others are:

* inferred from examples
* weakly anchored
* ambiguous
* supported by little or conflicting evidence

Task 10 makes that difference explicit.

---

# Deliverables

Create:

* `pipeline/component2/confidence.py`
* `tests/test_confidence.py`

Update:

* `knowledge_builder.py`
* `rule_reducer.py`
* optionally `exporters.py`

Do **not** add a new top-level stage in `main.py`.
This should be a **shared scoring module** used by earlier stages.

---

# Scope

Task 10 should cover confidence scoring for:

## 1. `KnowledgeEvent`

Scored during or right after Step 3 extraction.

## 2. `RuleCard`

Scored during Task 5 rule normalization / merge.

Optional later:

* evidence-level confidence
* concept-level confidence

But those are not required for Task 10.

---

# Core design principles

## 1. Deterministic first

Confidence should come from explicit heuristics, not from an LLM opinion.

## 2. Confidence must be explainable

Every score should be traceable to components like:

* explicitness
* concept clarity
* evidence support
* ambiguity
* structural consistency

## 3. Use both label and numeric score

Store:

* `confidence`: `"low" | "medium" | "high"`
* `confidence_score`: float in `[0.0, 1.0]`

## 4. Penalize ambiguity

If a statement is uncertain, inferred, vague, or weakly linked, confidence should drop.

## 5. Confidence is not truth

It is a **pipeline reliability score**, not a claim of market validity.

---

# Functional requirements

## 1. Create `pipeline/component2/confidence.py`

This module is the shared confidence engine.

It should contain:

* config values / weights
* event scoring
* rule-card scoring
* label conversion
* optional debug breakdown helpers

---

## 2. Add a confidence config model

Create a small internal config.

Suggested structure:

```python id="1"}
from dataclasses import dataclass


@dataclass(frozen=True)
class ConfidenceConfig:
    event_explicit_rule_weight: float = 0.25
    event_definition_weight: float = 0.20
    event_concept_present_weight: float = 0.15
    event_subconcept_present_weight: float = 0.10
    event_section_present_weight: float = 0.05
    event_visual_support_weight: float = 0.10
    event_ambiguity_penalty: float = 0.20
    event_example_only_penalty: float = 0.10

    rule_primary_statement_weight: float = 0.25
    rule_concept_present_weight: float = 0.10
    rule_subconcept_present_weight: float = 0.10
    rule_condition_support_weight: float = 0.10
    rule_invalidation_support_weight: float = 0.10
    rule_evidence_support_weight: float = 0.15
    rule_multi_event_agreement_weight: float = 0.10
    rule_ambiguity_penalty: float = 0.20
    rule_example_only_penalty: float = 0.10

    high_threshold: float = 0.75
    medium_threshold: float = 0.45
```

### Notes

* weights can be tuned later
* keep V1 simple and interpretable
* do not overfit

---

## 3. Add score normalization helpers

Implement:

```python id="2"}
def clamp_score(value: float) -> float:
    ...

def score_to_label(score: float, cfg: ConfidenceConfig) -> str:
    ...
```

### Behavior

* clamp to `[0.0, 1.0]`
* convert to:

  * `high` if `score >= high_threshold`
  * `medium` if `score >= medium_threshold`
  * otherwise `low`

---

## 4. Add `KnowledgeEvent` scoring

Implement:

```python id="3"}
def score_knowledge_event(
    event,
    cfg: ConfidenceConfig,
) -> tuple[str, float, dict]:
    ...
```

Return:

* confidence label
* confidence score
* breakdown dict

### Scoring signals for `KnowledgeEvent`

#### Positive signals

* event type is `rule_statement` or `definition`
* concept present
* subconcept present
* section/subsection present
* event has candidate visual support in metadata
* wording is explicit and short
* no ambiguity notes

#### Negative signals

* ambiguity notes present
* concept missing
* event appears inferred from example only
* wording is vague
* event type is `example` without rule/definition support

### Heuristic guidance

#### Stronger event types

* `rule_statement`
* `definition`

#### Medium-strength event types

* `condition`
* `invalidation`
* `exception`
* `algorithm_hint`

#### Lower-confidence by default

* `example`
* `comparison`
* `warning`
* `observation`

These lower-confidence event types are still valuable, but usually are not primary rules.

---

## 5. Add event-text explicitness helpers

Implement small text heuristics:

```python id="4"}
def is_explicit_rule_like(text: str) -> bool:
    ...

def is_definition_like(text: str) -> bool:
    ...

def is_vague_statement(text: str) -> bool:
    ...

def looks_example_only(text: str, event_type: str) -> bool:
    ...
```

### Example positive markers

* “is”
* “means”
* “becomes stronger when”
* “is valid if”
* “is invalid if”
* “should”
* “must”

### Example vague markers

* “looks like”
* “maybe”
* “seems”
* “can sometimes”
* “kind of”
* “possibly”

### Important

Keep these helpers light and heuristic, not linguistic overkill.

---

## 6. Add evidence-support detection for events

Implement:

```python id="5"}
def event_has_visual_support(event) -> bool:
    ...
```

### Rule

Return true if:

* `event.evidence_refs` is non-empty
  or
* metadata contains candidate visual frame keys
  or
* metadata contains non-empty candidate visual types

This helps boost confidence modestly, not overwhelmingly.

---

## 7. Add `RuleCard` scoring

Implement:

```python id="6"}
def score_rule_card(
    rule,
    *,
    linked_events: list,
    linked_evidence: list,
    cfg: ConfidenceConfig,
) -> tuple[str, float, dict]:
    ...
```

Return:

* confidence label
* confidence score
* breakdown dict

### Scoring signals for `RuleCard`

#### Positive signals

* clear canonical `rule_text`
* concept present
* subconcept present
* multiple supporting source events
* both conditions and invalidation present
* evidence refs linked
* source events agree on the same idea
* visual summary exists
* algorithm notes exist and align

#### Negative signals

* rule came only from examples
* no strong primary statement
* concept missing
* strong ambiguity in source events
* evidence weak or missing
* merged candidate was borderline or heavily split

---

## 8. Add source-event agreement scoring

Implement:

```python id="7"}
def score_event_agreement(events: list) -> float:
    ...
```

### V1 behavior

Use a simple heuristic:

* if most source events share same concept/subconcept → higher score
* if multiple primary statements are very similar → higher score
* if source events conflict in subconcept or wording → lower score

Return a float in `[0,1]`.

This feeds into rule confidence.

---

## 9. Add rule-primary-statement strength helper

Implement:

```python id="8"}
def has_strong_primary_statement(rule) -> bool:
    ...
```

### Rule

A rule has a strong primary statement if:

* `rule.rule_text` is non-empty
* length is reasonable
* it looks explicit rather than vague
* it is not just copied from an example description

This should strongly affect rule confidence.

---

## 10. Add a compact breakdown format

Each scorer should optionally return a breakdown dict like:

```json id="9"
{
  "explicit_rule": 0.25,
  "concept_present": 0.15,
  "subconcept_present": 0.10,
  "section_present": 0.05,
  "visual_support": 0.10,
  "ambiguity_penalty": -0.20,
  "total": 0.45
}
```

This breakdown should be used:

* in debug artifacts
* in tests
* optionally in review markdown later

But do **not** put the full breakdown into the main structured JSON unless you explicitly want that.

### Recommended place

Store breakdown only in debug output or in metadata under a compact key if needed.

---

## 11. Integrate into Step 3 (`knowledge_builder.py`)

Update Task 3 implementation so that after creating each `KnowledgeEvent`:

```python id="10"}
label, score, breakdown = score_knowledge_event(event, cfg)
event.confidence = label
event.confidence_score = score
```

### Optional

Add breakdown to debug rows only:

* `knowledge_debug.json`

### Important

Do not store huge scoring blobs in every final event unless needed.

---

## 12. Integrate into Step 5 (`rule_reducer.py`)

Update Task 5 implementation so that after building each `RuleCard`:

```python id="11"}
label, score, breakdown = score_rule_card(
    rule,
    linked_events=source_events,
    linked_evidence=linked_evidence,
    cfg=cfg,
)
rule.confidence = label
rule.confidence_score = score
```

### Optional

Write breakdown into:

* `rule_debug.json`

This is the best place for rule-level breakdowns.

---

## 13. Add config defaults in `config.py`

Task 10 should add config defaults for thresholds and maybe allow limited tuning.

Suggested defaults:

* `confidence_high_threshold = 0.75`
* `confidence_medium_threshold = 0.45`

Optional:

* expose the weights too, but only if your config system already supports that cleanly

### Recommendation

Expose thresholds in config first.
Keep weights in code for V1 unless you truly need runtime tuning.

---

## 14. Optionally surface confidence in review markdown

Task 10 does not require exporter changes, but you may optionally include:

* `Confidence: high (0.88)`

in `review_markdown.md`

I would recommend:

* include in **review markdown**
* omit in **RAG markdown** by default

Unless you explicitly want confidence available to retrieval.

---

## 15. Do not use confidence as a hard filter yet

Task 10 should **compute** confidence, not yet enforce hard filtering.

### Allowed

* annotate outputs
* use in manifests/debug
* support future filtering

### Not allowed yet

* automatically drop low-confidence rules from JSON
* automatically hide them from exports
* delete evidence because score is low

That should be a later policy decision.

---

# Suggested implementation skeleton

## `pipeline/component2/confidence.py`

```python id="12"}
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import re


@dataclass(frozen=True)
class ConfidenceConfig:
    event_explicit_rule_weight: float = 0.25
    event_definition_weight: float = 0.20
    event_concept_present_weight: float = 0.15
    event_subconcept_present_weight: float = 0.10
    event_section_present_weight: float = 0.05
    event_visual_support_weight: float = 0.10
    event_ambiguity_penalty: float = 0.20
    event_example_only_penalty: float = 0.10

    rule_primary_statement_weight: float = 0.25
    rule_concept_present_weight: float = 0.10
    rule_subconcept_present_weight: float = 0.10
    rule_condition_support_weight: float = 0.10
    rule_invalidation_support_weight: float = 0.10
    rule_evidence_support_weight: float = 0.15
    rule_multi_event_agreement_weight: float = 0.10
    rule_ambiguity_penalty: float = 0.20
    rule_example_only_penalty: float = 0.10

    high_threshold: float = 0.75
    medium_threshold: float = 0.45


def clamp_score(value: float) -> float:
    return max(0.0, min(1.0, value))


def score_to_label(score: float, cfg: ConfidenceConfig) -> str:
    if score >= cfg.high_threshold:
        return "high"
    if score >= cfg.medium_threshold:
        return "medium"
    return "low"
```

Then add the helpers and scorers below it.

---

# Exact scorer behavior I would recommend

## `score_knowledge_event(...)`

```python id="13"}
def score_knowledge_event(event, cfg: ConfidenceConfig) -> tuple[str, float, dict]:
    score = 0.0
    breakdown: dict[str, float] = {}

    text = (event.normalized_text or "").strip()

    if event.event_type == "rule_statement" and is_explicit_rule_like(text):
        score += cfg.event_explicit_rule_weight
        breakdown["explicit_rule"] = cfg.event_explicit_rule_weight

    if event.event_type == "definition" and is_definition_like(text):
        score += cfg.event_definition_weight
        breakdown["definition_like"] = cfg.event_definition_weight

    if event.concept:
        score += cfg.event_concept_present_weight
        breakdown["concept_present"] = cfg.event_concept_present_weight

    if event.subconcept:
        score += cfg.event_subconcept_present_weight
        breakdown["subconcept_present"] = cfg.event_subconcept_present_weight

    if getattr(event, "section", None):
        score += cfg.event_section_present_weight
        breakdown["section_present"] = cfg.event_section_present_weight

    if event_has_visual_support(event):
        score += cfg.event_visual_support_weight
        breakdown["visual_support"] = cfg.event_visual_support_weight

    ambiguity_count = len(getattr(event, "ambiguity_notes", []) or [])
    if ambiguity_count:
        penalty = min(cfg.event_ambiguity_penalty, 0.05 * ambiguity_count + 0.05)
        score -= penalty
        breakdown["ambiguity_penalty"] = -penalty

    if looks_example_only(text, event.event_type):
        score -= cfg.event_example_only_penalty
        breakdown["example_only_penalty"] = -cfg.event_example_only_penalty

    if is_vague_statement(text):
        score -= 0.10
        breakdown["vague_penalty"] = -0.10

    score = clamp_score(score)
    breakdown["total"] = score
    return score_to_label(score, cfg), score, breakdown
```

---

## `score_rule_card(...)`

```python id="14"}
def score_rule_card(
    rule,
    *,
    linked_events: list,
    linked_evidence: list,
    cfg: ConfidenceConfig,
) -> tuple[str, float, dict]:
    score = 0.0
    breakdown: dict[str, float] = {}

    if has_strong_primary_statement(rule):
        score += cfg.rule_primary_statement_weight
        breakdown["primary_statement"] = cfg.rule_primary_statement_weight

    if rule.concept:
        score += cfg.rule_concept_present_weight
        breakdown["concept_present"] = cfg.rule_concept_present_weight

    if rule.subconcept:
        score += cfg.rule_subconcept_present_weight
        breakdown["subconcept_present"] = cfg.rule_subconcept_present_weight

    if rule.conditions:
        score += cfg.rule_condition_support_weight
        breakdown["conditions_present"] = cfg.rule_condition_support_weight

    if rule.invalidation:
        score += cfg.rule_invalidation_support_weight
        breakdown["invalidation_present"] = cfg.rule_invalidation_support_weight

    if linked_evidence:
        score += cfg.rule_evidence_support_weight
        breakdown["evidence_support"] = cfg.rule_evidence_support_weight

    agreement = score_event_agreement(linked_events)
    agreement_component = cfg.rule_multi_event_agreement_weight * agreement
    score += agreement_component
    breakdown["multi_event_agreement"] = agreement_component

    ambiguity_count = sum(len(getattr(ev, "ambiguity_notes", []) or []) for ev in linked_events)
    if ambiguity_count:
        penalty = min(cfg.rule_ambiguity_penalty, 0.03 * ambiguity_count + 0.05)
        score -= penalty
        breakdown["ambiguity_penalty"] = -penalty

    if linked_events and all(ev.event_type == "example" for ev in linked_events):
        score -= cfg.rule_example_only_penalty
        breakdown["example_only_penalty"] = -cfg.rule_example_only_penalty

    score = clamp_score(score)
    breakdown["total"] = score
    return score_to_label(score, cfg), score, breakdown
```

---

# Tests I would add exactly

## `tests/test_confidence.py`

### Test 1 — strong event scores higher than weak event

* explicit `rule_statement`
* concept/subconcept present
* no ambiguity
* visual support present

should score above:

* vague `example`
* missing concept
* ambiguity present

### Test 2 — definition gets medium/high

A clean `definition` with concept should not score low.

### Test 3 — ambiguity lowers score

Same event with added ambiguity notes should score lower.

### Test 4 — rule with evidence and support scores higher

A rule with:

* primary statement
* conditions
* invalidation
* evidence
* agreeing source events

should beat one with only weak example-derived content.

### Test 5 — score label thresholds

Check:

* `0.80 -> high`
* `0.50 -> medium`
* `0.20 -> low`

### Test 6 — clamp works

Scores above 1.0 and below 0.0 should clamp.

---

# My recommendation

Yes — for Task 10, I would **definitely** add these exact method details.

Because otherwise “add confidence scoring” becomes too vague, and the coding agent might:

* scatter scoring logic across multiple files
* use inconsistent heuristics between events and rules
* overstore debug breakdowns
* make confidence depend on unstable LLM wording

This addendum keeps it deterministic and clean.

If you want, next I can do the same for **Task 11**.


Yes — a few important things.

**Confidence: High**

For Task 10, I would add these points so the coding agent does not implement confidence in a way that becomes noisy or hard to trust.

## 1. Confidence breakdowns should go to debug, not the main artifacts

We already said this partly, but I would make it explicit.

In final JSON:

* keep `confidence`
* keep `confidence_score`

In debug JSON:

* keep full score breakdown

That prevents `knowledge_events.json` and `rule_cards.json` from becoming cluttered.

## 2. Confidence must be recomputed after merging

For `RuleCard`, confidence should be computed only after:

* candidate grouping
* duplicate merge
* over-broad splitting
* evidence attachment

Not before.

Otherwise the final score may reflect a pre-merge candidate shape that no longer exists.

## 3. Low confidence should never block output in Task 10

This is important enough to say explicitly.

Task 10 should:

* annotate
* not filter
* not skip writing
* not delete low-confidence rules

Filtering can come later as a policy layer.

## 4. Keep thresholds centralized

Do not hardcode thresholds in:

* `knowledge_builder.py`
* `rule_reducer.py`
* `exporters.py`

All thresholds should come from:

* `confidence.py`
* and optionally `config.py`

That avoids drift.

## 5. Confidence should be stable for the same input

The same input should produce the same score.

So avoid:

* randomization
* dependence on LLM wording beyond already extracted structured fields
* unstable ordering effects

This matters for regression testing.

## 6. Add a “missing-data is neutral, not catastrophic” rule

If something is absent, do not automatically crush confidence unless the absence is truly meaningful.

Examples:

* no visual evidence does not mean the rule is bad
* no subconcept does not mean the rule is useless
* no invalidation does not mean the rule is low-confidence by default

Absence should usually reduce the upside, not force a heavy penalty.

## 7. Penalize ambiguity only once per factor

Do not accidentally double-penalize the same weakness.

For example, if a rule:

* has ambiguity notes
* also came from example-only events

make sure those penalties are deliberate and bounded.

I would explicitly cap total penalties.

## 8. Add score component names that are stable

Use fixed breakdown keys like:

* `explicit_rule`
* `definition_like`
* `concept_present`
* `subconcept_present`
* `visual_support`
* `ambiguity_penalty`
* `example_only_penalty`
* `total`

That makes debug files easier to compare across runs.

## 9. Add regression fixtures

Task 10 should include a few small frozen fixtures:

* strong rule event
* weak ambiguous example event
* strong rule card with evidence
* weak rule card inferred mostly from examples

That gives you stable tests when heuristics change.

## 10. Decide now whether exporters show confidence

I recommend:

* show confidence in `review_markdown.md`
* do not show confidence in `rag_ready.md` by default

That should be stated in Task 10 so the agent does not guess.

## 11. Add one safety cap

I would explicitly say:

* no event confidence score may exceed `0.95`
* no rule confidence score may exceed `0.95`

This keeps room for future manual validation layers and avoids the false impression of certainty.

## 12. Treat confidence as pipeline quality, not trading truth

I would say this plainly in the task text.

A high-confidence rule means:

* the pipeline extracted and normalized it cleanly

It does **not** mean:

* the rule is objectively profitable or universally correct in the market

That distinction is important for future ML work.

---

## One sentence I would add to Task 10

You can paste this directly:

```text
Confidence in this task measures extraction and normalization reliability, not market validity; low-confidence items must still be preserved, and full scoring breakdowns should go to debug artifacts rather than the main structured outputs.
```

