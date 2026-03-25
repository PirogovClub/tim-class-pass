Below is an **exact implementation task** for the coding agent.

---

# Task: add final ML-eligibility guard for weak evidence

## Why this patch is needed

The pipeline is now **structurally strong**:

* `knowledge_events.json` is good
* `rule_cards.json` is clean
* `evidence_index.json` has intact backlinks
* Phase 2A provenance is working
* Q&A/title/intro slides are no longer leaking into ML examples

But one narrow inconsistency remains:

### Current remaining bad case

There is still **1 ML-eligible evidence row** that should probably not be ML-eligible:

* role: `counterexample`
* timestamp: `33:30`
* summary: `"concepts: atr_values, entry_values, level"`
* linked to 2 rules
* metadata:

  * `"promotion_reason": "insufficient_visual_specificity"`

That means the system is currently allowing an evidence row into:

* `ml_manifest.examples`
* `negative_example_refs`
* `labeling_manifest.tasks`

even though its own metadata says the visual evidence is too weak.

---

# Goal

Add a **final downstream ML-eligibility safety gate** so weak evidence cannot become:

* ML examples
* rule-side ML refs
* labeling tasks

even if upstream role inference assigns:

* `positive_example`
* `negative_example`
* `counterexample`
* `ambiguous_example`

---

# Required behavior after patch

## Keep all current good behavior

Do **not** disturb:

* Phase 2A fields
* tightened `timestamp_confidence`
* clean `rule_cards.json`
* conservative evidence linking
* Q&A downgrade behavior

## New required behavior

Any evidence row with weak-specificity metadata must be blocked from ML outputs.

At minimum, block ML eligibility when:

* `metadata.promotion_reason == "insufficient_visual_specificity"`

Recommended also to block when semantic warnings indicate weak grounding.

### Expected result for this lesson

After rerun of `2025-09-29-sviatoslav-chornyi`:

* `ml_manifest.examples` should go from **1** to **0**
* `labeling_manifest.tasks` should go from **2** to **0**
* `negative_example_refs` should go from **2** to **0**
* the weak counterexample should remain in `evidence_index.json`, but not propagate into ML artifacts

---

# Do not change

Do **not** do any of the following:

* do not redesign evidence role inference again
* do not change positive-example gating from the previous successful patch
* do not change rule export logic
* do not change schemas unless a tiny helper field is necessary
* do not remove evidence from `evidence_index.json`
* do not broaden ML eligibility
* do not invent lineage ids
* do not move into canonicalization or graph work

This patch is a **downstream ML safety filter only**.

---

# Where to patch

Search for the active code:

```bash
rg -n "is_evidence_ml_eligible|build_ml_examples|attach_rule_example_refs|build_labeling_tasks|promotion_reason|semantic_warnings|counterexample|negative_example_refs"
```

Likely modules:

* ML manifest builder
* labeling manifest builder
* evidence filtering helper

Patch the **active code path only**.

---

# Exact implementation

## 1. Add a helper for weak-specificity blocking

Create a helper like this near ML eligibility logic:

```python
def has_weak_visual_specificity(evidence: dict) -> bool:
    metadata = evidence.get("metadata") or {}
    promotion_reason = (metadata.get("promotion_reason") or "").strip().lower()

    if promotion_reason == "insufficient_visual_specificity":
        return True

    semantic_warnings = evidence.get("semantic_warnings") or []
    warning_text = " ".join(str(x).lower() for x in semantic_warnings)

    weak_warning_markers = [
        "insufficient_visual_specificity",
        "weak visual grounding",
        "generic teaching visual",
        "low visual specificity",
        "not concrete enough",
    ]

    return any(marker in warning_text for marker in weak_warning_markers)
```

---

## 2. Tighten `is_evidence_ml_eligible(...)`

Patch the final ML eligibility gate.

### Current contract must still hold

Only these roles are ML-eligible in principle:

```python
ML_ELIGIBLE_ROLES = {
    "positive_example",
    "negative_example",
    "counterexample",
    "ambiguous_example",
}
```

### New contract

Even if role is eligible in principle, the evidence must be rejected if it is weakly grounded.

Use logic like this:

```python
ML_ELIGIBLE_ROLES = {
    "positive_example",
    "negative_example",
    "counterexample",
    "ambiguous_example",
}

def is_evidence_ml_eligible(evidence: dict) -> bool:
    role = (evidence.get("example_role") or "").strip()

    if role not in ML_ELIGIBLE_ROLES:
        return False

    if not evidence.get("linked_rule_ids"):
        return False

    if not evidence.get("source_event_ids"):
        return False

    if has_weak_visual_specificity(evidence):
        return False

    return True
```

This is the key patch.

---

## 3. Ensure all downstream ML outputs use the same gate

Make sure **all** of the following use `is_evidence_ml_eligible(...)` and do not bypass it:

### A. `ml_manifest.examples`

Only eligible evidence rows may appear.

