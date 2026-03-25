Yes. Here is the **exact agent brief** for the current regression.

The current problem is no longer broken export structure.
The problem is that **generic teaching visuals are being treated as counterexamples and then pushed into ML / labeling**.

You can see it directly in the current artifacts:

* early evidence rows like `evcand_Lesson 2. Levels part 1_0_0` are marked `example_role: "counterexample"` even though the compact summary is an intro slide / instructor / overlay / concept sketch, not a failed setup or invalidation 
* `labeling_manifest.json` is generating `expected_role: "counterexample"` tasks from those same early visuals for trend-break rules 
* `ml_manifest.json` is also carrying those counterexample examples into the examples section and negative-example flow

So the fix is:

> Keep those visuals in `evidence_index.json` if they are useful as supporting evidence, but block them from becoming `counterexample`, `negative_example_refs`, or labeling tasks unless there is explicit failure/invalidation evidence.

---

# Agent task: make evidence semantics conservative again

## Goal

Prevent:

* intro slides
* instructor shots
* title cards
* concept explanation overlays
* hand-drawn diagrams
* generic teaching charts

from being labeled as:

* `counterexample`
* `negative_example_refs`
* `expected_role: "counterexample"`

unless there is **strong explicit evidence** of invalidation/failure.

---

# Files to edit

## 1) `pipeline/component2/evidence_linker.py`

### What to change

Tighten `infer_example_role(...)`.

Right now the role assignment is still too willing to produce `counterexample` for generic teaching visuals. The new logic must require **both**:

1. a negative/invalidation signal from linked events or content
2. non-generic visual semantics

### Add these helper sets

```python
# pipeline/component2/evidence_linker.py

GENERIC_VISUAL_MARKERS = {
    "introduction slide",
    "intro slide",
    "title",
    "logo",
    "instructor",
    "speaker",
    "overlay",
    "text overlay",
    "hand drawing",
    "diagram",
    "sketch",
    "abstract diagram",
    "concept explanation",
    "level area",
    "horizontal line",
    "candlestick sketch",
}

NEGATIVE_VISUAL_MARKERS = {
    "failed breakout",
    "false breakout",
    "did not hold",
    "failure",
    "invalid",
    "invalidation",
    "rejected",
    "rejection",
    "trap",
    "mistake",
    "broke and reversed",
    "pierced and returned",
}
```

### Add these helpers

```python
# pipeline/component2/evidence_linker.py

def _norm_text(text: str | None) -> str:
    return (text or "").strip().lower()


def _contains_any(text: str, phrases: set[str]) -> bool:
    return any(p in text for p in phrases)


def _is_generic_teaching_visual(candidate, linked_events) -> bool:
    content = " ".join(
        [
            _norm_text(getattr(candidate, "compact_visual_summary", "")),
            " ".join(_norm_text(x) for x in getattr(candidate, "concept_hints", []) or []),
            " ".join(
                _norm_text(getattr(evt, "change_summary", ""))
                for evt in getattr(candidate, "visual_events", []) or []
            ),
        ]
    ).strip()

    event_types = [getattr(e, "event_type", "") for e in linked_events]

    generic_visual = _contains_any(content, GENERIC_VISUAL_MARKERS)
    negative_visual = _contains_any(content, NEGATIVE_VISUAL_MARKERS)

    # If the visual is generic and there is no explicit negative visual evidence,
    # treat it as teaching/support material, not a counterexample.
    if generic_visual and not negative_visual:
        return True

    # Chunk-wide teaching bundles are often generic context, not example semantics.
    if len(getattr(candidate, "source_event_ids", []) or []) >= 6:
        if any(t in event_types for t in ("definition", "comparison", "algorithm_hint")):
            return True

    return False


def _has_explicit_negative_semantics(candidate, linked_events) -> bool:
    content = " ".join(
        [
            _norm_text(getattr(candidate, "compact_visual_summary", "")),
            " ".join(_norm_text(x) for x in getattr(candidate, "concept_hints", []) or []),
            " ".join(
                _norm_text(getattr(evt, "change_summary", ""))
                for evt in getattr(candidate, "visual_events", []) or []
            ),
        ]
    ).strip()

    event_types = [getattr(e, "event_type", "") for e in linked_events]

    negative_from_events = any(
        t in event_types for t in ("invalidation", "exception", "warning")
    )
    negative_from_visual = _contains_any(content, NEGATIVE_VISUAL_MARKERS)

    return negative_from_events or negative_from_visual
```

