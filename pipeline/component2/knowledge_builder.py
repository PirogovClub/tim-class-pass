"""Structured post-parse knowledge extraction from *.chunks.json (Task 3)."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Protocol

from pydantic import BaseModel, Field

from pipeline.io_utils import atomic_write_text, atomic_write_json
from pipeline.component2.parser import seconds_to_mmss
from pipeline.component2.visual_compaction import (
    VisualCompactionConfig,
    assert_no_raw_visual_blob_leak,
    strip_raw_visual_blobs_from_metadata,
    summarize_visual_events_for_extraction,
)
from pipeline.schemas import (
    ConfidenceLabel,
    KnowledgeEvent,
    KnowledgeEventCollection,
)

logger = logging.getLogger(__name__)

MIN_NORMALIZED_LENGTH = 3
BUCKET_TO_EVENT_TYPE: dict[str, str] = {
    "definitions": "definition",
    "rule_statements": "rule_statement",
    "conditions": "condition",
    "invalidations": "invalidation",
    "exceptions": "exception",
    "comparisons": "comparison",
    "warnings": "warning",
    "process_steps": "process_step",
    "algorithm_hints": "algorithm_hint",
    "examples": "example",
}


# ----- Chunk adapter -----


def _lesson_slug(lesson_id: str) -> str:
    return re.sub(r"\W+", "_", lesson_id).strip("_").lower() or "lesson"


@dataclass
class AdaptedChunk:
    chunk_index: int
    lesson_id: str
    lesson_title: Optional[str]
    section: Optional[str]
    subsection: Optional[str]
    start_time_seconds: float
    end_time_seconds: float
    transcript_lines: list[dict[str, Any]] = field(default_factory=list)
    transcript_text: str = ""
    visual_events: list[dict[str, Any]] = field(default_factory=list)
    previous_visual_state: Optional[dict[str, Any]] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def candidate_visual_frame_keys(self) -> list[str]:
        keys: list[str] = []
        for v in self.visual_events:
            frame_key = v.get("frame_key")
            if frame_key:
                keys.append(str(frame_key))
        return keys

    @property
    def candidate_visual_types(self) -> list[str]:
        values: list[str] = []
        for v in self.visual_events:
            val = v.get("visual_representation_type")
            if val:
                values.append(str(val))
        return values

    @property
    def candidate_example_types(self) -> list[str]:
        values: list[str] = []
        for v in self.visual_events:
            val = v.get("example_type")
            if val:
                values.append(str(val))
        return values


def load_chunks_json(path: Path) -> list[dict]:
    """Load and validate *.chunks.json as a list of chunk dicts."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("chunks.json must be a JSON array")
    return data


def build_transcript_text(transcript_lines: list[dict]) -> str:
    """Join non-empty stripped line texts; ignore blanks."""
    parts: list[str] = []
    for line in transcript_lines:
        if not isinstance(line, dict):
            continue
        text = (line.get("text") or "").strip()
        if text:
            parts.append(text)
    return "\n".join(parts) if parts else ""


def get_transcript_time_bounds(
    transcript_lines: list[dict], fallback_start: float, fallback_end: float
) -> tuple[float, float]:
    """Use first/last line start/end if present, else fallbacks."""
    if not transcript_lines:
        return (fallback_start, fallback_end)
    start = fallback_start
    end = fallback_end
    first = transcript_lines[0]
    if isinstance(first, dict) and "start_seconds" in first:
        try:
            start = float(first["start_seconds"])
        except (TypeError, ValueError):
            pass
    last = transcript_lines[-1]
    if isinstance(last, dict) and "end_seconds" in last:
        try:
            end = float(last["end_seconds"])
        except (TypeError, ValueError):
            pass
    return (start, end)


