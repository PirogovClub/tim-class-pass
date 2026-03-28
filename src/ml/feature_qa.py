"""Feature and dataset quality checks (Step 7)."""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

from ml.feature_spec_loader import load_feature_spec


def _rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def _split_balance(trainable: list[dict[str, Any]]) -> dict[str, Any]:
    """Per-split counts and label / tier distributions for trainable rows."""
    by_split: dict[str, dict[str, Any]] = {}
    for r in trainable:
        sp = str(r.get("split", "none"))
        if sp not in by_split:
            by_split[sp] = {"row_count": 0, "by_label": Counter(), "by_confidence_tier": Counter()}
        by_split[sp]["row_count"] += 1
        by_split[sp]["by_label"][str(r.get("label"))] += 1
        by_split[sp]["by_confidence_tier"][str(r.get("confidence_tier"))] += 1
    out: dict[str, Any] = {}
    for sp, d in sorted(by_split.items()):
        out[sp] = {
            "row_count": d["row_count"],
            "label_distribution": dict(d["by_label"]),
            "confidence_tier_distribution": dict(d["by_confidence_tier"]),
        }
    return out


def _numeric_correlation_warnings(
    trainable: list[dict[str, Any]],
    num_cols: list[str],
    *,
    threshold: float = 0.95,
) -> list[dict[str, Any]]:
    if len(trainable) < 3 or len(num_cols) < 2:
        return []
    X: list[list[float]] = []
    for r in trainable:
        f = r.get("features") or {}
        row: list[float] = []
        for c in num_cols:
            v = f.get(c)
            if v is None or (isinstance(v, float) and math.isnan(v)):
                row.append(0.0)
            else:
                row.append(float(v))
        X.append(row)
    m = np.asarray(X, dtype=np.float64)
    if m.shape[0] < 2:
        return []
    c = np.corrcoef(m, rowvar=False)
    warns: list[dict[str, Any]] = []
    for i in range(len(num_cols)):
        for j in range(i + 1, len(num_cols)):
            rij = c[i, j]
            if math.isnan(float(rij)):
                continue
            if abs(float(rij)) >= threshold:
                warns.append(
                    {
                        "feature_a": num_cols[i],
                        "feature_b": num_cols[j],
                        "pearson_r": float(rij),
                    }
                )
    return warns


def run_feature_qa(
    dataset_path: Path,
    spec_path: Path,
) -> dict[str, Any]:
    spec = load_feature_spec(spec_path)
    num_cols = spec["modeling_feature_columns"]["numeric"]
    bool_cols = spec["modeling_feature_columns"]["boolean"]
    cat_cols = spec["modeling_feature_columns"]["categorical"]

    rows = _rows(dataset_path)
    trainable = [r for r in rows if r.get("eligible_for_training")]
    excluded_n = sum(1 for r in rows if r.get("label_status") in ("excluded", "skipped_invalid_input"))
    amb_n = sum(1 for r in rows if r.get("label_status") == "ambiguous")
    weak_n = sum(1 for r in rows if r.get("confidence_tier") == "weak")

    by_label = Counter(str(r.get("label")) for r in rows)
    by_tier = Counter(str(r.get("confidence_tier")) for r in rows)

    null_rates: dict[str, float] = {}
    constants: list[str] = []
    extremes: dict[str, int] = {}

    for col in num_cols:
        vals = []
        for r in trainable:
            f = r.get("features") or {}
            v = f.get(col)
            if v is None or (isinstance(v, float) and math.isnan(v)):
                vals.append(None)
            else:
                vals.append(float(v))
        n = len(vals)
        null_rates[col] = sum(1 for v in vals if v is None) / n if n else 0.0
        finite = [v for v in vals if v is not None]
        if len(finite) >= 2 and max(finite) - min(finite) < 1e-12:
            constants.append(col)
        extremes[col] = sum(1 for v in finite if v is not None and (abs(v) > 1e6 or abs(v) < 1e-12 and v != 0))

    dup_candidates = Counter(r.get("candidate_id") for r in rows)
    dups = {k: v for k, v in dup_candidates.items() if v > 1}

    pit_ok = sum(1 for r in rows if r.get("point_in_time_safe"))
    pit_bad = len(rows) - pit_ok

    split_bal = _split_balance(trainable)
    trainable_with_split = [r for r in trainable if r.get("split") not in (None, "none", "")]
    corr_warns = _numeric_correlation_warnings(trainable_with_split, num_cols, threshold=0.95)

    return {
        "feature_quality_report_id": "feature_quality_v2",
        "row_counts": {
            "total_rows": len(rows),
            "trainable_row_counts": len(trainable),
            "excluded_or_skipped_rows": excluded_n,
            "ambiguous_rows": amb_n,
            "weak_tier_rows": weak_n,
        },
        "split_balance_trainable": split_bal,
        "high_correlation_numeric_pairs_trainable": corr_warns,
        "label_distribution": dict(by_label),
        "confidence_tier_distribution": dict(by_tier),
        "per_feature_null_rates_trainable": null_rates,
        "near_constant_numeric_features": constants,
        "extreme_value_flags": extremes,
        "duplicate_candidate_ids": dups,
        "point_in_time_safe_rows": pit_ok,
        "point_in_time_safe_false_rows": pit_bad,
        "leakage_heuristics": {
            "note": "Post-anchor bars must not appear in features; enforced in feature_builder.",
            "feature_columns_checked": num_cols,
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Run feature QA on modeling dataset")
    ap.add_argument("--dataset", type=Path, default=Path("ml_output/step7/modeling_dataset.jsonl"))
    ap.add_argument("--spec", type=Path, default=Path("src/ml/feature_spec.yaml"))
    ap.add_argument("--out", type=Path, default=Path("ml_output/step7/feature_quality_report.json"))
    args = ap.parse_args()
    if not args.dataset.resolve().is_file():
        print(f"ERROR: {args.dataset}", file=sys.stderr)
        return 1
    rep = run_feature_qa(args.dataset.resolve(), args.spec.resolve())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(rep, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
