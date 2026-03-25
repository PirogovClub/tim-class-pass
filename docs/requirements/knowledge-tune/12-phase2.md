Below is an **exact task** for the coding agent to implement regression tests for the guarantees you have already stabilized.

---

# Task: Add regression tests for stable Phase 1 + Phase 2A guarantees

## Objective

Create a regression test suite that protects the current good behavior of the pipeline.

The tests must ensure future code changes do **not** reintroduce:

* placeholder leakage into final artifacts
* empty backlinks in final evidence
* missing Phase 2A provenance fields
* overly broad `timestamp_confidence="line"`
* `illustration` leakage into `ml_manifest.examples`
* unwanted `labeling_manifest` tasks for non-ML-eligible evidence

This task is about **locking current behavior**, not redesigning the pipeline.

---

# Scope

Add tests for these artifact guarantees:

## Final artifact guarantees to protect

### `knowledge_events.json`

* required Phase 2A fields exist on all final events:

  * `source_chunk_index`
  * `source_line_start`
  * `source_line_end`
  * `source_quote`
  * `transcript_anchors`
  * `timestamp_confidence`
* no empty or placeholder `normalized_text`
* no event with:

  * `timestamp_confidence == "line"` and `anchor_span_width > 3`

### `rule_cards.json`

* no final rule with `rule_text == "No rule text extracted."`
* no final rule with empty `source_event_ids`

### `evidence_index.json`

* no final evidence row with empty `linked_rule_ids`
* no final evidence row with empty `source_event_ids`

### `ml_manifest.json`

* no `illustration` rows inside `ml_manifest.examples`
* no positive/negative/ambiguous refs unless backed by ML-eligible evidence

### `labeling_manifest.json`

* no tasks from non-ML-eligible evidence
* for the current validation lesson, task list should remain empty

### Cross-file integrity

* every rule `source_event_id` must resolve to a real event
* every evidence `source_event_id` must resolve to a real event
* every evidence `linked_rule_id` must resolve to a real rule

---

# Do not change

Do **not** do any of the following in this task:

* do not redesign prompts
* do not change schemas unless a test helper truly requires import access
* do not change evidence role inference
* do not reopen `KnowledgeEvent.source_event_ids`
* do not invent lineage IDs
* do not move into rule canonicalization or graph work

This task is **tests only**, except tiny refactors needed to make code testable.

---

# Implementation approach

Use a **two-layer regression suite**:

## Layer 1 — unit tests

Test narrow logic directly:

* `compute_timestamp_confidence(...)`
* `is_evidence_ml_eligible(...)`
* ML example filtering
* labeling task filtering
* rule example ref filtering

## Layer 2 — artifact-level integration test

Run the pipeline on the known validation lesson and assert the final exported JSON files satisfy all guarantees.

---

# Suggested test file layout

Create or update something close to this:

```text
tests/
  unit/
    test_timestamp_confidence.py
    test_ml_eligibility.py
    test_ml_manifest_filtering.py
    test_labeling_manifest_filtering.py
  integration/
    test_lesson2_artifact_regression.py
  fixtures/
    lesson2_expected_contract.md   # optional note file, not required
```

If your repo already has a test layout, use the existing conventions, but keep the logic split between unit and integration tests.

---

# Part 1: unit tests for confidence grading

## Goal

Protect the new confidence contract:

* `line` only when:

  * line bounds exist
  * anchors exist
  * `anchor_span_width <= 3`
  * `anchor_density >= 0.60`
* `span` for broader bounded localization
* `chunk` for fallback

## Required tests

Create `tests/unit/test_timestamp_confidence.py`

### Example test cases

```python
import pytest

from pipeline.component2.knowledge_builder import compute_timestamp_confidence


def test_line_confidence_for_compact_dense_span():
    result = compute_timestamp_confidence(
        source_line_start=10,
        source_line_end=12,
        transcript_anchors=["support", "resistance"],
        anchor_density=2 / 3,
    )
    assert result == "line"


def test_span_confidence_when_span_width_is_four():
    result = compute_timestamp_confidence(
        source_line_start=10,
        source_line_end=13,
        transcript_anchors=["support", "resistance"],
        anchor_density=0.50,
    )
    assert result == "span"


def test_span_confidence_when_density_is_too_low_for_line():
    result = compute_timestamp_confidence(
        source_line_start=10,
        source_line_end=12,
        transcript_anchors=["support"],
        anchor_density=1 / 3,
    )
    assert result == "span"


def test_chunk_confidence_when_line_bounds_missing():
    result = compute_timestamp_confidence(
        source_line_start=None,
        source_line_end=None,
        transcript_anchors=["support"],
        anchor_density=1.0,
    )
    assert result == "chunk"


def test_chunk_confidence_when_no_anchors():
    result = compute_timestamp_confidence(
        source_line_start=10,
        source_line_end=11,
        transcript_anchors=[],
        anchor_density=0.0,
    )
    assert result == "chunk"
```

