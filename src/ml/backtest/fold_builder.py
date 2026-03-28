"""Deterministic time-aware walk-forward fold construction."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from ml.backtest.walkforward_config_loader import load_walkforward_config


def _tier_ok(row: dict[str, Any], primary: list[str], include_weak_track: bool) -> bool:
    tier = str(row.get("confidence_tier", ""))
    if tier in primary:
        return True
    if include_weak_track and tier == "weak":
        return True
    return False


def _status_excluded(row: dict[str, Any], excluded: list[str]) -> bool:
    st = str(row.get("label_status", ""))
    return st in excluded


def filter_eval_pool(rows: list[dict[str, Any]], inclusion: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Return (pool, exclusion_log). Primary pool uses tiers + status rules."""
    primary = list(inclusion.get("confidence_tiers_primary") or [])
    excl = list(inclusion.get("exclude_label_status") or [])
    weak_track = bool(inclusion.get("include_weak_sensitivity_track"))
    req_elig = bool(inclusion.get("require_eligible_for_training", True))

    excl_lessons = {str(x) for x in (inclusion.get("exclude_lesson_ids") or [])}
    pool: list[dict[str, Any]] = []
    log: dict[str, Any] = {
        "input_rows": len(rows),
        "excluded_not_eligible": 0,
        "excluded_tier": 0,
        "excluded_label_status": 0,
        "excluded_lesson_id": 0,
        "included_primary": 0,
    }
    for r in rows:
        if req_elig and not r.get("eligible_for_training"):
            log["excluded_not_eligible"] += 1
            continue
        if _status_excluded(r, excl):
            log["excluded_label_status"] += 1
            continue
        if excl_lessons:
            ref = r.get("source_refs") if isinstance(r.get("source_refs"), dict) else {}
            lid = ref.get("lesson_id")
            if lid is not None and str(lid) in excl_lessons:
                log["excluded_lesson_id"] += 1
                continue
        if not _tier_ok(r, primary, weak_track):
            log["excluded_tier"] += 1
            continue
        pool.append(r)
        log["included_primary"] += 1
    return pool, log


def sort_by_time(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda r: (str(r.get("anchor_timestamp", "")), str(r.get("candidate_id", ""))))


