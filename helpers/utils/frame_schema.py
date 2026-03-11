"""
Frame JSON schema for dense_analysis.json and per-frame frame_XXXXXX.json.

Semantic contract:
- material_change: True iff the current screenshot is materially different from the previous one
  (symbol/timeframe/chart/annotations/context changed). Do NOT derive from lesson_relevant.
- lesson_relevant: True iff the pipeline accepts this frame for scene/teaching (relevance gate).
  This remains useful metadata for higher-level teaching relevance; material_change stays the extraction/comparison signal.
- scene_boundary: Legacy relevance marker kept for backward compatibility with older analysis records.

Downstream consumers:
- invalidation_filter.py: frame_timestamp, material_change, visual_representation_type, current_state
- pipeline/component2/parser.py: normalized visual event fields
- scripts/run_ide_batch_loop.write_no_change_batch_response(): frame_timestamp, material_change
"""

from __future__ import annotations

from typing import Any

# Fields that MUST be present for downstream compatibility (merge, IDE batch)
REQUIRED_DEDUP_FIELDS = ("frame_timestamp", "material_change")
REQUIRED_FOR_SUMMARIZE = ("current_state", "visual_representation_type", "change_summary")

# Optional legacy fields retained in dense analysis records
OPTIONAL_LEGACY_FIELDS = (
    "change_summary",
    "visual_representation_type",
    "example_type",
    "extraction_mode",
    "screen_type",
    "educational_event_type",
    "current_state",
    "extracted_entities",
    "notes",
    "description",
)

# New pipeline fields (backward compat: old analysis files won't have these)
RICH_FIELDS = (
    "structural_change",
    "structural_score",
    "content_changed",
    "lesson_relevant",
    "scene_boundary",
    "skip_reason",
    "extracted_facts",
    "explanation_summary",
    "previous_relevant_frame",
    "timings",
    "pipeline_status",
)


def key_to_timestamp(key: str) -> str:
    """Convert frame key (zero-padded seconds) to HH:MM:SS."""
    seconds = int(key)
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def minimal_no_change_frame(key: str, skip_reason: str = "structural_unchanged") -> dict[str, Any]:
    """Produce a minimal frame record when SSIM says no meaningful change."""
    return {
        "frame_timestamp": key_to_timestamp(key),
        "material_change": False,
        "structural_change": False,
        "structural_score": 1.0,
        "lesson_relevant": False,
        "skip_reason": skip_reason,
        "pipeline_status": "compared",
    }


def minimal_relevance_skip_frame(
    key: str,
    extracted_facts: dict[str, Any] | None = None,
    skip_reason: str = "lesson_irrelevant",
) -> dict[str, Any]:
    """Produce a frame record when extraction ran but relevance gate said skip.
    material_change is preserved from extraction (visual change), not derived from lesson_relevant.
    """
    material = False
    if isinstance(extracted_facts, dict) and "material_change" in extracted_facts:
        material = bool(extracted_facts["material_change"])
    out: dict[str, Any] = {
        "frame_timestamp": key_to_timestamp(key),
        "material_change": material,
        "structural_change": True,
        "lesson_relevant": False,
        "skip_reason": skip_reason,
        "pipeline_status": "relevance_skipped",
    }
    if extracted_facts is not None:
        out["extracted_facts"] = extracted_facts
    return out


def ensure_material_change(entry: dict[str, Any]) -> dict[str, Any]:
    """
    No-op: do not overwrite material_change from lesson_relevant.
    material_change = visual material change; lesson_relevant = acceptance for scenes.
    Kept for backward compatibility of call sites; callers must set material_change from extraction/comparison.
    """
    return entry
