"""
Sviatoslav lesson artifact regression (Task 14).

Read-only: If the JSON artifacts exist under
data/2025-09-29-sviatoslav-chornyi/output_intermediate/, run all A-H assertions;
pytest.skip if any file is missing.

This lesson is the primary regression target for:
  - generic teaching slide downgrades
  - weak-specificity evidence not leaking into ML outputs
  - concept graph generation

Run: pytest tests/integration -m integration -q
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from regression_helpers import (
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
    collect_all_rule_example_refs,
    load_json,
)

pytestmark = pytest.mark.integration

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SV_DIR = _REPO_ROOT / "data" / "2025-09-29-sviatoslav-chornyi"
_SV_INTERMEDIATE = _SV_DIR / "output_intermediate"
_SV_PREFIX = "2025-09-29-sviatoslav-chornyi"

_ARTIFACT_NAMES = [
    f"{_SV_PREFIX}.knowledge_events.json",
    f"{_SV_PREFIX}.rule_cards.json",
    f"{_SV_PREFIX}.evidence_index.json",
    f"{_SV_PREFIX}.concept_graph.json",
    f"{_SV_PREFIX}.ml_manifest.json",
    f"{_SV_PREFIX}.labeling_manifest.json",
]


def _skip_if_missing() -> None:
    if not _SV_INTERMEDIATE.is_dir():
        pytest.skip("Sviatoslav output_intermediate directory not found")
    for name in _ARTIFACT_NAMES:
        if not (_SV_INTERMEDIATE / name).is_file():
            pytest.skip(f"Missing artifact: {name}")


def _load_all():
    base = _SV_INTERMEDIATE
    ke = load_json(base / f"{_SV_PREFIX}.knowledge_events.json")
    rc = load_json(base / f"{_SV_PREFIX}.rule_cards.json")
    ev = load_json(base / f"{_SV_PREFIX}.evidence_index.json")
    ml = load_json(base / f"{_SV_PREFIX}.ml_manifest.json")
    lb = load_json(base / f"{_SV_PREFIX}.labeling_manifest.json")
    cg = load_json(base / f"{_SV_PREFIX}.concept_graph.json")
    return ke, rc, ev, ml, lb, cg


def test_sviatoslav_artifact_existence():
    """A: All structured artifacts and markdown outputs exist."""
    _skip_if_missing()
    rag_path = _SV_DIR / "output_rag_ready" / f"{_SV_PREFIX}.rag_ready.md"
    review_path = _SV_DIR / "output_review" / f"{_SV_PREFIX}.review_markdown.md"
    assert rag_path.is_file(), f"Missing: {rag_path.name}"
    assert review_path.is_file(), f"Missing: {review_path.name}"


def test_sviatoslav_knowledge_events_clean():
    """B/C/D: Knowledge events have Phase 2A fields, no placeholders, valid timestamp confidence."""
    _skip_if_missing()
    ke, *_ = _load_all()
    assert_knowledge_events_clean(ke["events"])


def test_sviatoslav_rule_cards_provenance():
    """B: Rule cards have provenance, no placeholder rule_text."""
    _skip_if_missing()
    _, rc, *_ = _load_all()
    assert_rule_cards_provenance(rc["rules"])


def test_sviatoslav_evidence_backlinks():
    """E: Every evidence row has linked_rule_ids and source_event_ids."""
    _skip_if_missing()
    _, _, ev, *_ = _load_all()
    assert_evidence_backlinks(ev["evidence_refs"])


def test_sviatoslav_ml_safety_guard():
    """F: No illustration or weak-specificity evidence in ML outputs."""
    _skip_if_missing()
    _, _, _, ml, lb, _ = _load_all()
    ml_examples = ml["examples"]
    label_tasks = lb.get("tasks", [])

    assert_ml_safety(ml_examples, label_tasks, ml.get("rules", []))


def test_sviatoslav_weak_specificity_in_evidence_not_in_ml():
    """F+: Evidence with generic_teaching_visual exists in evidence_index but NOT in ML outputs."""
    _skip_if_missing()
    _, _, ev, ml, lb, _ = _load_all()

    weak_evidence_ids = {
        x["evidence_id"]
        for x in ev["evidence_refs"]
        if (x.get("metadata", {}).get("promotion_reason") or "").lower()
        in ("generic_teaching_visual", "insufficient_visual_specificity")
    }
    assert weak_evidence_ids, (
        "Expected at least one evidence row with weak promotion_reason in evidence_index"
    )

    ml_evidence_ids = {ex["evidence_id"] for ex in ml["examples"]}
    leaked = weak_evidence_ids & ml_evidence_ids
    assert not leaked, f"Weak evidence leaked into ml_manifest.examples: {leaked}"

    task_evidence_ids = {t["evidence_id"] for t in lb.get("tasks", [])}
    leaked_tasks = weak_evidence_ids & task_evidence_ids
    assert not leaked_tasks, f"Weak evidence leaked into labeling_manifest.tasks: {leaked_tasks}"


def test_sviatoslav_concept_graph_structure():
    """A+: Concept graph has valid structure, non-empty nodes and relations."""
    _skip_if_missing()
    *_, cg = _load_all()
    assert_concept_graph_structure(cg)
    assert len(cg["nodes"]) > 0, "Concept graph should have nodes"
    assert len(cg["relations"]) > 0, "Concept graph should have relations"


def test_sviatoslav_concept_graph_nodes_deduplicated():
    """Concept graph nodes are deduplicated by concept_id."""
    _skip_if_missing()
    *_, cg = _load_all()
    seen = set()
    for node in cg["nodes"]:
        cid = node.get("concept_id")
        assert cid not in seen, f"Duplicate concept graph node: {cid}"
        seen.add(cid)


def test_sviatoslav_markdown_quality():
    """G: RAG markdown is not spammy, preserves timestamps."""
    _skip_if_missing()
    rag_path = _SV_DIR / "output_rag_ready" / f"{_SV_PREFIX}.rag_ready.md"
    assert_markdown_quality(rag_path)


def test_sviatoslav_cross_file_integrity():
    """H: All cross-file references resolve between events, rules, and evidence."""
    _skip_if_missing()
    ke, rc, ev, *_ = _load_all()
    assert_cross_file_integrity(ke["events"], rc["rules"], ev["evidence_refs"])


def test_sviatoslav_canonical_ids():
    """I: Canonical ID fields populated on events, rules, and evidence."""
    _skip_if_missing()
    ke, rc, ev, *_ = _load_all()
    assert_canonical_ids_on_events(ke["events"])
    assert_canonical_ids_on_rules(rc["rules"])
    assert_canonical_ids_on_evidence(ev["evidence_refs"])
