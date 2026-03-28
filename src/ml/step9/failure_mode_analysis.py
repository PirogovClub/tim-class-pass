"""Evidence-backed failure-mode analysis from Step 8 payloads."""

from __future__ import annotations

import json
import re
from pathlib import Path
from statistics import mean, pstdev
from typing import Any


def _macro_f1_from_fold_model(m: dict[str, Any]) -> float | None:
    cr = m.get("classification_report")
    if not isinstance(cr, dict):
        return None
    ma = cr.get("macro avg")
    if isinstance(ma, dict) and "f1-score" in ma:
        return float(ma["f1-score"])
    return None


def _hit_rates_from_policy(pol: dict[str, Any]) -> list[float]:
    out: list[float] = []
    for b in pol.get("summary_bullets") or pol.get("per_fold_bullets") or []:
        if not isinstance(b, str):
            continue
        m = re.search(r"hit_rate=([\d.]+)", b)
        if m:
            out.append(float(m.group(1)))
    return out


def _accuracy_spread_from_aggregate(agg: dict[str, Any] | None) -> dict[str, float]:
    if not isinstance(agg, dict):
        return {"timeframe": 0.0, "session": 0.0}
    def spread(section: str) -> float:
        block = agg.get(section) or {}
        if not isinstance(block, dict) or not block:
            return 0.0
        accs = []
        for _k, v in block.items():
            if isinstance(v, dict) and "accuracy" in v and v.get("n_predictions", 0) > 0:
                accs.append(float(v["accuracy"]))
        if len(accs) < 2:
            return 0.0
        return max(accs) - min(accs)

    return {
        "timeframe": spread("by_timeframe"),
        "session": spread("by_session_bucket"),
    }


def analyze_failure_modes(
    cfg: dict[str, Any],
    raw: dict[str, Any],
    repo_root: Path,
) -> dict[str, Any]:
    """
    raw: loaded Step 8 artifacts (walkforward_report, fold_metrics, model_comparison_report,
         calibration_drift_report, policy_report, backtest_predictions, step8_manifest).
    """
    wf = raw["walkforward_report"]
    fm = raw["fold_metrics"]
    mc = raw["model_comparison_report"]
    cal = raw["calibration_drift_report"]
    pol = raw["policy_report"]
    man = raw["step8_manifest"]

    fold_metrics_list = fm.get("fold_metrics") or []
    tab_key = (cfg.get("baseline_comparison") or {}).get("tabular_model_key", "logistic_regression")

    lr_f1s = [_macro_f1_from_fold_model(f.get("models", {}).get(tab_key, {})) for f in fold_metrics_list]
    lr_f1s = [x for x in lr_f1s if x is not None]

    class_weak = wf.get("answers", {}).get("which_classes_remain_weak") or []
    cw_cfg = cfg.get("class_weakness") or {}
    weak_thr = float(cw_cfg.get("weak_mean_f1_max", 0.35))
    low_sup = int(cw_cfg.get("min_class_support_low", 2))

    low_support_classes: list[str] = []
    for f in fold_metrics_list:
        m = f.get("models", {}).get(tab_key, {})
        cr = m.get("classification_report") if isinstance(m, dict) else None
        if not isinstance(cr, dict):
            continue
        for cls, row in cr.items():
            if not isinstance(row, dict) or "support" not in row:
                continue
            if cls in ("macro avg", "weighted avg", "accuracy"):
                continue
            if float(row["support"]) < low_sup:
                low_support_classes.append(str(cls))
    low_support_classes = sorted(set(low_support_classes))

    cal_narr = wf.get("answers", {}).get("calibration_forward_behavior") or {}
    drift_flag = bool(cal_narr.get("flag_potential_drift_raw_brier"))
    dh = cal.get("drift_heuristic") if isinstance(cal, dict) else None
    if isinstance(dh, dict) and dh.get("flag_potential_drift"):
        drift_flag = True

    f1_range = 0.0
    if len(lr_f1s) > 1:
        f1_range = max(lr_f1s) - min(lr_f1s)

    hits = _hit_rates_from_policy(pol if isinstance(pol, dict) else {})
    poor_pol = bool(hits) and max(hits) <= float((cfg.get("policy_utility") or {}).get("max_hit_rate_considered_poor", 0.15))

    agg_path = None
    arts = man.get("artifacts") if isinstance(man, dict) else {}
    if isinstance(arts, dict):
        ar = arts.get("aggregate_dimensions_report")
        if ar:
            agg_path = Path(str(ar))
    agg: dict[str, Any] | None = None
    if agg_path and agg_path.is_file():
        agg = json.loads(agg_path.read_text(encoding="utf-8"))
    spreads = _accuracy_spread_from_aggregate(agg)

    opt = (cfg.get("evidence") or {}).get("optional_files") or {}
    feature_concern = False
    fq_path = opt.get("feature_quality_report")
    if fq_path:
        fp = (repo_root / str(fq_path)).resolve()
        if fp.is_file():
            fq = json.loads(fp.read_text(encoding="utf-8"))
            amb = (fq.get("row_counts") or {}).get("ambiguous_rows")
            if amb is not None and int(amb) > 0:
                feature_concern = True
            nulls = fq.get("per_feature_null_rates_trainable") or {}
            if isinstance(nulls, dict) and any(float(v) > 0.25 for v in nulls.values() if v is not None):
                feature_concern = True

    label_concern = False
    lm_path = opt.get("label_dataset_manifest")
    if lm_path:
        lp = (repo_root / str(lm_path)).resolve()
        if lp.is_file():
            lm = json.loads(lp.read_text(encoding="utf-8"))
            if lm.get("row_count") is not None and lm.get("labels_written") is not None:
                if int(lm["labels_written"]) != int(lm["row_count"]):
                    label_concern = True

    chart_geometry = (
        spreads["timeframe"] >= float((cfg.get("vision_justification") or {}).get("timeframe_accuracy_spread_min", 0.35))
        and spreads["session"] >= float((cfg.get("vision_justification") or {}).get("session_accuracy_spread_min", 0.30))
        and feature_concern
    )

    fold_collapse = any((x is not None and x < 0.05) for x in lr_f1s)

    return {
        "failure_mode_report_id": "failure_mode_report_v1",
        "class_level": {
            "weak_classes_from_walkforward": class_weak,
            "weak_f1_threshold": weak_thr,
            "low_support_class_labels": low_support_classes,
        },
        "fold_level": {
            "logistic_regression_macro_f1_per_fold": lr_f1s,
            "macro_f1_range": f1_range,
            "fold_collapse_suspected": fold_collapse,
        },
        "calibration_level": {
            "drift_flag": drift_flag,
            "summary": cal_narr.get("plain_language"),
        },
        "policy_level": {
            "parsed_hit_rates": hits,
            "policies_likely_low_utility": poor_pol,
        },
        "data_support": {
            "n_folds": len(fold_metrics_list),
            "n_predictions_manifest": (man.get("counts") or {}).get("prediction_lines"),
        },
        "representation_hints": {
            "aggregate_dimension_accuracy_spreads": spreads,
            "chart_geometry_hypothesis": chart_geometry,
            "feature_quality_concern": feature_concern,
            "label_manifest_concern": label_concern,
        },
    }


