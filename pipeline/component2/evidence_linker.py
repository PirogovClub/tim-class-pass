"""Step 4: Deterministic evidence linking — map visual evidence to KnowledgeEvents."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pipeline.io_utils import atomic_write_text, atomic_write_json
from pipeline.component2.parser import seconds_to_mmss, timestamp_to_seconds
from pipeline.component2.visual_compaction import (
    VisualCompactionConfig,
    assert_no_raw_visual_blob_leak,
    build_evidence_provenance_payload,
    strip_raw_visual_blobs_from_metadata,
    summarize_visual_candidate_for_evidence,
)
from pipeline.invalidation_filter import load_dense_analysis
from pipeline.schemas import (
    EvidenceIndex,
    EvidenceRef,
    ExampleRole,
    KnowledgeEvent,
    KnowledgeEventCollection,
    VisualType,
)


# ----- Internal adapter models -----


@dataclass
class AdaptedVisualEvent:
    timestamp_seconds: float
    frame_key: str
    visual_representation_type: str
    example_type: str
    change_summary: str | None
    current_state: dict[str, Any]
    extracted_entities: dict[str, Any]
    chunk_index: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class VisualEvidenceCandidate:
    candidate_id: str
    lesson_id: str
    chunk_index: int | None
    timestamp_start: float
    timestamp_end: float
    frame_keys: list[str] = field(default_factory=list)
    visual_events: list[AdaptedVisualEvent] = field(default_factory=list)
    compact_visual_summary: str | None = None
    visual_type: str = "unknown"
    example_role: str = "unknown"
    concept_hints: list[str] = field(default_factory=list)
    subconcept_hints: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


# ----- Loaders -----


def load_chunks_json(path: Path) -> list[dict]:
    """Load *.chunks.json as a list of chunk dicts."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("chunks.json must be a JSON array")
    return data


def load_knowledge_events(path: Path) -> list[KnowledgeEvent]:
    """Load KnowledgeEventCollection from JSON and return .events."""
    text = path.read_text(encoding="utf-8")
    collection = KnowledgeEventCollection.model_validate_json(text)
    return list(collection.events)


def _change_summary_to_str(raw: Any) -> str | None:
    """Normalize change_summary from list or str to single str."""
    if raw is None:
        return None
    if isinstance(raw, str):
        return raw.strip() or None
    if isinstance(raw, list):
        parts = [str(item).strip() for item in raw if item]
        return " ".join(parts) if parts else None
    return str(raw).strip() or None


def adapt_visual_events_from_chunks(
    raw_chunks: list[dict],
    lesson_id: str,
) -> list[AdaptedVisualEvent]:
    """Build AdaptedVisualEvent list from chunk dicts; preserve chunk context."""
    events: list[AdaptedVisualEvent] = []
    for chunk in raw_chunks:
        chunk_index = chunk.get("chunk_index")
        if chunk_index is not None:
            chunk_index = int(chunk_index)
        for ve in chunk.get("visual_events") or []:
            if not isinstance(ve, dict):
                continue
            ts = ve.get("timestamp_seconds")
            if ts is None:
                continue
            if isinstance(ts, (int, float)):
                ts_float = float(ts)
            else:
                try:
                    ts_float = float(ts)
                except (TypeError, ValueError):
                    continue
            frame_key = ve.get("frame_key")
            if not frame_key:
                continue
            events.append(
                AdaptedVisualEvent(
                    timestamp_seconds=ts_float,
                    frame_key=str(frame_key),
                    visual_representation_type=str(ve.get("visual_representation_type") or "unknown"),
                    example_type=str(ve.get("example_type") or "unknown"),
                    change_summary=_change_summary_to_str(ve.get("change_summary")),
                    current_state=dict(ve.get("current_state") or {}),
                    extracted_entities=dict(ve.get("extracted_entities") or {}),
                    chunk_index=chunk_index,
                    metadata=dict(ve.get("metadata") or {}),
                )
            )
    return events