def adapt_chunk(
    raw_chunk: dict,
    lesson_id: str,
    lesson_title: str | None = None,
) -> AdaptedChunk:
    """Normalize a raw chunk dict into AdaptedChunk."""
    meta = raw_chunk.get("metadata") or {}
    transcript_lines = raw_chunk.get("transcript_lines") or []
    visual_events = raw_chunk.get("visual_events") or []
    transcript_text = build_transcript_text(transcript_lines)
    return AdaptedChunk(
        chunk_index=int(raw_chunk.get("chunk_index", 0)),
        lesson_id=lesson_id,
        lesson_title=lesson_title,
        section=meta.get("section") or None,
        subsection=meta.get("subsection") or None,
        start_time_seconds=float(raw_chunk.get("start_time_seconds", 0.0)),
        end_time_seconds=float(raw_chunk.get("end_time_seconds", 0.0)),
        transcript_lines=transcript_lines,
        transcript_text=transcript_text,
        visual_events=visual_events,
        previous_visual_state=raw_chunk.get("previous_visual_state"),
        metadata=dict(meta),
    )


def adapt_chunks(
    raw_chunks: list[dict],
    lesson_id: str,
    lesson_title: str | None = None,
) -> list[AdaptedChunk]:
    """Adapt a list of raw chunk dicts."""
    return [
        adapt_chunk(c, lesson_id=lesson_id, lesson_title=lesson_title)
        for c in raw_chunks
    ]


# ----- Extraction models -----


class ExtractedStatement(BaseModel):
    text: str
    concept: Optional[str] = None
    subconcept: Optional[str] = None
    ambiguity_notes: list[str] = Field(default_factory=list)


class ChunkExtractionResult(BaseModel):
    definitions: list[ExtractedStatement] = Field(default_factory=list)
    rule_statements: list[ExtractedStatement] = Field(default_factory=list)
    conditions: list[ExtractedStatement] = Field(default_factory=list)
    invalidations: list[ExtractedStatement] = Field(default_factory=list)
    exceptions: list[ExtractedStatement] = Field(default_factory=list)
    comparisons: list[ExtractedStatement] = Field(default_factory=list)
    warnings: list[ExtractedStatement] = Field(default_factory=list)
    process_steps: list[ExtractedStatement] = Field(default_factory=list)
    algorithm_hints: list[ExtractedStatement] = Field(default_factory=list)
    examples: list[ExtractedStatement] = Field(default_factory=list)
    global_notes: list[str] = Field(default_factory=list)


# ----- Prompt -----


def build_knowledge_extraction_prompt(
    chunk: AdaptedChunk,
    visual_summaries: list[str],
) -> str:
    """Build the extraction prompt with transcript and compact visual summaries."""
    time_range = f"{seconds_to_mmss(chunk.start_time_seconds)} - {seconds_to_mmss(chunk.end_time_seconds)}"
    visual_block = "\n".join(f"- {s}" for s in visual_summaries) if visual_summaries else "(none)"
    return f"""Extract atomic trading knowledge from this lesson chunk. Output valid JSON only. Split distinct ideas into separate entries. Prefer explicit teaching rules over narration. Keep statements short and normalized. Use visuals as supporting evidence only. Do not describe frame-by-frame. Do not summarize the whole lesson. Do not invent absent information. Leave concept/subconcept null when unclear; note ambiguity in ambiguity_notes.

Lesson ID: {chunk.lesson_id}
Chunk index: {chunk.chunk_index}
Time range: {time_range}

<transcript>
{chunk.transcript_text or "(empty)"}
</transcript>

<compact_visual_summaries>
{visual_block}
</compact_visual_summaries>

Output a single JSON object with exactly these keys (each a list of objects with text, optional concept, optional subconcept, optional ambiguity_notes list): definitions, rule_statements, conditions, invalidations, exceptions, comparisons, warnings, process_steps, algorithm_hints, examples, global_notes (list of strings). Use empty lists for missing buckets. No markdown, no prose."""


# ----- LLM client protocol -----


class LLMExtractionClient(Protocol):
    """Protocol for extraction: (user_text, system_instruction) -> raw JSON string."""

    def generate_extraction(self, user_text: str, system_instruction: str) -> str:
        ...


# ----- Extraction and parsing -----


