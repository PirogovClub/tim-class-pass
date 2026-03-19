Below is an **exact implementation task** you can paste to the coding agent.

---

# Task: Finalize Phase 2A confidence grading and make ML manifest trainable-only

## Goal

Patch the current pipeline without redesigning it.

The latest run is already structurally good:

* `knowledge_events.json` has Phase 2A fields
* `rule_cards.json` is clean
* `evidence_index.json` is conservative and linked
* `labeling_manifest.json` is empty

Only two issues remain:

1. `timestamp_confidence="line"` is too generous
2. `ml_manifest.json` still exports `illustration` evidence in `examples`

Your task is to fix only those two issues and keep everything else stable.

---

# Do not change

Do **not** change any of the following:

* Do not redesign extraction prompts
* Do not change the Phase 2A field set
* Do not reopen `KnowledgeEvent.source_event_ids`
* Do not invent lineage IDs
* Do not broaden evidence role inference
* Do not promote generic teaching visuals into positive/counterexample roles
* Do not move into canonicalization / concept graph work yet

---

# Required behavior after patch

## `knowledge_events.json`

Must still contain:

* `source_chunk_index`
* `source_line_start`
* `source_line_end`
* `source_quote`
* `transcript_anchors`
* `timestamp_confidence`

But now:

* no event may have `timestamp_confidence == "line"` when `anchor_span_width > 3`

## `rule_cards.json`

Must remain clean:

* zero `"No rule text extracted."`
* zero rules with empty `source_event_ids`

## `evidence_index.json`

Must remain conservative:

* no rows with empty `linked_rule_ids`
* no rows with empty `source_event_ids`
* generic teaching visuals may remain `illustration`

## `ml_manifest.json`

Must become **trainable-only**:

* `illustration` must not appear in `ml_manifest.examples`
* `illustration` must not populate:

  * `positive_example_refs`
  * `negative_example_refs`
  * `ambiguous_example_refs`

For this lesson, it is acceptable and expected that:

* `ml_manifest.examples == []`

## `labeling_manifest.json`

Must remain:

* `tasks == []`

---

# Files to inspect and patch

Search for the active code path first.

Run:

```bash
rg -n "timestamp_confidence|anchor_span_width|anchor_density|ml_manifest|labeling_manifest|example_role|is_evidence_ml_eligible|positive_example_refs|negative_example_refs|ambiguous_example_refs" .
```

Most likely files are around:

* `pipeline/component2/knowledge_builder.py`
* `pipeline/component2/llm_processor.py`
* the module that builds `ml_manifest.json`
* the module that builds `labeling_manifest.json`

Patch the **active** code path only.

---

# Part 1: tighten `timestamp_confidence`

## Required grading contract

Use this exact rule:

### `line`

Only when all of these are true:

* line bounds exist
* transcript anchors exist
* `anchor_span_width <= 3`
* `anchor_density >= 0.60`

### `span`

Use when:

* line bounds exist
* transcript localization is bounded
* but either:

  * `anchor_span_width >= 4`
  * or density is not strong enough for `line`

### `chunk`

Use when:

* no reliable line bounds
* no anchors
* matching is weak/sparse
* or provenance is only chunk-level fallback

---

## Exact implementation logic

Patch the provenance finalization step to use something equivalent to this:

```python
def compute_timestamp_confidence(
    source_line_start: int | None,
    source_line_end: int | None,
    transcript_anchors: list[str] | None,
    anchor_density: float | None,
) -> str:
    anchors = transcript_anchors or []

    if source_line_start is None or source_line_end is None:
        return "chunk"

    span_width = source_line_end - source_line_start + 1
    density = float(anchor_density or 0.0)

    if not anchors:
        return "chunk"

    if span_width <= 3 and density >= 0.60:
        return "line"

    if span_width >= 4:
        return "span"

    if density > 0:
        return "span"

    return "chunk"
```

Also ensure diagnostics remain coherent:

```python
event.anchor_line_count = len(transcript_anchors or [])
event.anchor_span_width = (
    source_line_end - source_line_start + 1
    if source_line_start is not None and source_line_end is not None
    else None
)
event.anchor_density = (
    event.anchor_line_count / event.anchor_span_width
    if event.anchor_span_width and event.anchor_span_width > 0
    else 0.0
)

event.timestamp_confidence = compute_timestamp_confidence(
    event.source_line_start,
    event.source_line_end,
    event.transcript_anchors,
    event.anchor_density,
)
```

