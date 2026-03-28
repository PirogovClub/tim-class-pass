"""Step 8 CLI: validate config, build folds, run walk-forward, full audit pipeline."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def _repo() -> Path:
    # Repository root (this file lives at src/ml/backtest/cli.py).
    return Path(__file__).resolve().parents[3]


def main() -> int:
    root = _repo()
    py = sys.executable
    p = argparse.ArgumentParser(description="ML Step 8 walk-forward backtest")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("validate-config", help="Validate walkforward_config.yaml")
    sub.add_parser("build-folds", help="Write walkforward_folds.json")
    sub.add_parser("run", help="Run full walk-forward evaluation")
    sub.add_parser(
        "full-audit-run",
        help="validate-config, build-folds, run (same as audit script inner steps)",
    )
    sub.add_parser(
        "policy-eval",
        help="Rebuild policy_report.json from backtest_predictions.jsonl + dataset (no retrain)",
    )
    sub.add_parser(
        "build-reports",
        help="Rebuild walkforward_report + dimensions + comparisons from fold_metrics (no retrain)",
    )

    args = p.parse_args()
    cfg = root / "ml" / "walkforward_config.yaml"

    if args.cmd == "validate-config":
        return subprocess.call([py, "-m", "ml.backtest.walkforward_config_loader", "--config", str(cfg)], cwd=root)
    if args.cmd == "build-folds":
        return subprocess.call([py, "-m", "ml.backtest.fold_builder", "--config", str(cfg)], cwd=root)
    if args.cmd == "run":
        return subprocess.call([py, "-m", "ml.backtest.walkforward_runner", "--config", str(cfg)], cwd=root)
    if args.cmd == "full-audit-run":
        rc = subprocess.call([py, "-m", "ml.backtest.walkforward_config_loader", "--config", str(cfg)], cwd=root)
        if rc != 0:
            return rc
        rc = subprocess.call([py, "-m", "ml.backtest.fold_builder", "--config", str(cfg)], cwd=root)
        if rc != 0:
            return rc
        return subprocess.call([py, "-m", "ml.backtest.walkforward_runner", "--config", str(cfg)], cwd=root)
    if args.cmd == "policy-eval":
        return subprocess.call([py, "-m", "ml.backtest.artifact_reports", "policy-eval", "--config", str(cfg)], cwd=root)
    if args.cmd == "build-reports":
        return subprocess.call([py, "-m", "ml.backtest.artifact_reports", "build-reports", "--config", str(cfg)], cwd=root)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