## If helper is not importable

If `compute_timestamp_confidence` is currently buried inside a method or private block, do a **minimal refactor**:

* extract it into a small module-level function
* do not change behavior beyond making it testable

---

# Part 2: unit tests for ML eligibility

## Goal

Protect the contract that only these roles are ML-eligible:

* `positive_example`
* `negative_example`
* `counterexample`
* `ambiguous_example`

And specifically:

* `illustration` is **not** ML-eligible

## Required tests

Create `tests/unit/test_ml_eligibility.py`

```python
from pipeline.componentX.ml_manifest_builder import is_evidence_ml_eligible


def test_illustration_is_not_ml_eligible():
    evidence = {
        "example_role": "illustration",
        "linked_rule_ids": ["r1"],
        "source_event_ids": ["e1"],
    }
    assert is_evidence_ml_eligible(evidence) is False


def test_positive_example_is_ml_eligible():
    evidence = {
        "example_role": "positive_example",
        "linked_rule_ids": ["r1"],
        "source_event_ids": ["e1"],
    }
    assert is_evidence_ml_eligible(evidence) is True


def test_counterexample_is_ml_eligible():
    evidence = {
        "example_role": "counterexample",
        "linked_rule_ids": ["r1"],
        "source_event_ids": ["e1"],
    }
    assert is_evidence_ml_eligible(evidence) is True


def test_ml_eligibility_requires_linked_rule_ids():
    evidence = {
        "example_role": "positive_example",
        "linked_rule_ids": [],
        "source_event_ids": ["e1"],
    }
    assert is_evidence_ml_eligible(evidence) is False


def test_ml_eligibility_requires_source_event_ids():
    evidence = {
        "example_role": "positive_example",
        "linked_rule_ids": ["r1"],
        "source_event_ids": [],
    }
    assert is_evidence_ml_eligible(evidence) is False
```

Replace `componentX` with the real module path.

---

# Part 3: unit tests for ML manifest filtering

## Goal

Protect that `ml_manifest.examples` excludes non-ML-eligible evidence.

Create `tests/unit/test_ml_manifest_filtering.py`

```python
from pipeline.componentX.ml_manifest_builder import build_ml_examples


def test_build_ml_examples_excludes_illustrations():
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

    result = build_ml_examples(evidence_refs)

    assert [x["evidence_id"] for x in result] == ["ev2"]


def test_build_ml_examples_returns_empty_for_illustration_only_input():
    evidence_refs = [
        {
            "evidence_id": "ev1",
            "example_role": "illustration",
            "linked_rule_ids": ["r1"],
            "source_event_ids": ["e1"],
        }
    ]

    result = build_ml_examples(evidence_refs)

    assert result == []
```

---

# Part 4: unit tests for rule-side example refs

## Goal

Protect that `illustration` never populates:

* `positive_example_refs`
* `negative_example_refs`
* `ambiguous_example_refs`

Create a test in `tests/unit/test_ml_manifest_filtering.py` or separate file.

```python
from pipeline.componentX.ml_manifest_builder import attach_rule_example_refs


def test_attach_rule_example_refs_ignores_illustrations():
    rule = {"rule_id": "r1"}

    evidence_refs = [
        {
            "evidence_id": "ev1",
            "example_role": "illustration",
            "linked_rule_ids": ["r1"],
            "source_event_ids": ["e1"],
        }
    ]

    result = attach_rule_example_refs(rule, evidence_refs)

    assert result["positive_example_refs"] == []
    assert result["negative_example_refs"] == []
    assert result["ambiguous_example_refs"] == []


def test_attach_rule_example_refs_maps_roles_correctly():
    rule = {"rule_id": "r1"}

    evidence_refs = [
        {
            "evidence_id": "ev_pos",
            "example_role": "positive_example",
            "linked_rule_ids": ["r1"],
            "source_event_ids": ["e1"],
        },
        {
            "evidence_id": "ev_neg",
            "example_role": "negative_example",
            "linked_rule_ids": ["r1"],
            "source_event_ids": ["e2"],
        },
        {
            "evidence_id": "ev_cnt",
            "example_role": "counterexample",
            "linked_rule_ids": ["r1"],
            "source_event_ids": ["e3"],
        },
        {
            "evidence_id": "ev_amb",
            "example_role": "ambiguous_example",
            "linked_rule_ids": ["r1"],
            "source_event_ids": ["e4"],
        },
    ]

    result = attach_rule_example_refs(rule, evidence_refs)

    assert result["positive_example_refs"] == ["ev_pos"]
    assert sorted(result["negative_example_refs"]) == ["ev_cnt", "ev_neg"]
    assert result["ambiguous_example_refs"] == ["ev_amb"]
```