## Important

Do not remove Phase 2A fields.
Do not simplify back to legacy shape.

---

# Part 2: make `ml_manifest.json` trainable-only

## Required contract

`evidence_index.json` is the conservative evidence registry.

`ml_manifest.json` must contain **only ML-eligible examples**.

That means:

```python
ML_ELIGIBLE_ROLES = {
    "positive_example",
    "negative_example",
    "counterexample",
    "ambiguous_example",
}
```

`illustration` is **not** ML-eligible.

---

## Patch eligibility gate

Find or create the ML eligibility function and make it strict:

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

    return True
```

---

## Patch ML example export

Only export eligible evidence rows:

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

---

## Patch rule-side refs inside ML manifest

Only eligible evidence may populate rule example refs:

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

---

## Patch labeling task generation

Tasks must be created only from ML-eligible evidence:

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

# Do not change evidence role inference right now

Current `evidence_index.json` is already behaving correctly for this lesson:

* all evidence rows are `illustration`
* backlinks are present
* source links are present

So:

* do not rewrite `infer_example_role(...)`
* do not change conservative evidence registry behavior

Only patch downstream ML export/gating.

---

# Tests to add

Add or update tests for these exact behaviors.

## 1. Confidence grading tests

```python
def test_line_confidence_for_compact_dense_span():
    event = finalize_anchor_provenance(
        source_line_start=10,
        source_line_end=12,
        transcript_anchors=["a", "b"],
        anchor_density=0.67,
    )
    assert event["timestamp_confidence"] == "line"

def test_span_confidence_for_width_four():
    event = finalize_anchor_provenance(
        source_line_start=10,
        source_line_end=13,
        transcript_anchors=["a", "b"],
        anchor_density=0.50,
    )
    assert event["timestamp_confidence"] == "span"

def test_chunk_confidence_without_line_bounds():
    event = finalize_anchor_provenance(
        source_line_start=None,
        source_line_end=None,
        transcript_anchors=[],
        anchor_density=0.0,
    )
    assert event["timestamp_confidence"] == "chunk"
```

## 2. ML eligibility tests

```python
def test_illustration_is_not_ml_eligible():
    ev = {
        "example_role": "illustration",
        "linked_rule_ids": ["r1"],
        "source_event_ids": ["e1"],
    }
    assert is_evidence_ml_eligible(ev) is False

def test_positive_example_is_ml_eligible():
    ev = {
        "example_role": "positive_example",
        "linked_rule_ids": ["r1"],
        "source_event_ids": ["e1"],
    }
    assert is_evidence_ml_eligible(ev) is True
```

## 3. Labeling manifest tests

```python
def test_labeling_manifest_empty_when_only_illustrations():
    evidence_refs = [
        {
            "evidence_id": "ev1",
            "example_role": "illustration",
            "linked_rule_ids": ["r1"],
            "source_event_ids": ["e1"],
        }
    ]
    tasks = build_labeling_tasks(evidence_refs)
    assert tasks == []
```

## 4. ML manifest export tests

```python
def test_ml_examples_excludes_illustrations():
    evidence_refs = [
        {
            "evidence_id": "ev1",
            "example_role": "illustration",
            "linked_rule_ids": ["r1"],
            "source_event_ids": ["e1"],
        },
        {
            "evidence_id": "ev2",
            "example_role": "positive_example",
            "linked_rule_ids": ["r1"],
            "source_event_ids": ["e2"],
        },
    ]

    examples = build_ml_examples(evidence_refs)
    assert [x["evidence_id"] for x in examples] == ["ev2"]
```

---

# Temporary debug logging for one rerun

Add temporary logs before final write:

```python
print(
    "[DEBUG] knowledge_events:",
    len(events),
    "line=", sum(1 for e in events if e.get("timestamp_confidence") == "line"),
    "span=", sum(1 for e in events if e.get("timestamp_confidence") == "span"),
    "chunk=", sum(1 for e in events if e.get("timestamp_confidence") == "chunk"),
)

print(
    "[DEBUG] evidence_index:",
    len(evidence_refs),
    "roles=", sorted({e.get("example_role") for e in evidence_refs}),
)

print(
    "[DEBUG] ml_manifest:",
    "rules=", len(ml_rules),
    "examples=", len(ml_examples),
)

