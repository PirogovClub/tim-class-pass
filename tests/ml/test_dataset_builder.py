"""Tests for modeling dataset builder."""

from __future__ import annotations

import json
from pathlib import Path

from ml.dataset_builder import TRAINABLE_TIERS, build_modeling_rows, _is_eligible, compute_step6_integrity
from ml.split_builder import SPLIT_POLICY_LESSON_GROUP, assign_splits
from ml.feature_spec_loader import load_feature_spec

from tests.ml.step7_audit_fixtures import (
    STEP6_DIR,
    load_step6_fixture_labels,
    modeling_rows_from_committed_step6,
)

ML = Path(__file__).resolve().parents[2] / "src" / "ml"
FIX = ML / "fixtures" / "market_windows"


def _windows() -> dict[str, dict]:
    out = {}
    for p in FIX.glob("*.json"):
        w = json.loads(p.read_text(encoding="utf-8"))
        out[str(w.get("candidate_id", p.stem))] = w
    return out


def test_consumes_step6_labels_from_committed_fixture() -> None:
    """End-to-end: committed Step 6 JSONL + bundled market windows -> modeling rows."""
    labels = load_step6_fixture_labels()
    spec = load_feature_spec(ML / "feature_spec.yaml")
    max_lb = int(spec["observation_window"]["max_lookback_bars"])
    task_id = labels[0].get("task_id", "level_interaction_rule_satisfaction_v1")
    rows, summary = build_modeling_rows(
        labels,
        _windows(),
        task_id=task_id,
        max_lookback_bars=max_lb,
        apply_splits=True,
        include_weak_in_training=True,
    )
    assert len(rows) >= 10
    assert summary["eligible_for_training"] >= 1
    for r in rows:
        assert "dataset_row_id" in r
        assert "features" in r

    lbl_path = STEP6_DIR / "generated_labels.jsonl"
    integrity = compute_step6_integrity(lbl_path, labels, rows, task_id)
    assert integrity["checks_passed"] is True


def test_eligible_policy_gold_silver_only() -> None:
    lab = {
        "candidate_id": "x",
        "status": "assigned",
        "confidence_tier": "weak",
        "label": "no_setup",
        "point_in_time_safe": True,
    }
    assert not _is_eligible(lab, tiers=TRAINABLE_TIERS)
    lab["confidence_tier"] = "gold"
    assert _is_eligible(lab, tiers=TRAINABLE_TIERS)


def test_ambiguous_not_trainable_by_tier_gate() -> None:
    lab = {
        "candidate_id": "x",
        "status": "ambiguous",
        "confidence_tier": "silver",
        "label": "ambiguous",
        "point_in_time_safe": True,
    }
    assert not _is_eligible(lab, tiers=TRAINABLE_TIERS)


def test_step6_integrity_with_sidecars(tmp_path: Path) -> None:
    lbl = tmp_path / "generated_labels.jsonl"
    lbl.write_text("{}\n{}\n", encoding="utf-8")
    (tmp_path / "label_dataset_manifest.json").write_text(
        json.dumps({"task_id": "t_match", "row_count": 2}),
        encoding="utf-8",
    )
    (tmp_path / "label_generation_report.json").write_text(
        json.dumps({"task_id": "t_match", "row_count": 2}),
        encoding="utf-8",
    )
    labels = [{}, {}]
    integrity = compute_step6_integrity(lbl, labels, [{}], "t_match")
    assert integrity["checks_passed"] is True
    assert integrity["label_generation_report_present"] is True
    assert integrity["label_dataset_manifest_present"] is True
    assert any("modeling rows" in w for w in integrity["warnings"])


def test_lesson_group_same_split_within_lesson() -> None:
    rows = [
        {
            "eligible_for_training": True,
            "anchor_timestamp": "2020-01-01T00:00:00Z",
            "candidate_id": "c0",
            "split": "none",
            "source_refs": {"lesson_id": "L1"},
        },
        {
            "eligible_for_training": True,
            "anchor_timestamp": "2020-01-02T00:00:00Z",
            "candidate_id": "c1",
            "split": "none",
            "source_refs": {"lesson_id": "L1"},
        },
        {
            "eligible_for_training": True,
            "anchor_timestamp": "2020-01-03T00:00:00Z",
            "candidate_id": "c2",
            "split": "none",
            "source_refs": {"lesson_id": "L2"},
        },
        {
            "eligible_for_training": True,
            "anchor_timestamp": "2020-01-04T00:00:00Z",
            "candidate_id": "c3",
            "split": "none",
            "source_refs": {"lesson_id": "L2"},
        },
    ]
    assign_splits(rows, policy=SPLIT_POLICY_LESSON_GROUP)
    assert rows[0]["split"] == rows[1]["split"]
    assert rows[2]["split"] == rows[3]["split"]


def test_split_counts_sum() -> None:
    rows, _ = modeling_rows_from_committed_step6(include_weak_in_training=True)
    elig = [r for r in rows if r["eligible_for_training"]]
    splits = [r["split"] for r in elig]
    assert sum(1 for s in splits if s == "train") >= 1
    assert all(s in ("train", "validation", "test", "none") for s in splits)


def test_optional_repo_step6_sample_aligned_with_fixture_if_present() -> None:
    """If ml_output/step6_sample exists with the same row count as the committed fixture, task_id should match."""
    labels_path = Path(__file__).resolve().parents[2] / "ml_output" / "step6_sample" / "generated_labels.jsonl"
    if not labels_path.is_file():
        return
    from_repo = [json.loads(l) for l in labels_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    from_fix = load_step6_fixture_labels()
    if len(from_repo) != len(from_fix):
        return
    assert from_repo[0].get("task_id") == from_fix[0].get("task_id")
