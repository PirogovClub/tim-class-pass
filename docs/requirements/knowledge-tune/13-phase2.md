Below is an **exact coding task** for the agent based on the current lesson result.

---

# Task: tighten positive-example promotion and labeling-task generation

## Why this patch is needed

The pipeline is now **structurally healthy**:

* `knowledge_events.json` is good
* `rule_cards.json` is clean
* `evidence_index.json` has intact backlinks
* `ml_manifest.json` is mostly conservative
* `labeling_manifest.json` is small and linked correctly

But in the current lesson there is still a **semantic over-promotion** problem:

### Current suspicious evidence

#### Keep under review, likely valid

* `evidence_id = evcand_2025-09-29-sviatoslav-chornyi_10_35`
* timestamp `22:44`
* summary:

  * `"New chart displayed with annotations.. concepts: atr_values, entry_values, level"`
* current role:

  * `positive_example`
* linked to 3 rules

This one is **plausibly valid**, because it is a chart with annotations and concrete setup terms.

#### Likely wrong, should downgrade

* `evidence_id = evcand_2025-09-29-sviatoslav-chornyi_12_43`
* timestamp `28:10`
* summary:

  * `"new slide displayed with text 'Ответы на вопросы'. concepts: abstract_teaching_example, atr_values, entry_values"`
* current role:

  * `positive_example`
* linked to 1 rule
* currently creates 1 ML example and 1 labeling task chain contribution

This one should **not** be a `positive_example`.
It looks like a **generic Q&A / teaching slide**, not concrete visual proof of a trading setup.

---

# Goal

Make the system **more conservative** when promoting evidence from `illustration` to `positive_example`.

## Desired behavior after patch

* generic teaching slides remain `illustration`
* Q&A / title / intro / summary / concept slides do not become ML examples
* `ml_manifest.examples` should only contain truly concrete examples
* `labeling_manifest.tasks` should only be created from truly concrete ML-eligible evidence

For this lesson specifically, the expected result is:

* the `28:10` evidence row should downgrade from `positive_example` to `illustration`
* `ml_manifest.examples` should drop from **2** to **1 or 0**
* `labeling_manifest.tasks` should drop from **4** to **3 or fewer**
* no task should be based on a Q&A slide

---

# Do not change

Do **not** do any of the following:

* do not redesign the whole evidence pipeline
* do not change the successful Phase 2A provenance logic
* do not change rule export behavior
* do not reopen `KnowledgeEvent.source_event_ids`
* do not broaden ML eligibility
* do not invent new schemas unless a tiny metadata/debug field is needed
* do not promote more evidence to positive roles

This patch must be **strictly conservative**.

---

# Where to patch

Search first:

```bash
rg -n "infer_example_role|example_role|positive_example|illustration|is_evidence_ml_eligible|build_labeling_tasks|build_ml_examples|compact_visual_summary" .
```

Likely modules are around:

* evidence role inference builder
* ML manifest builder
* labeling manifest builder

Patch the **active code path only**.

---

# Required logic change

## High-level rule

An evidence row may be promoted to `positive_example` only if it has **strong concrete visual evidence**.

If it looks like a generic teaching slide, it must remain `illustration`.

---

# Part 1: add strict visual-promotion gating

Create a helper like this in the evidence builder path.

```python
import re

GENERIC_SLIDE_PATTERNS = [
    r"\bq&a\b",
    r"\bqa\b",
    r"\bquestions?\b",
    r"\banswers?\b",
    r"\bответы?\b",
    r"\bвопросы?\b",
    r"\bsummary\b",
    r"\bagenda\b",
    r"\bintro\b",
    r"\bintroduction\b",
    r"\btitle\s*slide\b",
    r"\bnew slide displayed\b",
    r"\babstract_teaching_example\b",
    r"\bconcept explanation\b",
]

CONCRETE_MARKET_VISUAL_PATTERNS = [
    r"\bchart\b",
    r"\bcandles?\b",
    r"\bannotated\b",
    r"\blevel\b",
    r"\bentry\b",
    r"\batr\b",
    r"\bbreakout\b",
    r"\bfalse breakout\b",
    r"\bconsolidation\b",
    r"\btouch(es)?\b",
    r"\bprice\b",
    r"\bwick\b",
    r"\bbar(s)?\b",
    r"\bstop[- ]?loss\b",
    r"\breward[- ]?to[- ]?risk\b",
]
```

Add text normalization:

```python
def _norm_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())
```

Add helper:

```python
def is_generic_teaching_visual(summary: str | None) -> bool:
    text = _norm_text(summary)
    if not text:
        return True

    for pat in GENERIC_SLIDE_PATTERNS:
        if re.search(pat, text, flags=re.IGNORECASE):
            return True

    return False
```

Add concrete evidence helper:

```python
def has_concrete_market_visual_signals(summary: str | None) -> bool:
    text = _norm_text(summary)
    if not text:
        return False

    hits = 0
    for pat in CONCRETE_MARKET_VISUAL_PATTERNS:
        if re.search(pat, text, flags=re.IGNORECASE):
            hits += 1

    return hits >= 2
```