def build_folds(sorted_pool: list[dict[str, Any]], fold_policy: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    """
    Expanding walk-forward: fold k uses train [0:val_start), val [val_start:test_start), test [test_start:test_end).
    Next fold: val_start := test_start, test_start := test_end, test_end += test_window_rows; train is always [0:val_start).
    """
    skips: list[str] = []
    min_tr = int(fold_policy["min_train_rows"])
    min_va = int(fold_policy["min_val_rows"])
    test_w = int(fold_policy["test_window_rows"])
    step_decl = fold_policy.get("step_size_rows")
    if step_decl is not None and int(step_decl) != test_w:
        raise ValueError(
            "fold_policy.step_size_rows must equal test_window_rows for expanding_absorb_val_into_train v1 "
            f"(got step_size_rows={step_decl}, test_window_rows={test_w})"
        )
    max_folds = int(fold_policy["max_folds"])
    skip_insuff = bool(fold_policy.get("skip_fold_if_insufficient_classes", True))
    min_cls = int(fold_policy.get("min_classes_in_train", 2))

    n = len(sorted_pool)
    folds: list[dict[str, Any]] = []
    val_start = min_tr
    test_start = val_start + min_va
    test_end = test_start + test_w
    fold_idx = 0

    while test_end <= n and fold_idx < max_folds:
        train_rows = sorted_pool[0:val_start]
        val_rows = sorted_pool[val_start:test_start]
        test_rows = sorted_pool[test_start:test_end]

        if skip_insuff:
            train_labels = {str(r.get("label")) for r in train_rows if r.get("label") is not None}
            if len(train_labels) < min_cls:
                skips.append(
                    f"fold_candidate_{fold_idx}: insufficient distinct labels in train ({len(train_labels)}<{min_cls})"
                )
                val_start = test_start
                test_start = test_end
                test_end = test_start + test_w
                fold_idx += 1
                continue

        def _bounds(chunk: list[dict[str, Any]]) -> tuple[str, str]:
            if not chunk:
                return "", ""
            ts = [str(r.get("anchor_timestamp", "")) for r in chunk]
            return min(ts), max(ts)

        def _label_counts(chunk: list[dict[str, Any]]) -> dict[str, int]:
            return dict(Counter(str(r.get("label")) for r in chunk if r.get("label") is not None))

        tr_s, tr_e = _bounds(train_rows)
        va_s, va_e = _bounds(val_rows)
        te_s, te_e = _bounds(test_rows)

        fold_id = f"fold_{fold_idx:03d}"
        fold_obj: dict[str, Any] = {
            "fold_id": fold_id,
            "train_anchor_start": tr_s,
            "train_anchor_end": tr_e,
            "val_anchor_start": va_s,
            "val_anchor_end": va_e,
            "test_anchor_start": te_s,
            "test_anchor_end": te_e,
            "train_start": tr_s,
            "train_end": tr_e,
            "val_start": va_s,
            "val_end": va_e,
            "test_start": te_s,
            "test_end": te_e,
            "row_counts": {
                "train": len(train_rows),
                "validation": len(val_rows),
                "test": len(test_rows),
            },
            "label_counts": {
                "train": _label_counts(train_rows),
                "validation": _label_counts(val_rows),
                "test": _label_counts(test_rows),
            },
            "train_row_indices": list(range(0, val_start)),
            "val_row_indices": list(range(val_start, test_start)),
            "test_row_indices": list(range(test_start, test_end)),
            "step_size_rows": test_w,
        }
        folds.append(fold_obj)

        val_start = test_start
        test_start = test_end
        test_end = test_start + test_w
        fold_idx += 1

    if not folds:
        skips.append("no folds: pool too small for min_train+min_val+test_window")
    return folds, skips


def materialize_fold_rows(sorted_pool: list[dict[str, Any]], fold: dict[str, Any]) -> tuple[list, list, list]:
    tr_i = fold["train_row_indices"]
    va_i = fold["val_row_indices"]
    te_i = fold["test_row_indices"]
    return (
        [sorted_pool[i] for i in tr_i],
        [sorted_pool[i] for i in va_i],
        [sorted_pool[i] for i in te_i],
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Build walk-forward folds JSON from config + dataset")
    ap.add_argument("--config", type=Path, default=Path("src/ml/walkforward_config.yaml"))
    ap.add_argument("--dataset", type=Path, default=None, help="Override dataset path")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    repo = Path(__file__).resolve().parents[3]
    try:
        cfg = load_walkforward_config(args.config.resolve())
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    ds_path = args.dataset or Path(cfg["dataset"]["path"])
    if not ds_path.is_absolute():
        ds_path = repo / ds_path
    if not ds_path.is_file():
        print(f"ERROR: missing dataset {ds_path}", file=sys.stderr)
        return 1
    rows = [json.loads(l) for l in ds_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    pool, excl = filter_eval_pool(rows, cfg["inclusion"])
    sorted_pool = sort_by_time(pool)
    folds, skips = build_folds(sorted_pool, cfg["fold_policy"])
    out_root = Path(cfg["outputs"]["root"])
    if not out_root.is_absolute():
        out_root = repo / out_root
    out_path = args.out or (out_root / cfg["outputs"]["walkforward_folds"])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "walkforward_folds_id": "walkforward_folds_v1",
        "task_id": cfg["task_id"],
        "dataset_path": str(ds_path),
        "exclusion_log": excl,
        "pool_size_after_filter": len(sorted_pool),
        "folds": folds,
        "skipped_fold_reasons": skips,
        "pit_note": cfg.get("pit_declaration", ""),
    }
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {out_path} ({len(folds)} folds)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