### Replace `infer_example_role(...)` with this version

```python
# pipeline/component2/evidence_linker.py

def infer_example_role(candidate, linked_events) -> str:
    event_types = [getattr(e, "event_type", "") for e in linked_events]

    if _is_generic_teaching_visual(candidate, linked_events):
        return "illustration"

    if _has_explicit_negative_semantics(candidate, linked_events):
        return "counterexample"

    if any(t in event_types for t in ("rule_statement", "condition", "example")):
        return "positive_example"

    if any(t in event_types for t in ("definition", "comparison", "process_step")):
        return "illustration"

    if not linked_events:
        return "illustration"

    return "illustration"
```

## Important behavior rule

`counterexample` must now be **hard to earn**.

It must **not** be assigned just because:

* the chunk contains warnings
* the lesson is describing a trap concept in theory
* the visual shows a concept sketch
* the word “false” appears somewhere in text without actual failure depiction

---

## 2) `pipeline/component2/ml_prep.py`

### What to change

Add a second strict gate so that even if a row survives in `evidence_index.json`, it does **not** automatically become:

* a negative example
* a counterexample labeling task

The ML gate must be stricter than the evidence-export gate.

### Add these helpers

```python
# pipeline/component2/ml_prep.py

GENERIC_EVIDENCE_MARKERS = {
    "introduction slide",
    "intro slide",
    "title",
    "logo",
    "instructor",
    "speaker",
    "overlay",
    "hand drawing",
    "diagram",
    "sketch",
    "concept explanation",
    "abstract diagram",
}


def _norm_text(text: str | None) -> str:
    return (text or "").strip().lower()


def _contains_any(text: str, phrases: set[str]) -> bool:
    return any(p in text for p in phrases)


def is_generic_evidence(ref) -> bool:
    summary = _norm_text(getattr(ref, "compact_visual_summary", ""))
    return _contains_any(summary, GENERIC_EVIDENCE_MARKERS)


def has_explicit_negative_evidence(ref) -> bool:
    summary = _norm_text(getattr(ref, "compact_visual_summary", ""))
    return any(
        phrase in summary
        for phrase in (
            "failed breakout",
            "false breakout",
            "did not hold",
            "invalid",
            "rejected",
            "rejection",
            "trap",
            "mistake",
            "pierced and returned",
            "broke and reversed",
        )
    )
```

### Tighten `is_evidence_ml_eligible(ref, rule)`

Replace or update it so it behaves like this:

```python
# pipeline/component2/ml_prep.py

def is_evidence_ml_eligible(ref, rule) -> bool:
    if not (getattr(ref, "linked_rule_ids", []) or []):
        return False
    if not (getattr(ref, "source_event_ids", []) or []):
        return False
    if getattr(rule, "rule_id", None) not in (getattr(ref, "linked_rule_ids", []) or []):
        return False

    role = getattr(ref, "example_role", None)
    if role not in {"positive_example", "counterexample"}:
        return False

    # Generic teaching visuals are not ML examples.
    if is_generic_evidence(ref):
        return False

    # Counterexamples require explicit negative evidence.
    if role == "counterexample" and not has_explicit_negative_evidence(ref):
        return False

    return True
```

### Tighten example assignment in `build_ml_manifest(...)`

Where you currently map evidence roles into:

* `positive_example_refs`
* `negative_example_refs`
* `ambiguous_example_refs`

use this behavior:

```python
# pipeline/component2/ml_prep.py

if not is_evidence_ml_eligible(ref, rule):
    continue

if ref.example_role == "positive_example":
    positive_example_refs.append(ref.evidence_id)
elif ref.example_role == "counterexample":
    negative_example_refs.append(ref.evidence_id)
```

Do **not** let `illustration` or `ambiguous_example` enter ML example buckets.

---

## 3) `pipeline/component2/ml_prep.py` — tighten labeling manifest generation

