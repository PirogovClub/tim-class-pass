import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from pipeline.schemas import (
    EvidenceIndex,
    EvidenceRef,
    KnowledgeEvent,
    KnowledgeEventCollection,
    RuleCard,
    RuleCardCollection,
)
from pipeline.component2.llm_processor import (
    assemble_video_markdown,
    build_user_prompt,
    parse_enriched_markdown_chunk,
)
from pipeline.component2.knowledge_builder import (
    AdaptedChunk,
    ChunkExtractionResult,
    ExtractedStatement,
    build_knowledge_events_from_extraction_results,
    save_knowledge_events,
)
from pipeline.component2.main import main, run_component2_pipeline
from pipeline.component2.models import EnrichedMarkdownChunk, LessonChunk, TranscriptLine, VisualEvent
from pipeline.component2.parser import create_lesson_chunks
from pipeline.invalidation_filter import build_debug_report, filter_visual_events, is_valid_visual_event, load_dense_analysis

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _sample_json_path() -> Path:
    return (
        _REPO_ROOT
        / "data"
        / "Lesson 2. Levels part 1"
        / "batches"
        / "dense_batch_response_000063-000258.json"
    )


def test_filter_visual_events_sample_json_uses_instructional_frames_only() -> None:
    sample_path = _sample_json_path()
    if not sample_path.is_file():
        pytest.skip("sample dense batch response fixture is not present in this workspace state")

    raw = load_dense_analysis(sample_path)

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
    reducer_calls: list[dict] = []

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
                [
                    {
                        "provider": "gemini",
                        "model": "gemini-2.5-flash",
                        "attempt": 1,
                        "status": "succeeded",
                        "prompt_tokens": 12,
                        "output_tokens": 5,
                        "total_tokens": 17,
                    }
                ],
            )
            for chunk in chunks
        ]

    monkeypatch.setattr("pipeline.component2.main.process_chunks", fake_process_chunks)
    def fake_synthesize_full_document(raw_markdown, **kwargs):
        reducer_calls.append(kwargs)
        return (
            "---\ntags:\n  - Trend Break Level\n---\n\n# lesson\n\n## Topic\n- **Rule 1:** Use the level.\n",
            [
                {
                    "provider": "gemini",
                    "model": "gemini-2.5-pro",
                    "attempt": 1,
                    "status": "succeeded",
                    "prompt_tokens": 30,
                    "output_tokens": 9,
                    "total_tokens": 39,
                }
            ],
        )

    monkeypatch.setattr("pipeline.component2.main.synthesize_full_document", fake_synthesize_full_document)

    outputs = run_component2_pipeline(
        vtt_path=vtt_path,
        visuals_json_path=visuals_json_path,
        output_root=lesson_dir,
        reducer_model="gemini-2.5-pro",
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
    llm_debug = json.loads(outputs["llm_debug_path"].read_text(encoding="utf-8"))
    reducer_usage = json.loads(outputs["reducer_usage_path"].read_text(encoding="utf-8"))
    assert "# lesson" in intermediate_markdown
    assert "Chunk 0 markdown" in intermediate_markdown
    assert "**Tags:** Trend Break Level" in intermediate_markdown
    assert rag_ready_markdown.startswith("---")
    assert "## Topic" in rag_ready_markdown
    assert llm_debug[0]["request_usage"][0]["total_tokens"] == 17
    assert reducer_usage[0]["total_tokens"] == 39
    assert reducer_calls[0]["model"] == "gemini-2.5-pro"
    assert any("Step 3.1/5" in message for message in progress_messages)
    assert any("Chunk 1/1 complete" in message and "chunk_time=0.2s" in message for message in progress_messages)
    assert any("Step 3.5/5 complete" in message for message in progress_messages)


def test_component2_main_help() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])

    assert result.exit_code == 0
    assert "Run the standalone Component 2 + Step 3 markdown synthesis pipeline." in result.output
    assert "--visuals-json" in result.output
    assert "--reducer-model" in result.output


# ----- Phase 2A: knowledge_events.json preserves line anchors -----


def test_pipeline_written_knowledge_events_contains_phase2a_fields() -> None:
    """Saved knowledge_events.json from a pipeline run contains Phase 2A fields (run after full Component 2)."""
    root = _REPO_ROOT / "data" / "Lesson 2. Levels part 1" / "output_intermediate"
    ke_path = root / "Lesson 2. Levels part 1.knowledge_events.json"
    if not ke_path.is_file():
        pytest.skip("knowledge_events.json not found; run Component 2 for Lesson 2 first")
    payload = json.loads(ke_path.read_text(encoding="utf-8"))
    assert payload.get("events"), "knowledge_events.json is empty"
    first = payload["events"][0]
    assert "timestamp_confidence" in first
    assert "transcript_anchors" in first