print(
    "[DEBUG] labeling_manifest:",
    "tasks=", len(labeling_tasks),
)
```

Remove later or guard behind a debug flag.

---

# Rerun target

Rerun only this lesson:

* **Lesson 2. Levels part 1**

Do not switch lessons yet.

---

# Acceptance criteria

The patch is accepted only if all conditions below pass.

## `knowledge_events.json`

* all Phase 2A fields still present
* zero empty / placeholder `normalized_text`
* zero events where:

  * `timestamp_confidence == "line"` and `anchor_span_width > 3`

## `rule_cards.json`

* zero `"No rule text extracted."`
* zero rules with empty `source_event_ids`

## `evidence_index.json`

* zero rows with empty `linked_rule_ids`
* zero rows with empty `source_event_ids`

## `ml_manifest.json`

* zero `illustration` rows in `examples`
* zero positive/negative/ambiguous refs unless truly ML-eligible evidence exists
* for this lesson, empty `examples` is acceptable

## `labeling_manifest.json`

* zero tasks

---

# Validation script to run after rerun

Use this exact validation script, adjusting the path if needed:

```python
import json
from collections import Counter
from pathlib import Path

base = Path("output_intermediate")

ke = json.loads((base / "Lesson 2. Levels part 1.knowledge_events.json").read_text())
rc = json.loads((base / "Lesson 2. Levels part 1.rule_cards.json").read_text())
ev = json.loads((base / "Lesson 2. Levels part 1.evidence_index.json").read_text())
ml = json.loads((base / "Lesson 2. Levels part 1.ml_manifest.json").read_text())
lb = json.loads((base / "Lesson 2. Levels part 1.labeling_manifest.json").read_text())

events = ke["events"]
rules = rc["rules"]
evidence = ev["evidence_refs"]
ml_rules = ml["rules"]
ml_examples = ml["examples"]
label_tasks = lb.get("tasks", [])

assert all("source_chunk_index" in e for e in events)
assert all("source_line_start" in e for e in events)
assert all("source_line_end" in e for e in events)
assert all("source_quote" in e for e in events)
assert all("transcript_anchors" in e for e in events)
assert all("timestamp_confidence" in e for e in events)

assert not any((e.get("normalized_text") or "").strip() in {"", "No normalized text extracted."} for e in events)
assert not any(e.get("timestamp_confidence") == "line" and (e.get("anchor_span_width") or 0) > 3 for e in events)

assert not any((r.get("rule_text") or "").strip() == "No rule text extracted." for r in rules)
assert not any(not r.get("source_event_ids") for r in rules)

assert not any(not x.get("linked_rule_ids") for x in evidence)
assert not any(not x.get("source_event_ids") for x in evidence)

assert not any(x.get("example_role") == "illustration" for x in ml_examples)
assert len(label_tasks) == 0

print("knowledge_events:", len(events), Counter(e["timestamp_confidence"] for e in events))
print("rule_cards:", len(rules))
print("evidence_index:", len(evidence), Counter(x["example_role"] for x in evidence))
print("ml_manifest: rules=", len(ml_rules), "examples=", len(ml_examples))
print("labeling_manifest:", len(label_tasks))
print("VALIDATION PASSED")
```

---

# Short version to paste directly to the coding agent

```text
Use the current latest run as the baseline. Do not redesign the pipeline.

Patch only two things:

1) Tighten timestamp_confidence:
- line only if line bounds exist, transcript anchors exist, anchor_span_width <= 3, and anchor_density >= 0.60
- downgrade 4+ line spans to span
- use chunk for fallback/no trustworthy line bounds

2) Make ml_manifest trainable-only:
- illustration must not appear in ml_manifest.examples
- illustration must not populate positive/negative/ambiguous refs
- labeling tasks must only come from ML-eligible evidence
- ML-eligible roles = positive_example, negative_example, counterexample, ambiguous_example

Do not change evidence_index conservatism.
Do not promote generic teaching visuals.
Do not invent lineage ids.

Acceptance:
- knowledge_events still has all Phase 2A fields
- no line-confidence event has anchor_span_width > 3
- rule_cards stays clean
- evidence_index keeps non-empty backlinks
- ml_manifest contains zero illustration examples
- labeling_manifest stays empty for this lesson
```

**Confidence: High** — this is the correct next coding task based on the current artifacts, and it is narrow, testable, and aligned with the stable baseline.