### Problem

Current `labeling_manifest.json` is creating `expected_role: "counterexample"` tasks from intro/concept visuals. 

### Fix

Only create a counterexample labeling task when the evidence is ML-eligible **and** explicitly negative.

### Patch pattern

```python
# pipeline/component2/ml_prep.py

def should_emit_labeling_task(ref, rule) -> bool:
    if not is_evidence_ml_eligible(ref, rule):
        return False

    if ref.example_role == "counterexample":
        return has_explicit_negative_evidence(ref)

    if ref.example_role == "positive_example":
        return True

    return False
```

Then in `build_labeling_manifest(...)`:

```python
# pipeline/component2/ml_prep.py

for ref in evidence_refs_for_rule:
    if not should_emit_labeling_task(ref, rule):
        continue

    expected_role = ref.example_role
    tasks.append(
        LabelingTask(
            rule_id=rule.rule_id,
            concept=rule.concept,
            subconcept=rule.subconcept,
            expected_role=expected_role,
            labeling_guidance=rule.labeling_guidance,
            evidence_id=ref.evidence_id,
            frame_ids=ref.frame_ids,
            screenshot_paths=ref.screenshot_paths,
        )
    )
```

### Important rule

If the evidence is just explanatory support, keep it in `evidence_index.json`, but do **not** emit a labeling task for it.

---

## 4) Optional but recommended: add semantic warnings to evidence debug

If you want easier QA, add a warning when a generic visual was downgraded from potential negative semantics to `illustration`.

Example:

```python
# pipeline/component2/evidence_linker.py

semantic_warnings = []
if _is_generic_teaching_visual(candidate, linked_events):
    semantic_warnings.append(
        "downgraded_to_illustration_due_to_generic_teaching_visual"
    )
```

If your schema already has metadata, attach this in `EvidenceRef.metadata`.

This is optional, but it will make QA much easier.

---

# Tests to add

## 1) `tests/test_evidence_linker.py`

### Test: intro slide stays illustration

```python
def test_intro_slide_with_overlay_is_illustration_not_counterexample() -> None:
    candidate = VisualEvidenceCandidate(
        candidate_id="ev1",
        lesson_id="lesson1",
        chunk_index=0,
        timestamp_start=2.0,
        timestamp_end=8.0,
        compact_visual_summary=(
            "First frame: introduction slide with logo and title. "
            "Instructor is visible. The screen shows an overlay with text "
            "and a horizontal level line."
        ),
        concept_hints=["trend break level"],
        visual_events=[],
        source_event_ids=["ke1", "ke2", "ke3", "ke4", "ke5", "ke6"],
    )

    linked_events = [
        KnowledgeEvent(
            lesson_id="lesson1",
            event_id="ke1",
            event_type="definition",
            raw_text="Definition text",
            normalized_text="Definition text",
            metadata={"chunk_index": 0},
        ),
        KnowledgeEvent(
            lesson_id="lesson1",
            event_id="ke2",
            event_type="rule_statement",
            raw_text="Rule text",
            normalized_text="Rule text",
            metadata={"chunk_index": 0},
        ),
    ]

    role = infer_example_role(candidate, linked_events)
    assert role == "illustration"
```

### Test: explicit failed breakout can still be counterexample

```python
def test_explicit_failed_breakout_can_be_counterexample() -> None:
    candidate = VisualEvidenceCandidate(
        candidate_id="ev2",
        lesson_id="lesson1",
        chunk_index=1,
        timestamp_start=30.0,
        timestamp_end=35.0,
        compact_visual_summary=(
            "Chart shows failed breakout above level, rejection, and return below the level."
        ),
        concept_hints=["failed breakout"],
        visual_events=[],
        source_event_ids=["ke10"],
    )

    linked_events = [
        KnowledgeEvent(
            lesson_id="lesson1",
            event_id="ke10",
            event_type="invalidation",
            raw_text="The breakout failed and returned under the level.",
            normalized_text="The breakout failed and returned under the level.",
            metadata={"chunk_index": 1},
        ),
    ]

    role = infer_example_role(candidate, linked_events)
    assert role == "counterexample"
```

---