```python
def build_ml_examples(evidence_refs: list[dict]) -> list[dict]:
    examples = []

    for ev in evidence_refs:
        if not is_evidence_ml_eligible(ev):
            continue

        examples.append({
            "evidence_id": ev["evidence_id"],
            "example_role": ev["example_role"],
            "frame_ids": ev.get("frame_ids", []),
            "screenshot_paths": ev.get("screenshot_paths", []),
            "timestamp_start": ev.get("timestamp_start"),
            "timestamp_end": ev.get("timestamp_end"),
            "source_event_ids": ev.get("source_event_ids", []),
            "linked_rule_ids": ev.get("linked_rule_ids", []),
        })

    return examples
```

### B. rule-side refs in `ml_manifest.rules`

Only eligible evidence rows may populate:

* `positive_example_refs`
* `negative_example_refs`
* `ambiguous_example_refs`

```python
def attach_rule_example_refs(rule: dict, evidence_refs: list[dict]) -> dict:
    positive = []
    negative = []
    ambiguous = []

    for ev in evidence_refs:
        if not is_evidence_ml_eligible(ev):
            continue

        if rule["rule_id"] not in ev.get("linked_rule_ids", []):
            continue

        role = ev["example_role"]

        if role == "positive_example":
            positive.append(ev["evidence_id"])
        elif role in {"negative_example", "counterexample"}:
            negative.append(ev["evidence_id"])
        elif role == "ambiguous_example":
            ambiguous.append(ev["evidence_id"])

    rule["positive_example_refs"] = sorted(set(positive))
    rule["negative_example_refs"] = sorted(set(negative))
    rule["ambiguous_example_refs"] = sorted(set(ambiguous))
    return rule
```

### C. `labeling_manifest.tasks`

Only eligible evidence rows may generate tasks.

```python
def build_labeling_tasks(evidence_refs: list[dict]) -> list[dict]:
    tasks = []

    for ev in evidence_refs:
        if not is_evidence_ml_eligible(ev):
            continue

        tasks.append(make_labeling_task_from_evidence(ev))

    return tasks
```

---

# Optional but recommended hardening

## Require concrete summary for any ML-eligible evidence

This is optional, but useful if the bad case still slips through.

Add another safety check:

```python
def has_minimum_concrete_summary(evidence: dict) -> bool:
    summary = (evidence.get("compact_visual_summary") or "").strip().lower()
    if not summary:
        return False

    generic_only_patterns = [
        "concepts:",
        "abstract_teaching_example",
    ]

    # block extremely weak summaries that are just concept tags
    if summary.startswith("concepts:"):
        return False

    if all(token in summary for token in ["atr_values", "entry_values", "level"]) and "chart" not in summary:
        return False

    return True
```

Then extend eligibility:

```python
if not has_minimum_concrete_summary(evidence):
    return False
```

Use this only if needed. The main required patch is the `promotion_reason` guard.

---

# Tests to add

## 1. Weak specificity blocks ML eligibility

Create or update unit tests:

```python
def test_insufficient_visual_specificity_blocks_ml_eligibility():
    evidence = {
        "example_role": "counterexample",
        "linked_rule_ids": ["r1"],
        "source_event_ids": ["e1"],
        "metadata": {
            "promotion_reason": "insufficient_visual_specificity"
        },
    }

    assert is_evidence_ml_eligible(evidence) is False
```

## 2. Strong evidence still remains eligible

```python
def test_concrete_counterexample_can_remain_ml_eligible():
    evidence = {
        "example_role": "counterexample",
        "linked_rule_ids": ["r1"],
        "source_event_ids": ["e1"],
        "compact_visual_summary": "Annotated chart showing failed entry near level and invalidation",
        "metadata": {
            "promotion_reason": "strong_concrete_visual"
        },
    }

    assert is_evidence_ml_eligible(evidence) is True
```

## 3. Weak evidence must be excluded from ML examples

```python
def test_build_ml_examples_excludes_weak_specificity_evidence():
    evidence_refs = [
        {
            "evidence_id": "ev_weak",
            "example_role": "counterexample",
            "linked_rule_ids": ["r1"],
            "source_event_ids": ["e1"],
            "metadata": {
                "promotion_reason": "insufficient_visual_specificity"
            },
        },
        {
            "evidence_id": "ev_strong",
            "example_role": "counterexample",
            "linked_rule_ids": ["r1"],
            "source_event_ids": ["e2"],
            "metadata": {
                "promotion_reason": "strong_concrete_visual"
            },
        },
    ]

    examples = build_ml_examples(evidence_refs)
    assert [x["evidence_id"] for x in examples] == ["ev_strong"]
```

## 4. Weak evidence must not populate rule refs

```python
def test_attach_rule_example_refs_ignores_weak_specificity_evidence():
    rule = {"rule_id": "r1"}

    evidence_refs = [
        {
            "evidence_id": "ev_weak",
            "example_role": "counterexample",
            "linked_rule_ids": ["r1"],
            "source_event_ids": ["e1"],
            "metadata": {
                "promotion_reason": "insufficient_visual_specificity"
            },
        }
    ]

    result = attach_rule_example_refs(rule, evidence_refs)

    assert result["positive_example_refs"] == []
    assert result["negative_example_refs"] == []
    assert result["ambiguous_example_refs"] == []
```