def enrich_visual_event_from_dense_analysis(
    event: AdaptedVisualEvent,
    dense_analysis: dict[str, Any],
) -> AdaptedVisualEvent:
    """Merge richer metadata from dense_analysis by frame_key; return copy or same."""
    entry = dense_analysis.get(event.frame_key)
    if not isinstance(entry, dict):
        return event
    current_state = dict(event.current_state)
    if entry.get("current_state"):
        current_state.update(entry["current_state"])
    extracted = dict(event.extracted_entities)
    if entry.get("extracted_entities"):
        extracted.update(entry["extracted_entities"])
    change = event.change_summary
    if entry.get("change_summary"):
        change = _change_summary_to_str(entry["change_summary"]) or change
    return AdaptedVisualEvent(
        timestamp_seconds=event.timestamp_seconds,
        frame_key=event.frame_key,
        visual_representation_type=str(
            entry.get("visual_representation_type") or event.visual_representation_type
        ),
        example_type=str(entry.get("example_type") or event.example_type),
        change_summary=change,
        current_state=current_state,
        extracted_entities=extracted,
        chunk_index=event.chunk_index,
        metadata={**event.metadata, **(entry if isinstance(entry, dict) else {})},
    )


# ----- Concept hint mapping (task 4 spec) -----

_CONCEPT_MAP: list[tuple[list[str], str]] = [
    (["level", "support", "resistance"], "level"),
    (["false breakout", "failed breakout", "ложный пробой", "false_breakout"], "false_breakout"),
    (["breakout", "пробой", "break_confirmation"], "break_confirmation"),
    (["trend break"], "trend_break_level"),
    (["multiple reactions", "touch", "reaction count"], "level_rating"),
]


def _normalize_concept_hint(text: str) -> str | None:
    t = text.strip().lower().replace(" ", "_").replace("-", "_")
    if not t:
        return None
    for keywords, concept in _CONCEPT_MAP:
        for kw in keywords:
            if kw.lower().replace(" ", "_") in t or t in kw.lower().replace(" ", "_"):
                return concept
    return t if t else None


def extract_visual_concept_hints(event: AdaptedVisualEvent) -> tuple[list[str], list[str]]:
    """Extract (concept_hints, subconcept_hints) from annotations, entities, change_summary, etc."""
    concepts: set[str] = set()
    subconcepts: set[str] = set()
    sources: list[str] = []

    # visible annotations
    for ann in (event.current_state.get("visible_annotations") or []):
        if ann:
            sources.append(str(ann).strip())
    # extracted entity labels
    for key, val in (event.extracted_entities or {}).items():
        if val is not None and val != "":
            sources.append(str(key).strip())
            if isinstance(val, str):
                sources.append(val.strip())
            elif isinstance(val, list):
                for v in val:
                    if v:
                        sources.append(str(v).strip())
    # change_summary
    if event.change_summary:
        sources.append(event.change_summary)
    # trading_relevant_interpretation (nested in current_state or extracted_entities)
    interp = (event.current_state or {}).get("trading_relevant_interpretation")
    if interp:
        sources.append(interp if isinstance(interp, str) else " ".join(str(x) for x in interp))
    # example_type
    if event.example_type and event.example_type != "unknown":
        sources.append(event.example_type)

    for s in sources:
        if not s:
            continue
        hint = _normalize_concept_hint(s)
        if hint:
            concepts.add(hint)
    return (sorted(concepts), sorted(subconcepts))


