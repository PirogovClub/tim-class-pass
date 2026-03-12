"""Optional Task 8 debug helpers: before/after compaction, dropped phrases, blocked fields."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from pipeline.io_utils import atomic_write_json
from pipeline.component2.visual_compaction import (
    VisualCompactionConfig,
    is_low_value_visual_phrase,
)

logger = logging.getLogger(__name__)


def collect_candidate_summary_debug(
    candidate_id: str,
    before_summary: str | None,
    after_summary: str | None,
    dropped_phrases: list[str],
    kept_screenshot_paths: list[str],
    blocked_metadata_keys: list[str],
) -> dict[str, Any]:
    """Build one debug record for a candidate (evidence or chunk)."""
    return {
        "candidate_id": candidate_id,
        "summary_before_compaction": before_summary,
        "summary_after_compaction": after_summary,
        "dropped_low_value_phrases": dropped_phrases,
        "kept_screenshot_candidates": kept_screenshot_paths,
        "blocked_raw_fields": blocked_metadata_keys,
    }


def collect_dropped_phrases_from_text(text: str) -> list[str]:
    """Split text into phrases and return those that are low-value (for debug)."""
    if not text or not text.strip():
        return []
    # Simple split by sentence or bullet
    parts = [p.strip() for p in text.replace(". ", ".\n").splitlines() if p.strip()]
    return [p for p in parts if is_low_value_visual_phrase(p)]


def collect_blocked_metadata_keys(metadata: dict[str, Any]) -> list[str]:
    """Return keys that would be stripped by strip_raw_visual_blobs_from_metadata."""
    from pipeline.component2.visual_compaction import _FORBIDDEN_VISUAL_KEYS
    return [k for k in (metadata or {}).keys() if k in _FORBIDDEN_VISUAL_KEYS]


def write_visual_compaction_debug(
    lesson_name: str,
    output_dir: Path,
    debug_entries: list[dict[str, Any]],
    *,
    compaction_cfg_used: VisualCompactionConfig | None = None,
) -> Path:
    """Write output_intermediate/<lesson>.visual_compaction_debug.json."""
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{lesson_name}.visual_compaction_debug.json"
    payload: dict[str, Any] = {
        "lesson_id": lesson_name,
        "entries": debug_entries,
    }
    if compaction_cfg_used is not None:
        payload["config"] = {
            "max_visual_summaries_for_extract": compaction_cfg_used.max_visual_summaries_for_extract,
            "max_visual_summary_chars_evidence": compaction_cfg_used.max_visual_summary_chars_evidence,
            "max_visual_summary_chars_rule": compaction_cfg_used.max_visual_summary_chars_rule,
            "max_visual_bullets_review": compaction_cfg_used.max_visual_bullets_review,
            "max_visual_bullets_rag": compaction_cfg_used.max_visual_bullets_rag,
        }
    atomic_write_json(path, payload)
    logger.debug("Wrote visual compaction debug to %s", path)
    return path
