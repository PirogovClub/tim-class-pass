"""Rebuild policy report and aggregate reports from existing Step 8 artifacts (no retrain)."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from ml.backtest.policy_evaluator import evaluate_policies
from ml.backtest.report_builder import (
    build_aggregate_dimensions_report,
    build_confusion_matrices_bundle,
    build_model_comparison_report,
    build_per_class_fold_metrics,
    build_threshold_sweep_report,
    build_walkforward_report,
    write_json,
)
from ml.backtest.walkforward_config_loader import load_walkforward_config, resolve_paths


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _rows_by_id(dataset_path: Path) -> dict[str, dict[str, Any]]:
    rows = [json.loads(l) for l in dataset_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    return {str(r["dataset_row_id"]): r for r in rows if r.get("dataset_row_id")}


def run_policy_eval(repo_root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    paths = resolve_paths(cfg, repo_root)
    out_root = Path(cfg["outputs"]["root"])
    if not out_root.is_absolute():
        out_root = repo_root / out_root
    pred_path = out_root / cfg["outputs"]["backtest_predictions"]
    by_id = _rows_by_id(paths["dataset"])
    by_fold: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for line in pred_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        o = json.loads(line)
        by_fold[str(o["fold_id"])].append(o)

    all_policies: dict[str, list[dict[str, Any]]] = defaultdict(list)
    bullets: list[str] = []

    for fold_id, recs in sorted(by_fold.items()):
        by_model: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for o in recs:
            by_model[str(o["model_name"])].append(o)
        lr = by_model.get("logistic_regression", [])
        lr.sort(key=lambda x: str(x.get("dataset_row_id", "")))
        test_rows = []
        aligned_lr = []
        for o in lr:
            rid = str(o.get("dataset_row_id", ""))
            r = by_id.get(rid)
            if r is None:
                continue
            test_rows.append(r)
            aligned_lr.append(o)
        preds_for_pol: dict[str, list[dict[str, Any]]] = {}
        if aligned_lr:
            preds_for_pol["logistic_regression"] = aligned_lr
        sym_recs = by_model.get("symbolic", [])
        sym_recs.sort(key=lambda x: str(x.get("dataset_row_id", "")))
        aligned_sym = []
        test_sym = []
        for o in sym_recs:
            rid = str(o.get("dataset_row_id", ""))
            r = by_id.get(rid)
            if r is None:
                continue
            aligned_sym.append(o)
            test_sym.append(r)
        if aligned_sym and len(aligned_sym) == len(test_sym):
            preds_for_pol["symbolic"] = aligned_sym
        if not preds_for_pol or not test_rows:
            continue
        pol = evaluate_policies(
            test_rows,
            preds_for_pol,
            thresholds=[float(x) for x in cfg["policy"].get("probability_thresholds", [0.35])],
            symbolic_and_model_threshold=float(cfg["policy"].get("symbolic_and_model_threshold", 0.35)),
        )
        for k, v in pol["policies"].items():
            if isinstance(v, dict):
                all_policies[k].append({"fold_id": fold_id, **v})
        bullets.append(f"{fold_id}: n_policies={len(pol['policies'])}")

    return {
        "policy_report_id": "policy_report_v1",
        "source": "artifact_regeneration_from_predictions",
        "per_policy_across_folds": {k: v for k, v in all_policies.items()},
        "per_fold_bullets": bullets,
        "summary_bullets": bullets[:5],
    }


def run_build_reports(repo_root: Path, cfg: dict[str, Any]) -> None:
    paths = resolve_paths(cfg, repo_root)
    out_root = Path(cfg["outputs"]["root"])
    if not out_root.is_absolute():
        out_root = repo_root / out_root
    fm_path = out_root / cfg["outputs"]["fold_metrics"]
    drift_path = out_root / cfg["outputs"]["calibration_drift_report"]
    folds_path = out_root / cfg["outputs"]["walkforward_folds"]
    pred_path = out_root / cfg["outputs"]["backtest_predictions"]

    fm_data = _load_json(fm_path)
    fold_metrics = fm_data["fold_metrics"] if isinstance(fm_data, dict) and "fold_metrics" in fm_data else fm_data
    if not isinstance(fold_metrics, list):
        raise ValueError("fold_metrics.json must contain key fold_metrics or be a list")

    folds_payload = _load_json(folds_path) if folds_path.is_file() else {"skipped_fold_reasons": []}
    drift = _load_json(drift_path) if drift_path.is_file() else {}

    from ml.backtest.report_builder import infer_weak_classes

    weak = infer_weak_classes(fold_metrics)
    by_id = _rows_by_id(paths["dataset"])
    dim = build_aggregate_dimensions_report(pred_path, by_id)
    headline_parts: list[str] = []
    for label, block in (("tf", dim.get("by_timeframe")), ("tier", dim.get("by_confidence_tier"))):
        if isinstance(block, dict) and block:
            first_k = next(iter(block.keys()))
            headline_parts.append(f"{label}:{first_k} acc={block[first_k].get('accuracy', 0):.3f}")
    dim_summary = {"headline": "; ".join(headline_parts) if headline_parts else None}

    policy_agg = run_policy_eval(repo_root, cfg)

    wf = build_walkforward_report(
        task_id=cfg["task_id"],
        folds_payload=folds_payload,
        fold_metrics=fold_metrics,
        policy_aggregate=policy_agg,
        pit_declaration=cfg.get("pit_declaration", ""),
        drift_report=drift if isinstance(drift, dict) else {},
        weak_classes=weak,
        aggregate_dimensions_summary=dim_summary,
    )
    write_json(out_root / cfg["outputs"]["walkforward_report"], wf)
    write_json(out_root / cfg["outputs"]["model_comparison_report"], build_model_comparison_report(fold_metrics))
    write_json(out_root / cfg["outputs"]["aggregate_dimensions_report"], dim)
    write_json(out_root / cfg["outputs"]["policy_report"], policy_agg)
    write_json(out_root / cfg["outputs"]["threshold_sweep_report"], build_threshold_sweep_report([]))
    write_json(out_root / cfg["outputs"]["per_class_fold_metrics"], build_per_class_fold_metrics(fold_metrics))
    write_json(out_root / cfg["outputs"]["confusion_matrices"], build_confusion_matrices_bundle(fold_metrics))


def main() -> int:
    ap = argparse.ArgumentParser(description="Step 8 artifact-only policy/report regeneration")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_pol = sub.add_parser("policy-eval", help="Rebuild policy_report.json from predictions + dataset")
    p_pol.add_argument("--config", type=Path, default=Path("src/ml/walkforward_config.yaml"))
    p_rep = sub.add_parser("build-reports", help="Rebuild walkforward + comparison + dimensions from fold_metrics")
    p_rep.add_argument("--config", type=Path, default=Path("src/ml/walkforward_config.yaml"))
    args = ap.parse_args()
    repo = Path(__file__).resolve().parents[3]
    try:
        cfg = load_walkforward_config(args.config.resolve())
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    out_root = Path(cfg["outputs"]["root"])
    if not out_root.is_absolute():
        out_root = repo / out_root
    if args.cmd == "policy-eval":
        rep = run_policy_eval(repo, cfg)
        write_json(out_root / cfg["outputs"]["policy_report"], rep)
        print(json.dumps({"wrote": str(out_root / cfg["outputs"]["policy_report"])}, indent=2))
        return 0
    if args.cmd == "build-reports":
        try:
            run_build_reports(repo, cfg)
        except Exception as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 1
        print(json.dumps({"out_dir": str(out_root)}, indent=2))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
