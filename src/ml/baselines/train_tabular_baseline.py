"""Train logistic regression (+ optional XGBoost) and calibration; write reports."""

from __future__ import annotations

import argparse
import json
import pickle
import sys
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from ml.baselines.calibration import brier_multiclass_aligned, calibration_bucket_report
from ml.baselines.evaluate_tabular_baseline import evaluate_multiclass
from ml.feature_spec_loader import load_feature_spec


def _load_rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def main() -> int:
    ap = argparse.ArgumentParser(description="Train tabular baselines (Step 7)")
    ap.add_argument("--ml-root", type=Path, default=Path("ml"))
    ap.add_argument("--dataset", type=Path, default=Path("ml_output/step7/modeling_dataset.jsonl"))
    ap.add_argument("--out-dir", type=Path, default=Path("ml_output/step7"))
    args = ap.parse_args()
    ml_root = args.ml_root.resolve()
    spec = load_feature_spec(ml_root / "feature_spec.yaml")
    path = args.dataset.resolve()
    if not path.is_file():
        print(f"ERROR: {path}", file=sys.stderr)
        return 1
    rows = _load_rows(path)

    num = spec["modeling_feature_columns"]["numeric"]
    cats = spec["modeling_feature_columns"]["categorical"]
    bools = spec["modeling_feature_columns"]["boolean"]
    num_ext = num + list(bools)

    eligible = [r for r in rows if r.get("eligible_for_training") and r.get("split") != "none"]
    class_labels = sorted({str(r["label"]) for r in eligible if r.get("label") is not None})
    if len(class_labels) < 2:
        print("ERROR: need at least 2 classes among eligible rows", file=sys.stderr)
        return 1

    lab_to_i = {l: i for i, l in enumerate(class_labels)}
    X_num: list[list[float]] = []
    X_cat: list[list[str]] = []
    y_list: list[int] = []
    for r in eligible:
        f = r.get("features") or {}
        X_num.append([float(f.get(c, 0) or 0) for c in num])
        if cats:
            X_cat.append([str(f.get(c, "unknown")) for c in cats])
        for c in bools:
            X_num[-1].append(1.0 if f.get(c) else 0.0)
        y_list.append(lab_to_i[str(r["label"])])

    Xn = np.array(X_num, dtype=np.float64)
    y = np.array(y_list, dtype=np.int64)
    train_m = np.array([r.get("split") == "train" for r in eligible], dtype=bool)
    val_m = np.array([r.get("split") == "validation" for r in eligible], dtype=bool)
    test_m = np.array([r.get("split") == "test" for r in eligible], dtype=bool)

    if not np.any(train_m) or not np.any(test_m):
        print("ERROR: need train and test splits among eligible rows", file=sys.stderr)
        return 1

    ohe: OneHotEncoder | None = None
    if cats:
        ohe = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
        Xc = np.array(X_cat, dtype=object)
        scaler = StandardScaler()
        X_train_num = scaler.fit_transform(Xn[train_m])
        X_train_cat = ohe.fit_transform(Xc[train_m])
        X_train = np.hstack([X_train_num, X_train_cat])
        X_test = np.hstack([scaler.transform(Xn[test_m]), ohe.transform(Xc[test_m])])
        X_val = (
            np.hstack([scaler.transform(Xn[val_m]), ohe.transform(Xc[val_m])])
            if np.any(val_m)
            else None
        )
    else:
        scaler = StandardScaler()
        X_train = scaler.fit_transform(Xn[train_m])
        X_test = scaler.transform(Xn[test_m])
        X_val = scaler.transform(Xn[val_m]) if np.any(val_m) else None

    y_train = y[train_m]
    y_test = y[test_m]
    y_val = y[val_m] if np.any(val_m) else None

    clf = LogisticRegression(max_iter=500, random_state=42)
    clf.fit(X_train, y_train)

    out_dir = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    proba_test_raw = clf.predict_proba(X_test)
    pred_test = clf.predict(X_test)
    rep_raw = evaluate_multiclass(
        [class_labels[i] for i in y_test],
        [class_labels[i] for i in pred_test],
        class_labels,
    )
    brier_raw = brier_multiclass_aligned(y_test, proba_test_raw, clf.classes_)

    cal_report: dict[str, Any] = {"calibration_method": "none", "reason": "insufficient validation rows"}
    proba_test_cal = proba_test_raw
    brier_cal = brier_raw

    if X_val is not None and y_val is not None and len(y_val) >= 2 and np.unique(y_val).size >= 2:
        try:
            cal = CalibratedClassifierCV(clf, method="sigmoid", cv="prefit")
            cal.fit(X_val, y_val)
            proba_test_cal = cal.predict_proba(X_test)
            brier_cal = brier_multiclass_aligned(y_test, proba_test_cal, cal.classes_)
            cal_report = {
                "calibration_method": "Platt_sigmoid_CalibratedClassifierCV_prefit",
                "validation_rows": int(len(y_val)),
                "brier_score_before": brier_raw,
                "brier_score_after": brier_cal,
                "bucket_report_after": calibration_bucket_report(
                    y_test, proba_test_cal, cal.classes_, n_bins=4
                ),
            }
            with (out_dir / "logreg_calibrated_model.pkl").open("wb") as f:
                pickle.dump({"scaler": scaler, "ohe": ohe, "model": cal}, f)
        except Exception as e:
            cal_report = {"calibration_method": "failed", "error": str(e)}

    pred_cal = proba_test_cal.argmax(axis=1)
    rep_cal = evaluate_multiclass(
        [class_labels[i] for i in y_test],
        [class_labels[i] for i in pred_cal],
        class_labels,
    )

    n_feat = X_train.shape[1]
    coef_report: dict[str, Any] = {
        "model": "logistic_regression",
        "n_features_in": int(n_feat),
        "feature_names_hint": num_ext + [f"ohe_dim_{i}" for i in range(max(0, n_feat - len(num_ext)))],
        "coef": clf.coef_.tolist() if hasattr(clf, "coef_") else [],
        "intercept": clf.intercept_.tolist() if hasattr(clf, "intercept_") else [],
        "classes": class_labels,
    }

    (out_dir / "baseline_logreg_report.json").write_text(
        json.dumps(
            {
                "model": "logistic_regression",
                "test_evaluation_uncalibrated": rep_raw,
                "test_evaluation_after_calibration": rep_cal,
                "brier_uncalibrated": brier_raw,
                "brier_calibrated": brier_cal,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (out_dir / "coefficient_report.json").write_text(json.dumps(coef_report, indent=2) + "\n", encoding="utf-8")
    (out_dir / "calibration_report.json").write_text(json.dumps(cal_report, indent=2) + "\n", encoding="utf-8")

    xgb_rep: dict[str, Any] = {"status": "skipped"}
    try:
        import xgboost as xgb  # type: ignore

        if len(y_train) >= 4 and len(np.unique(y_train)) >= 2:
            xclf = xgb.XGBClassifier(
                n_estimators=40,
                max_depth=4,
                random_state=42,
                learning_rate=0.2,
            )
            xclf.fit(X_train, y_train)
            pred_x = xclf.predict(X_test)
            xgb_rep = {
                "status": "ok",
                "evaluation": evaluate_multiclass(
                    [class_labels[i] for i in y_test],
                    [class_labels[i] for i in pred_x],
                    class_labels,
                ),
                "feature_importance_gain": xclf.feature_importances_.tolist(),
            }
    except Exception as e:
        xgb_rep = {"status": "error", "error": str(e)}

    lgb_rep: dict[str, Any] = {"status": "skipped"}
    try:
        import lightgbm as lgb  # type: ignore

        if len(y_train) >= 4 and len(np.unique(y_train)) >= 2:
            lclf = lgb.LGBMClassifier(
                n_estimators=40,
                max_depth=4,
                random_state=42,
                learning_rate=0.2,
                verbosity=-1,
            )
            lclf.fit(X_train, y_train)
            pred_l = lclf.predict(X_test)
            lgb_rep = {
                "status": "ok",
                "evaluation": evaluate_multiclass(
                    [class_labels[i] for i in y_test],
                    [class_labels[i] for i in pred_l],
                    class_labels,
                ),
                "feature_importance_gain": lclf.feature_importances_.tolist(),
            }
    except Exception as e:
        lgb_rep = {"status": "error", "error": str(e)}

    tree_rep = {
        "xgboost": xgb_rep,
        "lightgbm": lgb_rep,
        "note": "Either tree library may be unavailable in the environment; errors are non-fatal.",
    }
    (out_dir / "baseline_xgb_or_lgbm_report.json").write_text(json.dumps(tree_rep, indent=2) + "\n", encoding="utf-8")
    (out_dir / "feature_importance_report.json").write_text(
        json.dumps(
            {
                "xgb_gain": xgb_rep.get("feature_importance_gain"),
                "lightgbm_gain": lgb_rep.get("feature_importance_gain"),
                "logreg_coef_shape": list(np.array(clf.coef_).shape),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"Wrote reports under {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
