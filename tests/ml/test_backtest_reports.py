"""Report / manifest consistency."""

from __future__ import annotations

from pathlib import Path

from ml.backtest.report_builder import (
    build_model_comparison_report,
    build_step8_manifest,
    build_walkforward_report,
)


def test_model_comparison_skips_non_metric_blocks() -> None:
    fold_metrics = [
        {
            "fold_id": "fold_000",
            "models": {
                "symbolic": {"accuracy": 0.5, "classification_report": {"macro avg": {"f1-score": 0.4}}},
                "logistic_regression_calibrated": {"note": "skipped"},
            },
        }
    ]
    mc = build_model_comparison_report(fold_metrics)
    assert "symbolic" in mc
    assert mc["symbolic"]["n_folds"] == 1


def test_manifest_counts_align(tmp_path: Path) -> None:
    cfg = {"task_id": "t1", "outputs": {"a": "x.json"}, "pit_declaration": "pit"}
    m = build_step8_manifest(
        out_dir=tmp_path,
        cfg=cfg,
        artifact_paths={"a": str(tmp_path / "x.json")},
        fold_metrics=[{"fold_id": "f0", "models": {}}],
        n_prediction_lines=3,
    )
    assert m["counts"]["folds"] == 1
    assert m["counts"]["prediction_lines"] == 3


def test_walkforward_report_lists_folds(tmp_path: Path) -> None:
    folds_payload = {"skipped_fold_reasons": ["none"]}
    fm = [
        {
            "fold_id": "fold_000",
            "models": {
                "symbolic": {
                    "accuracy": 0.2,
                    "classification_report": {"macro avg": {"f1-score": 0.15}},
                },
                "logistic_regression": {
                    "accuracy": 0.3,
                    "classification_report": {"macro avg": {"f1-score": 0.25}},
                },
            },
        }
    ]
    rep = build_walkforward_report(
        task_id="t1",
        folds_payload=folds_payload,
        fold_metrics=fm,
        policy_aggregate={"summary_bullets": ["p1"]},
        pit_declaration="safe",
    )
    assert rep["n_folds_evaluated"] == 1
    assert rep["answers"]["how_many_folds"] == 1
