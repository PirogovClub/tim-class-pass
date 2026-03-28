"""Threshold / combined policies over replay predictions (not a full execution engine)."""

from __future__ import annotations

from collections import Counter
from typing import Any

from ml.baselines.symbolic_baseline import symbolic_predict


def evaluate_policies(
    test_rows: list[dict[str, Any]],
    model_predictions: dict[str, list[dict[str, Any]]],
    *,
    thresholds: list[float],
    symbolic_and_model_threshold: float,
) -> dict[str, Any]:
    """
    model_predictions maps model_name -> list of prediction_record dicts aligned with test_rows order
    (same length as test_rows).
    """
    policies: dict[str, Any] = {}

    n = len(test_rows)
    sym_preds = [symbolic_predict(r.get("features") or {}) for r in test_rows]

    # top class only (per model)
    for mname, preds in model_predictions.items():
        if len(preds) != n:
            continue
        correct = sum(
            1
            for r, p in zip(test_rows, preds)
            if p.get("predicted_label") == str(r.get("label", ""))
        )
        policies[f"{mname}__top_class"] = {
            "eligible_count": n,
            "abstain_count": 0,
            "hit_rate": correct / n if n else 0.0,
            "class_mix_predicted": dict(Counter(str(p.get("predicted_label")) for p in preds)),
        }

    logreg_preds = model_predictions.get("logistic_regression") or model_predictions.get("logistic_regression_raw")
    if logreg_preds and len(logreg_preds) == n:
        for tau in thresholds:
            abst = 0
            hits = 0
            eligible = 0
            confs: list[float] = []
            pred_dist: Counter[str] = Counter()
            for row, pr in zip(test_rows, logreg_preds):
                raw = pr.get("predicted_probabilities") or {}
                if not raw:
                    abst += 1
                    continue
                mx = max(raw.values()) if raw else 0.0
                confs.append(mx)
                if mx < tau:
                    abst += 1
                    continue
                eligible += 1
                pred_dist[str(pr.get("predicted_label"))] += 1
                if pr.get("predicted_label") == str(row.get("label", "")):
                    hits += 1
            key = f"logistic_regression__prob_ge_{tau}"
            policies[key] = {
                "threshold": tau,
                "eligible_count": eligible,
                "abstain_count": abst,
                "hit_rate": hits / eligible if eligible else 0.0,
                "confidence_mean": sum(confs) / len(confs) if confs else None,
                "class_mix_predicted": dict(pred_dist),
            }

    # symbolic + model threshold (both must agree on direction: model pred must match symbolic OR we require prob)
    if logreg_preds and len(logreg_preds) == n:
        tau = symbolic_and_model_threshold
        abst = 0
        hits = 0
        elig = 0
        for row, sym, pr in zip(test_rows, sym_preds, logreg_preds):
            raw = pr.get("predicted_probabilities") or {}
            mx = max(raw.values()) if raw else 0.0
            mp = str(pr.get("predicted_label", ""))
            if mx < tau:
                abst += 1
                continue
            # combined: require symbolic agrees with model top class (lightweight proxy for "eligibility")
            if sym != mp:
                abst += 1
                continue
            elig += 1
            if mp == str(row.get("label", "")):
                hits += 1
        policies["symbolic_agree_logreg_prob_ge_threshold"] = {
            "threshold": tau,
            "eligible_count": elig,
            "abstain_count": abst,
            "hit_rate": hits / elig if elig else 0.0,
            "description": "Abstain unless max(raw prob) >= tau AND symbolic top class == model top class.",
        }

    policies["symbolic_only"] = {
        "eligible_count": n,
        "abstain_count": 0,
        "hit_rate": sum(1 for r, s in zip(test_rows, sym_preds) if s == str(r.get("label", ""))) / n if n else 0.0,
        "class_mix_predicted": dict(Counter(sym_preds)),
    }

    return {"policies": policies, "n_test_rows": n}


