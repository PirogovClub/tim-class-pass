import json
from pathlib import Path

from click.testing import CliRunner

from pipeline.component2.llm_processor import (
    assemble_video_markdown,
    build_user_prompt,
    parse_enriched_markdown_chunk,
)
from pipeline.component2.main import main, run_component2_pipeline
from pipeline.component2.models import EnrichedMarkdownChunk, LessonChunk, TranscriptLine, VisualEvent
from pipeline.component2.parser import create_lesson_chunks
from pipeline.invalidation_filter import build_debug_report, filter_visual_events, is_valid_visual_event, load_dense_analysis


def _sample_json_path() -> Path:
    return (
        Path(__file__).resolve().parents[1]
        / "data"
        / "Lesson 2. Levels part 1"
        / "batches"
        / "dense_batch_response_000063-000258.json"
    )


def test_filter_visual_events_sample_json_uses_instructional_frames_only() -> None:
    raw = load_dense_analysis(_sample_json_path())

    events = filter_visual_events(raw)
    kept_keys = {event.frame_key for event in events}

    assert "000063" not in kept_keys
    assert "000085" not in kept_keys
    assert "000250" not in kept_keys
    assert "000083" in kept_keys
    assert "000084" in kept_keys
    assert "000088" in kept_keys
    assert "000249" in kept_keys
    assert all(event.visual_representation_type.lower() != "unknown" for event in events)
    assert [event.timestamp_seconds for event in events] == sorted(event.timestamp_seconds for event in events)

    report = build_debug_report(raw, events)
    assert report["rejected_frame_keys"]["000063"] == "unknown_visual_type_without_instructional_signal"
    assert report["rejected_frame_keys"]["000128"] == "no_material_change"


def test_create_lesson_chunks_carries_previous_visual_state() -> None:
    transcript_lines = [
        TranscriptLine(start_seconds=0.0, end_seconds=25.0, text="Первый блок без конца"),
        TranscriptLine(start_seconds=25.1, end_seconds=65.0, text="Первый блок завершен."),
        TranscriptLine(start_seconds=130.0, end_seconds=135.0, text="Второй блок завершен."),
    ]
    visual_events = [
        VisualEvent(
            timestamp_seconds=15,
            frame_key="000015",
            visual_representation_type="abstract_bar_diagram",
            example_type="abstract_teaching_example",
            change_summary=["First diagram appears"],
            current_state={"diagram": "A"},
            extracted_entities={},
        ),
        VisualEvent(
            timestamp_seconds=132,
            frame_key="000132",
            visual_representation_type="text_slide",
            example_type="conceptual_only",
            change_summary=["Definition slide appears"],
            current_state={"diagram": "B"},
            extracted_entities={},
        ),
    ]

    chunks = create_lesson_chunks(
        transcript_lines,
        visual_events,
        target_duration_seconds=60.0,
    )

    assert len(chunks) == 2
    assert chunks[0].previous_visual_state is None
    assert chunks[0].visual_events[0].frame_key == "000015"
    assert chunks[1].previous_visual_state == {"diagram": "A"}
    assert chunks[1].visual_events[0].frame_key == "000132"


def test_invalidation_filter_keeps_unknown_frame_with_annotation_signal() -> None:
    entry = {
        "frame_timestamp": "000010",
        "material_change": True,
        "visual_representation_type": "unknown",
        "change_summary": ["A red X annotation appears near the level"],
        "current_state": {
            "visible_annotations": [{"text": "X", "location": "top-right", "language": "symbol"}],
        },
        "extracted_entities": {},
    }

    assert is_valid_visual_event(entry) is True


def test_build_user_prompt_contains_xml_sections_and_timestamps() -> None:
    chunk = LessonChunk(
        chunk_index=0,
        start_time_seconds=0.0,
        end_time_seconds=10.0,
        transcript_lines=[
            TranscriptLine(start_seconds=5.0, end_seconds=6.0, text="Итак, первый уровень."),
        ],
        visual_events=[
            VisualEvent(
                timestamp_seconds=8,
                frame_key="000008",
                visual_representation_type="abstract_bar_diagram",
                example_type="abstract_teaching_example",
                change_summary=["Level diagram appears"],
                current_state={"level": "trend break"},
                extracted_entities={"pattern_terms": ["Уровень излома тренда"]},
            )
        ],
        previous_visual_state={"previous": "state"},
    )

    prompt = build_user_prompt(chunk)

    assert "<previous_visual_state>" in prompt
    assert "<transcript>" in prompt
    assert "<visual_events>" in prompt
    assert "[00:05] Итак, первый уровень." in prompt
    assert "timestamp: 00:08" in prompt
    assert "abstract_teaching_example" in prompt


