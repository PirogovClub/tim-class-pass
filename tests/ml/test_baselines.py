"""Tests for Step 7 baselines."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression

from ml.baselines.symbolic_baseline import symbolic_predict, evaluate
from ml.baselines.train_tabular_baseline import _load_rows

from tests.ml.step7_audit_fixtures import modeling_rows_from_committed_step6

ROOT = Path(__file__).resolve().parents[2]


def test_symbolic_predict_returns_class() -> None:
    feats = {
        "close_distance_pct": 0.01,
        "n_closes_above_level_pre": 3,
        "persistence_ratio_above_pre": 0.4,
        "upper_wick_ratio_anchor": 0.1,
        "lower_wick_ratio_anchor": 0.1,
        "n_closes_below_level_pre": 0,
        "reentry_through_level_pre": 0,
    }
    lab = symbolic_predict(feats)
    assert lab in (
        "acceptance_above",
        "acceptance_below",
        "false_breakout_up",
        "false_breakout_down",
        "rejection",
        "no_setup",
    )


def test_symbolic_fallback_no_setup() -> None:
    feats = {k: 0 for k in ("close_distance_pct", "upper_wick_ratio_anchor", "lower_wick_ratio_anchor")}
    feats.update(
        {
            "n_closes_above_level_pre": 0,
            "n_closes_below_level_pre": 0,
            "persistence_ratio_above_pre": 0,
            "reentry_through_level_pre": 0,
        }
    )
    assert symbolic_predict(feats) == "no_setup"


def test_symbolic_evaluate_runs_on_fixture_modeling_rows() -> None:
    rows, _ = modeling_rows_from_committed_step6(include_weak_in_training=True)
    rep = evaluate(rows)
    assert "accuracy" in rep
    assert "confusion_matrix" in rep


def test_logreg_fits_on_fixture_eligible_rows() -> None:
    rows, _ = modeling_rows_from_committed_step6(include_weak_in_training=True)
    elig = [r for r in rows if r.get("eligible_for_training")]
    assert len(elig) >= 4, "fixture must yield enough trainable rows for baseline smoke test"
    X = np.array([[r["features"].get("close_distance_pct", 0)] for r in elig], dtype=float)
    y = np.array([0] * (len(elig) // 2) + [1] * (len(elig) - len(elig) // 2), dtype=int)[: len(elig)]
    clf = LogisticRegression(max_iter=200)
    clf.fit(X, y)
    assert clf.predict_proba(X).shape[1] == 2


def test_optional_ml_output_step7_dataset_if_present() -> None:
    p = ROOT / "ml_output" / "step7" / "modeling_dataset.jsonl"
    if not p.is_file():
        return
    rows = _load_rows(p)
    rep = evaluate(rows)
    assert "accuracy" in rep
