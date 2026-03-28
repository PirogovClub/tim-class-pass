"""Heuristic symbolic classifier from PIT-safe features only."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

CLASSES = [
    "acceptance_above",
    "acceptance_below",
    "false_breakout_up",
    "false_breakout_down",
    "rejection",
    "no_setup",
]


def symbolic_predict(feats: dict[str, Any]) -> str:
    """Simple depth-1 rules; fallback no_setup."""
    cdp = float(feats.get("close_distance_pct", 0))
    nap = int(feats.get("n_closes_above_level_pre", 0))
    nbp = int(feats.get("n_closes_below_level_pre", 0))
    pup = float(feats.get("persistence_ratio_above_pre", 0))
    uwick = float(feats.get("upper_wick_ratio_anchor", 0))
    lwick = float(feats.get("lower_wick_ratio_anchor", 0))
    reentry = int(feats.get("reentry_through_level_pre", 0))

    if nap >= 2 and cdp > 0.0005 and pup > 0.2:
        return "acceptance_above"
    if nbp >= 2 and cdp < -0.0005:
        return "acceptance_below"
    if uwick > 0.45 and cdp < 0.001 and nap < 2:
        return "false_breakout_up"
    if lwick > 0.45 and cdp > -0.001 and nbp < 2:
        return "false_breakout_down"
    if reentry >= 2 and abs(cdp) < 0.003:
        return "rejection"
    return "no_setup"


def _confusion(y_true: list[str], y_pred: list[str], labels: list[str]) -> dict[str, dict[str, int]]:
    m: dict[str, dict[str, int]] = {t: {p: 0 for p in labels} for t in labels}
    for t, p in zip(y_true, y_pred):
        if t in m and p in m[t]:
            m[t][p] += 1
    return m


def evaluate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    eligible = [r for r in rows if r.get("eligible_for_training")]
    y_true = [str(r.get("label")) for r in eligible]
    y_pred = [symbolic_predict(r.get("features") or {}) for r in eligible]
    labels = CLASSES + ["ambiguous"]
    # map unknown labels to string
    cm = _confusion(y_true, y_pred, labels)
    correct = sum(1 for a, b in zip(y_true, y_pred) if a == b)
    acc = correct / len(eligible) if eligible else 0.0
    return {
        "baseline_id": "symbolic_v1",
        "n_samples": len(eligible),
        "accuracy": acc,
        "confusion_matrix": cm,
        "limitations": "Heuristic thresholds; not trained; misses ambiguous (treated as structural classes only).",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Symbolic baseline evaluation")
    ap.add_argument("--dataset", type=Path, default=Path("ml_output/step7/modeling_dataset.jsonl"))
    ap.add_argument("--out", type=Path, default=Path("ml_output/step7/baseline_symbolic_report.json"))
    args = ap.parse_args()
    path = args.dataset.resolve()
    if not path.is_file():
        print(f"ERROR: {path}", file=sys.stderr)
        return 1
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    rep = evaluate(rows)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(rep, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {args.out} accuracy={rep['accuracy']:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
