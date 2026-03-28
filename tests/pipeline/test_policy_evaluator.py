"""Policy evaluator tests."""

from __future__ import annotations

from ml.backtest.policy_evaluator import evaluate_policies
from ml.backtest.prediction_replay import prediction_record


def test_threshold_abstain_increases_with_higher_tau() -> None:
    test_rows = [
        {
            "label": "no_setup",
            "features": {},
            "candidate_id": "x",
            "dataset_row_id": "d1",
            "anchor_timestamp": "t",
            "timeframe": "1h",
            "confidence_tier": "gold",
            "point_in_time_safe": True,
        }
    ]
    hi = {"no_setup": 0.9, "acceptance_above": 0.1}
    lo = {"no_setup": 0.2, "acceptance_above": 0.8}
    preds_hi = [
        prediction_record(
            fold_id="f0",
            model_name="logistic_regression",
            row=test_rows[0],
            predicted_label="no_setup",
            predicted_probabilities=hi,
            calibrated_probabilities=None,
        )
    ]
    preds_lo = [
        prediction_record(
            fold_id="f0",
            model_name="logistic_regression",
            row=test_rows[0],
            predicted_label="acceptance_above",
            predicted_probabilities=lo,
            calibrated_probabilities=None,
        )
    ]
    r_lo = evaluate_policies(
        test_rows,
        {"logistic_regression": preds_lo},
        thresholds=[0.5, 0.9],
        symbolic_and_model_threshold=0.5,
    )
    pol_lo = r_lo["policies"].get("logistic_regression__prob_ge_0.5")
    assert pol_lo is not None
    assert pol_lo["abstain_count"] == 0
    r_hi = evaluate_policies(
        test_rows,
        {"logistic_regression": preds_hi},
        thresholds=[0.95],
        symbolic_and_model_threshold=0.5,
    )
    assert r_hi["policies"]["logistic_regression__prob_ge_0.95"]["abstain_count"] == 1


def test_symbolic_only_policy_present() -> None:
    test_rows = [
        {
            "label": "no_setup",
            "features": {"close_distance_pct": 0, "n_closes_above_level_pre": 0},
            "candidate_id": "x",
            "dataset_row_id": "d1",
            "anchor_timestamp": "t",
            "timeframe": "1h",
            "confidence_tier": "gold",
            "point_in_time_safe": True,
        }
    ]
    r = evaluate_policies(test_rows, {}, thresholds=[0.5], symbolic_and_model_threshold=0.5)
    assert "symbolic_only" in r["policies"]