def test_pipeline_outputs_not_all_events_are_line_confidence() -> None:
    """Pipeline output has a mix of line/span/chunk confidence (run after full Component 2)."""
    root = _REPO_ROOT / "data" / "Lesson 2. Levels part 1" / "output_intermediate"
    ke_path = root / "Lesson 2. Levels part 1.knowledge_events.json"
    if not ke_path.is_file():
        pytest.skip("knowledge_events.json not found; run Component 2 for Lesson 2 first")
    collection = KnowledgeEventCollection.model_validate_json(ke_path.read_text(encoding="utf-8"))
    confidences = [ev.timestamp_confidence for ev in collection.events]
    assert "line" in confidences
    assert any(c in {"span", "chunk"} for c in confidences)


def test_knowledge_events_json_preserves_line_anchors(tmp_path: Path) -> None:
    """Build collection with source_line_indices, save to knowledge_events.json, assert line-anchored event."""
    chunk = AdaptedChunk(
        lesson_id="L2",
        lesson_title=None,
        chunk_index=0,
        section=None,
        subsection=None,
        start_time_seconds=1.0,
        end_time_seconds=20.0,
        transcript_lines=[
            {"start_seconds": 1.0, "end_seconds": 4.0, "text": "Intro."},
            {"start_seconds": 4.0, "end_seconds": 8.0, "text": "A level forms after repeated reactions."},
            {"start_seconds": 8.0, "end_seconds": 12.0, "text": "This level becomes important."},
        ],
        transcript_text="Intro.\nA level forms after repeated reactions.\nThis level becomes important.",
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
    collection, _ = build_knowledge_events_from_extraction_results(
        [chunk], [extraction], lesson_id="L2", lesson_title=None
    )
    ke_path = tmp_path / "knowledge_events.json"
    save_knowledge_events(collection, ke_path)
    data = json.loads(ke_path.read_text(encoding="utf-8"))
    events = data.get("events", [])
    assert len(events) >= 1
    line_anchored = [e for e in events if e.get("timestamp_confidence") == "line"]
    assert len(line_anchored) >= 1
    ev = line_anchored[0]
    assert ev.get("source_line_start") is not None
    assert ev.get("source_line_end") is not None
    assert len(ev.get("transcript_anchors", [])) > 0


# ----- 03-phase1: final saved knowledge has evidence_refs, evidence has linked_rule_ids -----


def test_final_saved_knowledge_events_contain_evidence_refs_after_evidence_linking(
    monkeypatch, tmp_path: Path
) -> None:
    """After evidence linking, backfill overwrites knowledge_events.json with evidence_refs populated."""
    lesson_dir = tmp_path / "lesson"
    lesson_dir.mkdir()
    vtt_path = lesson_dir / "lesson.vtt"
    visuals_path = lesson_dir / "dense.json"
    vtt_path.write_text(
        "WEBVTT\n\n1\n00:00:01.000 --> 00:00:03.000\nFirst.\n\n",
        encoding="utf-8",
    )
    visuals_path.write_text(
        json.dumps(
            {
                "000001": {
                    "frame_timestamp": "000001",
                    "material_change": True,
                    "visual_representation_type": "annotated_chart",
                    "example_type": "abstract_teaching_example",
                    "change_summary": ["Chart"],
                    "current_state": {},
                    "extracted_entities": {},
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    def fake_build_knowledge(adapted, extraction_results, lesson_id, lesson_title):
        event = KnowledgeEvent(
            lesson_id=lesson_id,
            event_id="ke1",
            event_type="rule_statement",
            raw_text="A rule.",
            normalized_text="A rule.",
            metadata={"chunk_index": 0},
        )
        return (KnowledgeEventCollection(lesson_id=lesson_id, events=[event]), [])

    def fake_build_evidence(*, lesson_id, **kwargs):
        ref = EvidenceRef(
            lesson_id=lesson_id,
            evidence_id="ev1",
            frame_ids=["001"],
            source_event_ids=["ke1"],
        )
        return (EvidenceIndex(lesson_id=lesson_id, evidence_refs=[ref]), [])

    async def fake_knowledge_extract(adapted, **kwargs):
        return [(c, {}, []) for c in adapted]

    monkeypatch.setattr(
        "pipeline.component2.main.build_knowledge_events_from_extraction_results",
        fake_build_knowledge,
    )
    monkeypatch.setattr("pipeline.component2.main.build_evidence_index", fake_build_evidence)
    monkeypatch.setattr("pipeline.component2.main.process_chunks_knowledge_extract", fake_knowledge_extract)

    from pipeline.component2.main import run_component2_pipeline

    run_component2_pipeline(
        vtt_path=vtt_path,
        visuals_json_path=visuals_path,
        output_root=lesson_dir,
        enable_knowledge_events=True,
        enable_evidence_linking=True,
    )

    ke_path = lesson_dir / "output_intermediate" / "lesson.knowledge_events.json"
    assert ke_path.exists()
    data = json.loads(ke_path.read_text(encoding="utf-8"))
    events = data.get("events", [])
    assert len(events) >= 1
    ke1 = next((e for e in events if e.get("event_id") == "ke1"), None)
    assert ke1 is not None
    assert ke1.get("evidence_refs") == ["ev1"]


def test_final_saved_evidence_contains_linked_rule_ids_after_rule_build(
    monkeypatch, tmp_path: Path
) -> None:
    """After rule cards are built, backfill overwrites evidence_index.json with linked_rule_ids populated."""
    lesson_dir = tmp_path / "lesson"
    lesson_dir.mkdir()
    vtt_path = lesson_dir / "lesson.vtt"
    visuals_path = lesson_dir / "dense.json"
    vtt_path.write_text(
        "WEBVTT\n\n1\n00:00:01.000 --> 00:00:03.000\nFirst.\n\n",
        encoding="utf-8",
    )
    visuals_path.write_text(
        json.dumps(
            {
                "000001": {
                    "frame_timestamp": "000001",
                    "material_change": True,
                    "visual_representation_type": "annotated_chart",
                    "example_type": "abstract_teaching_example",
                    "change_summary": ["Chart"],
                    "current_state": {},
                    "extracted_entities": {},
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    def fake_build_knowledge(adapted, extraction_results, lesson_id, lesson_title):
        event = KnowledgeEvent(
            lesson_id=lesson_id,
            event_id="ke1",
            event_type="rule_statement",
            raw_text="A rule.",
            normalized_text="A rule.",
            metadata={"chunk_index": 0},
        )
        return (KnowledgeEventCollection(lesson_id=lesson_id, events=[event]), [])

    def fake_build_evidence(*, lesson_id, **kwargs):
        ref = EvidenceRef(
            lesson_id=lesson_id,
            evidence_id="ev1",
            frame_ids=["001"],
            source_event_ids=["ke1"],
        )
        return (EvidenceIndex(lesson_id=lesson_id, evidence_refs=[ref]), [])

    def fake_build_rule_cards(*, knowledge_collection, evidence_index, **kwargs):
        rule = RuleCard(
            lesson_id=knowledge_collection.lesson_id,
            rule_id="r1",
            concept="level",
            rule_text="A valid rule.",
            source_event_ids=["ke1"],
            evidence_refs=["ev1"],
        )
        return (RuleCardCollection(lesson_id=knowledge_collection.lesson_id, rules=[rule]), [])

    async def fake_knowledge_extract(adapted, **kwargs):
        return [(c, {}, []) for c in adapted]

    monkeypatch.setattr(
        "pipeline.component2.main.build_knowledge_events_from_extraction_results",
        fake_build_knowledge,
    )
    monkeypatch.setattr("pipeline.component2.main.build_evidence_index", fake_build_evidence)
    monkeypatch.setattr("pipeline.component2.main.build_rule_cards", fake_build_rule_cards)
    monkeypatch.setattr("pipeline.component2.main.process_chunks_knowledge_extract", fake_knowledge_extract)

    from pipeline.component2.main import run_component2_pipeline

    run_component2_pipeline(
        vtt_path=vtt_path,
        visuals_json_path=visuals_path,
        output_root=lesson_dir,
        enable_knowledge_events=True,
        enable_evidence_linking=True,
        enable_rule_cards=True,
    )

    ei_path = lesson_dir / "output_intermediate" / "lesson.evidence_index.json"
    assert ei_path.exists()
    data = json.loads(ei_path.read_text(encoding="utf-8"))
    refs = data.get("evidence_refs", [])
    assert len(refs) >= 1
    ev1 = next((r for r in refs if r.get("evidence_id") == "ev1"), None)
    assert ev1 is not None
    assert ev1.get("linked_rule_ids") == ["r1"]