def group_visual_events_into_candidates(
    visual_events: list[AdaptedVisualEvent],
    lesson_id: str = "unknown",
    max_time_gap_seconds: float = 20.0,
) -> list[VisualEvidenceCandidate]:
    """Group nearby events into teaching-example-level candidates."""
    if not visual_events:
        return []
    sorted_events = sorted(visual_events, key=lambda e: (e.chunk_index or -1, e.timestamp_seconds, e.frame_key))
    candidates: list[VisualEvidenceCandidate] = []
    current: list[AdaptedVisualEvent] = []
    chunk_idx: int | None = None
    candidate_idx = 0

    def flush() -> None:
        nonlocal candidate_idx
        if not current:
            return
        cid = chunk_idx is not None
        cid_str = f"evcand_{lesson_id}_{chunk_idx}_{candidate_idx}" if cid else f"evcand_{candidate_idx}"
        candidate_idx += 1
        all_concepts: set[str] = set()
        all_sub: set[str] = set()
        for e in current:
            ch, sub = extract_visual_concept_hints(e)
            all_concepts.update(ch)
            all_sub.update(sub)
        ts_start = min(e.timestamp_seconds for e in current)
        ts_end = max(e.timestamp_seconds for e in current)
        frame_keys = [e.frame_key for e in current]
        candidates.append(
            VisualEvidenceCandidate(
                candidate_id=cid_str,
                lesson_id=lesson_id or "unknown",
                chunk_index=chunk_idx,
                timestamp_start=ts_start,
                timestamp_end=ts_end,
                frame_keys=frame_keys,
                visual_events=list(current),
                concept_hints=sorted(all_concepts),
                subconcept_hints=sorted(all_sub),
            )
        )
        current.clear()

    for e in sorted_events:
        if not current:
            current.append(e)
            chunk_idx = e.chunk_index
            continue
        prev = current[-1]
        same_chunk = (e.chunk_index == prev.chunk_index)
        gap = e.timestamp_seconds - prev.timestamp_seconds
        same_or_compat_type = (
            (e.example_type == prev.example_type or "unknown" in (e.example_type, prev.example_type))
            and (e.visual_representation_type == prev.visual_representation_type or "unknown" in (e.visual_representation_type, prev.visual_representation_type))
        )
        if same_chunk and same_or_compat_type and gap <= max_time_gap_seconds:
            current.append(e)
        else:
            flush()
            current.append(e)
            chunk_idx = e.chunk_index
    flush()
    return candidates


def infer_example_role(
    candidate: VisualEvidenceCandidate,
    linked_events: list[KnowledgeEvent],
) -> str:
    """Heuristic example role from linked events and candidate content."""
    content_lower = " ".join(
        (candidate.compact_visual_summary or "")
        + " "
        + " ".join(candidate.concept_hints)
        + " "
        + " ".join(e.change_summary or "" for e in candidate.visual_events)
    ).lower()
    counter_indicators = ["failure", "false", "trap", "mistake", "invalid", "counter"]
    if any(x in content_lower for x in counter_indicators):
        return "counterexample"
    event_types = [e.event_type for e in linked_events]
    if any(t in event_types for t in ("invalidation", "exception", "warning")):
        return "counterexample"
    if any(t in event_types for t in ("rule_statement", "condition")):
        return "positive_example"
    if any(t in event_types for t in ("definition", "comparison")):
        return "illustration"
    if not linked_events or (len(linked_events) == 1 and linked_events[0].event_type == "example"):
        return "ambiguous_example"
    return "illustration"


# ----- Scoring and linking -----

def _event_time_range_seconds(event: KnowledgeEvent) -> tuple[float, float] | None:
    """Return (start_sec, end_sec) or None if not parseable."""
    s, e = event.timestamp_start, event.timestamp_end
    if not s or not e:
        return None
    try:
        start = timestamp_to_seconds(s)
        end = timestamp_to_seconds(e)
        return (start, end)
    except (ValueError, TypeError):
        return None


