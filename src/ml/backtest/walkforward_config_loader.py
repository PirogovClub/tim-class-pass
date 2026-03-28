"""Load and validate ml/walkforward_config.yaml."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml


class WalkforwardConfigError(Exception):
    pass


REQUIRED_TOP = (
    "task_id",
    "dataset",
    "ml_root",
    "inclusion",
    "fold_policy",
    "reproducibility",
    "models",
    "calibration",
    "policy",
    "metrics",
    "outputs",
    "pit_declaration",
)


def load_walkforward_config(path: Path) -> dict[str, Any]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise WalkforwardConfigError("root must be a mapping")
    miss = [k for k in REQUIRED_TOP if k not in raw]
    if miss:
        raise WalkforwardConfigError(f"missing keys: {miss}")
    ds = raw["dataset"]
    if not isinstance(ds, dict) or "path" not in ds:
        raise WalkforwardConfigError("dataset.path required")
    fp = raw["fold_policy"]
    for k in ("min_train_rows", "min_val_rows", "test_window_rows", "max_folds"):
        if k not in fp:
            raise WalkforwardConfigError(f"fold_policy.{k} required")
    if int(fp["min_train_rows"]) < 1 or int(fp["min_val_rows"]) < 0:
        raise WalkforwardConfigError("invalid fold_policy row minima")
    raw.setdefault("grouping_constraints", {"mode": "none", "note": ""})

    if int(fp["test_window_rows"]) < 1:
        raise WalkforwardConfigError("test_window_rows must be >= 1")
    tw = int(fp["test_window_rows"])
    if fp.get("step_size_rows") is not None and int(fp["step_size_rows"]) != tw:
        raise WalkforwardConfigError(
            f"fold_policy.step_size_rows must equal test_window_rows ({tw}) for current fold mode, or omit step_size_rows"
        )
    inc = raw["inclusion"]
    if "confidence_tiers_primary" not in inc:
        raise WalkforwardConfigError("inclusion.confidence_tiers_primary required")
    raw["outputs"].setdefault("aggregate_dimensions_report", "aggregate_dimensions_report.json")
    return raw


def resolve_paths(cfg: dict[str, Any], repo_root: Path) -> dict[str, Path]:
    """Return resolved Path objects for dataset, ml_root, feature_spec."""
    ds = Path(cfg["dataset"]["path"])
    if not ds.is_absolute():
        ds = repo_root / ds
    ml_root = Path(cfg["ml_root"])
    if not ml_root.is_absolute():
        ml_root = repo_root / ml_root
    fsp = cfg.get("feature_spec_path") or "src/ml/feature_spec.yaml"
    fp = Path(fsp)
    if not fp.is_absolute():
        fp = repo_root / fp if not (repo_root / fsp).exists() else repo_root / fsp
    if not fp.is_file():
        fp = ml_root / "feature_spec.yaml"
    return {"dataset": ds, "ml_root": ml_root, "feature_spec": fp}


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate walkforward_config.yaml")
    ap.add_argument("--config", type=Path, default=Path("src/ml/walkforward_config.yaml"))
    args = ap.parse_args()
    path = args.config.resolve()
    try:
        load_walkforward_config(path)
    except WalkforwardConfigError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    except FileNotFoundError:
        print(f"ERROR: missing {path}", file=sys.stderr)
        return 1
    print(f"OK: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
