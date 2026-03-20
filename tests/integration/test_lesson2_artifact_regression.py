"""
Lesson 2 artifact regression (12-phase2 Part 6).

6a — Read-only (fast CI default): If the JSON artifacts exist under
data/Lesson 2. Levels part 1/output_intermediate/, run assertions;
pytest.skip if any file is missing.

6b — Full regression: Use fixtures run_lesson2_pipeline and lesson2_output_dir;
run only when RUN_LESSON2_REGRESSION=1 (slow, requires API keys).

Run: pytest tests/integration -m integration -q
     pytest tests/unit tests/integration -m integration -q
"""

import json
import os
from collections import Counter
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

_REPO_ROOT = Path(__file__).resolve().parents[2]
_LESSON2_BASE = _REPO_ROOT / "data" / "Lesson 2. Levels part 1" / "output_intermediate"
_ARTIFACT_NAMES = [
    "Lesson 2. Levels part 1.knowledge_events.json",
    "Lesson 2. Levels part 1.rule_cards.json",
    "Lesson 2. Levels part 1.evidence_index.json",
    "Lesson 2. Levels part 1.ml_manifest.json",
    "Lesson 2. Levels part 1.labeling_manifest.json",
]
_LESSON2_PREFIX = "Lesson 2. Levels part 1"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _assert_lesson2_artifacts(base: Path) -> None:
    """Shared Phase 2A assertion block (brief lines 479-564)."""
    ke = load_json(base / f"{_LESSON2_PREFIX}.knowledge_events.json")
    rc = load_json(base / f"{_LESSON2_PREFIX}.rule_cards.json")
    ev = load_json(base / f"{_LESSON2_PREFIX}.evidence_index.json")
    ml = load_json(base / f"{_LESSON2_PREFIX}.ml_manifest.json")
    lb = load_json(base / f"{_LESSON2_PREFIX}.labeling_manifest.json")

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

    forbidden_normalized = {"", "No normalized text extracted."}
    assert not any(
        (e.get("normalized_text") or "").strip() in forbidden_normalized for e in events
    )

    assert not any(
        e.get("timestamp_confidence") == "line"
        and (e.get("anchor_span_width") or 0) > 3
        for e in events
    )

    assert rules
    assert not any(
        (r.get("rule_text") or "").strip() == "No rule text extracted." for r in rules
    )
    assert not any(not r.get("source_event_ids") for r in rules)

    assert not any(not x.get("linked_rule_ids") for x in evidence)
    assert not any(not x.get("source_event_ids") for x in evidence)

    assert not any(x.get("example_role") == "illustration" for x in ml_examples)

    assert label_tasks == []

    event_ids = {e["event_id"] for e in events}
    rule_ids = {r["rule_id"] for r in rules}

    for rule in rules:
        assert set(rule.get("source_event_ids", [])).issubset(event_ids)

    for item in evidence:
        assert set(item.get("source_event_ids", [])).issubset(event_ids)
        assert set(item.get("linked_rule_ids", [])).issubset(rule_ids)

    print("knowledge_events:", len(events), Counter(e["timestamp_confidence"] for e in events))
    print("rule_cards:", len(rules))
    print("evidence_index:", len(evidence), Counter(x["example_role"] for x in evidence))
    print("ml_manifest: rules=", len(ml_rules), "examples=", len(ml_examples))
    print("labeling_manifest:", len(label_tasks))


def test_lesson2_final_artifacts_regression():
    """6a: Assert Phase 2A guarantees on existing Lesson 2 artifacts; skip if any missing."""
    if not _LESSON2_BASE.is_dir():
        pytest.skip("Lesson 2 output_intermediate directory not found")
    for name in _ARTIFACT_NAMES:
        if not (_LESSON2_BASE / name).is_file():
            pytest.skip(f"Missing artifact: {name}")

    _assert_lesson2_artifacts(_LESSON2_BASE)


def test_lesson2_final_artifacts_regression_full(run_lesson2_pipeline, lesson2_output_dir):
    """6b: Run pipeline then assert Phase 2A guarantees. Run only when RUN_LESSON2_REGRESSION=1."""
    if os.environ.get("RUN_LESSON2_REGRESSION") != "1":
        pytest.skip("Set RUN_LESSON2_REGRESSION=1 to run full Lesson 2 pipeline regression")

    run_lesson2_pipeline()
    _assert_lesson2_artifacts(lesson2_output_dir)