def score_candidate_event_match(
    candidate: VisualEvidenceCandidate,
    event: KnowledgeEvent,
) -> tuple[float, dict[str, float]]:
    """Score match; return (total, breakdown). Weights: chunk 0.40, time 0.25, concept 0.20, subconcept 0.10, type 0.05; cap 1.0."""
    breakdown: dict[str, float] = {
        "chunk_match": 0.0,
        "time_overlap": 0.0,
        "concept_match": 0.0,
        "subconcept_match": 0.0,
        "type_compatibility": 0.0,
    }
    event_chunk = event.metadata.get("chunk_index") if event.metadata else None
    if event_chunk is not None and candidate.chunk_index is not None and int(event_chunk) == int(candidate.chunk_index):
        breakdown["chunk_match"] = 0.40
    event_range = _event_time_range_seconds(event)
    if event_range and candidate.visual_events:
        ev_start, ev_end = event_range
        cand_start, cand_end = candidate.timestamp_start, candidate.timestamp_end
        overlap_start = max(ev_start, cand_start)
        overlap_end = min(ev_end, cand_end)
        if overlap_end > overlap_start:
            breakdown["time_overlap"] = 0.25
        else:
            gap = min(abs(cand_start - ev_end), abs(cand_end - ev_start))
            if gap <= 30:
                breakdown["time_overlap"] = 0.25 * (1.0 - gap / 30.0)
    event_concept = (event.concept or "").strip().lower().replace(" ", "_")
    if event_concept and any(event_concept == h.lower() for h in candidate.concept_hints):
        breakdown["concept_match"] = 0.20
    event_sub = (event.subconcept or "").strip().lower().replace(" ", "_")
    if event_sub and any(event_sub == h.lower() for h in candidate.subconcept_hints):
        breakdown["subconcept_match"] = 0.10
    breakdown["type_compatibility"] = 0.05
    total = min(1.0, sum(breakdown.values()))
    breakdown["total"] = total
    return (total, breakdown)


def link_candidates_to_knowledge_events(
    candidates: list[VisualEvidenceCandidate],
    knowledge_events: list[KnowledgeEvent],
    threshold: float = 0.50,
    compaction_cfg: VisualCompactionConfig | None = None,
) -> tuple[list[tuple[VisualEvidenceCandidate, list[KnowledgeEvent]]], list[dict]]:
    """For each candidate, link events with score >= threshold; return (pairs, debug_rows)."""
    cfg = compaction_cfg if compaction_cfg is not None else VisualCompactionConfig()
    linked: list[tuple[VisualEvidenceCandidate, list[KnowledgeEvent]]] = []
    debug_rows: list[dict] = []
    for c in candidates:
        c.compact_visual_summary = c.compact_visual_summary or summarize_visual_candidate_for_evidence(c, cfg)
        scores: list[dict] = []
        best_events: list[KnowledgeEvent] = []
        for ev in knowledge_events:
            score, br = score_candidate_event_match(c, ev)
            if score >= threshold:
                best_events.append(ev)
            scores.append({
                "event_id": ev.event_id,
                "score_breakdown": br,
            })
        role = infer_example_role(c, best_events)
        c.example_role = role
        linked.append((c, best_events))
        debug_rows.append({
            "candidate_id": c.candidate_id,
            "chunk_index": c.chunk_index,
            "frame_keys": c.frame_keys,
            "timestamp_start": c.timestamp_start,
            "timestamp_end": c.timestamp_end,
            "concept_hints": c.concept_hints,
            "compact_visual_summary": c.compact_visual_summary,
            "candidate_scores": scores,
            "linked_event_ids": [e.event_id for e in best_events],
            "example_role": role,
        })
    return (linked, debug_rows)


def _visual_type_to_schema(v: str) -> VisualType:
    vt = (v or "").strip().lower().replace(" ", "_")
    for choice in ["annotated_chart", "plain_chart", "hand_drawing", "diagram", "text_slide", "mixed_visual"]:
        if choice == vt or choice.replace("_", " ") == v:
            return choice  # type: ignore[return-value]
    return "unknown"


def _example_role_to_schema(r: str) -> ExampleRole:
    for choice in ["positive_example", "negative_example", "counterexample", "ambiguous_example", "illustration", "unknown"]:
        if (r or "").strip().lower().replace(" ", "_") == choice:
            return choice  # type: ignore[return-value]
    return "unknown"