---

# Part 2: require strong promotion conditions

Add a promotion gate before assigning `positive_example`.

## Required rule

Only allow `positive_example` if **all** of the following are true:

1. visual summary is **not** generic teaching content
2. visual summary contains **concrete market/setup signals**
3. evidence is linked to at least one rule
4. evidence is linked to at least one source event
5. optional but recommended: linked rule count is not excessive unless summary is very strong

Implement:

```python
def should_promote_to_positive_example(
    compact_visual_summary: str | None,
    linked_rule_ids: list[str] | None,
    source_event_ids: list[str] | None,
) -> bool:
    rules = linked_rule_ids or []
    events = source_event_ids or []

    if not rules or not events:
        return False

    if is_generic_teaching_visual(compact_visual_summary):
        return False

    if not has_concrete_market_visual_signals(compact_visual_summary):
        return False

    return True
```

Then in the role inference path:

```python
def infer_example_role(
    compact_visual_summary: str | None,
    linked_rule_ids: list[str] | None,
    source_event_ids: list[str] | None,
    current_role_hint: str | None = None,
) -> str:
    if should_promote_to_positive_example(
        compact_visual_summary=compact_visual_summary,
        linked_rule_ids=linked_rule_ids,
        source_event_ids=source_event_ids,
    ):
        return "positive_example"

    return "illustration"
```

---

# Part 3: optional additional safeguard for over-linking

This is recommended, because the current valid-looking chart at `22:44` is linked to **3 rules**.

That may still be okay, but only if the summary is clearly concrete.

Add a stricter condition:

* if an evidence row links to more than 2 rules, require at least **3 concrete-market hits** instead of 2

Example:

```python
def concrete_visual_hit_count(summary: str | None) -> int:
    text = _norm_text(summary)
    if not text:
        return 0

    hits = 0
    for pat in CONCRETE_MARKET_VISUAL_PATTERNS:
        if re.search(pat, text, flags=re.IGNORECASE):
            hits += 1
    return hits


def should_promote_to_positive_example(
    compact_visual_summary: str | None,
    linked_rule_ids: list[str] | None,
    source_event_ids: list[str] | None,
) -> bool:
    rules = linked_rule_ids or []
    events = source_event_ids or []

    if not rules or not events:
        return False

    if is_generic_teaching_visual(compact_visual_summary):
        return False

    hit_count = concrete_visual_hit_count(compact_visual_summary)

    if len(rules) > 2:
        return hit_count >= 3

    return hit_count >= 2
```

This keeps the `22:44` case more defensible while blocking weak slides.

---

# Part 4: keep ML eligibility strict

Do **not** loosen ML eligibility.

Keep:

```python
ML_ELIGIBLE_ROLES = {
    "positive_example",
    "negative_example",
    "counterexample",
    "ambiguous_example",
}
```

And keep:

```python
def is_evidence_ml_eligible(evidence: dict) -> bool:
    role = (evidence.get("example_role") or "").strip()

    if role not in ML_ELIGIBLE_ROLES:
        return False

    if not evidence.get("linked_rule_ids"):
        return False

    if not evidence.get("source_event_ids"):
        return False

    return True
```

This part is already working correctly.
The fix is to stop weak slides from reaching `positive_example` in the first place.

---

# Part 5: labeling task generation must follow downgraded evidence

The labeling manifest builder should continue using ML-eligible evidence only.

If the `28:10` row is downgraded to `illustration`, it must automatically disappear from:

* `ml_manifest.examples`
* `positive_example_refs`
* `labeling_manifest.tasks`

No separate special-case hack is needed if the role inference is corrected upstream.

---

# Part 6: optional debug metadata

This is optional but strongly recommended for debugging.

If schema allows metadata fields, attach a promotion reason:

```python
def classify_promotion_reason(summary: str | None, linked_rule_ids: list[str] | None) -> str:
    if is_generic_teaching_visual(summary):
        return "generic_teaching_visual"
    hit_count = concrete_visual_hit_count(summary)
    if hit_count >= 3:
        return "strong_concrete_visual"
    if hit_count >= 2:
        return "concrete_visual"
    return "insufficient_visual_specificity"
```

Then when building evidence:

```python
evidence["metadata"] = {
    **(evidence.get("metadata") or {}),
    "promotion_reason": classify_promotion_reason(
        evidence.get("compact_visual_summary"),
        evidence.get("linked_rule_ids"),
    ),
}
```

This helps debug future lessons without changing the top-level schema.

---

# Unit tests to add

## 1. Generic Q&A slide must not promote

```python
def test_generic_qa_slide_does_not_promote_to_positive_example():
    summary = "new slide displayed with text 'Ответы на вопросы'. concepts: abstract_teaching_example, atr_values, entry_values"

    result = should_promote_to_positive_example(
        compact_visual_summary=summary,
        linked_rule_ids=["rule1"],
        source_event_ids=["event1"],
    )

    assert result is False
```

## 2. Annotated chart may promote