def _load_aggregate_from_manifest(man: dict[str, Any]) -> dict[str, Any] | None:
    arts = man.get("artifacts") if isinstance(man, dict) else {}
    if not isinstance(arts, dict):
        return None
    ar = arts.get("aggregate_dimensions_report")
    if not ar:
        return None
    p = Path(str(ar))
    if not p.is_file():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def build_regime_breakdown_report(
    cfg: dict[str, Any],
    raw: dict[str, Any],
    failure: dict[str, Any],
) -> dict[str, Any]:
    """Session / timeframe / tier buckets from Step 8 aggregate_dimensions_report (optional)."""
    man = raw.get("step8_manifest") or {}
    agg = _load_aggregate_from_manifest(man if isinstance(man, dict) else {})
    spreads = (failure.get("representation_hints") or {}).get("aggregate_dimension_accuracy_spreads") or {}
    seq_tf = float((cfg.get("sequence_justification") or {}).get("timeframe_accuracy_spread_min", 0.18))
    seq_sess = float((cfg.get("sequence_justification") or {}).get("session_accuracy_spread_min", 0.15))

    by_tf = (agg or {}).get("by_timeframe") if isinstance(agg, dict) else {}
    by_sess = (agg or {}).get("by_session_bucket") if isinstance(agg, dict) else {}
    by_tier = (agg or {}).get("by_confidence_tier") if isinstance(agg, dict) else {}

    return {
        "regime_breakdown_report_id": "regime_breakdown_v1",
        "source_artifact": "aggregate_dimensions_report.json (via step8_manifest.artifacts)",
        "aggregate_present": agg is not None,
        "by_timeframe": by_tf if isinstance(by_tf, dict) else {},
        "by_session_bucket": by_sess if isinstance(by_sess, dict) else {},
        "by_confidence_tier": by_tier if isinstance(by_tier, dict) else {},
        "interpretation": {
            "accuracy_spread_timeframe": float(spreads.get("timeframe") or 0),
            "accuracy_spread_session": float(spreads.get("session") or 0),
            "high_timeframe_dispersion_vs_sequence_gate": float(spreads.get("timeframe") or 0) >= seq_tf,
            "high_session_dispersion_vs_sequence_gate": float(spreads.get("session") or 0) >= seq_sess,
        },
    }


def build_class_stability_report(cfg: dict[str, Any], raw: dict[str, Any]) -> dict[str, Any]:
    """Per-class F1 across folds for the configured tabular model (stability vs fold-specific weakness)."""
    fm = raw.get("fold_metrics") or {}
    fold_metrics_list = fm.get("fold_metrics") or []
    tab_key = (cfg.get("baseline_comparison") or {}).get("tabular_model_key", "logistic_regression")
    weak_thr = float((cfg.get("class_weakness") or {}).get("weak_mean_f1_max", 0.35))

    f1_by_class: dict[str, list[float]] = {}
    for f in fold_metrics_list:
        m = f.get("models", {}).get(tab_key, {})
        cr = m.get("classification_report") if isinstance(m, dict) else None
        if not isinstance(cr, dict):
            continue
        for cls, row in cr.items():
            if not isinstance(row, dict) or "f1-score" not in row:
                continue
            if cls in ("macro avg", "weighted avg", "accuracy"):
                continue
            f1_by_class.setdefault(str(cls), []).append(float(row["f1-score"]))

    rows: list[dict[str, Any]] = []
    for cls, vals in sorted(f1_by_class.items()):
        m = mean(vals)
        sd = pstdev(vals) if len(vals) > 1 else 0.0
        if m < weak_thr and sd < 0.08:
            pattern = "stable_weak"
        elif len(vals) > 1 and sd >= 0.12:
            pattern = "unstable_or_fold_specific"
        elif m < weak_thr:
            pattern = "weak_moderate_variance"
        else:
            pattern = "acceptable_mean"
        rows.append(
            {
                "class": cls,
                "n_folds": len(vals),
                "f1_per_fold": vals,
                "mean_f1": m,
                "pstdev_f1": sd,
                "pattern": pattern,
            }
        )

    return {
        "class_stability_report_id": "class_stability_v1",
        "tabular_model_key": tab_key,
        "weak_f1_threshold": weak_thr,
        "per_class": rows,
    }