def test_parse_enriched_markdown_chunk_validates_json() -> None:
    payload = json.dumps(
        {
            "synthesized_markdown": "Translated text\n\n**[00:08]** > [*Abstract Teaching Example*: Level test.]",
            "metadata_tags": ["Trend Break Level", "Intraday trading"],
        }
    )
    result = parse_enriched_markdown_chunk(payload)

    assert result.synthesized_markdown.startswith("Translated text")
    assert result.metadata_tags == ["Trend Break Level", "Intraday trading"]


def test_assemble_video_markdown_adds_header_and_tags() -> None:
    chunk = LessonChunk(
        chunk_index=0,
        start_time_seconds=0.0,
        end_time_seconds=10.0,
        transcript_lines=[],
        visual_events=[],
        previous_visual_state=None,
    )
    enriched = EnrichedMarkdownChunk(
        synthesized_markdown="English section",
        metadata_tags=["Trend Break Level"],
    )

    markdown = assemble_video_markdown("Lesson 2", [(chunk, enriched)])

    assert markdown.startswith("# Lesson 2")
    assert "**Tags:** Trend Break Level" in markdown


def test_run_component2_pipeline_writes_outputs(monkeypatch, tmp_path: Path) -> None:
    lesson_dir = tmp_path / "lesson"
    lesson_dir.mkdir()
    vtt_path = lesson_dir / "lesson.vtt"
    visuals_json_path = lesson_dir / "dense.json"

    vtt_path.write_text(
        "WEBVTT\n\n"
        "1\n"
        "00:00:01.000 --> 00:00:03.000\n"
        "Итак, первый уровень.\n\n"
        "2\n"
        "00:00:04.000 --> 00:00:06.000\n"
        "Это точка излома тренда.\n",
        encoding="utf-8",
    )
    visuals_json_path.write_text(
        json.dumps(
            {
                "000001": {
                    "frame_timestamp": "000001",
                    "material_change": True,
                    "visual_representation_type": "abstract_bar_diagram",
                    "example_type": "abstract_teaching_example",
                    "change_summary": ["Diagram appears"],
                    "current_state": {"diagram": "A"},
                    "extracted_entities": {"pattern_terms": ["Уровень излома тренда"]},
                },
                "000002": {
                    "frame_timestamp": "000002",
                    "material_change": False,
                    "visual_representation_type": "unknown",
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    progress_messages: list[str] = []

    async def fake_process_chunks(chunks, **kwargs):
        progress_callback = kwargs.get("progress_callback")
        total = len(chunks)
        if progress_callback is not None:
            for index, chunk in enumerate(chunks, start=1):
                progress_callback(index, total, chunk, 0.25)
        return [
            (
                chunk,
                EnrichedMarkdownChunk(
                    synthesized_markdown=f"Chunk {chunk.chunk_index} markdown",
                    metadata_tags=["Trend Break Level"],
                ),
            )
            for chunk in chunks
        ]

    monkeypatch.setattr("pipeline.component2.main.process_chunks", fake_process_chunks)
    monkeypatch.setattr(
        "pipeline.component2.main.synthesize_full_document",
        lambda raw_markdown, **kwargs: "---\ntags:\n  - Trend Break Level\n---\n\n# lesson\n\n## Topic\n- **Rule 1:** Use the level.\n",
    )

    outputs = run_component2_pipeline(
        vtt_path=vtt_path,
        visuals_json_path=visuals_json_path,
        output_root=lesson_dir,
        target_duration_seconds=30.0,
        progress_callback=progress_messages.append,
    )

    assert outputs["filtered_events_path"].is_file()
    assert outputs["chunk_debug_path"].is_file()
    assert outputs["llm_debug_path"].is_file()
    assert outputs["intermediate_markdown_path"].is_file()
    assert outputs["rag_ready_markdown_path"].is_file()
    assert outputs["markdown_path"] == outputs["rag_ready_markdown_path"]

    intermediate_markdown = outputs["intermediate_markdown_path"].read_text(encoding="utf-8")
    rag_ready_markdown = outputs["rag_ready_markdown_path"].read_text(encoding="utf-8")
    assert "# lesson" in intermediate_markdown
    assert "Chunk 0 markdown" in intermediate_markdown
    assert "**Tags:** Trend Break Level" in intermediate_markdown
    assert rag_ready_markdown.startswith("---")
    assert "## Topic" in rag_ready_markdown
    assert any("[+00:00] Step 3.1/5" in message for message in progress_messages)
    assert any("Chunk 1/1 complete" in message and "chunk_time=0.2s" in message for message in progress_messages)
    assert any("Step 3.5/5 complete" in message for message in progress_messages)


def test_component2_main_help() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])

    assert result.exit_code == 0
    assert "Run the standalone Component 2 + Step 3 markdown synthesis pipeline." in result.output
    assert "--visuals-json" in result.output