def extract_chunk_knowledge(
    chunk: AdaptedChunk,
    llm_client: Any,
    max_visual_summaries: int = 5,
    compaction_cfg: VisualCompactionConfig | None = None,
) -> tuple[ChunkExtractionResult, dict]:
    """Call LLM, parse JSON into ChunkExtractionResult, return result and debug payload."""
    cfg = compaction_cfg if compaction_cfg is not None else VisualCompactionConfig()
    visual_summaries = summarize_visual_events_for_extraction(chunk.visual_events, cfg)
    prompt = build_knowledge_extraction_prompt(chunk, visual_summaries)
    system = "You are a trading knowledge extractor. Respond only with valid JSON."
    debug: dict = {
        "chunk_index": chunk.chunk_index,
        "start_time_seconds": chunk.start_time_seconds,
        "end_time_seconds": chunk.end_time_seconds,
        "transcript_text": (chunk.transcript_text or "")[:500],
        "compact_visual_summaries": visual_summaries,
        "raw_model_response": "",
        "parsed_extraction": {},
        "emitted_event_ids": [],
        "error": None,
    }
    raw_response = ""
    try:
        if hasattr(llm_client, "generate_extraction"):
            raw_response = llm_client.generate_extraction(prompt, system)
        elif callable(llm_client):
            raw_response = str(llm_client(prompt, system) or "").strip()
        else:
            resp = llm_client.generate_text(
                user_text=prompt,
                system_instruction=system,
                response_mime_type="application/json",
                response_schema=ChunkExtractionResult,
            )
            raw_response = (resp.text or "").strip() if hasattr(resp, "text") else str(resp).strip()
    except Exception as e:
        debug["error"] = str(e)
        debug["raw_model_response"] = raw_response or "(no response)"
        return (ChunkExtractionResult(), debug)

    debug["raw_model_response"] = raw_response[:2000] if raw_response else ""

    parsed: ChunkExtractionResult | None = None
    try:
        if raw_response:
            raw_response = raw_response.strip()
            if raw_response.startswith("```"):
                raw_response = re.sub(r"^```\w*\n?", "", raw_response)
                raw_response = re.sub(r"\n?```\s*$", "", raw_response)
            parsed = ChunkExtractionResult.model_validate_json(raw_response)
    except Exception as e:
        debug["error"] = f"Parse error: {e}"
        return (ChunkExtractionResult(), debug)

    if parsed is None:
        parsed = ChunkExtractionResult()
    debug["parsed_extraction"] = parsed.model_dump()

    events = extraction_result_to_knowledge_events(parsed, chunk)
    debug["emitted_event_ids"] = [e.event_id for e in events]
    return (parsed, debug)


# ----- Concept inference -----

_CONCEPT_KEYWORDS: list[tuple[list[str], str, str | None]] = [
    (["level", "support", "resistance", "уровень"], "level", None),
    (["false breakout", "failed breakout", "ложный пробой", "false breakout"], "false_breakout", None),
    (["breakout", "break", "пробой", "break confirmation"], "break_confirmation", None),
    (["trend break"], "trend_break_level", None),
    (["reaction", "touches", "multiple reactions", "level rating"], "level_rating", None),
]


def infer_concept_from_text(text: str) -> tuple[str | None, str | None]:
    """Conservative keyword-based concept/subconcept from text."""
    if not text or not text.strip():
        return (None, None)
    lower = text.strip().lower()
    for keywords, concept, subconcept in _CONCEPT_KEYWORDS:
        for kw in keywords:
            if kw in lower:
                return (concept, subconcept)
    return (None, None)


def infer_concept_from_visuals(visual_events: list[dict]) -> tuple[str | None, str | None]:
    """Conservative concept from visual annotation/example_type."""
    for event in visual_events:
        etype = (event.get("example_type") or "").lower()
        if "false" in etype and "breakout" in etype:
            return ("false_breakout", None)
        if "level" in etype:
            return ("level", None)
        current = event.get("current_state") or {}
        if isinstance(current, dict):
            ann = (current.get("visible_annotations") or "")
            if isinstance(ann, str) and "level" in ann.lower():
                return ("level", None)
    return (None, None)


def resolve_concept(
    statement_concept: str | None,
    statement_subconcept: str | None,
    chunk: AdaptedChunk,
    statement_text: str,
) -> tuple[str | None, str | None]:
    """Prefer LLM-provided, then transcript keywords, then visual hints."""
    if statement_concept and statement_concept.strip():
        return (statement_concept.strip(), (statement_subconcept or "").strip() or None)
    c, s = infer_concept_from_text(statement_text)
    if c:
        return (c, s)
    c, s = infer_concept_from_visuals(chunk.visual_events)
    if c:
        return (c, s)
    return (None, None)


