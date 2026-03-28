"""Join Step 6 labels + market windows + PIT-safe features into modeling rows."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from ml.feature_builder import compute_features
from ml.feature_spec_loader import load_feature_spec
from ml.split_builder import (
    SPLIT_POLICY_LESSON_GROUP,
    SPLIT_POLICY_TIME_ORDERED,
    assign_splits,
    write_split_manifest,
)

# Explicit policy (see docs/ml_step7_feature_store_and_baselines.md)
TRAINABLE_STATUSES = frozenset({"assigned"})
TRAINABLE_TIERS = frozenset({"gold", "silver"})
TRAINABLE_TIERS_WITH_WEAK = frozenset({"gold", "silver", "weak"})


def _row_id(task_id: str, cid: str, anchor: str) -> str:
    h = hashlib.sha256(f"{task_id}|{cid}|{anchor}".encode()).hexdigest()[:24]
    return f"dr_{h}"


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _load_json_if_exists(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def compute_step6_integrity(
    labels_path: Path,
    labels: list[dict[str, Any]],
    modeling_rows: list[dict[str, Any]],
    task_id: str,
) -> dict[str, Any]:
    """
    Load label_generation_report.json and label_dataset_manifest.json beside labels file;
    compare task_id and row counts. Modeling row count may be lower if some labels lack window JSON.
    """
    parent = labels_path.parent
    report = _load_json_if_exists(parent / "label_generation_report.json")
    manifest = _load_json_if_exists(parent / "label_dataset_manifest.json")
    critical: list[str] = []
    info: dict[str, Any] = {
        "label_generation_report_path": str(parent / "label_generation_report.json"),
        "label_dataset_manifest_path": str(parent / "label_dataset_manifest.json"),
        "label_generation_report_present": report is not None,
        "label_dataset_manifest_present": manifest is not None,
    }
    if manifest:
        mt = manifest.get("task_id")
        if mt and str(mt) != str(task_id):
            critical.append(f"label_dataset_manifest task_id {mt!r} != dataset builder task_id {task_id!r}")
        mr = manifest.get("row_count")
        if mr is not None and int(mr) != len(labels):
            critical.append(f"label_dataset_manifest row_count {mr} != len(generated_labels.jsonl) {len(labels)}")
    if report:
        rt = report.get("task_id")
        if rt and str(rt) != str(task_id):
            critical.append(f"label_generation_report task_id {rt!r} != dataset builder task_id {task_id!r}")
        rr = report.get("row_count")
        if rr is not None and int(rr) != len(labels):
            critical.append(f"label_generation_report row_count {rr} != len(generated_labels.jsonl) {len(labels)}")
    warnings: list[str] = []
    if len(modeling_rows) != len(labels):
        warnings.append(
            f"built {len(modeling_rows)} modeling rows from {len(labels)} labels "
            "(typically missing market_window JSON for some candidate_ids)"
        )
    info["label_row_count"] = len(labels)
    info["modeling_row_count"] = len(modeling_rows)
    info["critical_issues"] = critical
    info["warnings"] = warnings
    info["checks_passed"] = len(critical) == 0
    return info


def _windows_by_candidate(wdir: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for p in sorted(wdir.glob("*.json")):
        w = json.loads(p.read_text(encoding="utf-8"))
        cid = str(w.get("candidate_id", p.stem))
        out[cid] = w
    return out


def _is_eligible(
    lab: dict[str, Any],
    *,
    tiers: frozenset[str],
) -> bool:
    st = lab.get("status", "")
    tier = lab.get("confidence_tier", "")
    return (
        st in TRAINABLE_STATUSES
        and tier in tiers
        and lab.get("label") is not None
        and lab.get("point_in_time_safe", True) is True
    )


def build_modeling_rows(
    labels: list[dict[str, Any]],
    windows: dict[str, dict[str, Any]],
    *,
    task_id: str,
    max_lookback_bars: int,
    apply_splits: bool = True,
    include_weak_in_training: bool = False,
    split_policy: str = SPLIT_POLICY_TIME_ORDERED,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Returns all rows (with features); eligible_for_training flags policy."""
    tiers = TRAINABLE_TIERS_WITH_WEAK if include_weak_in_training else TRAINABLE_TIERS
    rows: list[dict[str, Any]] = []
    for lab in labels:
        cid = str(lab.get("candidate_id", ""))
        w = windows.get(cid)
        if w is None:
            continue
        st = lab.get("status", "")
        tier = lab.get("confidence_tier", "")
        eligible = _is_eligible(lab, tiers=tiers)
        try:
            feats = compute_features(w, max_lookback_bars=max_lookback_bars)
        except Exception:
            feats = {}

        meta = lab.get("metadata") if isinstance(lab.get("metadata"), dict) else {}
        src = meta.get("source") if isinstance(meta.get("source"), dict) else {}

        row = {
            "dataset_row_id": _row_id(task_id, cid, str(lab.get("anchor_timestamp", ""))),
            "candidate_id": cid,
            "task_id": task_id,
            "label": lab.get("label"),
            "confidence_tier": tier,
            "label_status": str(st),
            "split": "none",
            "timeframe": str(lab.get("timeframe", "")),
            "anchor_timestamp": str(lab.get("anchor_timestamp", "")),
            "reference_level": float(w.get("reference_level", 0) or 0),
            "point_in_time_safe": bool(lab.get("point_in_time_safe", True)),
            "eligible_for_training": eligible,
            "source_refs": {
                "matched_concept_ids": lab.get("matched_concept_ids", []),
                "matched_rule_refs": lab.get("matched_rule_refs", []),
                "lesson_id": src.get("lesson_id"),
            },
            "features": feats,
            "metadata": {
                "label_provenance": {
                    "decision_order_path": lab.get("decision_order_path"),
                    "matched_conditions": lab.get("matched_conditions"),
                },
                "window_source": src,
            },
        }
        rows.append(row)

    if apply_splits and rows:
        assign_splits(rows, policy=split_policy)

    summary = {
        "total_rows": len(rows),
        "eligible_for_training": sum(1 for r in rows if r["eligible_for_training"]),
        "task_id": task_id,
        "policy": {
            "trainable_statuses": sorted(TRAINABLE_STATUSES),
            "trainable_tiers": sorted(tiers),
            "requires_point_in_time_safe": True,
            "include_weak_in_training": include_weak_in_training,
            "split_policy": split_policy,
        },
    }
    return rows, summary


