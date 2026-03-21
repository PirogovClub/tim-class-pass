"""
Lesson 2 artifact regression (Task 14).

6a -- Read-only (fast CI default): If the JSON artifacts exist under
data/Lesson 2. Levels part 1/output_intermediate/, run assertions;
pytest.skip if any file is missing.

6b -- Full regression: Use fixtures run_lesson2_pipeline and lesson2_output_dir;
run only when RUN_LESSON2_REGRESSION=1 (slow, requires API keys).

Run: pytest tests/integration -m integration -q
"""

from __future__ import annotations

import os
from collections import Counter
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from regression_helpers import (
    artifact_paths_for_lesson,
    assert_canonical_ids_on_events,
    assert_canonical_ids_on_evidence,
    assert_canonical_ids_on_rules,
    assert_concept_graph_structure,
    assert_cross_file_integrity,
    assert_evidence_backlinks,
    assert_knowledge_events_clean,
    assert_markdown_quality,
    assert_ml_safety,
    assert_rule_cards_provenance,
    load_json,
)

pytestmark = pytest.mark.integration

_REPO_ROOT = Path(__file__).resolve().parents[2]
_LESSON2_DIR = _REPO_ROOT / "data" / "Lesson 2. Levels part 1"
_LESSON2_INTERMEDIATE = _LESSON2_DIR / "output_intermediate"
_LESSON2_PREFIX = "Lesson 2. Levels part 1"

_ARTIFACT_NAMES = [
    f"{_LESSON2_PREFIX}.knowledge_events.json",
    f"{_LESSON2_PREFIX}.rule_cards.json",
    f"{_LESSON2_PREFIX}.evidence_index.json",
    f"{_LESSON2_PREFIX}.concept_graph.json",
    f"{_LESSON2_PREFIX}.ml_manifest.json",
    f"{_LESSON2_PREFIX}.labeling_manifest.json",
]


def _skip_if_missing() -> None:
    if not _LESSON2_INTERMEDIATE.is_dir():
        pytest.skip("Lesson 2 output_intermediate directory not found")
    for name in _ARTIFACT_NAMES:
        if not (_LESSON2_INTERMEDIATE / name).is_file():
            pytest.skip(f"Missing artifact: {name}")


def _load_all(base: Path) -> tuple:
    ke = load_json(base / f"{_LESSON2_PREFIX}.knowledge_events.json")
    rc = load_json(base / f"{_LESSON2_PREFIX}.rule_cards.json")
    ev = load_json(base / f"{_LESSON2_PREFIX}.evidence_index.json")
    ml = load_json(base / f"{_LESSON2_PREFIX}.ml_manifest.json")
    lb = load_json(base / f"{_LESSON2_PREFIX}.labeling_manifest.json")
    cg = load_json(base / f"{_LESSON2_PREFIX}.concept_graph.json")
    return ke, rc, ev, ml, lb, cg


def _assert_lesson2_artifacts(base: Path) -> None:
    """Run all A-H regression checks for Lesson 2."""
    ke, rc, ev, ml, lb, cg = _load_all(base)

    events = ke["events"]
    rules = rc["rules"]
    evidence = ev["evidence_refs"]
    ml_examples = ml["examples"]
    label_tasks = lb.get("tasks", [])

    # A: structured artifact existence (checked before entry)

    # B: rule cards provenance
    assert_rule_cards_provenance(rules)

    # C: knowledge events clean + D: timestamp confidence
    assert_knowledge_events_clean(events)

    # E: evidence backlinks
    assert_evidence_backlinks(evidence)

    # F: ML safety guard
    assert_ml_safety(ml_examples, label_tasks, ml.get("rules", []))

    # A+: concept graph structure
    assert_concept_graph_structure(cg)
    assert len(cg["nodes"]) > 0, "Lesson 2 concept graph should have nodes"

    # G: markdown quality
    rag_path = base.parent / "output_rag_ready" / f"{_LESSON2_PREFIX}.rag_ready.md"
    assert_markdown_quality(rag_path)

    # H: cross-file integrity
    assert_cross_file_integrity(events, rules, evidence)

    # I: canonical ID fields
    assert_canonical_ids_on_events(events)
    assert_canonical_ids_on_rules(rules)
    assert_canonical_ids_on_evidence(evidence)

    print("knowledge_events:", len(events), Counter(e["timestamp_confidence"] for e in events))
    print("rule_cards:", len(rules))
    print("evidence_index:", len(evidence), Counter(x["example_role"] for x in evidence))
    print("ml_manifest: rules=", len(ml.get("rules", [])), "examples=", len(ml_examples))
    print("labeling_manifest:", len(label_tasks))
    print("concept_graph: nodes=", len(cg["nodes"]), "relations=", len(cg["relations"]))


def test_lesson2_final_artifacts_regression():
    """6a: Assert all A-H guarantees on existing Lesson 2 artifacts; skip if any missing."""
    _skip_if_missing()
    _assert_lesson2_artifacts(_LESSON2_INTERMEDIATE)


def test_lesson2_final_artifacts_regression_full(run_lesson2_pipeline, lesson2_output_dir):
    """6b: Run pipeline then assert all guarantees. Run only when RUN_LESSON2_REGRESSION=1."""
    if os.environ.get("RUN_LESSON2_REGRESSION") != "1":
        pytest.skip("Set RUN_LESSON2_REGRESSION=1 to run full Lesson 2 pipeline regression")

    run_lesson2_pipeline()
    _assert_lesson2_artifacts(lesson2_output_dir)
