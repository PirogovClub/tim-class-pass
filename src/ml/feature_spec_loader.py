"""Load and validate ml/feature_spec.yaml (Step 7)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml

REQUIRED_FEATURE_KEYS = frozenset(
    {
        "feature_name",
        "feature_family",
        "dtype",
        "description",
        "required_inputs",
        "optional_inputs",
        "formula_summary",
        "point_in_time_safe",
        "null_policy",
        "default_behavior",
        "linked_rule_concepts",
        "notes",
    }
)


class FeatureSpecError(Exception):
    pass


def load_feature_spec(path: Path) -> dict[str, Any]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise FeatureSpecError("root must be a mapping")
    feats = raw.get("features")
    if not isinstance(feats, list) or not feats:
        raise FeatureSpecError("features must be a non-empty list")
    names: list[str] = []
    for i, f in enumerate(feats):
        if not isinstance(f, dict):
            raise FeatureSpecError(f"features[{i}] must be a mapping")
        miss = sorted(REQUIRED_FEATURE_KEYS - set(f.keys()))
        if miss:
            raise FeatureSpecError(f"features[{i}] missing keys: {miss}")
        if not f.get("point_in_time_safe"):
            raise FeatureSpecError(f"features[{i}] must declare point_in_time_safe: true")
        nm = f["feature_name"]
        if not isinstance(nm, str) or not nm.strip():
            raise FeatureSpecError(f"features[{i}] invalid feature_name")
        names.append(nm)
    if len(names) != len(set(names)):
        raise FeatureSpecError(f"duplicate feature_name: {names}")
    mfc = raw.get("modeling_feature_columns", {})
    for group in ("numeric", "categorical", "boolean"):
        for c in mfc.get(group, []):
            if c not in names:
                raise FeatureSpecError(f"modeling_feature_columns.{group} references unknown {c!r}")
    return raw


def main() -> int:
    p = argparse.ArgumentParser(description="Validate ml/feature_spec.yaml")
    p.add_argument("--path", type=Path, default=Path("src/ml/feature_spec.yaml"))
    args = p.parse_args()
    path = args.path.resolve()
    try:
        spec = load_feature_spec(path)
    except FeatureSpecError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    n = len(spec["features"])
    print(f"OK: {n} features in {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