def write_dataset_manifest(
    rows: list[dict[str, Any]],
    summary: dict[str, Any],
    *,
    out_path: Path,
    spec_versions: dict[str, str],
    generator_version: str,
    pit_declaration: str,
    step6_integrity: dict[str, Any] | None = None,
) -> None:
    from datetime import datetime, timezone

    eligible = [r for r in rows if r["eligible_for_training"]]
    by_split: dict[str, int] = {}
    for r in eligible:
        s = r.get("split", "none")
        by_split[s] = by_split.get(s, 0) + 1
    man = {
        "manifest_id": "modeling_dataset_manifest_v1",
        "created_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "spec_versions": spec_versions,
        "builder_version": generator_version,
        "row_counts": {
            "total_with_features": len(rows),
            "eligible_for_training": len(eligible),
            "by_split_eligible": by_split,
        },
        "summary": summary,
        "point_in_time_safety_declaration": pit_declaration,
    }
    if step6_integrity is not None:
        man["step6_integrity"] = step6_integrity
    out_path.write_text(json.dumps(man, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Build Step 7 modeling dataset from labels + windows")
    ap.add_argument("--ml-root", type=Path, default=Path("ml"))
    ap.add_argument("--labels", type=Path, default=Path("ml_output/step6_sample/generated_labels.jsonl"))
    ap.add_argument("--windows-dir", type=Path, default=None)
    ap.add_argument("--out-dir", type=Path, default=Path("ml_output/step7"))
    ap.add_argument(
        "--include-weak",
        action="store_true",
        help="Treat confidence_tier=weak assigned rows as trainable (default: gold+silver only)",
    )
    ap.add_argument(
        "--split-policy",
        choices=(SPLIT_POLICY_TIME_ORDERED, SPLIT_POLICY_LESSON_GROUP),
        default=SPLIT_POLICY_TIME_ORDERED,
        help="Split assignment: time_ordered (default) or lesson_group (by source_refs.lesson_id)",
    )
    args = ap.parse_args()
    ml_root = args.ml_root.resolve()
    try:
        spec = load_feature_spec(ml_root / "feature_spec.yaml")
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    max_lb = int(spec.get("observation_window", {}).get("max_lookback_bars", 20))
    labels_path = args.labels.resolve()
    if not labels_path.is_file():
        print(f"ERROR: missing labels {labels_path}", file=sys.stderr)
        return 1
    wdir = (args.windows_dir or (ml_root / "fixtures" / "market_windows")).resolve()
    labels = _load_jsonl(labels_path)
    task_id = labels[0].get("task_id", "level_interaction_rule_satisfaction_v1") if labels else ""
    windows = _windows_by_candidate(wdir)
    rows, summary = build_modeling_rows(
        labels,
        windows,
        task_id=task_id,
        max_lookback_bars=max_lb,
        apply_splits=True,
        include_weak_in_training=bool(args.include_weak),
        split_policy=str(args.split_policy),
    )
    integrity = compute_step6_integrity(labels_path, labels, rows, task_id)
    out_dir = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    ds_path = out_dir / "modeling_dataset.jsonl"
    with ds_path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    ls = json.loads((ml_root / "label_specs.json").read_text(encoding="utf-8")) if (ml_root / "label_specs.json").is_file() else {}
    write_dataset_manifest(
        rows,
        summary,
        out_path=out_dir / "dataset_manifest.json",
        spec_versions={
            "feature_spec": str(spec.get("version", "")),
            "label_specs": ls.get("compiled_at_utc", ""),
            "task_definition": ls.get("task_definition_version", ""),
        },
        generator_version="1.0.0",
        pit_declaration=(
            "Features use only bars[0..anchor_bar_index]; labels from Step 6 may use post-anchor horizon. "
            "No post-anchor OHLCV is copied into feature vectors."
        ),
        step6_integrity=integrity,
    )
    write_split_manifest(rows, out_dir / "split_manifest.json", split_policy=str(args.split_policy))
    print(f"Wrote {ds_path} ({len(rows)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