---

# Part 5: unit tests for labeling manifest filtering

## Goal

Protect that labeling tasks are created only from ML-eligible evidence.

Create `tests/unit/test_labeling_manifest_filtering.py`

```python
from pipeline.componentX.labeling_manifest_builder import build_labeling_tasks


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

If `build_labeling_tasks` currently depends on a larger context object, either:

* create a minimal test helper wrapper, or
* add a thin pure function for the filtering step and test that directly

Do not redesign the architecture.

---

# Part 6: artifact-level integration regression test

## Goal

Protect the exact final artifact guarantees on the known validation lesson:

* **Lesson 2. Levels part 1**

This is the most important test because it catches:

* stale writer regressions
* final export gate regressions
* cross-file link regressions
* missing Phase 2A fields
* semantic leakage into ML / labeling outputs

## Create

`tests/integration/test_lesson2_artifact_regression.py`

## Required behavior

This test should:

1. run the pipeline on the known lesson fixture or command path used in local runs
2. read the final artifact files
3. assert all guarantees directly

## Required assertions

Use logic equivalent to this:

```python
import json
from collections import Counter
from pathlib import Path


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_lesson2_final_artifacts_regression(run_lesson2_pipeline, lesson2_output_dir):
    """
    run_lesson2_pipeline:
        fixture that executes the pipeline for Lesson 2. Levels part 1

    lesson2_output_dir:
        fixture that returns Path to final output directory
    """
    run_lesson2_pipeline()

    base = lesson2_output_dir

    ke = load_json(base / "Lesson 2. Levels part 1.knowledge_events.json")
    rc = load_json(base / "Lesson 2. Levels part 1.rule_cards.json")
    ev = load_json(base / "Lesson 2. Levels part 1.evidence_index.json")
    ml = load_json(base / "Lesson 2. Levels part 1.ml_manifest.json")
    lb = load_json(base / "Lesson 2. Levels part 1.labeling_manifest.json")

    events = ke["events"]
    rules = rc["rules"]
    evidence = ev["evidence_refs"]
    ml_rules = ml["rules"]
    ml_examples = ml["examples"]
    label_tasks = lb.get("tasks", [])

    # knowledge_events.json: required Phase 2A fields
    assert events
    assert all("source_chunk_index" in e for e in events)
    assert all("source_line_start" in e for e in events)
    assert all("source_line_end" in e for e in events)
    assert all("source_quote" in e for e in events)
    assert all("transcript_anchors" in e for e in events)
    assert all("timestamp_confidence" in e for e in events)

    # no placeholder/empty normalized_text
    forbidden_normalized = {"", "No normalized text extracted."}
    assert not any((e.get("normalized_text") or "").strip() in forbidden_normalized for e in events)

    # no overly broad "line" confidence
    assert not any(
        e.get("timestamp_confidence") == "line" and (e.get("anchor_span_width") or 0) > 3
        for e in events
    )

    # rule_cards.json clean
    assert rules
    assert not any((r.get("rule_text") or "").strip() == "No rule text extracted." for r in rules)
    assert not any(not r.get("source_event_ids") for r in rules)

    # evidence_index.json linked
    assert not any(not x.get("linked_rule_ids") for x in evidence)
    assert not any(not x.get("source_event_ids") for x in evidence)

    # ml_manifest trainable-only
    assert not any(x.get("example_role") == "illustration" for x in ml_examples)

    # labeling_manifest conservative
    assert label_tasks == []

    # cross-file integrity
    event_ids = {e["event_id"] for e in events}
    rule_ids = {r["rule_id"] for r in rules}

    for rule in rules:
        assert set(rule.get("source_event_ids", [])).issubset(event_ids)

    for item in evidence:
        assert set(item.get("source_event_ids", [])).issubset(event_ids)
        assert set(item.get("linked_rule_ids", [])).issubset(rule_ids)

    # optional debug print for local visibility
    print("knowledge_events:", len(events), Counter(e["timestamp_confidence"] for e in events))
    print("rule_cards:", len(rules))
    print("evidence_index:", len(evidence), Counter(x["example_role"] for x in evidence))
    print("ml_manifest: rules=", len(ml_rules), "examples=", len(ml_examples))
    print("labeling_manifest:", len(label_tasks))
