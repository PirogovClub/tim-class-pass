"""Task 8: Shared visual compaction policy — rich source, compact downstream."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# 1. Config
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VisualCompactionConfig:
    max_visual_summaries_for_extract: int = 5
    max_annotations_per_visual: int = 3
    max_entities_per_visual: int = 6
    max_change_summaries_per_candidate: int = 3
    max_frames_per_evidence_ref: int = 12
    max_screenshot_paths_per_evidence_ref: int = 4
    max_visual_summary_chars_evidence: int = 240
    max_visual_summary_chars_rule: int = 180
    max_visual_bullets_review: int = 2
    max_visual_bullets_rag: int = 1
    include_screenshot_candidates: bool = True
    store_previous_visual_state_in_debug_only: bool = True
    store_raw_visual_blobs_in_structured_outputs: bool = False


def _int_default(d: dict[str, Any], key: str, default: int) -> int:
    val = d.get(key)
    if val is None:
        return default
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def from_pipeline_config(config_dict: dict[str, Any] | None) -> VisualCompactionConfig:
    """Build VisualCompactionConfig from pipeline config dict (e.g. get_config_for_video)."""
    if not config_dict:
        return VisualCompactionConfig()
    d = config_dict
    return VisualCompactionConfig(
        max_visual_summaries_for_extract=_int_default(d, "visual_extract_max_summaries", 5),
        max_visual_summary_chars_evidence=_int_default(d, "visual_evidence_summary_max_chars", 240),
        max_visual_summary_chars_rule=_int_default(d, "visual_rule_summary_max_chars", 180),
        max_visual_bullets_review=_int_default(d, "visual_review_max_bullets", 2),
        max_visual_bullets_rag=_int_default(d, "visual_rag_max_bullets", 1),
        include_screenshot_candidates=bool(d.get("visual_include_screenshot_candidates", True)),
        store_raw_visual_blobs_in_structured_outputs=bool(d.get("visual_store_raw_blobs", False)),
    )


# ---------------------------------------------------------------------------
# 2. Low-level extraction helpers
# ---------------------------------------------------------------------------


def extract_frame_key(event: dict[str, Any]) -> str | None:
    value = event.get("frame_key")
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def extract_timestamp_seconds(event: dict[str, Any]) -> float | None:
    value = event.get("timestamp_seconds")
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def build_raw_visual_event_id(frame_key: str | None) -> str | None:
    if not frame_key:
        return None
    return f"ve_raw_{frame_key}"


def extract_visual_type(event: dict[str, Any]) -> str:
    value = event.get("visual_representation_type")
    if not value:
        return "unknown"
    return str(value).strip() or "unknown"


def extract_example_type(event: dict[str, Any]) -> str | None:
    value = event.get("example_type")
    if value is None:
        return None
    value = str(value).strip()
    return value or None


# ---------------------------------------------------------------------------
# 3. Text cleanup and filtering
# ---------------------------------------------------------------------------

_UI_NOISE_PATTERNS = [
    r"\btoolbar\b",
    r"\bpanel\b",
    r"\bwindow\b",
    r"\bmenu\b",
    r"\blayout\b",
    r"\bbutton\b",
    r"\bicon\b",
    r"\bcolor\b",
    r"\bborder\b",
    r"\bbackground\b",
]

_FRAME_BY_FRAME_PATTERNS = [
    r"\bslightly moves\b",
    r"\bthen moves\b",
    r"\bcontinues moving\b",
    r"\bnext frame\b",
    r"\bin this frame\b",
    r"\bchart shifts a little\b",
    r"\bsmall movement\b",
]

_LOW_VALUE_PATTERNS = _UI_NOISE_PATTERNS + _FRAME_BY_FRAME_PATTERNS


def normalize_visual_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    text = text.replace(" ,", ",").replace(" .", ".")
    return text


def is_layout_or_ui_noise(text: str) -> bool:
    text_norm = normalize_visual_text(text).lower()
    return any(re.search(p, text_norm) for p in _UI_NOISE_PATTERNS)


def is_frame_by_frame_motion_narration(text: str) -> bool:
    text_norm = normalize_visual_text(text).lower()
    return any(re.search(p, text_norm) for p in _FRAME_BY_FRAME_PATTERNS)


def is_low_value_visual_phrase(text: str) -> bool:
    text_norm = normalize_visual_text(text)
    if not text_norm:
        return True
    return (
        is_layout_or_ui_noise(text_norm)
        or is_frame_by_frame_motion_narration(text_norm)
        or len(text_norm) < 12
    )


def dedupe_visual_phrases(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        norm = normalize_visual_text(item).lower()
        if not norm or norm in seen:
            continue
        seen.add(norm)
        result.append(normalize_visual_text(item))
    return result


def clamp_text_length(text: str, max_chars: int) -> str:
    text = normalize_visual_text(text)
    if len(text) <= max_chars:
        return text
    trimmed = text[: max_chars - 1].rstrip()
    if " " in trimmed:
        trimmed = trimmed.rsplit(" ", 1)[0]
    return trimmed + "…"


# ---------------------------------------------------------------------------
# 4. Pull meaningful visual fields (event as dict)
# ---------------------------------------------------------------------------


def _change_summary_to_str(raw: Any) -> str:
    """Normalize change_summary from list or str to single str."""
    if raw is None:
        return ""
    if isinstance(raw, str):
        return raw.strip()
    if isinstance(raw, list):
        parts = [str(item).strip() for item in raw if item]
        return " ".join(parts) if parts else ""
    return str(raw).strip()


def _extract_visible_annotations(event: dict[str, Any], cfg: VisualCompactionConfig) -> list[str]:
    current_state = event.get("current_state") or {}
    annotations = current_state.get("visible_annotations") or []
    out: list[str] = []

    for item in annotations[: cfg.max_annotations_per_visual]:
        if isinstance(item, str):
            text = item
        elif isinstance(item, dict):
            text = item.get("text") or item.get("label") or ""
        else:
            text = ""
        text = normalize_visual_text(text)
        if text and not is_low_value_visual_phrase(text):
            out.append(text)

    return dedupe_visual_phrases(out)


def _extract_entities(event: dict[str, Any], cfg: VisualCompactionConfig) -> list[str]:
    extracted_entities = event.get("extracted_entities") or {}
    out: list[str] = []

    if isinstance(extracted_entities, dict):
        for _, value in extracted_entities.items():
            if isinstance(value, list):
                for item in value:
                    if len(out) >= cfg.max_entities_per_visual:
                        break
                    if isinstance(item, str):
                        text = item
                    elif isinstance(item, dict):
                        text = item.get("text") or item.get("label") or item.get("name") or ""
                    else:
                        text = ""
                    text = normalize_visual_text(text)
                    if text and not is_low_value_visual_phrase(text):
                        out.append(text)
            if len(out) >= cfg.max_entities_per_visual:
                break

    return dedupe_visual_phrases(out)


# ---------------------------------------------------------------------------
# 5. Step 3 extraction-context summaries
# ---------------------------------------------------------------------------


def summarize_visual_event_for_extraction(
    event: dict[str, Any],
    cfg: VisualCompactionConfig,
) -> str | None:
    visual_type = extract_visual_type(event)
    example_type = extract_example_type(event)

    parts: list[str] = []

    if visual_type != "unknown":
        parts.append(visual_type.replace("_", " "))

    if example_type:
        parts.append(example_type.replace("_", " "))

    change_summary = normalize_visual_text(_change_summary_to_str(event.get("change_summary")))
    if change_summary and not is_low_value_visual_phrase(change_summary):
        parts.append(change_summary)

    tri = normalize_visual_text(str(event.get("trading_relevant_interpretation") or ""))
    if tri and not is_low_value_visual_phrase(tri):
        parts.append(tri)

    annotations = _extract_visible_annotations(event, cfg)
    if annotations:
        parts.append("annotations: " + "; ".join(annotations[: cfg.max_annotations_per_visual]))

    entities = _extract_entities(event, cfg)
    if entities:
        parts.append("entities: " + "; ".join(entities[: cfg.max_entities_per_visual]))

    parts = dedupe_visual_phrases(parts)
    parts = [p for p in parts if not is_low_value_visual_phrase(p)]

    if not parts:
        return None

    summary = ". ".join(parts)
    summary = clamp_text_length(summary, cfg.max_visual_summary_chars_evidence)
    return summary


def summarize_visual_events_for_extraction(
    visual_events: list[dict[str, Any]],
    cfg: VisualCompactionConfig,
) -> list[str]:
    summaries: list[str] = []
    for event in visual_events:
        summary = summarize_visual_event_for_extraction(event, cfg)
        if summary:
            summaries.append(summary)

    summaries = dedupe_visual_phrases(summaries)
    return summaries[: cfg.max_visual_summaries_for_extract]


# ---------------------------------------------------------------------------
# 6. Screenshot candidate derivation
# ---------------------------------------------------------------------------


def build_screenshot_candidate_paths(
    video_root: Path,
    frame_key: str | None,
    cfg: VisualCompactionConfig,
) -> list[str]:
    if not cfg.include_screenshot_candidates or not frame_key:
        return []

    candidates = [
        video_root / "frames_dense" / f"frame_{frame_key}.jpg",
        video_root / "frames_dense" / f"frame_{frame_key}.png",
        video_root / "llm_queue" / f"{frame_key}.jpg",
        video_root / "llm_queue" / f"{frame_key}.png",
    ]

    existing = [str(p) for p in candidates if p.exists()]
    return existing[: cfg.max_screenshot_paths_per_evidence_ref]


# ---------------------------------------------------------------------------
# 7. Evidence-level compaction
# ---------------------------------------------------------------------------


def summarize_visual_candidate_for_evidence(
    candidate: Any,
    cfg: VisualCompactionConfig,
) -> str | None:
    phrases: list[str] = []

    if getattr(candidate, "visual_type", None) and getattr(candidate, "visual_type") != "unknown":
        phrases.append(str(candidate.visual_type).replace("_", " "))

    if getattr(candidate, "example_role", None) and getattr(candidate, "example_role") != "unknown":
        phrases.append(str(candidate.example_role).replace("_", " "))

    for event in getattr(candidate, "visual_events", [])[: cfg.max_change_summaries_per_candidate]:
        change_summary = normalize_visual_text(str(getattr(event, "change_summary", "") or ""))
        if change_summary and not is_low_value_visual_phrase(change_summary):
            phrases.append(change_summary)

    concept_hints = getattr(candidate, "concept_hints", []) or []
    if concept_hints:
        phrases.append("concepts: " + ", ".join(dedupe_visual_phrases(list(concept_hints))[:3]))

    phrases = dedupe_visual_phrases(phrases)
    phrases = [p for p in phrases if not is_low_value_visual_phrase(p)]

    if not phrases:
        return None

    summary = ". ".join(phrases)
    return clamp_text_length(summary, cfg.max_visual_summary_chars_evidence)


def build_evidence_provenance_payload(
    candidate: Any,
    video_root: Path | None,
    cfg: VisualCompactionConfig,
) -> dict[str, Any]:
    frame_keys = list(dict.fromkeys(getattr(candidate, "frame_keys", []) or []))
    frame_keys = frame_keys[: cfg.max_frames_per_evidence_ref]

    screenshot_paths: list[str] = []
    if video_root is not None:
        for fk in frame_keys:
            screenshot_paths.extend(build_screenshot_candidate_paths(video_root, fk, cfg))
    screenshot_paths = list(dict.fromkeys(screenshot_paths))[: cfg.max_screenshot_paths_per_evidence_ref]

    raw_ids = [build_raw_visual_event_id(k) for k in frame_keys]
    raw_ids = [x for x in raw_ids if x]

    return {
        "frame_ids": frame_keys,
        "screenshot_paths": screenshot_paths,
        "raw_visual_event_ids": raw_ids,
    }


# ---------------------------------------------------------------------------
# 8. Rule-card compaction
# ---------------------------------------------------------------------------


def summarize_evidence_for_rule_card(
    evidence_refs: list[Any],
    cfg: VisualCompactionConfig,
) -> str | None:
    phrases = [
        normalize_visual_text(str(getattr(ev, "compact_visual_summary", "") or ""))
        for ev in evidence_refs
    ]
    phrases = [p for p in phrases if p and not is_low_value_visual_phrase(p)]
    phrases = dedupe_visual_phrases(phrases)

    if not phrases:
        return None

    best = phrases[0]
    return clamp_text_length(best, cfg.max_visual_summary_chars_rule)


def trim_rule_card_visual_refs(
    evidence_refs: list[str],
    max_refs: int = 3,
) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for ref in evidence_refs:
        if not ref or ref in seen:
            continue
        seen.add(ref)
        result.append(ref)
        if len(result) >= max_refs:
            break
    return result


# ---------------------------------------------------------------------------
# 9. Export compaction
# ---------------------------------------------------------------------------


def summarize_evidence_for_review_markdown(
    evidence_refs: list[Any],
    cfg: VisualCompactionConfig,
) -> list[str]:
    phrases = [
        normalize_visual_text(str(getattr(ev, "compact_visual_summary", "") or ""))
        for ev in evidence_refs
    ]
    phrases = [p for p in phrases if p and not is_low_value_visual_phrase(p)]
    phrases = dedupe_visual_phrases(phrases)
    phrases = [clamp_text_length(p, cfg.max_visual_summary_chars_rule) for p in phrases]
    return phrases[: cfg.max_visual_bullets_review]


def summarize_evidence_for_rag_markdown(
    evidence_refs: list[Any],
    cfg: VisualCompactionConfig,
) -> list[str]:
    phrases = summarize_evidence_for_review_markdown(evidence_refs, cfg)
    return phrases[: cfg.max_visual_bullets_rag]


# ---------------------------------------------------------------------------
# 10. Raw-blob stripping and guards
# ---------------------------------------------------------------------------

_FORBIDDEN_VISUAL_KEYS = {
    "current_state",
    "previous_visual_state",
    "visual_facts",
    "raw_visual_events",
    "dense_analysis_frame",
    "full_annotations",
    "full_extracted_entities",
}


def strip_raw_visual_blobs_from_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    clean: dict[str, Any] = {}
    for key, value in (metadata or {}).items():
        if key in _FORBIDDEN_VISUAL_KEYS:
            continue
        clean[key] = value
    return clean


def assert_no_raw_visual_blob_leak(obj: Any) -> None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in _FORBIDDEN_VISUAL_KEYS:
                raise ValueError(
                    f"Forbidden raw visual blob leaked into structured output: {key}"
                )
            assert_no_raw_visual_blob_leak(value)
    elif isinstance(obj, list):
        for item in obj:
            assert_no_raw_visual_blob_leak(item)


# ---------------------------------------------------------------------------
# 11. Final-markdown spam validator
# ---------------------------------------------------------------------------


def detect_visual_spam_lines(lines: list[str]) -> list[str]:
    flagged: list[str] = []
    seen_norm: set[str] = set()

    for line in lines:
        norm = normalize_visual_text(line).lower()
        if not norm:
            continue

        repeated = norm in seen_norm
        noisy = is_frame_by_frame_motion_narration(norm)

        if repeated or noisy:
            flagged.append(line)

        seen_norm.add(norm)

    return flagged


def validate_markdown_visual_compaction(markdown: str) -> list[str]:
    lines = [line.strip() for line in markdown.splitlines() if line.strip()]
    return detect_visual_spam_lines(lines)
