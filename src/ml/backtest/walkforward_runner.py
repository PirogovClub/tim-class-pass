"""Walk-forward evaluation: train baselines per fold, replay predictions, write reports."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from ml.backtest.calibration_drift import build_calibration_drift_report, summarize_fold_calibration
from ml.backtest.dataset_integrity import build_step7_alignment_report
from ml.backtest.fold_builder import build_folds, filter_eval_pool, materialize_fold_rows, sort_by_time
from ml.backtest.policy_evaluator import evaluate_policies
from ml.backtest.prediction_replay import append_jsonl, prediction_record
from ml.backtest.report_builder import (
    build_aggregate_dimensions_report,
    build_confusion_matrices_bundle,
    build_model_comparison_report,
    build_per_class_fold_metrics,
    build_step8_manifest,
    build_threshold_sweep_report,
    build_walkforward_report,
    infer_weak_classes,
    write_json,
)
from ml.backtest.walkforward_config_loader import load_walkforward_config, resolve_paths
from ml.baselines.calibration import brier_multiclass_aligned, calibration_bucket_report
from ml.baselines.evaluate_tabular_baseline import evaluate_multiclass
from ml.baselines.symbolic_baseline import symbolic_predict
from ml.feature_spec_loader import load_feature_spec


def _load_dataset(path: Path) -> list[dict[str, Any]]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def _global_class_labels(pool: list[dict[str, Any]]) -> list[str]:
    return sorted({str(r["label"]) for r in pool if r.get("label") is not None})


def _optional_resolved_path(repo_root: Path, rel_or_abs: str | None) -> Path | None:
    if not rel_or_abs:
        return None
    p = Path(rel_or_abs)
    return p.resolve() if p.is_absolute() else (repo_root / p).resolve()


def _build_design(
    rows: list[dict[str, Any]],
    spec: dict[str, Any],
    class_labels: list[str],
) -> tuple[np.ndarray, np.ndarray | None, np.ndarray, dict[str, int]]:
    num = spec["modeling_feature_columns"]["numeric"]
    cats = spec["modeling_feature_columns"]["categorical"]
    bools = spec["modeling_feature_columns"]["boolean"]
    lab_to_i = {l: i for i, l in enumerate(class_labels)}
    X_num: list[list[float]] = []
    X_cat: list[list[str]] = []
    y_list: list[int] = []
    for r in rows:
        f = r.get("features") or {}
        X_num.append([float(f.get(c, 0) or 0) for c in num])
        if cats:
            X_cat.append([str(f.get(c, "unknown")) for c in cats])
        for c in bools:
            X_num[-1].append(1.0 if f.get(c) else 0.0)
        y_list.append(lab_to_i[str(r["label"])])
    Xn = np.array(X_num, dtype=np.float64)
    y = np.array(y_list, dtype=np.int64)
    Xc = np.array(X_cat, dtype=object) if cats else None
    return Xn, Xc, y, lab_to_i


def _align_proba_to_labels(proba: np.ndarray, clf_classes: np.ndarray, n_global: int) -> np.ndarray:
    """Scatter clf output columns into full n_global columns by class index."""
    full = np.zeros((proba.shape[0], n_global), dtype=np.float64)
    for j, c in enumerate(clf_classes):
        full[:, int(c)] = proba[:, j]
    return full


def _metrics_block(y_true_str: list[str], y_pred_str: list[str], labels: list[str]) -> dict[str, Any]:
    rep = evaluate_multiclass(y_true_str, y_pred_str, labels)
    acc = accuracy_score(y_true_str, y_pred_str) if y_true_str else 0.0
    cr = rep["classification_report"]
    macro_f1 = float(cr.get("macro avg", {}).get("f1-score", 0))
    weighted_f1 = float(cr.get("weighted avg", {}).get("f1-score", 0))
    out = {
        "accuracy": float(acc),
        "macro_f1": macro_f1,
        "weighted_f1": weighted_f1,
        "classification_report": cr,
        "confusion_matrix": rep["confusion_matrix"],
        "labels_order": rep["labels_order"],
    }
    return out


def run_walkforward(repo_root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    cfg["outputs"].setdefault("aggregate_dimensions_report", "aggregate_dimensions_report.json")
    paths = resolve_paths(cfg, repo_root)
    ds_path = paths["dataset"]
    if not ds_path.is_file():
        raise FileNotFoundError(f"dataset not found: {ds_path}")
    spec = load_feature_spec(paths["feature_spec"])
    rows = _load_dataset(ds_path)
    rows_by_id = {str(r["dataset_row_id"]): r for r in rows if r.get("dataset_row_id")}

    ds_block = cfg.get("dataset") or {}
    alignment = build_step7_alignment_report(
        ds_path,
        dataset_manifest_path=_optional_resolved_path(repo_root, ds_block.get("manifest_path")),
        split_manifest_path=_optional_resolved_path(repo_root, ds_block.get("split_manifest_path")),
    )
    if alignment.get("critical_issues"):
        raise ValueError("Step 7 dataset alignment failed: " + "; ".join(alignment["critical_issues"]))

    pool, excl_log = filter_eval_pool(rows, cfg["inclusion"])
    sorted_pool = sort_by_time(pool)
    class_labels = _global_class_labels(sorted_pool)
    if len(class_labels) < 2:
        raise ValueError("need at least 2 classes in eval pool")

    folds_meta, skips = build_folds(sorted_pool, cfg["fold_policy"])
    out_root = Path(cfg["outputs"]["root"])
    if not out_root.is_absolute():
        out_root = repo_root / out_root
    out_root.mkdir(parents=True, exist_ok=True)

    pred_path = out_root / cfg["outputs"]["backtest_predictions"]
    pred_path.unlink(missing_ok=True)

    seed = int(cfg["reproducibility"].get("sklearn_random_state", 42))
    cal_cfg = cfg["calibration"]
    min_val_cal = int(cal_cfg.get("min_val_rows_for_calibration", 2))
    min_distinct_val = int(cal_cfg.get("min_distinct_classes_in_val", 2))
    n_bins = int(cal_cfg.get("n_probability_bins", 4))

    fold_metrics: list[dict[str, Any]] = []
    cal_summaries: list[dict[str, Any]] = []
    policy_fold_bullets: list[str] = []
    threshold_sweep_rows: list[dict[str, Any]] = []

    models_cfg = cfg.get("models", {})

    for fold in folds_meta:
        fold_id = fold["fold_id"]
        train_rows, val_rows, test_rows = materialize_fold_rows(sorted_pool, fold)
        y_true_test = [str(r["label"]) for r in test_rows]

        models_out: dict[str, Any] = {}
        preds_by_model: dict[str, list[dict[str, Any]]] = {}

        # Symbolic
        if models_cfg.get("symbolic", True):
            sym_pred = [symbolic_predict(r.get("features") or {}) for r in test_rows]
            models_out["symbolic"] = _metrics_block(y_true_test, sym_pred, class_labels)
            sym_recs = [
                prediction_record(
                    fold_id=fold_id,
                    model_name="symbolic",
                    row=r,
                    predicted_label=p,
                    predicted_probabilities=None,
                    calibrated_probabilities=None,
                )
                for r, p in zip(test_rows, sym_pred)
            ]
            preds_by_model["symbolic"] = sym_recs
            append_jsonl(pred_path, sym_recs)

        # Logistic regression
        if models_cfg.get("logistic_regression", True):
            Xn_tr, Xc_tr, y_tr, _ = _build_design(train_rows, spec, class_labels)
            Xn_va, Xc_va, y_va, _ = _build_design(val_rows, spec, class_labels)
            Xn_te, Xc_te, y_te, _ = _build_design(test_rows, spec, class_labels)
            cats = spec["modeling_feature_columns"]["categorical"]
            if cats:
                ohe = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
                scaler = StandardScaler()
                X_train = np.hstack([scaler.fit_transform(Xn_tr), ohe.fit_transform(Xc_tr)])
                X_val = np.hstack([scaler.transform(Xn_va), ohe.transform(Xc_va)])
                X_test = np.hstack([scaler.transform(Xn_te), ohe.transform(Xc_te)])
            else:
                ohe = None
                scaler = StandardScaler()
                X_train = scaler.fit_transform(Xn_tr)
                X_val = scaler.transform(Xn_va)
                X_test = scaler.transform(Xn_te)

            clf = LogisticRegression(max_iter=500, random_state=seed)
            clf.fit(X_train, y_tr)
            proba_raw = clf.predict_proba(X_test)
            pred_idx = proba_raw.argmax(axis=1)
            y_pred_str = [class_labels[int(i)] for i in pred_idx]
            models_out["logistic_regression"] = _metrics_block(y_true_test, y_pred_str, class_labels)

            full_raw = _align_proba_to_labels(proba_raw, clf.classes_, len(class_labels))

            def row_probs(full_row: np.ndarray) -> dict[str, float]:
                return {class_labels[j]: float(full_row[j]) for j in range(len(class_labels))}

            proba_cal = proba_raw
            full_cal = full_raw
            cal_bucket_raw = calibration_bucket_report(y_te, proba_raw, clf.classes_, n_bins=n_bins)
            cal_bucket_cal: dict[str, Any] | None = cal_bucket_raw
            brier_raw = brier_multiclass_aligned(y_te, proba_raw, clf.classes_)
            brier_cal = brier_raw
            cal_method = "none"

            if (
                len(val_rows) >= min_val_cal
                and len(np.unique(y_va)) >= min_distinct_val
                and X_val.shape[0] == len(y_va)
            ):
                try:
                    cal = CalibratedClassifierCV(clf, method="sigmoid", cv="prefit")
                    cal.fit(X_val, y_va)
                    proba_cal = cal.predict_proba(X_test)
                    full_cal = _align_proba_to_labels(proba_cal, cal.classes_, len(class_labels))
                    brier_cal = brier_multiclass_aligned(y_te, proba_cal, cal.classes_)
                    cal_bucket_cal = calibration_bucket_report(y_te, proba_cal, cal.classes_, n_bins=n_bins)
                    cal_method = "platt_sigmoid_prefit"
                    pred_cal_idx = proba_cal.argmax(axis=1)
                    y_pred_cal = [class_labels[int(i)] for i in pred_cal_idx]
                    models_out["logistic_regression_calibrated"] = _metrics_block(
                        y_true_test, y_pred_cal, class_labels
                    )
                except Exception as e:
                    models_out["logistic_regression_calibrated"] = {"error": str(e), "calibration_method": "failed"}
            else:
                models_out["logistic_regression_calibrated"] = {
                    "note": "skipped_insufficient_validation",
                    "validation_rows": len(val_rows),
                }

            lr_recs = []
            for i, r in enumerate(test_rows):
                lr_recs.append(
                    prediction_record(
                        fold_id=fold_id,
                        model_name="logistic_regression",
                        row=r,
                        predicted_label=y_pred_str[i],
                        predicted_probabilities=row_probs(full_raw[i]),
                        calibrated_probabilities=row_probs(full_cal[i]) if cal_method != "none" else None,
                    )
                )
            preds_by_model["logistic_regression"] = lr_recs
            append_jsonl(pred_path, lr_recs)

            cal_summaries.append(
                summarize_fold_calibration(
                    fold_id,
                    y_true_idx=list(y_te),
                    proba_raw=proba_raw.tolist(),
                    proba_cal=proba_cal.tolist() if cal_method != "none" else None,
                    class_order=class_labels,
                    bucket_report_raw=cal_bucket_raw,
                    bucket_report_cal=cal_bucket_cal,
                    brier_raw=brier_raw,
                    brier_cal=brier_cal if cal_method != "none" else None,
                )
            )

        # Optional trees (same matrices as logreg)
        if models_cfg.get("logistic_regression", True) and len(train_rows) >= 4:
            Xn_tr, Xc_tr, y_tr, _ = _build_design(train_rows, spec, class_labels)
            Xn_te, Xc_te, y_te, _ = _build_design(test_rows, spec, class_labels)
            cats = spec["modeling_feature_columns"]["categorical"]
            if cats:
                ohe = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
                scaler = StandardScaler()
                X_train = np.hstack([scaler.fit_transform(Xn_tr), ohe.fit_transform(Xc_tr)])
                X_test = np.hstack([scaler.transform(Xn_te), ohe.transform(Xc_te)])
            else:
                scaler = StandardScaler()
                X_train = scaler.fit_transform(Xn_tr)
                X_test = scaler.transform(Xn_te)

            if models_cfg.get("xgboost", True):
                try:
                    import xgboost as xgb  # type: ignore

                    if len(np.unique(y_tr)) >= 2:
                        xclf = xgb.XGBClassifier(
                            n_estimators=40, max_depth=4, random_state=seed, learning_rate=0.2
                        )
                        xclf.fit(X_train, y_tr)
                        px = xclf.predict(X_test)
                        y_x = [class_labels[int(i)] for i in px]
                        models_out["xgboost"] = _metrics_block(y_true_test, y_x, class_labels)
                        x_recs = [
                            prediction_record(
                                fold_id=fold_id,
                                model_name="xgboost",
                                row=r,
                                predicted_label=p,
                                predicted_probabilities=None,
                                calibrated_probabilities=None,
                            )
                            for r, p in zip(test_rows, y_x)
                        ]
                        preds_by_model["xgboost"] = x_recs
                        append_jsonl(pred_path, x_recs)
                except Exception as e:
                    models_out["xgboost"] = {"error": str(e)}

            if models_cfg.get("lightgbm", True):
                try:
                    import lightgbm as lgb  # type: ignore

                    if len(np.unique(y_tr)) >= 2:
                        lclf = lgb.LGBMClassifier(
                            n_estimators=40,
                            max_depth=4,
                            random_state=seed,
                            learning_rate=0.2,
                            verbosity=-1,
                        )
                        lclf.fit(X_train, y_tr)
                        pl = lclf.predict(X_test)
                        y_l = [class_labels[int(i)] for i in pl]
                        models_out["lightgbm"] = _metrics_block(y_true_test, y_l, class_labels)
                        l_recs = [
                            prediction_record(
                                fold_id=fold_id,
                                model_name="lightgbm",
                                row=r,
                                predicted_label=p,
                                predicted_probabilities=None,
                                calibrated_probabilities=None,
                            )
                            for r, p in zip(test_rows, y_l)
                        ]
                        preds_by_model["lightgbm"] = l_recs
                        append_jsonl(pred_path, l_recs)
                except Exception as e:
                    models_out["lightgbm"] = {"error": str(e)}

        pol = evaluate_policies(
            test_rows,
            {k: v for k, v in preds_by_model.items() if k in ("logistic_regression", "symbolic")},
            thresholds=[float(x) for x in cfg["policy"].get("probability_thresholds", [0.35])],
            symbolic_and_model_threshold=float(cfg["policy"].get("symbolic_and_model_threshold", 0.35)),
        )
        for pk, pv in pol["policies"].items():
            if isinstance(pv, dict) and pv.get("hit_rate") is not None:
                threshold_sweep_rows.append({"fold_id": fold_id, "policy": pk, **pv})
        best_pol = max(
            pol["policies"].items(),
            key=lambda x: float(x[1].get("hit_rate") or 0) if isinstance(x[1], dict) else 0,
        )
        policy_fold_bullets.append(f"{fold_id}: best policy key={best_pol[0]} hit_rate={best_pol[1].get('hit_rate')}")

        fold_metrics.append({"fold_id": fold_id, "models": models_out})

    folds_payload = {
        "walkforward_folds_id": "walkforward_folds_v1",
        "task_id": cfg["task_id"],
        "dataset_path": str(ds_path),
        "exclusion_log": excl_log,
        "pool_size_after_filter": len(sorted_pool),
        "folds": folds_meta,
        "skipped_fold_reasons": skips,
        "pit_note": cfg.get("pit_declaration", ""),
    }
    write_json(out_root / cfg["outputs"]["walkforward_folds"], folds_payload)

    write_json(out_root / cfg["outputs"]["fold_metrics"], {"fold_metrics": fold_metrics})

    drift = build_calibration_drift_report(cal_summaries)
    write_json(out_root / cfg["outputs"]["calibration_drift_report"], drift)

    dim_rep = build_aggregate_dimensions_report(pred_path, rows_by_id)
    write_json(out_root / cfg["outputs"]["aggregate_dimensions_report"], dim_rep)
    headline_parts: list[str] = []
    for label, block in (("tf", dim_rep.get("by_timeframe")), ("tier", dim_rep.get("by_confidence_tier"))):
        if isinstance(block, dict) and block:
            first_k = next(iter(block.keys()))
            headline_parts.append(f"{label}:{first_k} acc={block[first_k].get('accuracy', 0):.3f}")
    dim_summary = {"headline": "; ".join(headline_parts) if headline_parts else None}
    weak = infer_weak_classes(fold_metrics)

    policy_agg = {
        "policy_report_id": "policy_report_v1",
        "per_fold_bullets": policy_fold_bullets,
        "summary_bullets": policy_fold_bullets[: min(5, len(policy_fold_bullets))],
    }
    write_json(out_root / cfg["outputs"]["policy_report"], policy_agg)

    wf = build_walkforward_report(
        task_id=cfg["task_id"],
        folds_payload=folds_payload,
        fold_metrics=fold_metrics,
        policy_aggregate=policy_agg,
        pit_declaration=cfg.get("pit_declaration", ""),
        drift_report=drift,
        weak_classes=weak,
        aggregate_dimensions_summary=dim_summary,
    )
    write_json(out_root / cfg["outputs"]["walkforward_report"], wf)

    mc = build_model_comparison_report(fold_metrics)
    write_json(out_root / cfg["outputs"]["model_comparison_report"], mc)

    write_json(out_root / cfg["outputs"]["threshold_sweep_report"], build_threshold_sweep_report(threshold_sweep_rows))
    write_json(out_root / cfg["outputs"]["per_class_fold_metrics"], build_per_class_fold_metrics(fold_metrics))
    write_json(out_root / cfg["outputs"]["confusion_matrices"], build_confusion_matrices_bundle(fold_metrics))

    n_pred_lines = (
        len([ln for ln in pred_path.read_text(encoding="utf-8").splitlines() if ln.strip()])
        if pred_path.is_file()
        else 0
    )
    artifacts = {k: str(out_root / v) for k, v in cfg["outputs"].items() if isinstance(v, str)}
    manifest = build_step8_manifest(
        out_dir=out_root,
        cfg=cfg,
        artifact_paths=artifacts,
        fold_metrics=fold_metrics,
        n_prediction_lines=n_pred_lines,
        step7_alignment=alignment,
    )
    write_json(out_root / cfg["outputs"]["step8_manifest"], manifest)

    return {
        "out_dir": str(out_root),
        "n_folds": len(fold_metrics),
        "n_predictions": n_pred_lines,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Run Step 8 walk-forward backtest")
    ap.add_argument("--config", type=Path, default=Path("src/ml/walkforward_config.yaml"))
    ap.add_argument("--repo-root", type=Path, default=None)
    args = ap.parse_args()
    repo = (args.repo_root or Path(__file__).resolve().parents[3]).resolve()
    try:
        cfg = load_walkforward_config(args.config.resolve())
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    try:
        summary = run_walkforward(repo, cfg)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
