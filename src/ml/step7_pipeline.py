"""Step 7 orchestration: validate spec, features, dataset, QA, baselines."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def main() -> int:
    # Repository root (this file lives at src/ml/step7_pipeline.py).
    root = Path(__file__).resolve().parents[2]
    py = sys.executable
    p = argparse.ArgumentParser(description="ML Step 7 pipeline entrypoints")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("validate-spec", help="Validate ml/feature_spec.yaml")
    b = sub.add_parser("build-features", help="Write feature_rows.jsonl")
    b.add_argument("--out", type=Path, default=root / "ml_output/step7/feature_rows.jsonl")
    d = sub.add_parser("build-dataset", help="Join labels + windows -> modeling_dataset.jsonl")
    d.add_argument("--labels", type=Path, default=root / "ml_output/step6_sample/generated_labels.jsonl")
    d.add_argument("--include-weak", action="store_true")
    d.add_argument(
        "--split-policy",
        choices=("time_ordered", "lesson_group"),
        default="time_ordered",
    )
    q = sub.add_parser("qa", help="Feature quality report")
    sub.add_parser("train-symbolic", help="Symbolic baseline report")
    sub.add_parser("train-tabular", help="LogReg + tree baselines (XGB/LGBM) + calibration reports")

    args = p.parse_args()
    if args.cmd == "validate-spec":
        return subprocess.call([py, "-m", "ml.feature_spec_loader"], cwd=root)
    if args.cmd == "build-features":
        return subprocess.call(
            [py, "-m", "ml.feature_builder", "--out", str(args.out)],
            cwd=root,
        )
    if args.cmd == "build-dataset":
        cmd = [
            py,
            "-m",
            "ml.dataset_builder",
            "--labels",
            str(args.labels),
        ]
        if args.include_weak:
            cmd.append("--include-weak")
        cmd.extend(["--split-policy", args.split_policy])
        return subprocess.call(cmd, cwd=root)
    if args.cmd == "qa":
        return subprocess.call([py, "-m", "ml.feature_qa"], cwd=root)
    if args.cmd == "train-symbolic":
        return subprocess.call([py, "-m", "ml.baselines.symbolic_baseline"], cwd=root)
    if args.cmd == "train-tabular":
        return subprocess.call([py, "-m", "ml.baselines.train_tabular_baseline"], cwd=root)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
