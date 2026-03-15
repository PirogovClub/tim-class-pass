"""Tests for pipeline.component2.llm_processor. No real API calls; uses mocks."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pipeline.component2.knowledge_builder import AdaptedChunk, ChunkExtractionResult
from pipeline.component2.llm_processor import (
    MarkdownRenderResult,
    assemble_legacy_video_markdown,
    assemble_video_markdown,
    build_knowledge_extract_prompt,
    build_legacy_markdown_prompt,
    build_markdown_render_prompt,
    legacy_debug_rows,
    parse_knowledge_extraction,
    parse_legacy_enriched_markdown_chunk,
    process_chunk,
    process_chunk_knowledge_extract,
    process_chunk_legacy_markdown,
    process_chunks,
    process_chunks_legacy_markdown,
    process_rule_cards_markdown_render,
    write_llm_debug,
    _call_provider_for_mode,
)
from pipeline.component2.models import (
    EnrichedMarkdownChunk,
    LessonChunk,
    TranscriptLine,
    VisualEvent,
)
from pipeline.schemas import EvidenceRef, RuleCard


# ----- 1. build_legacy_markdown_prompt -----


def test_build_legacy_markdown_prompt_produces_expected_structure() -> None:
    chunk = LessonChunk(
        chunk_index=0,
        start_time_seconds=0.0,
        end_time_seconds=60.0,
        transcript_lines=[
            TranscriptLine(start_seconds=0.0, end_seconds=5.0, text="Hello"),
            TranscriptLine(start_seconds=6.0, end_seconds=10.0, text="World"),
        ],
        visual_events=[
            VisualEvent(
                timestamp_seconds=30,
                frame_key="f30",
                visual_representation_type="chart",
                example_type="example",
                change_summary=["change"],
                current_state={},
                extracted_entities={},
            ),
        ],
        previous_visual_state=None,
    )
    result = build_legacy_markdown_prompt(chunk)
    assert "<previous_visual_state>" in result
    assert "<transcript>" in result
    assert "<visual_events>" in result


# ----- 2. build_knowledge_extract_prompt -----


def test_build_knowledge_extract_prompt_contains_transcript_and_visuals() -> None:
    result = build_knowledge_extract_prompt(
        lesson_id="L1",
        chunk_index=0,
        section=None,
        transcript_text="Some text",
        visual_summaries=["v1", "v2"],
        concept_context=None,
    )
    assert "Some text" in result
    assert "v1" in result or "v2" in result
    assert "literal-scribe" not in result.lower()
    assert "Literal Scribe" not in result


def test_build_knowledge_extract_prompt_renders_numbered_transcript_lines() -> None:
    chunk_lines = [
        TranscriptLine(start_seconds=1.0, end_seconds=3.0, text="Price reacts from the level."),
        TranscriptLine(start_seconds=3.0, end_seconds=5.0, text="Then it returns below the level."),
    ]
    prompt = build_knowledge_extract_prompt(
        lesson_id="L2",
        chunk_index=0,
        transcript_text="ignored when transcript_lines exist",
        transcript_lines=chunk_lines,
        visual_summaries=["Annotated chart with level"],
        start_time_seconds=1.0,
        end_time_seconds=5.0,
    )
    assert "[L0 00:01-00:03] Price reacts from the level." in prompt
    assert "[L1 00:03-00:05] Then it returns below the level." in prompt


def test_parse_knowledge_extraction_accepts_source_line_indices_and_source_quote() -> None:
    payload = """
    {
      "definitions": [
        {
          "text": "A level is a price area of repeated reaction.",
          "concept": "level",
          "subconcept": null,
          "source_type": "explicit",
          "ambiguity_notes": [],
          "source_line_indices": [0, 1],
          "source_quote": "price reacts from the same area several times"
        }
      ],
      "rule_statements": [],
      "conditions": [],
      "invalidations": [],
      "exceptions": [],
      "comparisons": [],
      "warnings": [],
      "process_steps": [],
      "algorithm_hints": [],
      "examples": [],
      "global_notes": []
    }
    """
    parsed = parse_knowledge_extraction(payload)
    assert parsed.definitions[0].source_line_indices == [0, 1]
    assert parsed.definitions[0].source_quote is not None


# ----- 3. build_markdown_render_prompt -----


def test_build_markdown_render_prompt_uses_rule_cards_and_evidence() -> None:
    rule = RuleCard(
        lesson_id="L1",
        rule_id="r1",
        concept="levels",
        rule_text="Test rule text here",
    )
    evidence = EvidenceRef(
        lesson_id="L1",
        evidence_id="e1",
        compact_visual_summary="Evidence summary",
    )
    result = build_markdown_render_prompt(
        lesson_id="L1",
        lesson_title="Title",
        rule_cards=[rule],
        evidence_refs=[evidence],
        render_mode="review",
    )
    assert "Test rule text here" in result or "rule_text" in result
    assert "e1" in result or "evidence_id" in result or "Evidence summary" in result
    assert "<transcript>" not in result
    assert "chunk replay" not in result.lower()


# ----- 4. _call_provider_for_mode -----


def test_call_provider_for_mode_returns_parsed_and_usage() -> None:
    mock_response = MagicMock()
    mock_response.text = '{"markdown":"x","metadata_tags":[]}'
    mock_response.usage_records = [{"tokens": 1}]
    mock_provider = MagicMock()
    mock_provider.generate_text.return_value = mock_response

    with patch(
        "pipeline.component2.llm_processor.get_provider",
        return_value=mock_provider,
    ):
        result = _call_provider_for_mode(
            mode="markdown_render",
            user_text="u",
            response_schema=MarkdownRenderResult,
            system_instruction="s",
        )
    assert isinstance(result, tuple)
    assert len(result) == 2
    assert isinstance(result[0], MarkdownRenderResult)
    assert result[0].markdown == "x"
    assert result[0].metadata_tags == []
    assert result[1] == [{"tokens": 1}]


# ----- 5. process_chunk_knowledge_extract -----


def test_process_chunk_knowledge_extract_returns_chunk_extraction_result() -> None:
    chunk = AdaptedChunk(
        chunk_index=0,
        lesson_id="L1",
        lesson_title=None,
        section=None,
        subsection=None,
        start_time_seconds=0.0,
        end_time_seconds=60.0,
        transcript_text="Some transcript",
        visual_events=[],
    )
    parsed = ChunkExtractionResult(definitions=[], rule_statements=[])
    usage = [{"tokens": 10}]

    with patch(
        "pipeline.component2.llm_processor._call_provider_for_mode",
        return_value=(parsed, usage),
    ):
        result = asyncio.run(process_chunk_knowledge_extract(chunk))

    assert isinstance(result, tuple)
    assert isinstance(result[0], ChunkExtractionResult)
    assert isinstance(result[1], list)
    assert result[1] == usage


# ----- 6. process_rule_cards_markdown_render -----


def test_process_rule_cards_markdown_render_returns_markdown_render_result() -> None:
    parsed = MarkdownRenderResult(markdown="# Rendered", metadata_tags=["tag1"])
    usage = [{"tokens": 5}]

    with patch(
        "pipeline.component2.llm_processor._call_provider_for_mode",
        return_value=(parsed, usage),
    ):
        result = process_rule_cards_markdown_render(
            lesson_id="L1",
            rule_cards=[],
            evidence_refs=[],
            render_mode="review",
        )

    assert isinstance(result, tuple)
    assert result[0].markdown == "# Rendered"
    assert result[0].metadata_tags == ["tag1"]
    assert result[1] == usage


# ----- 7. parse_legacy_enriched_markdown_chunk -----


def test_parse_legacy_enriched_markdown_chunk() -> None:
    payload = json.dumps({
        "synthesized_markdown": "## Section\n\nContent here.",
        "metadata_tags": ["level", "breakout"],
    })
    result = parse_legacy_enriched_markdown_chunk(payload)
    assert isinstance(result, EnrichedMarkdownChunk)
    assert result.synthesized_markdown == "## Section\n\nContent here."
    assert result.metadata_tags == ["level", "breakout"]


# ----- 8. write_llm_debug and legacy_debug_rows -----


def test_write_llm_debug_writes_rows(tmp_path: Path) -> None:
    rows = [
        {"chunk_index": 0, "result": {"a": 1}, "request_usage": []},
    ]
    out_path = tmp_path / "out.json"
    write_llm_debug(out_path, rows)
    assert out_path.exists()
    content = json.loads(out_path.read_text(encoding="utf-8"))
    assert content == rows


def test_write_llm_debug_legacy_debug_rows(tmp_path: Path) -> None:
    chunk = LessonChunk(
        chunk_index=1,
        start_time_seconds=60.0,
        end_time_seconds=120.0,
        transcript_lines=[],
        visual_events=[],
        previous_visual_state=None,
    )
    enriched = EnrichedMarkdownChunk(
        synthesized_markdown="**Chunk 1**",
        metadata_tags=["tag"],
    )
    usage = [{"tokens": 2}]
    processed_chunks = [(chunk, enriched, usage)]
    rows = legacy_debug_rows(processed_chunks)
    out_path = tmp_path / "legacy_debug.json"
    write_llm_debug(out_path, rows)
    assert out_path.exists()
    content = json.loads(out_path.read_text(encoding="utf-8"))
    assert len(content) == 1
    assert content[0]["chunk_index"] == 1
    assert "result" in content[0]
    assert content[0]["result"].get("synthesized_markdown") == "**Chunk 1**"
    assert content[0]["result"].get("metadata_tags") == ["tag"]
    assert content[0]["request_usage"] == usage


# ----- 9. Backward compatibility aliases -----


def test_backward_compatibility_process_chunks_alias() -> None:
    assert process_chunks is process_chunks_legacy_markdown
    assert process_chunk is process_chunk_legacy_markdown
    assert assemble_video_markdown is assemble_legacy_video_markdown
