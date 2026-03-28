from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pipeline.component2.models import VisualEvent


UNKNOWN_VISUAL_TYPES = {"", "n/a", "na", "none", "null", "unknown"}
INSTRUCTIONAL_CHANGE_KEYWORDS = (
    "annot",
    "arrow",
    "diagram",
    "draw",
    "highlight",
    "label",
    "level",
    "mark",
    "slide",
    "text",
    "trendline",
    "whipsaw",
    "x",
)
NEGATIVE_INSTRUCTIONAL_PHRASES = (
    "close-up shot of the instructor",
    "generic transition",
    "no diagram is present",
    "no direct trading information",
    "no visible educational material",
    "placeholder",
    "transition screen",
)


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
    if visual_type not in UNKNOWN_VISUAL_TYPES:
        return True
    return _has_instructional_signal(entry)


def rejection_reason(entry: dict[str, Any]) -> str:
    if not bool(entry.get("material_change")):
        return "no_material_change"
    return "unknown_visual_type_without_instructional_signal"


def _sequence_has_content(value: Any) -> bool:
    if isinstance(value, list):
        return any(bool(item) for item in value)
    return False


def _dict_has_content(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    for nested in value.values():
        if isinstance(nested, dict) and _dict_has_content(nested):
            return True
        if isinstance(nested, list) and _sequence_has_content(nested):
            return True
        if nested not in (None, "", [], {}, False):
            return True
    return False


def _contains_instructional_keyword(values: list[str]) -> bool:
    joined = " ".join(str(item).lower() for item in values if item)
    return any(keyword in joined for keyword in INSTRUCTIONAL_CHANGE_KEYWORDS)


def _has_instructional_signal(entry: dict[str, Any]) -> bool:
    change_summary = [str(item) for item in list(entry.get("change_summary") or [])]
    combined_text = " ".join(change_summary).lower()
    if any(phrase in combined_text for phrase in NEGATIVE_INSTRUCTIONAL_PHRASES):
        current_state = dict(entry.get("current_state") or {})
        extracted_entities = dict(entry.get("extracted_entities") or {})
        has_explicit_markup = (
            _sequence_has_content(current_state.get("visible_annotations"))
            or _sequence_has_content(current_state.get("drawn_objects"))
            or _sequence_has_content(current_state.get("structural_pattern_visible"))
            or _dict_has_content(extracted_entities)
        )
        if not has_explicit_markup:
            return False

    if _contains_instructional_keyword(change_summary):
        return True

    educational_events = [str(item) for item in list(entry.get("educational_event_type") or [])]
    if _contains_instructional_keyword(educational_events):
        return True

    current_state = dict(entry.get("current_state") or {})
    extracted_entities = dict(entry.get("extracted_entities") or {})

    if _sequence_has_content(current_state.get("visible_annotations")):
        return True
    if _sequence_has_content(current_state.get("drawn_objects")):
        return True
    if _sequence_has_content(current_state.get("structural_pattern_visible")):
        return True

    cursor_or_highlight = str(current_state.get("cursor_or_highlight") or "").strip().lower()
    if cursor_or_highlight and any(keyword in cursor_or_highlight for keyword in INSTRUCTIONAL_CHANGE_KEYWORDS):
        return True

    if _dict_has_content(extracted_entities):
        return True

    screen_type = str(entry.get("screen_type") or "").strip().lower()
    if screen_type in {"slides", "chart_with_annotation", "chart", "browser", "platform"} and (
        _sequence_has_content(current_state.get("visible_annotations"))
        or _sequence_has_content(current_state.get("drawn_objects"))
        or _sequence_has_content(current_state.get("structural_pattern_visible"))
        or _contains_instructional_keyword([str(item) for item in list(current_state.get("visual_facts") or [])])
    ):
        return True

    return False


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
