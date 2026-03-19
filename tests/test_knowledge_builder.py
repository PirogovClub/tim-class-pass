"""Tests for structured post-parse knowledge extraction (Task 3)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from pipeline.component2.knowledge_builder import (
    AdaptedChunk,
    ChunkExtractionResult,
    ExtractedStatement,
    build_transcript_text,
    adapt_chunk,
    adapt_chunks,
    load_chunks_json,
    summarize_visual_events_for_extraction,
    extraction_result_to_knowledge_events,
    normalize_statement_text,
    dedupe_statements,
    save_knowledge_events,
    save_knowledge_debug,
    build_knowledge_events_from_chunks,
    build_knowledge_events_from_file,
)
from pipeline.component2.visual_compaction import VisualCompactionConfig
from pipeline.schemas import KnowledgeEvent, KnowledgeEventCollection, TranscriptAnchor


# ---- Phase 2A: line anchors and timestamps ----


def test_extraction_result_to_knowledge_events_uses_line_indices_for_tighter_timestamps() -> None:
    chunk = AdaptedChunk(
        lesson_id="L2",
        lesson_title=None,
        chunk_index=0,
        section=None,
        subsection=None,
        start_time_seconds=1.0,
        end_time_seconds=20.0,
        transcript_lines=[
            {"start_seconds": 1.0, "end_seconds": 4.0, "text": "Intro line."},
            {"start_seconds": 4.0, "end_seconds": 7.0, "text": "A level forms after repeated reactions."},
            {"start_seconds": 7.0, "end_seconds": 10.0, "text": "This level becomes important for entries."},
        ],
        transcript_text="Intro line.\nA level forms after repeated reactions.\nThis level becomes important for entries.",
        visual_events=[],
    )
    extraction = ChunkExtractionResult(
        definitions=[
            ExtractedStatement(
                text="A level forms after repeated reactions.",
                concept="level",
                source_line_indices=[1, 2],
                source_quote="repeated reactions",
            )
        ]
    )
    events, rejected = extraction_result_to_knowledge_events(extraction, chunk)
    assert rejected == []
    assert len(events) == 1
    ev = events[0]
    assert ev.timestamp_start == "00:04"
    assert ev.timestamp_end == "00:10"
    assert ev.timestamp_confidence == "line"
    assert ev.source_line_start == 1
    assert ev.source_line_end == 2
    assert len(ev.transcript_anchors) == 2


def test_extraction_result_to_knowledge_events_falls_back_to_source_quote_match() -> None:
    chunk = AdaptedChunk(
        lesson_id="L2",
        lesson_title=None,
        chunk_index=0,
        section=None,
        subsection=None,
        start_time_seconds=1.0,
        end_time_seconds=20.0,
        transcript_lines=[
            {"start_seconds": 1.0, "end_seconds": 4.0, "text": "Intro line."},
            {"start_seconds": 4.0, "end_seconds": 7.0, "text": "A false breakout returns below the level."},
        ],
        transcript_text="Intro line.\nA false breakout returns below the level.",
        visual_events=[],
    )
    extraction = ChunkExtractionResult(
        invalidations=[
            ExtractedStatement(
                text="A false breakout is invalid when price returns below the level.",
                concept="false_breakout",
                source_line_indices=[],
                source_quote="returns below the level",
            )
        ]
    )
    events, rejected = extraction_result_to_knowledge_events(extraction, chunk)
    assert rejected == []
    ev = events[0]
    # Quote-matched anchors get "span" (not "line"); only explicit llm_line_indices can get "line"
    assert ev.timestamp_confidence == "span"
    assert ev.source_line_start == 1
    assert ev.source_line_end == 1
    assert len(ev.transcript_anchors) == 1


def test_extraction_result_to_knowledge_events_invalid_line_indices_fall_back_to_chunk_bounds() -> None:
    chunk = AdaptedChunk(
        lesson_id="L2",
        lesson_title=None,
        chunk_index=0,
        section=None,
        subsection=None,
        start_time_seconds=1.0,
        end_time_seconds=20.0,
        transcript_lines=[
            {"start_seconds": 1.0, "end_seconds": 4.0, "text": "One line."},
        ],
        transcript_text="One line.",
        visual_events=[],
    )
    extraction = ChunkExtractionResult(
        definitions=[
            ExtractedStatement(
                text="One line.",
                source_line_indices=[99],
                source_quote=None,
            )
        ]
    )
    events, rejected = extraction_result_to_knowledge_events(extraction, chunk)
    assert rejected == []
    ev = events[0]
    assert ev.timestamp_confidence == "chunk"
    assert ev.source_line_start is None
    assert ev.source_line_end is None
    assert ev.transcript_anchors == []


# ---- 1. Adapt chunk from real shape ----


def _real_shape_chunk() -> dict:
    """Chunk dict matching LessonChunk.model_dump() / *.chunks.json."""
    return {
        "chunk_index": 2,
        "start_time_seconds": 60.0,
        "end_time_seconds": 120.0,
        "transcript_lines": [
            {"start_seconds": 60.0, "end_seconds": 65.0, "text": "First line."},
            {"start_seconds": 66.0, "end_seconds": 70.0, "text": "Second line."},
        ],
        "visual_events": [
            {
                "timestamp_seconds": 62,
                "frame_key": "000062",
                "visual_representation_type": "annotated_chart",
                "example_type": "false_breakout_example",
                "change_summary": ["Price breaks above level then returns"],
                "current_state": {},
                "extracted_entities": {},
            },
        ],
        "previous_visual_state": None,
    }


def test_adapt_chunk_from_real_shape() -> None:
    raw = _real_shape_chunk()
    adapted = adapt_chunk(raw, lesson_id="Lesson 2", lesson_title="Levels part 1")
    assert isinstance(adapted, AdaptedChunk)
    assert adapted.chunk_index == 2
    assert adapted.lesson_id == "Lesson 2"
    assert adapted.lesson_title == "Levels part 1"
    assert adapted.start_time_seconds == 60.0
    assert adapted.end_time_seconds == 120.0
    assert "First line" in adapted.transcript_text and "Second line" in adapted.transcript_text
    assert adapted.candidate_visual_frame_keys == ["000062"]
    assert "annotated_chart" in adapted.candidate_visual_types
    assert "false_breakout_example" in adapted.candidate_example_types
    assert len(adapted.transcript_lines) == 2


# ---- 2. Build transcript text ----


def test_build_transcript_text_normalizes_blanks_and_spaces() -> None:
    lines = [
        {"start_seconds": 0.0, "end_seconds": 1.0, "text": "  One  "},
        {"start_seconds": 1.0, "end_seconds": 2.0, "text": ""},
        {"start_seconds": 2.0, "end_seconds": 3.0, "text": "  "},
        {"start_seconds": 3.0, "end_seconds": 4.0, "text": "Two"},
    ]
    result = build_transcript_text(lines)
    assert "One" in result
    assert "Two" in result
    assert result.count("\n") >= 1
    assert "  " not in result or result == "  One  \nTwo"  # we strip per-line but join with \n
    # After strip we join; build_transcript_text strips each text and skips empty
    parts = [p.strip() for p in ("  One  ", "", "  ", "Two") if p.strip()]
    assert result == "\n".join(parts)


# ---- 3. Visual pre-summarization ----


def test_summarize_visual_events_non_empty_capped_no_raw_dump() -> None:
    events = [
        {
            "visual_representation_type": "annotated_chart",
            "example_type": "false_breakout_example",
            "change_summary": ["Brief move above level fails and returns below."],
            "frame_key": "000100",
        },
        {
            "visual_representation_type": "hand_drawing",
            "example_type": "teaching_example",
            "change_summary": ["Level strength from repeated reactions."],
            "frame_key": "000101",
        },
        {"visual_representation_type": "diagram", "frame_key": "000102"},
    ]
    cfg = VisualCompactionConfig()
    summaries = summarize_visual_events_for_extraction(events, cfg)
    assert len(summaries) <= 5
    assert all(isinstance(s, str) and len(s) > 0 for s in summaries)
    assert not any("timestamp_seconds" in s or "extracted_entities" in s for s in summaries)
    if summaries:
        first = summaries[0].lower()
        assert "annotated" in first or "false" in first or "level" in first


# ---- 4 & 5. Extraction mapping and deterministic ids ----


def _sample_adapted_chunk() -> AdaptedChunk:
    return AdaptedChunk(
        chunk_index=1,
        lesson_id="Lesson_2_Levels",
        lesson_title="Levels part 1",
        section=None,
        subsection=None,
        start_time_seconds=30.0,
        end_time_seconds=90.0,
        transcript_lines=[
            {"start_seconds": 30.0, "end_seconds": 40.0, "text": "A level is..."},
            {"start_seconds": 50.0, "end_seconds": 90.0, "text": "False breakout invalidates."},
        ],
        transcript_text="A level is...\nFalse breakout invalidates.",
        visual_events=[{"frame_key": "000050", "visual_representation_type": "chart", "example_type": "example"}],
        previous_visual_state=None,
        metadata={},
    )


def test_extraction_mapping_and_deterministic_ids() -> None:
    extraction = ChunkExtractionResult(
        definitions=[
            ExtractedStatement(text="A level is a price zone where price reacted.", concept="level", subconcept=None),
        ],
        rule_statements=[
            ExtractedStatement(text="False breakout invalidates the level.", concept="false_breakout", subconcept=None),
        ],
        conditions=[],
        invalidations=[],
        exceptions=[],
        comparisons=[],
        warnings=[],
        process_steps=[],
        algorithm_hints=[],
        examples=[],
        global_notes=[],
    )
    chunk = _sample_adapted_chunk()
    events, _ = extraction_result_to_knowledge_events(extraction, chunk)
    assert len(events) >= 2
    event_types = {e.event_type for e in events}
    assert "definition" in event_types
    assert "rule_statement" in event_types
    ids_first = [e.event_id for e in events]
    events2, _ = extraction_result_to_knowledge_events(extraction, chunk)
    ids_second = [e.event_id for e in events2]
    assert ids_first == ids_second


# ---- 6. Provenance metadata present ----


def test_provenance_metadata_present() -> None:
    extraction = ChunkExtractionResult(
        definitions=[ExtractedStatement(text="Level is a price zone.", concept="level", subconcept=None)],
        rule_statements=[],
        conditions=[],
        invalidations=[],
        exceptions=[],
        comparisons=[],
        warnings=[],
        process_steps=[],
        algorithm_hints=[],
        examples=[],
        global_notes=[],
    )
    chunk = _sample_adapted_chunk()
    events, _ = extraction_result_to_knowledge_events(extraction, chunk)
    assert len(events) == 1
    meta = events[0].metadata
    assert meta.get("chunk_index") == 1
    assert "candidate_visual_frame_keys" in meta
    assert "candidate_visual_types" in meta
    assert "candidate_example_types" in meta


# ---- 7. Collection serialization ----


def test_collection_serialization_roundtrip() -> None:
    chunk = _sample_adapted_chunk()
    extraction = ChunkExtractionResult(
        definitions=[ExtractedStatement(text="Short def.", concept="level", subconcept=None)],
        rule_statements=[],
        conditions=[],
        invalidations=[],
        exceptions=[],
        comparisons=[],
        warnings=[],
        process_steps=[],
        algorithm_hints=[],
        examples=[],
        global_notes=[],
    )
    events, _ = extraction_result_to_knowledge_events(extraction, chunk)
    collection = KnowledgeEventCollection(
        schema_version="1.0",
        lesson_id=chunk.lesson_id,
        events=events,
    )
    js = collection.model_dump_json(indent=2)
    parsed = KnowledgeEventCollection.model_validate_json(js)
    assert parsed.schema_version == collection.schema_version
    assert parsed.lesson_id == collection.lesson_id
    assert len(parsed.events) == len(collection.events)
    assert parsed.events[0].event_id == collection.events[0].event_id


# ---- 8. Feature-flag-safe integration ----


def test_feature_flag_safe_when_disabled() -> None:
    """When enable_knowledge_events=False, pipeline does not call knowledge builder or write knowledge files."""
    from pipeline.component2.main import run_component2_pipeline

    # We cannot run the full pipeline without real paths; we assert the param exists and default is False.
    import inspect
    sig = inspect.signature(run_component2_pipeline)
    assert "enable_knowledge_events" in sig.parameters
    assert sig.parameters["enable_knowledge_events"].default is False


# ---- 9. Bad statements skipped ----


def test_blank_and_short_statements_skipped() -> None:
    extraction = ChunkExtractionResult(
        definitions=[
            ExtractedStatement(text="Valid definition here.", concept="level", subconcept=None),
            ExtractedStatement(text="", concept=None, subconcept=None),
            ExtractedStatement(text="  \t  ", concept=None, subconcept=None),
            ExtractedStatement(text="x", concept=None, subconcept=None),  # too short after normalize
        ],
        rule_statements=[],
        conditions=[],
        invalidations=[],
        exceptions=[],
        comparisons=[],
        warnings=[],
        process_steps=[],
        algorithm_hints=[],
        examples=[],
        global_notes=[],
    )
    chunk = _sample_adapted_chunk()
    events, _ = extraction_result_to_knowledge_events(extraction, chunk)
    assert len(events) == 1
    assert events[0].normalized_text == "Valid definition here."


def test_dedupe_statements_removes_duplicates() -> None:
    statements = [
        ExtractedStatement(text="Same rule.", concept="level", subconcept=None),
        ExtractedStatement(text="  same rule.  ", concept="level", subconcept=None),
        ExtractedStatement(text="SAME RULE.", concept="level", subconcept=None),
    ]
    deduped = dedupe_statements(statements)
    assert len(deduped) == 1
    assert normalize_statement_text(deduped[0].text).lower() == "same rule."


# ---- Helpers used elsewhere ----


def test_normalize_statement_text() -> None:
    assert normalize_statement_text("  a  b  ") == "a b"
    assert normalize_statement_text("") == ""


def test_load_chunks_json(tmp_path: Path) -> None:
    path = tmp_path / "chunks.json"
    data = [_real_shape_chunk()]
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    loaded = load_chunks_json(path)
    assert len(loaded) == 1
    assert loaded[0]["chunk_index"] == 2


def test_save_knowledge_events_preserves_phase2a_fields(tmp_path: Path) -> None:
    """Phase 2A fields survive save/load round-trip."""
    collection = KnowledgeEventCollection(
        lesson_id="L2",
        lesson_title="Lesson 2",
        events=[
            KnowledgeEvent(
                event_id="ke1",
                lesson_id="L2",
                event_type="definition",
                raw_text="A level is a repeated reaction area.",
                normalized_text="A level is a repeated reaction area.",
                timestamp_start="00:04",
                timestamp_end="00:07",
                source_chunk_index=0,
                source_line_start=1,
                source_line_end=2,
                source_quote="repeated reaction area",
                transcript_anchors=[
                    TranscriptAnchor(
                        line_index=1,
                        text="A level is a repeated reaction area.",
                        timestamp_start="00:04",
                        timestamp_end="00:07",
                        match_source="llm_line_indices",
                    )
                ],
                timestamp_confidence="line",
                metadata={"chunk_index": 0},
            )
        ],
    )
    out = tmp_path / "knowledge_events.json"
    save_knowledge_events(collection, out)
    payload = json.loads(out.read_text(encoding="utf-8"))
    ev = payload["events"][0]
    assert ev["source_chunk_index"] == 0
    assert ev["source_line_start"] == 1
    assert ev["source_line_end"] == 2
    assert ev["source_quote"] == "repeated reaction area"
    assert ev["timestamp_confidence"] == "line"
    assert len(ev["transcript_anchors"]) == 1


def test_extraction_result_to_knowledge_events_emits_phase2a_fields() -> None:
    """Builder populates Phase 2A fields on KnowledgeEvent."""
    chunk = AdaptedChunk(
        lesson_id="L2",
        lesson_title=None,
        chunk_index=0,
        section=None,
        subsection=None,
        start_time_seconds=1.0,
        end_time_seconds=10.0,
        transcript_lines=[
            {"start_seconds": 1.0, "end_seconds": 3.0, "text": "Intro."},
            {"start_seconds": 3.0, "end_seconds": 5.0, "text": "A level forms after repeated reactions."},
        ],
        transcript_text="Intro.\nA level forms after repeated reactions.",
        visual_events=[],
    )
    extraction = ChunkExtractionResult(
        definitions=[
            ExtractedStatement(
                text="A level forms after repeated reactions.",
                source_line_indices=[1],
                source_quote="repeated reactions",
            )
        ]
    )
    events, rejected = extraction_result_to_knowledge_events(extraction, chunk)
    assert rejected == []
    ev = events[0]
    assert hasattr(ev, "source_chunk_index")
    assert hasattr(ev, "source_line_start")
    assert hasattr(ev, "source_line_end")
    assert hasattr(ev, "source_quote")
    assert hasattr(ev, "transcript_anchors")
    assert hasattr(ev, "timestamp_confidence")


def test_compact_explicit_anchor_gets_line_confidence() -> None:
    chunk = AdaptedChunk(
        lesson_id="L2",
        lesson_title=None,
        chunk_index=0,
        section=None,
        subsection=None,
        start_time_seconds=1.0,
        end_time_seconds=20.0,
        transcript_lines=[
            {"start_seconds": 1.0, "end_seconds": 3.0, "text": "Intro."},
            {"start_seconds": 3.0, "end_seconds": 5.0, "text": "A level forms after repeated reactions."},
            {"start_seconds": 5.0, "end_seconds": 7.0, "text": "That level becomes important for entries."},
        ],
        transcript_text="Intro.\nA level forms after repeated reactions.\nThat level becomes important for entries.",
        visual_events=[],
    )
    extraction = ChunkExtractionResult(
        definitions=[
            ExtractedStatement(
                text="A level forms after repeated reactions.",
                source_line_indices=[1, 2],
                source_quote="repeated reactions",
            )
        ]
    )
    events, rejected = extraction_result_to_knowledge_events(extraction, chunk)
    assert rejected == []
    ev = events[0]
    assert ev.timestamp_confidence == "line"
    assert ev.anchor_match_source == "llm_line_indices"
    assert ev.anchor_line_count == 2
    assert ev.anchor_span_width == 2
    assert ev.anchor_density == 1.0


def test_broader_local_anchor_gets_span_confidence() -> None:
    chunk = AdaptedChunk(
        lesson_id="L2",
        lesson_title=None,
        chunk_index=0,
        section=None,
        subsection=None,
        start_time_seconds=0.0,
        end_time_seconds=30.0,
        transcript_lines=[
            {"start_seconds": 0.0, "end_seconds": 2.0, "text": "L0"},
            {"start_seconds": 2.0, "end_seconds": 4.0, "text": "L1"},
            {"start_seconds": 4.0, "end_seconds": 6.0, "text": "L2"},
            {"start_seconds": 6.0, "end_seconds": 8.0, "text": "L3"},
            {"start_seconds": 8.0, "end_seconds": 10.0, "text": "L4"},
            {"start_seconds": 10.0, "end_seconds": 12.0, "text": "L5"},
        ],
        transcript_text="...",
        visual_events=[],
    )
    extraction = ChunkExtractionResult(
        process_steps=[
            ExtractedStatement(
                text="A process spans multiple nearby lines.",
                source_line_indices=[0, 1, 2, 3, 4, 5],
                source_quote="multiple nearby lines",
            )
        ]
    )
    events, rejected = extraction_result_to_knowledge_events(extraction, chunk)
    assert rejected == []
    ev = events[0]
    assert ev.timestamp_confidence == "span"
    assert ev.anchor_match_source == "llm_line_indices"
    assert ev.anchor_line_count == 6
    assert ev.anchor_span_width == 6


def test_sparse_anchor_downgrades_to_chunk() -> None:
    chunk = AdaptedChunk(
        lesson_id="L2",
        lesson_title=None,
        chunk_index=0,
        section=None,
        subsection=None,
        start_time_seconds=0.0,
        end_time_seconds=30.0,
        transcript_lines=[
            {"start_seconds": 0.0, "end_seconds": 2.0, "text": "L0"},
            {"start_seconds": 2.0, "end_seconds": 4.0, "text": "L1"},
            {"start_seconds": 4.0, "end_seconds": 6.0, "text": "L2"},
            {"start_seconds": 6.0, "end_seconds": 8.0, "text": "L3"},
            {"start_seconds": 8.0, "end_seconds": 10.0, "text": "L4"},
            {"start_seconds": 10.0, "end_seconds": 12.0, "text": "L5"},
            {"start_seconds": 12.0, "end_seconds": 14.0, "text": "L6"},
        ],
        transcript_text="...",
        visual_events=[],
    )
    extraction = ChunkExtractionResult(
        warnings=[
            ExtractedStatement(
                text="This warning is only loosely supported across the chunk.",
                source_line_indices=[0, 3, 6],
                source_quote="loosely supported",
            )
        ]
    )
    events, rejected = extraction_result_to_knowledge_events(extraction, chunk)
    assert rejected == []
    ev = events[0]
    assert ev.timestamp_confidence == "chunk"
    assert ev.anchor_match_source == "chunk_fallback"
    assert ev.source_line_start is None
    assert ev.source_line_end is None
    assert ev.transcript_anchors == []
    assert ev.anchor_line_count == 3


def test_save_knowledge_events_and_debug(tmp_path: Path) -> None:
    chunk = _sample_adapted_chunk()
    extraction = ChunkExtractionResult(
        definitions=[ExtractedStatement(text="One def.", concept="level", subconcept=None)],
        rule_statements=[],
        conditions=[],
        invalidations=[],
        exceptions=[],
        comparisons=[],
        warnings=[],
        process_steps=[],
        algorithm_hints=[],
        examples=[],
        global_notes=[],
    )
    events, _ = extraction_result_to_knowledge_events(extraction, chunk)
    collection = KnowledgeEventCollection(schema_version="1.0", lesson_id=chunk.lesson_id, events=events)
    ke_path = tmp_path / "knowledge_events.json"
    save_knowledge_events(collection, ke_path)
    assert ke_path.exists()
    loaded = json.loads(ke_path.read_text(encoding="utf-8"))
    assert loaded["lesson_id"] == chunk.lesson_id
    assert len(loaded["events"]) == 1

    save_knowledge_debug([{"chunk_index": 0, "error": None}], tmp_path / "knowledge_debug.json")
    assert (tmp_path / "knowledge_debug.json").exists()


def test_build_knowledge_events_from_file_uses_adapt_and_extract(tmp_path: Path) -> None:
    path = tmp_path / "chunks.json"
    path.write_text(json.dumps([_real_shape_chunk()], indent=2), encoding="utf-8")
    mock_client = MagicMock()
    mock_client.generate_extraction = MagicMock(return_value=json.dumps({
        "definitions": [],
        "rule_statements": [],
        "conditions": [],
        "invalidations": [],
        "exceptions": [],
        "comparisons": [],
        "warnings": [],
        "process_steps": [],
        "algorithm_hints": [],
        "examples": [],
        "global_notes": [],
    }))
    collection, debug_rows = build_knowledge_events_from_file(
        path, lesson_id="L2", lesson_title=None, llm_client=mock_client, debug=True
    )
    assert collection.lesson_id == "L2"
    assert mock_client.generate_extraction.called
    assert len(debug_rows) == 1