## 5. Weak evidence must not create labeling tasks

```python
def test_labeling_manifest_excludes_weak_specificity_evidence():
    evidence_refs = [
        {
            "evidence_id": "ev_weak",
            "example_role": "counterexample",
            "linked_rule_ids": ["r1"],
            "source_event_ids": ["e1"],
            "metadata": {
                "promotion_reason": "insufficient_visual_specificity"
            },
        }
    ]

    tasks = build_labeling_tasks(evidence_refs)
    assert tasks == []
```

---

# Integration test for this lesson

Add a lesson-specific regression check for `2025-09-29-sviatoslav-chornyi`.

## Expected behavior after rerun

* no ML example with `promotion_reason == "insufficient_visual_specificity"`
* no labeling task derived from such evidence
* `ml_manifest.examples == []` for this lesson, unless there is a truly strong surviving example
* `negative_example_refs == []` unless backed by strong evidence

### Example integration assertion

```python
import json
from pathlib import Path

def test_sviatoslav_weak_specificity_evidence_is_blocked(run_sviatoslav_pipeline, sviatoslav_output_dir):
    run_sviatoslav_pipeline()

    base = sviatoslav_output_dir

    evidence = json.loads((base / "2025-09-29-sviatoslav-chornyi.evidence_index.json").read_text())["evidence_refs"]
    ml = json.loads((base / "2025-09-29-sviatoslav-chornyi.ml_manifest.json").read_text())
    labeling = json.loads((base / "2025-09-29-sviatoslav-chornyi.labeling_manifest.json").read_text())

    weak_ids = {
        ev["evidence_id"]
        for ev in evidence
        if (ev.get("metadata") or {}).get("promotion_reason") == "insufficient_visual_specificity"
    }

    ml_ids = {x["evidence_id"] for x in ml["examples"]}
    task_ids = {t["evidence_id"] for t in labeling.get("tasks", [])}

    assert ml_ids.isdisjoint(weak_ids)
    assert task_ids.isdisjoint(weak_ids)

    # Conservative outcome for this lesson
    assert len(ml["examples"]) == 0
    assert len(labeling.get("tasks", [])) == 0
```

If your labeling tasks do not store `evidence_id` directly, adapt the check to the actual task structure.

---

# Temporary debug logging

For one rerun, add a small debug summary before final export:

```python
weak_blocked = [
    ev["evidence_id"]
    for ev in evidence_refs
    if has_weak_visual_specificity(ev)
]

print("[DEBUG] weak_specificity_blocked_count:", len(weak_blocked))
print("[DEBUG] weak_specificity_blocked_ids:", weak_blocked[:10])

print("[DEBUG] ml_examples_count:", len(ml_examples))
print("[DEBUG] labeling_tasks_count:", len(labeling_tasks))
```

Remove later or guard behind a debug flag.

---

# Rerun target

Rerun only this lesson:

* `2025-09-29-sviatoslav-chornyi`

Do not mix with other lessons during this patch.

---

# Acceptance criteria

The patch is accepted only if all are true.

## Core stability stays intact

* `knowledge_events.json` still has all Phase 2A fields
* `rule_cards.json` still has zero placeholder rule text
* `rule_cards.json` still has zero empty `source_event_ids`
* `evidence_index.json` still has zero empty `linked_rule_ids`
* `evidence_index.json` still has zero empty `source_event_ids`

## New ML safety guard works

* no ML example may come from evidence with:

  * `metadata.promotion_reason == "insufficient_visual_specificity"`
* no labeling task may come from such evidence
* for this lesson:

  * `ml_manifest.examples == []`
  * `labeling_manifest.tasks == []`
  * total negative refs in `ml_manifest.rules` should be `0`

---

# Short instruction block for the agent

```text
Keep the current pipeline structure exactly as-is.

Patch only the final ML eligibility gate.

New rule:
Even if evidence has an ML-eligible role (positive_example / negative_example / counterexample / ambiguous_example), it must be blocked from:
- ml_manifest.examples
- rule-side example refs
- labeling_manifest.tasks

if:
- metadata.promotion_reason == "insufficient_visual_specificity"
or equivalent weak-specificity warning is present.

Do not change Phase 2A.
Do not change rule export.
Do not redesign evidence inference.
Do not remove evidence from evidence_index.
This is a downstream ML safety filter only.

Add tests so that:
- weak-specificity evidence is not ML-eligible
- weak-specificity evidence does not appear in ml_manifest.examples
- weak-specificity evidence does not populate negative refs
- weak-specificity evidence does not create labeling tasks

Rerun lesson:
2025-09-29-sviatoslav-chornyi

Expected result:
- ml_manifest.examples == []
- labeling_manifest.tasks == []
- negative_example_refs total == 0
```

**Confidence: High** — this is a narrow, safe, conservative fix that matches the exact remaining inconsistency in the current artifacts.
