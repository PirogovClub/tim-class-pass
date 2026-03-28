"""Build label_generation_report.json and label_dataset_manifest.json."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _source_dict(row: dict[str, Any]) -> dict[str, Any]:
    meta = row.get("metadata")
    if not isinstance(meta, dict):
        return {}
    src = meta.get("source")
    return src if isinstance(src, dict) else {}


def build_generation_report(labels: list[dict[str, Any]]) -> dict[str, Any]:
    by_class: Counter[str] = Counter()
    by_tier: Counter[str] = Counter()
    by_status: Counter[str] = Counter()
    by_lesson: Counter[str] = Counter()
    by_rule_family: Counter[str] = Counter()
    excluded = 0
    ambiguous_n = 0
    for row in labels:
        st = row.get("status", "")
        by_status[st] += 1
        if st == "assigned":
            by_class[row.get("label", "")] += 1
            by_tier[row.get("confidence_tier", "")] += 1
        elif st == "ambiguous":
            ambiguous_n += 1
            by_class["ambiguous"] += 1
            by_tier[row.get("confidence_tier", "")] += 1
        elif st in ("excluded", "skipped_invalid_input"):
            excluded += 1

        src = _source_dict(row)
        lid = src.get("lesson_id")
        if lid is not None and str(lid).strip():
            by_lesson[str(lid)] += 1
        rfh = src.get("rule_family_hint")
        if rfh is not None and str(rfh).strip():
            by_rule_family[str(rfh)] += 1

    out: dict[str, Any] = {
        "report_id": "label_generation_report_v1",
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "row_count": len(labels),
        "counts_by_class": dict(by_class),
        "counts_by_confidence_tier": dict(by_tier),
        "counts_by_status": dict(by_status),
        "excluded_or_skipped": excluded,
        "ambiguous_rows": ambiguous_n,
    }
    if by_lesson:
        out["counts_by_lesson_id"] = dict(by_lesson)
    if by_rule_family:
        out["counts_by_rule_family_hint"] = dict(by_rule_family)
    return out


def build_dataset_manifest(
    labels: list[dict[str, Any]],
    *,
    task_id: str,
    spec_versions: dict[str, str],
    generator_version: str,
    input_sources: list[str],
    pit_declaration: str,
    known_limitations: list[str],
) -> dict[str, Any]:
    report = build_generation_report(labels)
    tiers = report["counts_by_confidence_tier"]
    classes = report["counts_by_class"]
    return {
        "manifest_id": "label_dataset_manifest_v1",
        "created_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "task_id": task_id,
        "spec_versions": spec_versions,
        "generator_version": generator_version,
        "row_count": len(labels),
        "confidence_distribution": tiers,
        "class_distribution": classes,
        "input_sources": input_sources,
        "point_in_time_safety_declaration": pit_declaration,
        "known_limitations": known_limitations,
        "integrity": {
            "class_counts_sum": sum(classes.values()),
            "status_counts_sum": sum(report["counts_by_status"].values()),
        },
    }


def write_artifacts(
    labels: list[dict[str, Any]],
    out_dir: Path,
    *,
    task_id: str,
    spec_versions: dict[str, str],
    generator_version: str,
    input_sources: list[str],
    pit_declaration: str,
    known_limitations: list[str],
) -> tuple[Path, Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    jsonl = out_dir / "generated_labels.jsonl"
    with jsonl.open("w", encoding="utf-8") as f:
        for row in labels:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    rep_path = out_dir / "label_generation_report.json"
    rep_path.write_text(
        json.dumps(build_generation_report(labels), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    man = build_dataset_manifest(
        labels,
        task_id=task_id,
        spec_versions=spec_versions,
        generator_version=generator_version,
        input_sources=input_sources,
        pit_declaration=pit_declaration,
        known_limitations=known_limitations,
    )
    man_path = out_dir / "label_dataset_manifest.json"
    man_path.write_text(json.dumps(man, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return jsonl, rep_path, man_path
