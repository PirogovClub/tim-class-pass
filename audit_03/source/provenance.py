"""Task 11: Shared provenance helpers for KnowledgeEvent, EvidenceRef, and RuleCard."""

from __future__ import annotations

from typing import Any, Iterable


def dedupe_preserve_order(items: Iterable[Any]) -> list[Any]:
    seen = set()
    result: list[Any] = []
    for item in items:
        if item in (None, "", [], {}):
            continue
        try:
            key = item
            if key in seen:
                continue
            seen.add(key)
        except TypeError:
            key = repr(item)
            if key in seen:
                continue
            seen.add(key)
        result.append(item)
    return result


def compact_nonempty_strs(items: Iterable[Any]) -> list[str]:
    out: list[str] = []
    for item in items:
        if item is None:
            continue
        text = str(item).strip()
        if text:
            out.append(text)
    return dedupe_preserve_order(out)


def compact_nonempty_ints(items: Iterable[Any]) -> list[int]:
    out: list[int] = []
    for item in items:
        if item is None or item == "":
            continue
        try:
            out.append(int(item))
        except (TypeError, ValueError):
            continue
    return dedupe_preserve_order(out)


def prune_none_values(payload: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in payload.items():
        if value is None:
            continue
        if isinstance(value, list) and not value:
            continue
        if isinstance(value, dict) and not value:
            continue
        result[key] = value
    return result


def build_knowledge_event_provenance(
    *,
    lesson_id: str,
    chunk_index: int | None,
    chunk_start_time_seconds: float | None,
    chunk_end_time_seconds: float | None,
    transcript_line_count: int | None,
    candidate_visual_frame_keys: list[str],
    candidate_visual_types: list[str],
    candidate_example_types: list[str],
) -> dict[str, Any]:
    """Build compact metadata dict for KnowledgeEvent.metadata (provenance only)."""
    payload = {
        "chunk_index": chunk_index,
        "chunk_start_time_seconds": chunk_start_time_seconds,
        "chunk_end_time_seconds": chunk_end_time_seconds,
        "transcript_line_count": transcript_line_count,
        "candidate_visual_frame_keys": compact_nonempty_strs(candidate_visual_frame_keys),
        "candidate_visual_types": compact_nonempty_strs(candidate_visual_types),
        "candidate_example_types": compact_nonempty_strs(candidate_example_types),
    }
    return prune_none_values(payload)


def build_evidence_ref_provenance(
    *,
    lesson_id: str,
    timestamp_start: float | None,
    timestamp_end: float | None,
    frame_ids: list[str],
    screenshot_paths: list[str],
    raw_visual_event_ids: list[str],
    source_event_ids: list[str],
) -> dict[str, Any]:
    """Build normalized provenance dict for EvidenceRef fields."""
    payload = {
        "lesson_id": lesson_id,
        "timestamp_start": timestamp_start,
        "timestamp_end": timestamp_end,
        "frame_ids": compact_nonempty_strs(frame_ids),
        "screenshot_paths": compact_nonempty_strs(screenshot_paths),
        "raw_visual_event_ids": compact_nonempty_strs(raw_visual_event_ids),
        "source_event_ids": compact_nonempty_strs(source_event_ids),
    }
    return prune_none_values(payload)


def merge_source_event_ids(*collections: list[str]) -> list[str]:
    merged: list[str] = []
    for collection in collections:
        merged.extend(collection or [])
    return compact_nonempty_strs(merged)


def merge_evidence_refs(*collections: list[str]) -> list[str]:
    merged: list[str] = []
    for collection in collections:
        merged.extend(collection or [])
    return compact_nonempty_strs(merged)


def merge_source_sections(events: list[Any]) -> list[str]:
    return compact_nonempty_strs(getattr(ev, "section", None) for ev in events)


def merge_source_subsections(events: list[Any]) -> list[str]:
    return compact_nonempty_strs(getattr(ev, "subsection", None) for ev in events)


def merge_source_chunk_indexes(events: list[Any]) -> list[int]:
    indexes: list[int] = []
    for ev in events:
        metadata = getattr(ev, "metadata", {}) or {}
        indexes.append(metadata.get("chunk_index"))
    return compact_nonempty_ints(indexes)


def build_rule_card_provenance(
    *,
    lesson_id: str,
    source_events: list[Any],
    linked_evidence: list[Any],
) -> dict[str, Any]:
    """Build compact provenance for RuleCard (source_event_ids, evidence_refs, optional metadata)."""
    source_event_ids = merge_source_event_ids(
        [getattr(ev, "event_id", None) for ev in source_events]
    )
    evidence_refs = merge_evidence_refs(
        [getattr(ev, "evidence_id", None) for ev in linked_evidence]
    )

    payload = {
        "lesson_id": lesson_id,
        "source_event_ids": source_event_ids,
        "evidence_refs": evidence_refs,
        "source_sections": merge_source_sections(source_events),
        "source_subsections": merge_source_subsections(source_events),
        "source_chunk_indexes": merge_source_chunk_indexes(source_events),
    }
    return prune_none_values(payload)


def validate_knowledge_event_provenance(event: Any) -> list[str]:
    """Return list of provenance warnings for a KnowledgeEvent."""
    warnings: list[str] = []

    if not getattr(event, "lesson_id", None):
        warnings.append("missing lesson_id")

    metadata = getattr(event, "metadata", {}) or {}

    if metadata.get("chunk_index") is None:
        warnings.append("missing metadata.chunk_index")

    if (
        getattr(event, "timestamp_start", None) is None
        and metadata.get("chunk_start_time_seconds") is None
    ):
        warnings.append(
            "missing both event timestamp_start and metadata.chunk_start_time_seconds"
        )

    if (
        getattr(event, "timestamp_end", None) is None
        and metadata.get("chunk_end_time_seconds") is None
    ):
        warnings.append(
            "missing both event timestamp_end and metadata.chunk_end_time_seconds"
        )

    frame_keys = metadata.get("candidate_visual_frame_keys", []) or []
    visual_types = metadata.get("candidate_visual_types", []) or []

    if visual_types and not frame_keys:
        warnings.append("visual types present but candidate_visual_frame_keys missing")

    return warnings


def validate_evidence_ref_provenance(evidence: Any) -> list[str]:
    """Return list of provenance warnings for an EvidenceRef."""
    warnings: list[str] = []

    if not getattr(evidence, "lesson_id", None):
        warnings.append("missing lesson_id")

    if getattr(evidence, "timestamp_start", None) is None and getattr(
        evidence, "timestamp_end", None
    ) is None:
        warnings.append("missing both timestamp_start and timestamp_end")

    frame_ids = getattr(evidence, "frame_ids", []) or []
    raw_ids = getattr(evidence, "raw_visual_event_ids", []) or []

    if not frame_ids and not raw_ids:
        warnings.append("missing both frame_ids and raw_visual_event_ids")

    screenshot_paths = getattr(evidence, "screenshot_paths", []) or []
    if screenshot_paths and not frame_ids:
        warnings.append("screenshot_paths present but frame_ids missing")

    if not (getattr(evidence, "source_event_ids", []) or []):
        warnings.append("missing source_event_ids")

    return warnings


def validate_rule_card_provenance(rule: Any) -> list[str]:
    """Return list of provenance warnings for a RuleCard."""
    warnings: list[str] = []

    if not getattr(rule, "lesson_id", None):
        warnings.append("missing lesson_id")

    source_event_ids = getattr(rule, "source_event_ids", []) or []
    evidence_refs = getattr(rule, "evidence_refs", []) or []

    if not source_event_ids:
        warnings.append("missing source_event_ids")

    ev_req = getattr(rule, "evidence_requirement", None) or "optional"
    if getattr(rule, "visual_summary", None) and not evidence_refs and ev_req != "none":
        warnings.append("visual_summary present but evidence_refs missing")

    if not getattr(rule, "concept", None):
        warnings.append("missing concept")

    return warnings


def validate_rule_card_for_final_provenance(rule: Any) -> list[str]:
    """Return hard errors from provenance warnings; use at final export to reject rules."""
    warnings = validate_rule_card_provenance(rule)
    hard_errors: list[str] = []

    for warning in warnings:
        if warning in {
            "missing lesson_id",
            "missing source_event_ids",
            "missing concept",
            "visual_summary present but evidence_refs missing",
        }:
            hard_errors.append(warning)

    return hard_errors


def compute_provenance_coverage(
    *,
    knowledge_events: list[Any],
    evidence_refs: list[Any],
    rule_cards: list[Any],
) -> dict[str, int]:
    """Return counts for provenance coverage (QA/manifest)."""
    return {
        "knowledge_events_total": len(knowledge_events),
        "knowledge_events_with_chunk_index": sum(
            1
            for ev in knowledge_events
            if ((getattr(ev, "metadata", {}) or {}).get("chunk_index") is not None)
        ),
        "knowledge_events_with_visual_candidates": sum(
            1
            for ev in knowledge_events
            if (
                (getattr(ev, "metadata", {}) or {}).get("candidate_visual_frame_keys")
                or []
            )
        ),
        "evidence_refs_total": len(evidence_refs),
        "evidence_refs_with_frame_ids": sum(
            1 for ev in evidence_refs if (getattr(ev, "frame_ids", []) or [])
        ),
        "evidence_refs_with_source_event_ids": sum(
            1 for ev in evidence_refs if (getattr(ev, "source_event_ids", []) or [])
        ),
        "rule_cards_total": len(rule_cards),
        "rule_cards_with_source_event_ids": sum(
            1 for rule in rule_cards if (getattr(rule, "source_event_ids", []) or [])
        ),
        "rule_cards_with_evidence_refs": sum(
            1 for rule in rule_cards if (getattr(rule, "evidence_refs", []) or [])
        ),
    }


def format_compact_provenance(rule: Any) -> str | None:
    """Format a short provenance block for review markdown (Evidence refs / Source events)."""
    source_event_ids = getattr(rule, "source_event_ids", []) or []
    evidence_refs = getattr(rule, "evidence_refs", []) or []

    lines: list[str] = []

    if evidence_refs:
        lines.append(f"**Evidence refs:** {', '.join(evidence_refs[:3])}")

    if source_event_ids:
        lines.append(f"**Source events:** {', '.join(source_event_ids[:3])}")

    if not lines:
        return None

    return "\n".join(lines)