## 2) `tests/test_ml_prep.py`

### Test: generic illustration is not ML eligible

```python
def test_generic_teaching_visual_not_ml_eligible() -> None:
    ref = EvidenceRef(
        lesson_id="lesson1",
        evidence_id="ev1",
        source_event_ids=["ke1"],
        linked_rule_ids=["r1"],
        frame_ids=["000001"],
        example_role="illustration",
        compact_visual_summary="Introduction slide with instructor and title overlay.",
    )

    rule = RuleCard(
        lesson_id="lesson1",
        rule_id="r1",
        concept="Trend Break Level",
        rule_text="A trend break level forms after a strong move and reversal.",
        source_event_ids=["ke1"],
    )

    assert is_evidence_ml_eligible(ref, rule) is False
```

### Test: generic counterexample label is still rejected by ML gate

```python
def test_generic_visual_marked_counterexample_is_rejected_by_ml_gate() -> None:
    ref = EvidenceRef(
        lesson_id="lesson1",
        evidence_id="ev2",
        source_event_ids=["ke1"],
        linked_rule_ids=["r1"],
        frame_ids=["000001"],
        example_role="counterexample",
        compact_visual_summary="Introduction slide with instructor and logo.",
    )

    rule = RuleCard(
        lesson_id="lesson1",
        rule_id="r1",
        concept="Trend Break Level",
        rule_text="A trend break level forms after a strong move and reversal.",
        source_event_ids=["ke1"],
    )

    assert is_evidence_ml_eligible(ref, rule) is False
```

### Test: explicit negative evidence is ML eligible

```python
def test_explicit_negative_evidence_is_ml_eligible() -> None:
    ref = EvidenceRef(
        lesson_id="lesson1",
        evidence_id="ev3",
        source_event_ids=["ke10"],
        linked_rule_ids=["r1"],
        frame_ids=["000010"],
        example_role="counterexample",
        compact_visual_summary="Chart shows failed breakout, rejection, and return below level.",
    )

    rule = RuleCard(
        lesson_id="lesson1",
        rule_id="r1",
        concept="Breakout",
        rule_text="A clean breakout should hold above the level.",
        source_event_ids=["ke10"],
    )

    assert is_evidence_ml_eligible(ref, rule) is True
```

---

## 3) `tests/test_labeling_manifest.py`

### Test: no counterexample labeling task for intro visual

```python
def test_labeling_manifest_skips_generic_intro_counterexample() -> None:
    ref = EvidenceRef(
        lesson_id="lesson1",
        evidence_id="ev1",
        source_event_ids=["ke1"],
        linked_rule_ids=["r1"],
        frame_ids=["000001"],
        example_role="counterexample",
        compact_visual_summary="Introduction slide with title and instructor.",
    )

    rule = RuleCard(
        lesson_id="lesson1",
        rule_id="r1",
        concept="Trend Break Level",
        rule_text="A trend break level forms after a strong move and reversal.",
        source_event_ids=["ke1"],
        labeling_guidance="Label positive only when the setup clearly matches the rule.",
    )

    manifest = build_labeling_manifest(
        lesson_id="lesson1",
        rules=[rule],
        evidence_index=EvidenceIndex(
            lesson_id="lesson1",
            evidence_refs=[ref],
        ),
    )

    assert manifest.tasks == []
```

---

# Definition of done

This task is done only if rerunning **Lesson 2. Levels part 1** produces:

* no intro / instructor / title-card visuals labeled as `counterexample`
* `evidence_index.json` may still keep those rows, but as `illustration`
* `ml_manifest.json` does not include those rows in `negative_example_refs`
* `labeling_manifest.json` does not create `expected_role: "counterexample"` tasks from those visuals

---

# Suggested commit message

```text
Make evidence semantics conservative for ML and labeling

- downgrade generic teaching visuals to illustration
- require explicit negative evidence for counterexample
- block generic visuals from ML negative examples
- block generic visuals from counterexample labeling tasks
- add regression tests for intro/concept visuals
```

**Confidence: High — based on the current artifacts showing generic teaching visuals being used as counterexamples in `evidence_index.json`, `ml_manifest.json`, and `labeling_manifest.json`.**