```python
def test_annotated_chart_can_promote_to_positive_example():
    summary = "New chart displayed with annotations. concepts: atr_values, entry_values, level"

    result = should_promote_to_positive_example(
        compact_visual_summary=summary,
        linked_rule_ids=["rule1"],
        source_event_ids=["event1"],
    )

    assert result is True
```

## 3. Generic title/intro slide must not promote

```python
def test_intro_or_title_slide_does_not_promote():
    summary = "Title slide displayed. concepts: abstract_teaching_example, lesson_intro"

    result = should_promote_to_positive_example(
        compact_visual_summary=summary,
        linked_rule_ids=["rule1"],
        source_event_ids=["event1"],
    )

    assert result is False
```

## 4. No rules or no events means no promotion

```python
def test_positive_example_requires_links():
    summary = "Annotated chart with entry and level"

    assert should_promote_to_positive_example(summary, [], ["event1"]) is False
    assert should_promote_to_positive_example(summary, ["rule1"], []) is False
```

---

# Integration regression test for this lesson

Add a lesson-specific regression test for the current lesson.

## Expected minimum guarantees

After rerun of `2025-09-29-sviatoslav-chornyi`:

* evidence row at `28:10` with `"Ответы на вопросы"` must **not** be `positive_example`
* no ML example may have a summary containing:

  * `"Ответы на вопросы"`
  * `"questions"`
  * `"answers"`
  * `"q&a"`
* labeling tasks must not originate from such evidence
* total ML examples should be **<= 1**
* total labeling tasks should be **<= 3**

### Example integration assertion

```python
import json
from pathlib import Path

def test_sviatoslav_positive_example_promotion_is_conservative(run_sviatoslav_pipeline, sviatoslav_output_dir):
    run_sviatoslav_pipeline()

    base = sviatoslav_output_dir

    evidence = json.loads((base / "2025-09-29-sviatoslav-chornyi.evidence_index.json").read_text())["evidence_refs"]
    ml = json.loads((base / "2025-09-29-sviatoslav-chornyi.ml_manifest.json").read_text())
    labeling = json.loads((base / "2025-09-29-sviatoslav-chornyi.labeling_manifest.json").read_text())

    qna_like = []
    for ev in evidence:
        summary = (ev.get("compact_visual_summary") or "").lower()
        if "ответы на вопросы" in summary or "q&a" in summary or "questions" in summary or "answers" in summary:
            qna_like.append(ev)

    # Q&A slides must not be positive examples
    assert all(ev.get("example_role") != "positive_example" for ev in qna_like)

    # ML manifest must not contain Q&A evidence
    ml_example_ids = {x["evidence_id"] for x in ml["examples"]}
    qna_ids = {ev["evidence_id"] for ev in qna_like}
    assert ml_example_ids.isdisjoint(qna_ids)

    # Labeling tasks must not be created from Q&A evidence
    task_evidence_ids = {t["evidence_id"] for t in labeling.get("tasks", [])}
    assert task_evidence_ids.isdisjoint(qna_ids)

    # Conservative total size
    assert len(ml["examples"]) <= 1
    assert len(labeling.get("tasks", [])) <= 3
```

---

# Rerun target

Rerun this lesson only:

* `2025-09-29-sviatoslav-chornyi`

Do not mix with other lessons during this patch.

---

# Acceptance criteria

The patch is accepted only if all are true:

## Core stability must remain intact

* `knowledge_events.json` still has all Phase 2A fields
* `rule_cards.json` still has zero placeholder rule text
* `rule_cards.json` still has zero empty `source_event_ids`
* `evidence_index.json` still has zero empty `linked_rule_ids`
* `evidence_index.json` still has zero empty `source_event_ids`

## New semantic tightening must hold

* evidence summary containing `"Ответы на вопросы"` is not `positive_example`
* no generic Q&A/title/intro/summary slide is promoted to `positive_example`
* `ml_manifest.examples` contains no Q&A slide evidence
* `labeling_manifest.tasks` contains no Q&A slide evidence
* `ml_manifest.examples` count for this lesson is `<= 1`
* `labeling_manifest.tasks` count for this lesson is `<= 3`

---

# Suggested short instruction block for the agent

```text
Keep the current pipeline structure exactly as-is.

Patch only positive-example promotion logic so generic teaching slides do not become ML examples.

Required behavior:
- Q&A/title/intro/summary/concept slides must remain illustration
- only concrete market visuals may become positive_example
- require both:
  - non-generic visual summary
  - at least 2 concrete market/setup signals in the summary
- if linked_rule_ids > 2, require at least 3 concrete signals

Do not change ML eligibility rules.
Do not broaden evidence role inference.
Do not touch Phase 2A or rule export.

Add tests so that:
- "Ответы на вопросы" cannot be promoted to positive_example
- annotated chart summary can still promote
- ML examples exclude Q&A evidence
- labeling tasks exclude Q&A evidence
- for lesson 2025-09-29-sviatoslav-chornyi:
  - ml_manifest.examples <= 1
  - labeling_manifest.tasks <= 3
```

**Confidence: High** — the pipeline is structurally good, and the remaining issue is a narrow semantic promotion bug with a concrete example and a safe conservative fix.
