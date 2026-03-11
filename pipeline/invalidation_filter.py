from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pipeline.component2.models import VisualEvent


UNKNOWN_VISUAL_TYPES = {"", "n/a", "na", "none", "null", "unknown"}


def _sort_key(frame_key: str) -> tuple[int, str]:
    if str(frame_key).isdigit():
        return (0, f"{int(frame_key):012d}")
    return (1, str(frame_key))


def _timestamp_to_seconds(raw: str) -> int:
    cleaned = raw.strip().replace(",", ".")
    if cleaned.isdigit():
        return int(cleaned)
    parts = cleaned.split(":")
    if len(parts) == 2:
        parts = ["00", *parts]
    if len(parts) != 3:
        raise ValueError(f"Unsupported timestamp format: {raw}")
    hours, minutes, seconds = parts
    return int(hours) * 3600 + int(minutes) * 60 + int(float(seconds))


def _entry_timestamp_seconds(frame_key: str, entry: dict[str, Any]) -> int:
    raw_timestamp = str(entry.get("frame_timestamp") or "").strip()
    if raw_timestamp:
        try:
            return _timestamp_to_seconds(raw_timestamp)
        except ValueError:
            pass
    return _timestamp_to_seconds(frame_key)


def load_dense_analysis(path: Path | str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("Dense analysis input must be a JSON object keyed by frame timestamp.")
    return data


def is_valid_visual_event(entry: dict[str, Any]) -> bool:
    if not bool(entry.get("material_change")):
        return False
    visual_type = str(entry.get("visual_representation_type") or "").strip().lower()
    return visual_type not in UNKNOWN_VISUAL_TYPES


def rejection_reason(entry: dict[str, Any]) -> str:
    if not bool(entry.get("material_change")):
        return "no_material_change"
    return "unknown_visual_type"


def _normalize_visual_event(frame_key: str, entry: dict[str, Any]) -> VisualEvent:
    return VisualEvent(
        timestamp_seconds=_entry_timestamp_seconds(frame_key, entry),
        frame_key=frame_key,
        visual_representation_type=str(entry.get("visual_representation_type") or "unknown"),
        example_type=str(entry.get("example_type") or "unknown"),
        change_summary=list(entry.get("change_summary") or []),
        current_state=dict(entry.get("current_state") or {}),
        extracted_entities=dict(entry.get("extracted_entities") or {}),
    )


def filter_visual_events(raw_analysis: dict[str, Any]) -> list[VisualEvent]:
    events: list[VisualEvent] = []
    for frame_key in sorted(raw_analysis.keys(), key=_sort_key):
        entry = raw_analysis[frame_key]
        if not isinstance(entry, dict):
            continue
        if is_valid_visual_event(entry):
            events.append(_normalize_visual_event(frame_key, entry))
    return events


def build_debug_report(raw_analysis: dict[str, Any], events: list[VisualEvent]) -> dict[str, Any]:
    kept_keys = {event.frame_key for event in events}
    rejected: dict[str, str] = {}
    for frame_key in sorted(raw_analysis.keys(), key=_sort_key):
        entry = raw_analysis[frame_key]
        if not isinstance(entry, dict) or frame_key in kept_keys:
            continue
        rejected[frame_key] = rejection_reason(entry)
    return {
        "input_frames": len(raw_analysis),
        "kept_events": len(events),
        "rejected_frames": len(rejected),
        "kept_frame_keys": [event.frame_key for event in events],
        "rejected_frame_keys": rejected,
    }


def write_filtered_events(path: Path | str, events: list[VisualEvent]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with open(destination, "w", encoding="utf-8") as handle:
        json.dump([event.model_dump() for event in events], handle, indent=2, ensure_ascii=False)


def write_debug_report(path: Path | str, report: dict[str, Any]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with open(destination, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False)


def run_invalidation_filter(
    input_path: Path | str,
    output_path: Path | str | None = None,
    debug_path: Path | str | None = None,
) -> list[VisualEvent]:
    raw_analysis = load_dense_analysis(input_path)
    events = filter_visual_events(raw_analysis)
    if output_path is not None:
        write_filtered_events(output_path, events)
    if debug_path is not None:
        write_debug_report(debug_path, build_debug_report(raw_analysis, events))
    return events
