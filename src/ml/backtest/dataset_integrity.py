"""Align Step 8 dataset path with Step 7 manifests (optional integrity checks)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def count_jsonl_rows(path: Path) -> int:
    return sum(1 for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip())


def build_step7_alignment_report(
    dataset_path: Path,
    *,
    dataset_manifest_path: Path | None = None,
    split_manifest_path: Path | None = None,
) -> dict[str, Any]:
    """
    Compare modeling_dataset.jsonl line count to dataset_manifest.json row_counts when present.
    Attach split_manifest summary for audit traceability (Step 7 static splits vs Step 8 walk-forward).
    """
    n = count_jsonl_rows(dataset_path)
    rep: dict[str, Any] = {
        "dataset_path": str(dataset_path),
        "dataset_jsonl_row_count": n,
        "dataset_manifest_path": str(dataset_manifest_path) if dataset_manifest_path else None,
        "split_manifest_path": str(split_manifest_path) if split_manifest_path else None,
        "dataset_manifest_present": False,
        "split_manifest_present": False,
        "critical_issues": [],
        "warnings": [],
        "checks_passed": True,
    }
    if dataset_manifest_path and dataset_manifest_path.is_file():
        rep["dataset_manifest_present"] = True
        try:
            man = json.loads(dataset_manifest_path.read_text(encoding="utf-8"))
            tw = man.get("row_counts", {}).get("total_with_features")
            if tw is not None and int(tw) != n:
                rep["critical_issues"].append(
                    f"dataset_manifest row_counts.total_with_features ({tw}) != jsonl lines ({n})"
                )
                rep["checks_passed"] = False
            rep["manifest_task_id"] = man.get("summary", {}).get("task_id") or man.get("task_id")
        except Exception as e:
            rep["warnings"].append(f"failed to read dataset_manifest: {e}")
    elif dataset_manifest_path:
        rep["warnings"].append(f"dataset_manifest_path set but file missing: {dataset_manifest_path}")

    if split_manifest_path and split_manifest_path.is_file():
        rep["split_manifest_present"] = True
        try:
            sm = json.loads(split_manifest_path.read_text(encoding="utf-8"))
            rep["split_manifest_summary"] = {
                "split_manifest_id": sm.get("split_manifest_id"),
                "policy": sm.get("policy"),
                "eligible_counts_by_split": sm.get("eligible_counts_by_split"),
                "note": "Step 7 split_manifest describes static splits; Step 8 walk-forward uses time-ordered folds from config.",
            }
        except Exception as e:
            rep["warnings"].append(f"failed to read split_manifest: {e}")
    elif split_manifest_path:
        rep["warnings"].append(f"split_manifest_path set but file missing: {split_manifest_path}")

    return rep