def candidate_to_evidence_ref(
    candidate: VisualEvidenceCandidate,
    linked_events: list[KnowledgeEvent],
    lesson_id: str,
    lesson_title: str | None = None,
    video_root: Path | None = None,
    compaction_cfg: VisualCompactionConfig | None = None,
) -> EvidenceRef:
    """Build EvidenceRef from candidate and linked events."""
    cfg = compaction_cfg if compaction_cfg is not None else VisualCompactionConfig()
    payload = build_evidence_provenance_payload(candidate, video_root, cfg)
    section: str | None = None
    subsection: str | None = None
    if linked_events:
        sections = [e.section for e in linked_events if e.section]
        subsections = [e.subsection for e in linked_events if e.subsection]
        if len(set(sections)) == 1 and sections:
            section = sections[0]
        if len(set(subsections)) == 1 and subsections:
            subsection = subsections[0]
    ts_start_str = seconds_to_mmss(candidate.timestamp_start)
    ts_end_str = seconds_to_mmss(candidate.timestamp_end)
    compact_visual_summary = candidate.compact_visual_summary or summarize_visual_candidate_for_evidence(candidate, cfg)
    return EvidenceRef(
        evidence_id=candidate.candidate_id,
        lesson_id=lesson_id,
        lesson_title=lesson_title,
        section=section,
        subsection=subsection,
        timestamp_start=ts_start_str,
        timestamp_end=ts_end_str,
        frame_ids=payload["frame_ids"],
        screenshot_paths=payload["screenshot_paths"],
        visual_type=_visual_type_to_schema(candidate.visual_type),
        example_role=_example_role_to_schema(candidate.example_role),
        compact_visual_summary=compact_visual_summary,
        linked_rule_ids=[],
        raw_visual_event_ids=payload["raw_visual_event_ids"],
        source_event_ids=[e.event_id for e in linked_events],
        metadata=strip_raw_visual_blobs_from_metadata(candidate.metadata),
    )


def build_evidence_index(
    lesson_id: str,
    knowledge_events: list[KnowledgeEvent],
    chunks: list[dict],
    dense_analysis: dict[str, Any] | None = None,
    lesson_title: str | None = None,
    link_threshold: float = 0.50,
    video_root: Path | None = None,
    compaction_cfg: VisualCompactionConfig | None = None,
) -> tuple[EvidenceIndex, list[dict]]:
    """Adapt visuals from chunks, optionally enrich, group, link, convert to EvidenceRef; return (EvidenceIndex, debug_rows)."""
    cfg = compaction_cfg if compaction_cfg is not None else VisualCompactionConfig()
    adapted = adapt_visual_events_from_chunks(chunks, lesson_id)
    if dense_analysis:
        adapted = [enrich_visual_event_from_dense_analysis(e, dense_analysis) for e in adapted]
    candidates = group_visual_events_into_candidates(adapted, lesson_id=lesson_id)
    linked_pairs, debug_rows = link_candidates_to_knowledge_events(
        candidates, knowledge_events, threshold=link_threshold, compaction_cfg=cfg
    )
    refs: list[EvidenceRef] = []
    for candidate, linked in linked_pairs:
        refs.append(
            candidate_to_evidence_ref(
                candidate, linked, lesson_id, lesson_title,
                video_root=video_root, compaction_cfg=cfg,
            )
        )
    index = EvidenceIndex(
        schema_version="1.0",
        lesson_id=lesson_id,
        lesson_title=lesson_title,
        evidence_refs=refs,
        metadata={},
    )
    return (index, debug_rows)


def save_evidence_index(index: EvidenceIndex, output_path: Path) -> None:
    """Write EvidenceIndex as JSON."""
    assert_no_raw_visual_blob_leak(index.model_dump())
    atomic_write_text(output_path, index.model_dump_json(indent=2), encoding="utf-8")


def save_evidence_debug(debug_rows: list[dict], output_path: Path) -> None:
    """Write debug rows as JSON array."""
    atomic_write_json(output_path, debug_rows)
