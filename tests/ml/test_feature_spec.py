"""Tests for ML Step 7 feature spec."""

from __future__ import annotations

from pathlib import Path

import pytest

from ml.feature_spec_loader import FeatureSpecError, load_feature_spec

ML = Path(__file__).resolve().parents[2] / "src" / "ml"


def test_feature_spec_loads() -> None:
    spec = load_feature_spec(ML / "feature_spec.yaml")
    assert spec["task_id"] == "level_interaction_rule_satisfaction_v1"
    assert len(spec["features"]) >= 10


def test_no_duplicate_names() -> None:
    spec = load_feature_spec(ML / "feature_spec.yaml")
    names = [f["feature_name"] for f in spec["features"]]
    assert len(names) == len(set(names))


def test_all_pit_safe() -> None:
    spec = load_feature_spec(ML / "feature_spec.yaml")
    for f in spec["features"]:
        assert f["point_in_time_safe"] is True


def test_linked_concepts_format() -> None:
    spec = load_feature_spec(ML / "feature_spec.yaml")
    for f in spec["features"]:
        lc = f["linked_rule_concepts"]
        assert isinstance(lc, list)


def test_invalid_spec_rejected(tmp_path: Path) -> None:
    p = tmp_path / "bad.yaml"
    p.write_text(
        "spec_id: x\nfeatures:\n  - feature_name: a\n    feature_family: f\n    dtype: float\n"
        "    description: d\n    required_inputs: []\n    optional_inputs: []\n    formula_summary: x\n"
        "    point_in_time_safe: false\n    null_policy: n\n    default_behavior: '0'\n"
        "    linked_rule_concepts: []\n    notes: ''\n",
        encoding="utf-8",
    )
    with pytest.raises(FeatureSpecError):
        load_feature_spec(p)