# ----- Confidence -----


def score_event_confidence(
    text: str,
    event_type: str,
    concept: str | None,
    ambiguity_notes: list[str],
    chunk: AdaptedChunk,
) -> tuple[ConfidenceLabel, float]:
    """Heuristic label and score in [0, 1]."""
    score = 0.5
    if concept:
        score += 0.15
    if not ambiguity_notes:
        score += 0.1
    if text and len(text.strip()) < 200 and text.strip().endswith((".", "!")):
        score += 0.1
    if event_type in ("definition", "rule_statement") and concept:
        score += 0.1
    if not text or len(text.strip()) < 10:
        score -= 0.2
    if not concept and event_type in ("rule_statement", "condition"):
        score -= 0.15
    score = max(0.0, min(1.0, score))
    if score >= 0.7:
        label: ConfidenceLabel = "high"
    elif score >= 0.4:
        label = "medium"
    else:
        label = "low"
    return (label, score)


# ----- Normalize and dedupe -----


def normalize_statement_text(text: str) -> str:
    """Strip and collapse whitespace."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text.strip())


def dedupe_statements(statements: list[ExtractedStatement]) -> list[ExtractedStatement]:
    """Case-insensitive, whitespace-normalized exact-text dedupe."""
    seen: set[str] = set()
    out: list[ExtractedStatement] = []
    for s in statements:
        key = normalize_statement_text(s.text).lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(s)
    return out


# ----- Map to KnowledgeEvent -----


def _metadata_for_chunk(chunk: AdaptedChunk) -> dict[str, Any]:
    return {
        "chunk_index": chunk.chunk_index,
        "chunk_start_time_seconds": chunk.start_time_seconds,
        "chunk_end_time_seconds": chunk.end_time_seconds,
        "transcript_line_count": len(chunk.transcript_lines),
        "candidate_visual_frame_keys": chunk.candidate_visual_frame_keys,
        "candidate_visual_types": chunk.candidate_visual_types,
        "candidate_example_types": chunk.candidate_example_types,
        "has_previous_visual_state": chunk.previous_visual_state is not None,
    }


def extraction_result_to_knowledge_events(
    extraction: ChunkExtractionResult,
    chunk: AdaptedChunk,
) -> list[KnowledgeEvent]:
    """Map extraction buckets to KnowledgeEvents with provenance and deterministic ids."""
    slug = _lesson_slug(chunk.lesson_id)
    t_start, t_end = get_transcript_time_bounds(
        chunk.transcript_lines,
        chunk.start_time_seconds,
        chunk.end_time_seconds,
    )
    ts_start = seconds_to_mmss(t_start)
    ts_end = seconds_to_mmss(t_end)
    meta = _metadata_for_chunk(chunk)
    events: list[KnowledgeEvent] = []

    for bucket_name, event_type in BUCKET_TO_EVENT_TYPE.items():
        statements: list[ExtractedStatement] = getattr(extraction, bucket_name, []) or []
        statements = dedupe_statements(statements)
        for i, st in enumerate(statements):
            raw = (st.text or "").strip()
            norm = normalize_statement_text(raw)
            if not raw or len(norm) < MIN_NORMALIZED_LENGTH:
                continue
            concept, subconcept = resolve_concept(
                st.concept, st.subconcept, chunk, raw
            )
            label, conf_score = score_event_confidence(
                raw, event_type, concept, st.ambiguity_notes or [], chunk
            )
            event_id = f"ke_{slug}_{chunk.chunk_index}_{event_type}_{i}"
            try:
                ke = KnowledgeEvent(
                    event_id=event_id,
                    lesson_id=chunk.lesson_id,
                    lesson_title=chunk.lesson_title,
                    section=chunk.section,
                    subsection=chunk.subsection,
                    timestamp_start=ts_start,
                    timestamp_end=ts_end,
                    event_type=event_type,
                    raw_text=raw,
                    normalized_text=norm,
                    concept=concept,
                    subconcept=subconcept,
                    source_event_ids=[],
                    evidence_refs=[],
                    confidence=label,
                    confidence_score=conf_score,
                    ambiguity_notes=st.ambiguity_notes or [],
                    metadata=strip_raw_visual_blobs_from_metadata(meta),
                )
                events.append(ke)
            except Exception:
                continue
    return events


# ----- Collection build and save -----


def build_knowledge_events_from_extraction_results(
    adapted_chunks: list[AdaptedChunk],
    extraction_results: list[ChunkExtractionResult],
    lesson_id: str,
    lesson_title: str | None = None,
) -> tuple[KnowledgeEventCollection, list[dict]]:
    """Build KnowledgeEventCollection from pre-extracted chunk results (no LLM call)."""
    if len(adapted_chunks) != len(extraction_results):
        raise ValueError(
            f"adapted_chunks and extraction_results length mismatch: "
            f"{len(adapted_chunks)} chunks vs {len(extraction_results)} results"
        )
    all_events: list[KnowledgeEvent] = []
    debug_rows: list[dict] = []
    for chunk, extraction in zip(adapted_chunks, extraction_results):
        events = extraction_result_to_knowledge_events(extraction, chunk)
        all_events.extend(events)
        row: dict = {
            "chunk_index": chunk.chunk_index,
            "start_time_seconds": chunk.start_time_seconds,
            "end_time_seconds": chunk.end_time_seconds,
            "num_events_emitted": len(events),
        }
        row["parsed_extraction"] = extraction.model_dump()
        debug_rows.append(row)
    collection = KnowledgeEventCollection(
        schema_version="1.0",
        lesson_id=lesson_id,
        lesson_title=lesson_title,
        events=all_events,
    )
    return (collection, debug_rows)


def build_knowledge_events_from_chunks(
    chunks: list[AdaptedChunk],
    lesson_id: str,
    lesson_title: str | None,
    llm_client: Any,
    debug: bool = False,
) -> tuple[KnowledgeEventCollection, list[dict]]:
    """Extract per chunk, aggregate events, collect debug rows."""
    all_events: list[KnowledgeEvent] = []
    debug_rows: list[dict] = []
    success_count = 0
    for chunk in chunks:
        extraction, debug_payload = extract_chunk_knowledge(
            chunk, llm_client, max_visual_summaries=5
        )
        if debug:
            debug_rows.append(debug_payload)
        events = extraction_result_to_knowledge_events(extraction, chunk)
        if not debug_payload.get("error"):
            success_count += 1
        all_events.extend(events)
    collection = KnowledgeEventCollection(
        schema_version="1.0",
        lesson_id=lesson_id,
        events=all_events,
    )
    logger.info(
        "Knowledge extraction: chunks=%d extracted=%d events=%d failed=%d",
        len(chunks),
        success_count,
        len(all_events),
        len(chunks) - success_count,
    )
    return (collection, debug_rows)


def build_knowledge_events_from_file(
    chunks_path: Path,
    lesson_id: str,
    lesson_title: str | None,
    llm_client: Any,
    debug: bool = False,
) -> tuple[KnowledgeEventCollection, list[dict]]:
    """Load chunks from file, adapt, then build from chunks."""
    raw = load_chunks_json(chunks_path)
    adapted = adapt_chunks(raw, lesson_id=lesson_id, lesson_title=lesson_title)
    logger.info("Loaded %d chunks from %s", len(adapted), chunks_path)
    return build_knowledge_events_from_chunks(
        adapted, lesson_id=lesson_id, lesson_title=lesson_title, llm_client=llm_client, debug=debug
    )


def save_knowledge_events(collection: KnowledgeEventCollection, output_path: Path) -> None:
    """Write KnowledgeEventCollection as JSON."""
    assert_no_raw_visual_blob_leak(collection.model_dump())
    atomic_write_text(output_path, collection.model_dump_json(indent=2), encoding="utf-8")
    logger.info("Wrote %d events to %s", len(collection.events), output_path)


def save_knowledge_debug(debug_rows: list[dict], output_path: Path) -> None:
    """Write debug records as JSON array."""
    atomic_write_json(output_path, debug_rows)
    logger.info("Wrote debug %d rows to %s", len(debug_rows), output_path)
