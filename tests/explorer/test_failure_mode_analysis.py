"""Failure-mode analysis."""

from __future__ import annotations

from pathlib import Path

import pytest

from ml.step9.evidence_loader import load_step9_decision_config
from ml.step9.failure_mode_analysis import (
    analyze_failure_modes,
    build_class_stability_report,
    build_regime_breakdown_report,
)

REPO = Path(__file__).resolve().parents[2]


def _fold(f1: float, support_by_class: dict[str, float]) -> dict:
    cr = {"macro avg": {"f1-score": f1, "precision": 0, "recall": 0, "support": 0}}
    for c, s in support_by_class.items():
        cr[c] = {"precision": 0.1, "recall": 0.1, "f1-score": 0.1, "support": float(s)}
    return {
        "fold_id": "f",
        "models": {
            "logistic_regression": {
                "accuracy": 0.5,
                "classification_report": cr,
            }
        },
    }


def _raw_bundle(
    *,
    drift: bool,
    folds: list[dict],
    weak: list[dict],
    pol_bullets: list[str],
) -> dict:
    return {
        "walkforward_report": {
            "answers": {
                "which_classes_remain_weak": weak,
                "calibration_forward_behavior": {"flag_potential_drift_raw_brier": drift, "plain_language": "t"},
            }
        },
        "fold_metrics": {"fold_metrics": folds},
        "model_comparison_report": {"symbolic": {}, "logistic_regression": {}},
        "calibration_drift_report": {"drift_heuristic": None, "n_folds_with_metrics": len(folds)},
        "policy_report": {"summary_bullets": pol_bullets},
        "step8_manifest": {"counts": {"prediction_lines": 100}, "artifacts": {}},
        "backtest_predictions": [{}] * 50,
    }


def test_weak_class_and_low_support_detection() -> None:
    cfg = load_step9_decision_config(REPO / "src" / "ml" / "step9_decision_config.yaml")
    raw = _raw_bundle(
        drift=False,
        folds=[_fold(0.5, {"a": 1.0, "b": 5.0})],
        weak=[{"class": "a", "mean_f1_across_folds": 0.1, "n_folds": 1}],
        pol_bullets=["fold_0: hit_rate=0.5"],
    )
    rep = analyze_failure_modes(cfg, raw, REPO)
    assert any("a" in str(x) for x in rep["class_level"]["low_support_class_labels"]) or "a" in rep["class_level"]["low_support_class_labels"]


def test_unstable_fold_range() -> None:
    cfg = load_step9_decision_config(REPO / "src" / "ml" / "step9_decision_config.yaml")
    folds = [
        _fold(0.9, {"c": 10.0}),
        _fold(0.2, {"c": 10.0}),
    ]
    raw = _raw_bundle(drift=False, folds=folds, weak=[], pol_bullets=["hit_rate=0.5"])
    rep = analyze_failure_modes(cfg, raw, REPO)
    assert rep["fold_level"]["macro_f1_range"] == pytest.approx(0.7)


def test_calibration_risk_flag() -> None:
    cfg = load_step9_decision_config(REPO / "src" / "ml" / "step9_decision_config.yaml")
    raw = _raw_bundle(drift=True, folds=[_fold(0.5, {"c": 10.0})], weak=[], pol_bullets=["hit_rate=0.5"])
    rep = analyze_failure_modes(cfg, raw, REPO)
    assert rep["calibration_level"]["drift_flag"] is True


def test_policy_low_utility() -> None:
    cfg = load_step9_decision_config(REPO / "src" / "ml" / "step9_decision_config.yaml")
    raw = _raw_bundle(
        drift=False,
        folds=[_fold(0.5, {"c": 10.0})],
        weak=[],
        pol_bullets=["fold_0: best policy key=x hit_rate=0.05"],
    )
    rep = analyze_failure_modes(cfg, raw, REPO)
    assert rep["policy_level"]["policies_likely_low_utility"] is True


def test_regime_and_class_stability_reports() -> None:
    cfg = load_step9_decision_config(REPO / "src" / "ml" / "step9_decision_config.yaml")
    raw = _raw_bundle(
        drift=False,
        folds=[_fold(0.5, {"a": 10.0, "b": 10.0}), _fold(0.4, {"a": 10.0, "b": 10.0})],
        weak=[],
        pol_bullets=["hit_rate=0.5"],
    )
    failure = analyze_failure_modes(cfg, raw, REPO)
    reg = build_regime_breakdown_report(cfg, raw, failure)
    assert reg["regime_breakdown_report_id"] == "regime_breakdown_v1"
    assert "interpretation" in reg
    cs = build_class_stability_report(cfg, raw)
    assert cs["class_stability_report_id"] == "class_stability_v1"
    assert len(cs["per_class"]) >= 1
