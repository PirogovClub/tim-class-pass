"""Calibration drift report."""

from __future__ import annotations

from ml.backtest.calibration_drift import build_calibration_drift_report, summarize_fold_calibration


def test_drift_report_empty_summaries() -> None:
    r = build_calibration_drift_report([])
    assert r["n_folds_with_metrics"] == 0
    assert r["brier_raw"]["mean"] is None


def test_summarize_fold_calibration_shape() -> None:
    s = summarize_fold_calibration(
        "fold_000",
        y_true_idx=[0, 1],
        proba_raw=[[0.9, 0.1], [0.2, 0.8]],
        proba_cal=None,
        class_order=["a", "b"],
        bucket_report_raw={"buckets": [], "n_bins": 4},
        bucket_report_cal=None,
        brier_raw=0.25,
        brier_cal=None,
    )
    assert s["fold_id"] == "fold_000"
    assert s["brier_raw"] == 0.25
