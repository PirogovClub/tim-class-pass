"""Aggregate walk-forward reports and step8 manifest."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, pstdev
from typing import Any


def _macro_f1(rep: dict[str, Any]) -> float | None:
    cr = rep.get("classification_report") or {}
    ma = cr.get("macro avg") or {}
    return float(ma.get("f1-score", 0)) if ma else None


def _weighted_f1(rep: dict[str, Any]) -> float | None:
    cr = rep.get("classification_report") or {}
    wa = cr.get("weighted avg") or {}
    return float(wa.get("f1-score", 0)) if wa else None


def session_bucket_from_anchor(anchor: str) -> str:
    """Coarse UTC session bucket from ISO-like anchor (for aggregate reporting)."""
    s = str(anchor)
    ti = s.find("T")
    if ti < 0 or ti + 3 > len(s):
        return "unknown"
    try:
        hour = int(s[ti + 1 : ti + 3])
    except ValueError:
        return "unknown"
    if 0 <= hour < 8:
        return "utc_00_08"
    if hour < 16:
        return "utc_08_16"
    return "utc_16_24"


def infer_weak_classes(
    fold_metrics: list[dict[str, Any]],
    *,
    model_key: str = "logistic_regression",
    f1_threshold: float = 0.35,
) -> list[dict[str, Any]]:
    """Classes with mean per-fold F1 below threshold on the given model (if present)."""
    from collections import defaultdict

    f1_by_class: dict[str, list[float]] = defaultdict(list)
    for f in fold_metrics:
        m = f["models"].get(model_key, {})
        cr = m.get("classification_report") if isinstance(m, dict) else None
        if not isinstance(cr, dict):
            continue
        for k, v in cr.items():
            if not isinstance(v, dict) or "f1-score" not in v:
                continue
            if k in ("macro avg", "weighted avg"):
                continue
            f1_by_class[k].append(float(v["f1-score"]))
    out: list[dict[str, Any]] = []
    for cls, vals in f1_by_class.items():
        m = mean(vals)
        if m < f1_threshold:
            out.append({"class": cls, "mean_f1_across_folds": m, "n_folds": len(vals)})
    out.sort(key=lambda x: x["mean_f1_across_folds"])
    return out


def summarize_calibration_drift_narrative(drift: dict[str, Any]) -> dict[str, Any]:
    h = drift.get("drift_heuristic") or {}
    flag = bool(h.get("flag_potential_drift"))
    br = drift.get("brier_raw") or {}
    bc = drift.get("brier_calibrated") or {}
    return {
        "flag_potential_drift_raw_brier": flag,
        "brier_raw_mean": br.get("mean"),
        "brier_raw_pstdev": br.get("pstdev"),
        "brier_cal_mean": bc.get("mean"),
        "brier_cal_pstdev": bc.get("pstdev"),
        "n_folds_in_drift_report": drift.get("n_folds_with_metrics"),
        "plain_language": (
            "Heuristic suggests material forward variability in raw Brier across folds."
            if flag
            else "No drift heuristic triggered, or too few folds for variance estimate."
        ),
    }


def build_aggregate_dimensions_report(
    predictions_path: Path,
    rows_by_dataset_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """
    Accuracy of logistic_regression replay predictions broken down by timeframe,
    confidence_tier, and coarse session bucket (requires dataset rows merged by dataset_row_id).
    """
    from collections import defaultdict

    def bucket() -> defaultdict[str, dict[str, int]]:
        return defaultdict(lambda: {"n": 0, "correct": 0})

    by_tf: defaultdict[str, dict[str, int]] = bucket()
    by_tier: defaultdict[str, dict[str, int]] = bucket()
    by_sess: defaultdict[str, dict[str, int]] = bucket()

    if not predictions_path.is_file():
        return {
            "aggregate_dimensions_report_id": "aggregate_dimensions_v1",
            "note": "predictions file missing",
            "by_timeframe": {},
            "by_confidence_tier": {},
            "by_session_bucket": {},
        }

    for line in predictions_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        o = json.loads(line)
        if o.get("model_name") != "logistic_regression":
            continue
        rid = str(o.get("dataset_row_id", ""))
        row = rows_by_dataset_id.get(rid)
        if not row:
            continue
        act = o.get("actual_label")
        pred = o.get("predicted_label")
        if act is None or pred is None:
            continue
        ok = act == pred
        tf = str(row.get("timeframe", "")) or "unknown"
        tier = str(row.get("confidence_tier", "")) or "unknown"
        sess = session_bucket_from_anchor(str(row.get("anchor_timestamp", "")))
        for d in (by_tf[tf], by_tier[tier], by_sess[sess]):
            d["n"] += 1
            if ok:
                d["correct"] += 1

    def finalize(raw: defaultdict[str, dict[str, int]]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for k, v in sorted(raw.items()):
            n = v["n"]
            out[k] = {
                "n_predictions": n,
                "accuracy": (v["correct"] / n) if n else 0.0,
            }
        return out

    return {
        "aggregate_dimensions_report_id": "aggregate_dimensions_v1",
        "model": "logistic_regression",
        "by_timeframe": finalize(by_tf),
        "by_confidence_tier": finalize(by_tier),
        "by_session_bucket": finalize(by_sess),
    }


def build_walkforward_report(
    *,
    task_id: str,
    folds_payload: dict[str, Any],
    fold_metrics: list[dict[str, Any]],
    policy_aggregate: dict[str, Any],
    pit_declaration: str,
    drift_report: dict[str, Any] | None = None,
    weak_classes: list[dict[str, Any]] | None = None,
    aggregate_dimensions_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    n_folds = len(fold_metrics)
    skipped = folds_payload.get("skipped_fold_reasons") or []
    sym_f1 = [_macro_f1(f["models"].get("symbolic", {})) for f in fold_metrics if f["models"].get("symbolic")]
    lr_f1 = [
        _macro_f1(f["models"].get("logistic_regression", {})) for f in fold_metrics if f["models"].get("logistic_regression")
    ]
    sym_f1v = [x for x in sym_f1 if x is not None]
    lr_f1v = [x for x in lr_f1 if x is not None]

    best_model = "undetermined"
    if sym_f1v and lr_f1v:
        best_model = "logistic_regression" if mean(lr_f1v) > mean(sym_f1v) else "symbolic"
    elif lr_f1v:
        best_model = "logistic_regression"
    elif sym_f1v:
        best_model = "symbolic"

    stab_sym = pstdev(sym_f1v) if len(sym_f1v) > 1 else 0.0
    stab_lr = pstdev(lr_f1v) if len(lr_f1v) > 1 else 0.0
    if len(sym_f1v) <= 1 and len(lr_f1v) <= 1:
        most_stable = "insufficient_folds_for_stability"
    else:
        most_stable = "symbolic" if stab_sym <= stab_lr else "logistic_regression"

    drift = drift_report or {}
    weak = weak_classes or []
    dim = aggregate_dimensions_summary or {}
    cal_narr = summarize_calibration_drift_narrative(drift) if drift else {}

    return {
        "walkforward_report_id": "walkforward_report_v1",
        "created_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "task_id": task_id,
        "n_folds_evaluated": n_folds,
        "skipped_fold_reasons": skipped,
        "answers": {
            "how_many_folds": n_folds,
            "which_folds_skipped": skipped,
            "best_model_by_mean_macro_f1": best_model,
            "most_stable_by_macro_f1_std": most_stable,
            "symbolic_vs_logreg_macro_f1_means": {
                "symbolic": mean(sym_f1v) if sym_f1v else None,
                "logistic_regression": mean(lr_f1v) if lr_f1v else None,
            },
            "which_classes_remain_weak": weak,
            "calibration_forward_behavior": cal_narr,
            "calibration_drift_detail_file": "calibration_drift_report.json",
            "aggregate_dimensions_file": "aggregate_dimensions_report.json",
            "aggregate_dimensions_headline": dim.get("headline"),
            "promising_policies": policy_aggregate.get("summary_bullets", []),
            "limitations": [
                "Fixture-scale data; fold counts and class balance are limited.",
                "Policies use fixed thresholds from config (no test-set tuning).",
            ],
        },
        "pit_declaration": pit_declaration,
    }


def build_model_comparison_report(fold_metrics: list[dict[str, Any]]) -> dict[str, Any]:
    def collect(model_key: str) -> dict[str, Any]:
        accs = []
        f1s = []
        for f in fold_metrics:
            m = f["models"].get(model_key, {})
            if not m or not isinstance(m.get("classification_report"), dict):
                continue
            accs.append(float(m.get("accuracy", 0)))
            mf = _macro_f1(m)
            if mf is not None:
                f1s.append(mf)
        return {
            "n_folds": len(accs),
            "accuracy_mean": mean(accs) if accs else None,
            "accuracy_pstdev": pstdev(accs) if len(accs) > 1 else 0.0,
            "macro_f1_mean": mean(f1s) if f1s else None,
            "macro_f1_pstdev": pstdev(f1s) if len(f1s) > 1 else 0.0,
        }

    return {
        "model_comparison_report_id": "model_comparison_v1",
        "symbolic": collect("symbolic"),
        "logistic_regression": collect("logistic_regression"),
        "logistic_regression_calibrated": collect("logistic_regression_calibrated"),
        "xgboost": collect("xgboost"),
        "lightgbm": collect("lightgbm"),
    }


def build_step8_manifest(
    *,
    out_dir: Path,
    cfg: dict[str, Any],
    artifact_paths: dict[str, str],
    fold_metrics: list[dict[str, Any]],
    n_prediction_lines: int,
    step7_alignment: dict[str, Any] | None = None,
) -> dict[str, Any]:
    man: dict[str, Any] = {
        "step8_manifest_id": "step8_manifest_v1",
        "created_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "task_id": cfg["task_id"],
        "output_dir": str(out_dir),
        "artifacts": artifact_paths,
        "counts": {
            "folds": len(fold_metrics),
            "prediction_lines": n_prediction_lines,
        },
        "inclusion_policy_ref": "walkforward_config.yaml inclusion block",
        "pit_declaration": cfg.get("pit_declaration", ""),
    }
    if step7_alignment is not None:
        man["step7_dataset_alignment"] = step7_alignment
    return man


def build_threshold_sweep_report(threshold_rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {"threshold_sweep_report_id": "threshold_sweep_v1", "rows": threshold_rows}


def build_per_class_fold_metrics(fold_metrics: list[dict[str, Any]]) -> dict[str, Any]:
    """Flatten per-class metrics from each fold's classification_report."""
    out: dict[str, Any] = {"per_class_fold_metrics_id": "per_class_fold_v1", "folds": []}
    for f in fold_metrics:
        fold_entry: dict[str, Any] = {"fold_id": f["fold_id"], "models": {}}
        for mname, mrep in f.get("models", {}).items():
            cr = mrep.get("classification_report") if isinstance(mrep, dict) else None
            if isinstance(cr, dict):
                fold_entry["models"][mname] = {k: v for k, v in cr.items() if isinstance(v, dict)}
        out["folds"].append(fold_entry)
    return out


def build_confusion_matrices_bundle(fold_metrics: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "confusion_matrices_id": "confusion_matrices_v1",
        "by_fold": [
            {
                "fold_id": f["fold_id"],
                "models": {
                    k: v.get("confusion_matrix")
                    for k, v in f.get("models", {}).items()
                    if isinstance(v, dict) and v.get("confusion_matrix") is not None
                },
            }
            for f in fold_metrics
        ],
    }


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
