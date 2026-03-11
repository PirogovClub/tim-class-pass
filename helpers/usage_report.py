from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from helpers.clients.usage import summarize_usage_records


def is_usage_record(value: Any) -> bool:
    return isinstance(value, dict) and {"provider", "model", "attempt", "status"}.issubset(set(value.keys()))


def collect_usage_records(value: Any) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if is_usage_record(value):
        records.append(value)
        return records
    if isinstance(value, dict):
        for nested in value.values():
            records.extend(collect_usage_records(nested))
        return records
    if isinstance(value, list):
        for item in value:
            records.extend(collect_usage_records(item))
    return records


def _load_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_video_usage_summary(video_dir: Path | str) -> dict[str, Any]:
    root = Path(video_dir)
    sources: dict[str, int] = {}
    records: list[dict[str, Any]] = []
    candidates = []

    dense_analysis = root / "dense_analysis.json"
    targets_json = root / "targets.json"
    if dense_analysis.is_file():
        candidates.append(dense_analysis)
    if targets_json.is_file():
        candidates.append(targets_json)
    candidates.extend(sorted((root / "output_intermediate").glob("*.llm_debug.json")))
    candidates.extend(sorted((root / "output_intermediate").glob("*.reducer_usage.json")))

    for path in candidates:
        payload = _load_json(path)
        path_records = collect_usage_records(payload)
        records.extend(path_records)
        sources[str(path.relative_to(root))] = len(path_records)

    summary = summarize_usage_records(records)
    summary["video_dir"] = str(root)
    summary["sources"] = sources
    return summary


def write_video_usage_summary(video_dir: Path | str, output_path: Path | str | None = None) -> Path:
    root = Path(video_dir)
    destination = Path(output_path) if output_path is not None else root / "ai_usage_summary.json"
    summary = build_video_usage_summary(root)
    destination.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return destination