```

---

# Part 7: fixtures

## Goal

Make the integration test reproducible and stable.

If you already have an integration harness, reuse it.

If not, add fixtures in `tests/conftest.py` for:

* `run_lesson2_pipeline`
* `lesson2_output_dir`

### Required behavior of fixtures

* run the same entrypoint you use for local validation
* write outputs to a deterministic test output directory
* avoid reusing stale old outputs
* clean the output dir before execution

### Example shape

```python
from pathlib import Path
import shutil
import subprocess
import pytest


@pytest.fixture
def lesson2_output_dir(tmp_path):
    out = tmp_path / "output"
    out.mkdir(parents=True, exist_ok=True)
    return out


@pytest.fixture
def run_lesson2_pipeline(lesson2_output_dir):
    def _run():
        # replace with your real command
        cmd = [
            "python",
            "-m",
            "pipeline.run",
            "--lesson",
            "Lesson 2. Levels part 1",
            "--output-dir",
            str(lesson2_output_dir),
        ]
        subprocess.run(cmd, check=True)
    return _run
```

Adapt to your real entrypoint. The point is:

* deterministic output path
* clean run
* no stale artifact reuse

---

# Part 8: mark tests by speed

If the lesson-level integration test is slow, mark it clearly.

Use:

* fast unit tests by default
* integration test under a marker like `@pytest.mark.integration`

Example:

```python
import pytest

pytestmark = pytest.mark.integration
```

Then CI can run:

* unit tests on every change
* integration tests on protected branches or full validation runs

---

# Part 9: CI / command integration

Add or update commands so these are easy to run.

## Recommended commands

### unit only

```bash
pytest tests/unit -q
```

### lesson regression integration only

```bash
pytest tests/integration/test_lesson2_artifact_regression.py -q
```

### full regression

```bash
pytest tests/unit tests/integration/test_lesson2_artifact_regression.py -q
```

If your repo uses `make`, `poetry`, or `tox`, wire those in too.

Example:

```bash
make test-regression
```

---

# Part 10: acceptance criteria

This task is complete only if all of the following are true:

## Code/test criteria

* unit tests added for:

  * timestamp confidence
  * ML eligibility
  * ML example filtering
  * rule example ref filtering
  * labeling filtering
* one artifact-level integration regression test added for Lesson 2

## behavioral criteria

* the new tests fail if:

  * Phase 2A fields disappear
  * placeholder rules reappear
  * evidence backlinks become empty
  * `illustration` leaks into `ml_manifest.examples`
  * labeling tasks appear for illustration-only evidence
  * `line` confidence is assigned to spans wider than 3 lines

## execution criteria

* tests pass on the current good baseline
* integration test runs from a clean output directory
* no dependency on stale manual outputs

---

# Minimal refactors allowed

These are allowed only if necessary for testability:

* extract `compute_timestamp_confidence(...)` into an importable helper
* extract ML filtering into importable helper
* extract labeling filtering into importable helper

These are **not** allowed:

* changing business logic beyond current intended behavior
* redesigning builders
* changing artifact schemas

---

# Short version to paste to the agent

```text
Add regression tests to lock the current good behavior.

Create:
- unit tests for compute_timestamp_confidence
- unit tests for is_evidence_ml_eligible
- unit tests for build_ml_examples filtering
- unit tests for attach_rule_example_refs
- unit tests for build_labeling_tasks filtering
- one integration test that runs Lesson 2. Levels part 1 and validates final artifacts

The integration test must assert:
- knowledge_events has all Phase 2A fields
- no empty/placeholder normalized_text
- no line-confidence event with anchor_span_width > 3
- rule_cards has no placeholder rule_text
- rule_cards has no empty source_event_ids
- evidence_index has no empty linked_rule_ids
- evidence_index has no empty source_event_ids
- ml_manifest.examples contains no illustration rows
- labeling_manifest.tasks == []
- all rule->event and evidence->event/rule links resolve

Use a clean deterministic output directory for the integration test.
Do not redesign the pipeline. Only add tests and tiny extraction refactors needed for importability.
```

**Confidence: High** — this is the right next hardening step, and these tests directly protect the guarantees you just stabilized.
