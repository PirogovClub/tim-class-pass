"""Model-family decider outcomes."""

from __future__ import annotations

import copy
from pathlib import Path

from ml.step9.evidence_loader import load_step9_decision_config
from ml.step9.failure_mode_analysis import analyze_failure_modes
from ml.step9.model_family_decider import decide_model_family

REPO = Path(__file__).resolve().parents[2]


def _mc(sym: float, lr: float, lr_sd: float) -> dict:
    return {
        "symbolic": {"macro_f1_mean": sym, "macro_f1_pstdev": 0.0, "n_folds": 3},
        "logistic_regression": {"macro_f1_mean": lr, "macro_f1_pstdev": lr_sd, "n_folds": 3},
    }


def _fold(f1: float) -> dict:
    cr = {"macro avg": {"f1-score": f1, "precision": 0, "recall": 0, "support": 20}}
    for c in ("no_setup", "rejection"):
        cr[c] = {"precision": 0.5, "recall": 0.5, "f1-score": 0.5, "support": 10.0}
    return {
        "fold_id": "x",
        "models": {"logistic_regression": {"classification_report": cr, "accuracy": 0.5}},
    }


def _bundle(
    *,
    mc: dict,
    folds: list[dict],
    weak: list[dict],
    drift: bool,
    preds_n: int,
    pol: list[str] | None = None,
) -> dict:
    return {
        "walkforward_report": {
            "answers": {
                "which_classes_remain_weak": weak,
                "calibration_forward_behavior": {"flag_potential_drift_raw_brier": drift},
            }
        },
        "fold_metrics": {"fold_metrics": folds},
        "model_comparison_report": mc,
        "calibration_drift_report": {"drift_heuristic": None},
        "policy_report": {"summary_bullets": pol or ["hit_rate=0.5"]},
        "step8_manifest": {"counts": {"prediction_lines": preds_n}, "artifacts": {}},
        "backtest_predictions": [{}] * preds_n,
    }


def test_improve_upstream_small_data() -> None:
    cfg = load_step9_decision_config(REPO / "src" / "ml" / "step9_decision_config.yaml")
    raw = _bundle(
        mc=_mc(0.3, 0.3, 0.0),
        folds=[_fold(0.3)],
        weak=[{"class": "a", "mean_f1_across_folds": 0.0, "n_folds": 1}] * 6,
        drift=False,
        preds_n=5,
    )
    ev = {"counts": {"folds": 1, "prediction_lines": 5}}
    failure = analyze_failure_modes(cfg, raw, REPO)
    d = decide_model_family(cfg, ev, failure, raw)
    assert d["outcome"] == "improve_upstream_first"


def test_tabular_only_stable_beat() -> None:
    cfg = copy.deepcopy(load_step9_decision_config(REPO / "src" / "ml" / "step9_decision_config.yaml"))
    cfg["minimum_evidence"]["min_folds_evaluated"] = 2
    raw = _bundle(
        mc=_mc(0.35, 0.62, 0.04),
        folds=[_fold(0.6), _fold(0.62), _fold(0.61)],
        weak=[],
        drift=False,
        preds_n=120,
    )
    ev = {"counts": {"folds": 3, "prediction_lines": 120}}
    failure = analyze_failure_modes(cfg, raw, REPO)
    d = decide_model_family(cfg, ev, failure, raw)
    assert d["outcome"] == "tabular_only_for_now"


def test_sequence_when_temporal_spread_signal() -> None:
    cfg = copy.deepcopy(load_step9_decision_config(REPO / "src" / "ml" / "step9_decision_config.yaml"))
    cfg["minimum_evidence"]["min_folds_evaluated"] = 2
    weak = [
        {"class": "x", "mean_f1_across_folds": 0.2, "n_folds": 3},
        {"class": "y", "mean_f1_across_folds": 0.25, "n_folds": 3},
        {"class": "z", "mean_f1_across_folds": 0.22, "n_folds": 3},
    ]
    raw = _bundle(
        mc=_mc(0.35, 0.58, 0.05),
        folds=[_fold(0.58), _fold(0.57), _fold(0.59)],
        weak=weak,
        drift=False,
        preds_n=100,
    )
    ev = {"counts": {"folds": 3, "prediction_lines": 100}}
    failure = analyze_failure_modes(cfg, raw, REPO)
    failure["representation_hints"]["aggregate_dimension_accuracy_spreads"] = {
        "timeframe": 0.25,
        "session": 0.05,
    }
    d = decide_model_family(cfg, ev, failure, raw)
    assert d["outcome"] == "sequence_model_next"


def test_vision_not_triggered_without_chart_geometry() -> None:
    cfg = copy.deepcopy(load_step9_decision_config(REPO / "src" / "ml" / "step9_decision_config.yaml"))
    cfg["minimum_evidence"]["min_folds_evaluated"] = 2
    raw = _bundle(
        mc=_mc(0.35, 0.45, 0.2),
        folds=[_fold(0.5), _fold(0.4), _fold(0.45), _fold(0.42), _fold(0.48)],
        weak=[],
        drift=False,
        preds_n=200,
    )
    ev = {"counts": {"folds": 5, "prediction_lines": 200}}
    failure = analyze_failure_modes(cfg, raw, REPO)
    failure["representation_hints"]["aggregate_dimension_accuracy_spreads"] = {
        "timeframe": 0.5,
        "session": 0.4,
    }
    failure["representation_hints"]["chart_geometry_hypothesis"] = False
    d = decide_model_family(cfg, ev, failure, raw)
    assert d["outcome"] != "vision_model_next"


def test_no_automatic_deep_default_low_signal() -> None:
    cfg = copy.deepcopy(load_step9_decision_config(REPO / "src" / "ml" / "step9_decision_config.yaml"))
    raw = _bundle(
        mc=_mc(0.4, 0.41, 0.0),
        folds=[_fold(0.4), _fold(0.42)],
        weak=[{"class": "c", "mean_f1_across_folds": 0.3, "n_folds": 2}],
        drift=False,
        preds_n=80,
    )
    ev = {"counts": {"folds": 2, "prediction_lines": 80}}
    failure = analyze_failure_modes(cfg, raw, REPO)
    d = decide_model_family(cfg, ev, failure, raw)
    assert d["outcome"] in ("improve_upstream_first", "tabular_only_for_now", "sequence_model_next")
    assert d["outcome"] != "vision_model_next"
