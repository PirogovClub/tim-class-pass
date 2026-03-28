"""Load Step 8 (and optional upstream) artifacts; build normalized evidence summary."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

REQUIRED_TOP_LEVEL_KEYS = (
    "task_id",
    "evidence",
    "minimum_evidence",
    "baseline_comparison",
    "outputs",
    "tie_break_order",
    "scoring",
    "no_go",
)


class Step9ConfigError(ValueError):
    pass


class Step9EvidenceError(FileNotFoundError):
    pass


def load_step9_decision_config(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise Step9ConfigError(f"Decision config not found: {path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise Step9ConfigError("Decision config must be a YAML mapping")
    for k in REQUIRED_TOP_LEVEL_KEYS:
        if k not in raw:
            raise Step9ConfigError(f"Missing required key: {k}")
    ev = raw["evidence"]
    if not isinstance(ev, dict) or "step8_root" not in ev or "required_files" not in ev:
        raise Step9ConfigError("evidence.step8_root and evidence.required_files are required")
    req = ev["required_files"]
    if not isinstance(req, dict):
        raise Step9ConfigError("evidence.required_files must be a mapping")
    for name in (
        "walkforward_report",
        "fold_metrics",
        "model_comparison_report",
        "calibration_drift_report",
        "policy_report",
        "backtest_predictions",
        "step8_manifest",
    ):
        if name not in req:
            raise Step9ConfigError(f"evidence.required_files missing {name}")
    tbo = raw["tie_break_order"]
    if not isinstance(tbo, list) or len(tbo) < 4:
        raise Step9ConfigError("tie_break_order must list all four outcomes")
    expected = {"tabular_only_for_now", "sequence_model_next", "vision_model_next", "improve_upstream_first"}
    if set(tbo) != expected:
        raise Step9ConfigError(f"tie_break_order must be a permutation of {expected}")
    ng = raw.get("no_go")
    if not isinstance(ng, dict) or ng.get("outcome") != "improve_upstream_first":
        raise Step9ConfigError("no_go must be a mapping with outcome: improve_upstream_first")
    return raw


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def resolve_step8_paths(cfg: dict[str, Any], repo_root: Path) -> dict[str, Path]:
    ev = cfg["evidence"]
    root = (repo_root / str(ev["step8_root"])).resolve()
    req = ev["required_files"]
    out: dict[str, Path] = {}
    for logical, fname in req.items():
        out[logical] = (root / str(fname)).resolve()
    return out


def load_optional_paths(cfg: dict[str, Any], repo_root: Path) -> dict[str, Path | None]:
    ev = cfg["evidence"]
    opt = ev.get("optional_files") or {}
    out: dict[str, Path | None] = {}
    for key, val in opt.items():
        if val is None or val == "":
            out[key] = None
        else:
            p = (repo_root / str(val)).resolve()
            out[key] = p if p.is_file() else None
    return out


def load_step8_artifacts(paths: dict[str, Path], *, strict: bool = True) -> dict[str, Any]:
    loaded: dict[str, Any] = {}
    missing: list[str] = []
    for logical, p in paths.items():
        if not p.is_file():
            missing.append(str(p))
            continue
        if logical == "backtest_predictions":
            loaded[logical] = _read_jsonl(p)
        else:
            loaded[logical] = _read_json(p)
    if missing and strict:
        raise Step9EvidenceError("Missing required Step 8 artifacts:\n" + "\n".join(missing))
    if missing:
        loaded["_missing_paths"] = missing
    return loaded


def build_evidence_summary(
    cfg: dict[str, Any],
    repo_root: Path,
    *,
    strict: bool = True,
) -> dict[str, Any]:
    paths = resolve_step8_paths(cfg, repo_root)
    raw = load_step8_artifacts(paths, strict=strict)
    if not strict and raw.get("_missing_paths"):
        return {
            "step9_evidence_summary_id": "step9_evidence_summary_v1",
            "task_id": cfg.get("task_id"),
            "status": "incomplete",
            "missing_required": raw["_missing_paths"],
            "sources": {k: str(v) for k, v in paths.items()},
        }

    wf = raw["walkforward_report"]
    mc = raw["model_comparison_report"]
    fm = raw["fold_metrics"]
    man = raw["step8_manifest"]
    cal = raw["calibration_drift_report"]
    pol = raw["policy_report"]
    pred = raw["backtest_predictions"]

    fold_list = fm.get("fold_metrics") if isinstance(fm, dict) else None
    n_folds = len(fold_list) if isinstance(fold_list, list) else 0

    opt_paths = load_optional_paths(cfg, repo_root)
    optional_loaded: dict[str, Any] = {}
    for key, p in opt_paths.items():
        if p is not None:
            optional_loaded[key] = _read_json(p)

    answers = wf.get("answers") or {}
    sym = (mc.get("symbolic") or {}) if isinstance(mc, dict) else {}
    lr = (mc.get("logistic_regression") or {}) if isinstance(mc, dict) else {}

    return {
        "step9_evidence_summary_id": "step9_evidence_summary_v1",
        "task_id": cfg.get("task_id"),
        "status": "complete",
        "pit_declaration": cfg.get("pit_declaration", ""),
        "sources": {k: str(v) for k, v in paths.items()},
        "optional_sources": {k: str(v) for k, v in opt_paths.items() if v is not None},
        "counts": {
            "folds": n_folds,
            "prediction_lines": len(pred),
            "step8_manifest_prediction_lines": (man.get("counts") or {}).get("prediction_lines"),
        },
        "model_comparison_headline": {
            "symbolic_macro_f1_mean": sym.get("macro_f1_mean"),
            "logistic_regression_macro_f1_mean": lr.get("macro_f1_mean"),
            "logistic_regression_macro_f1_pstdev": lr.get("macro_f1_pstdev"),
            "symbolic_macro_f1_pstdev": sym.get("macro_f1_pstdev"),
        },
        "walkforward_answers_excerpt": {
            "best_model_by_mean_macro_f1": answers.get("best_model_by_mean_macro_f1"),
            "most_stable_by_macro_f1_std": answers.get("most_stable_by_macro_f1_std"),
            "which_classes_remain_weak": answers.get("which_classes_remain_weak"),
            "calibration_forward_behavior": answers.get("calibration_forward_behavior"),
        },
        "calibration_drift_excerpt": {
            "n_folds_with_metrics": cal.get("n_folds_with_metrics"),
            "drift_heuristic": cal.get("drift_heuristic"),
            "brier_raw_mean": (cal.get("brier_raw") or {}).get("mean"),
        },
        "policy_excerpt": {
            "summary_bullets": pol.get("summary_bullets"),
        },
        "optional_upstream": optional_loaded,
    }
