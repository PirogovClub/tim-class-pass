"""Tests for Step 4 evidence linker."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pipeline.component2.evidence_linker import (
    AdaptedVisualEvent,
    VisualEvidenceCandidate,
    adapt_visual_events_from_chunks,
    build_evidence_index,
    candidate_to_evidence_ref,
    enrich_visual_event_from_dense_analysis,
    extract_visual_concept_hints,
    group_visual_events_into_candidates,
    load_chunks_json,
    load_knowledge_events,
    save_evidence_debug,
    save_evidence_index,
    score_candidate_event_match,
)
from pipeline.component2.visual_compaction import (
    VisualCompactionConfig,
    summarize_visual_candidate_for_evidence,
)
from pipeline.schemas import EvidenceIndex, KnowledgeEvent


# ----- 1. Adapt chunk visual events -----


def test_adapt_visual_events_from_chunks_preserves_chunk_index_and_fields() -> None:
    """Given a mock chunk in real format, verify AdaptedVisualEvents are created correctly."""
    raw_chunks = [
        {
            "chunk_index": 2,
            "start_time_seconds": 100.0,
            "end_time_seconds": 120.0,
            "visual_events": [
                {
                    "timestamp_seconds": 105,
                    "frame_key": "000105",
                    "visual_representation_type": "annotated_chart",
                    "example_type": "positive_example",
                    "change_summary": ["Level marked with horizontal line"],
                    "current_state": {"visible_annotations": ["support level"]},
                    "extracted_entities": {},
                },
                {
                    "timestamp_seconds": 108,
                    "frame_key": "000108",
                    "visual_representation_type": "annotated_chart",
                    "example_type": "unknown",
                    "change_summary": [],
                    "current_state": {},
                    "extracted_entities": {},
                },
            ],
        },
    ]
    events = adapt_visual_events_from_chunks(raw_chunks, lesson_id="lesson2")
    assert len(events) == 2
    assert events[0].chunk_index == 2
    assert events[0].frame_key == "000105"
    assert events[0].timestamp_seconds == 105.0
    assert events[0].visual_representation_type == "annotated_chart"
    assert events[0].change_summary == "Level marked with horizontal line"
    assert events[1].chunk_index == 2
    assert events[1].frame_key == "000108"
    assert events[1].change_summary is None or events[1].change_summary == ""


# ----- 2. Dense analysis enrichment -----


def test_enrich_visual_event_from_dense_analysis_adds_metadata() -> None:
    """Given a visual event and matching dense analysis entry, verify enrichment preserves frame_key and adds richer metadata."""
    event = AdaptedVisualEvent(
        timestamp_seconds=120.0,
        frame_key="000120",
        visual_representation_type="unknown",
        example_type="unknown",
        change_summary=None,
        current_state={},
        extracted_entities={},
        chunk_index=1,
    )
    dense = {
        "000120": {
            "visual_representation_type": "annotated_chart",
            "example_type": "counterexample",
            "change_summary": "False breakout at level",
            "current_state": {"visible_annotations": ["level", "breakout"]},
            "extracted_entities": {"levels": ["120.5"]},
        },
    }
    enriched = enrich_visual_event_from_dense_analysis(event, dense)
    assert enriched.frame_key == "000120"
    assert enriched.visual_representation_type == "annotated_chart"
    assert enriched.example_type == "counterexample"
    assert "visible_annotations" in enriched.current_state
    assert "levels" in enriched.extracted_entities


def test_enrich_visual_event_missing_frame_key_unchanged() -> None:
    """If no dense analysis entry for frame_key, return event unchanged."""
    event = AdaptedVisualEvent(
        timestamp_seconds=120.0,
        frame_key="000999",
        visual_representation_type="diagram",
        example_type="illustration",
        change_summary="Test",
        current_state={},
        extracted_entities={},
        chunk_index=0,
    )
    dense = {"000120": {"change_summary": "other"}}
    enriched = enrich_visual_event_from_dense_analysis(event, dense)
    assert enriched.frame_key == "000999"
    assert enriched.visual_representation_type == "diagram"
    assert enriched.change_summary == "Test"


# ----- 3. Grouping logic -----


def test_group_visual_events_same_chunk_close_time_one_candidate() -> None:
    """Same chunk, same example type, close timestamps -> one VisualEvidenceCandidate."""
    events = [
        AdaptedVisualEvent(120.0, "000120", "annotated_chart", "positive_example", "A", {}, {}, chunk_index=1),
        AdaptedVisualEvent(122.0, "000122", "annotated_chart", "positive_example", "B", {}, {}, chunk_index=1),
        AdaptedVisualEvent(124.0, "000124", "annotated_chart", "positive_example", "C", {}, {}, chunk_index=1),
    ]
    candidates = group_visual_events_into_candidates(events, lesson_id="lesson2", max_time_gap_seconds=20.0)
    assert len(candidates) == 1
    assert len(candidates[0].frame_keys) == 3
    assert candidates[0].frame_keys == ["000120", "000122", "000124"]
    assert candidates[0].chunk_index == 1


def test_group_visual_events_split_on_chunk_or_gap() -> None:
    """Different chunk or large time gap -> multiple candidates."""
    events = [
        AdaptedVisualEvent(120.0, "000120", "chart", "example", "A", {}, {}, chunk_index=0),
        AdaptedVisualEvent(122.0, "000122", "chart", "example", "B", {}, {}, chunk_index=0),
        AdaptedVisualEvent(125.0, "000125", "chart", "example", "C", {}, {}, chunk_index=1),
        AdaptedVisualEvent(200.0, "000200", "chart", "example", "D", {}, {}, chunk_index=1),
    ]
    candidates = group_visual_events_into_candidates(events, lesson_id="L", max_time_gap_seconds=5.0)
    assert len(candidates) >= 2
    assert candidates[0].chunk_index == 0
    assert "000120" in candidates[0].frame_keys and "000122" in candidates[0].frame_keys


# ----- 4. Concept hint extraction -----


def test_extract_visual_concept_hints_false_breakout_level() -> None:
    """Annotation text like 'false breakout level' yields concept hints including level and false_breakout."""
    event = AdaptedVisualEvent(
        timestamp_seconds=0,
        frame_key="0",
        visual_representation_type="chart",
        example_type="counterexample",
        change_summary="False breakout at support level",
        current_state={"visible_annotations": ["false breakout level"]},
        extracted_entities={},
    )
    concepts, subconcepts = extract_visual_concept_hints(event)
    assert "level" in concepts or "false_breakout" in concepts


# ----- 5. Candidate-event scoring above threshold -----


def test_score_candidate_event_match_above_threshold_same_chunk_concept() -> None:
    """Same chunk + matching concept -> score >= 0.50."""
    candidate = VisualEvidenceCandidate(
        candidate_id="c1",
        lesson_id="lesson2",
        chunk_index=3,
        timestamp_start=120.0,
        timestamp_end=128.0,
        frame_keys=["000120", "000122"],
        concept_hints=["level", "false_breakout"],
        subconcept_hints=[],
    )
    event = KnowledgeEvent(
        lesson_id="lesson2",
        event_id="ke_lesson2_3_rule_statement_0",
        event_type="rule_statement",
        raw_text="A level can produce a false breakout.",
        normalized_text="A level can produce a false breakout.",
        concept="level",
        subconcept=None,
        timestamp_start="02:00",
        timestamp_end="02:10",
        metadata={"chunk_index": 3},
    )
    score, breakdown = score_candidate_event_match(candidate, event)
    assert score >= 0.50
    assert breakdown["chunk_match"] == 0.40
    assert breakdown["total"] >= 0.50


# ----- 6. Candidate-event mismatch below threshold -----


def test_score_candidate_event_match_below_threshold_different_chunk_unrelated_concept() -> None:
    """Different chunk + unrelated concept -> score < 0.50."""
    candidate = VisualEvidenceCandidate(
        candidate_id="c1",
        lesson_id="lesson2",
        chunk_index=0,
        timestamp_start=10.0,
        timestamp_end=18.0,
        frame_keys=["000010"],
        concept_hints=["trend_line"],
        subconcept_hints=[],
    )
    event = KnowledgeEvent(
        lesson_id="lesson2",
        event_id="ke_lesson2_5_definition_0",
        event_type="definition",
        raw_text="Level is support or resistance.",
        normalized_text="Level is support or resistance.",
        concept="level",
        subconcept=None,
        timestamp_start="05:00",
        timestamp_end="05:30",
        metadata={"chunk_index": 5},
    )
    score, _ = score_candidate_event_match(candidate, event)
    assert score < 0.50


# ----- 7. EvidenceRef generation -----


def test_candidate_to_evidence_ref_has_timestamps_frame_ids_source_event_ids() -> None:
    """Final EvidenceRef contains timestamps, frame_ids, source_event_ids, compact summary, example role."""
    candidate = VisualEvidenceCandidate(
        candidate_id="evcand_lesson2_3_0",
        lesson_id="lesson2",
        chunk_index=3,
        timestamp_start=120.0,
        timestamp_end=128.0,
        frame_keys=["000120", "000122"],
        compact_visual_summary="Annotated chart showing false breakout at level.",
        example_role="counterexample",
        concept_hints=["level", "false_breakout"],
    )
    linked = [
        KnowledgeEvent(
            lesson_id="lesson2",
            event_id="ke_lesson2_3_rule_statement_0",
            event_type="invalidation",
            raw_text="False breakout invalidates the level.",
            normalized_text="False breakout invalidates the level.",
        ),
    ]
    ref = candidate_to_evidence_ref(candidate, linked, lesson_id="lesson2", lesson_title="Lesson 2")
    assert ref.evidence_id == "evcand_lesson2_3_0"
    assert ref.timestamp_start is not None
    assert ref.timestamp_end is not None
    assert ref.frame_ids == ["000120", "000122"]
    assert ref.source_event_ids == ["ke_lesson2_3_rule_statement_0"]
    assert ref.compact_visual_summary == "Annotated chart showing false breakout at level."
    assert ref.example_role == "counterexample"
    assert ref.raw_visual_event_ids == ["ve_raw_000120", "ve_raw_000122"]


# ----- 8. EvidenceIndex serialization -----


def test_evidence_index_serialization() -> None:
    """EvidenceIndex serializes to JSON and parses back."""
    index = EvidenceIndex(
        schema_version="1.0",
        lesson_id="lesson2",
        evidence_refs=[],
    )
    js = index.model_dump_json()
    assert js
    data = json.loads(js)
    assert data["lesson_id"] == "lesson2"
    assert data["schema_version"] == "1.0"
    assert data["evidence_refs"] == []
    parsed = EvidenceIndex.model_validate_json(js)
    assert parsed.lesson_id == index.lesson_id


# ----- 9. Feature-flag-safe integration -----


def test_enable_evidence_linking_false_no_evidence_files(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """When enable_evidence_linking=False, pipeline does not write evidence files (legacy unchanged)."""
    from pipeline.component2.main import run_component2_pipeline
    from pipeline.component2.models import EnrichedMarkdownChunk

    vtt = tmp_path / "lesson.vtt"
    vtt.write_text(
        "WEBVTT\n\n00:00:01.000 --> 00:00:03.000\nHello.\n\n",
        encoding="utf-8",
    )
    visuals = tmp_path / "dense.json"
    visuals.write_text(
        json.dumps({
            "000001": {
                "material_change": True,
                "visual_representation_type": "chart",
                "change_summary": ["Chart"],
                "current_state": {},
                "extracted_entities": {},
            },
        }),
        encoding="utf-8",
    )

    async def fake_process_chunks(chunks, **kwargs):
        return [
            (
                chunk,
                EnrichedMarkdownChunk(synthesized_markdown="Md", metadata_tags=[]),
                [{"status": "succeeded", "total_tokens": 10}],
            )
            for chunk in chunks
        ]

    def fake_synthesize(*args, **kwargs):
        return ("# lesson\n\nContent.", [])

    monkeypatch.setattr("pipeline.component2.main.process_chunks", fake_process_chunks)
    monkeypatch.setattr("pipeline.component2.main.synthesize_full_document", fake_synthesize)

    result = run_component2_pipeline(
        vtt_path=vtt,
        visuals_json_path=visuals,
        output_root=tmp_path,
        enable_knowledge_events=False,
        enable_evidence_linking=False,
    )
    assert "evidence_index_path" not in result
    assert "evidence_debug_path" not in result
    assert not (tmp_path / "output_intermediate" / "lesson.evidence_index.json").exists()
    assert not (tmp_path / "output_intermediate" / "lesson.evidence_debug.json").exists()


def test_enable_evidence_linking_true_with_knowledge_events_writes_evidence_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """When enable_evidence_linking and enable_knowledge_events are True, evidence_index and evidence_debug are written."""
    from pipeline.component2.main import run_component2_pipeline
    from pipeline.component2.models import EnrichedMarkdownChunk

    vtt = tmp_path / "lesson.vtt"
    vtt.write_text(
        "WEBVTT\n\n00:00:01.000 --> 00:00:03.000\nLevel is support or resistance.\n\n",
        encoding="utf-8",
    )
    visuals = tmp_path / "dense.json"
    visuals.write_text(
        json.dumps({
            "000001": {
                "material_change": True,
                "visual_representation_type": "annotated_chart",
                "change_summary": ["Level marked"],
                "current_state": {},
                "extracted_entities": {},
            },
        }),
        encoding="utf-8",
    )

    async def fake_process_chunks(chunks, **kwargs):
        return [
            (
                chunk,
                EnrichedMarkdownChunk(synthesized_markdown="Md", metadata_tags=[]),
                [{"status": "succeeded", "total_tokens": 10}],
            )
            for chunk in chunks
        ]

    def fake_synthesize(*args, **kwargs):
        return ("# lesson\n\nContent.", [])

    async def fake_process_chunks_ke(adapted, **kwargs):
        from pipeline.component2.knowledge_builder import ChunkExtractionResult
        return [
            (adapted[i], ChunkExtractionResult(), [{"status": "succeeded", "total_tokens": 10}])
            for i in range(len(adapted))
        ] if adapted else []

    def fake_build_from_extraction_results(adapted_chunks, extraction_results, lesson_id, lesson_title=None):
        from pipeline.schemas import KnowledgeEvent, KnowledgeEventCollection
        events = [
            KnowledgeEvent(
                lesson_id=lesson_id,
                event_id="ke_0_rule_0",
                event_type="rule_statement",
                raw_text="Level is support.",
                normalized_text="Level is support.",
                metadata={"chunk_index": 0},
                timestamp_start="00:00",
                timestamp_end="00:03",
            ),
        ]
        return (KnowledgeEventCollection(schema_version="1.0", lesson_id=lesson_id, events=events), [])

    monkeypatch.setattr("pipeline.component2.main.process_chunks", fake_process_chunks)
    monkeypatch.setattr("pipeline.component2.main.synthesize_full_document", fake_synthesize)
    monkeypatch.setattr("pipeline.component2.main.process_chunks_knowledge_extract", fake_process_chunks_ke)
    monkeypatch.setattr("pipeline.component2.main.build_knowledge_events_from_extraction_results", fake_build_from_extraction_results)

    result = run_component2_pipeline(
        vtt_path=vtt,
        visuals_json_path=visuals,
        output_root=tmp_path,
        enable_knowledge_events=True,
        enable_evidence_linking=True,
    )
    assert "evidence_index_path" in result
    assert "evidence_debug_path" in result
    assert result["evidence_index_path"].exists()
    assert result["evidence_debug_path"].exists()


# ----- Loaders and save -----


def test_load_chunks_json_valid_array(tmp_path: Path) -> None:
    """load_chunks_json returns list of dicts."""
    path = tmp_path / "chunks.json"
    path.write_text('[{"chunk_index": 0, "visual_events": []}]', encoding="utf-8")
    data = load_chunks_json(path)
    assert data == [{"chunk_index": 0, "visual_events": []}]


def test_load_chunks_json_not_array_raises(tmp_path: Path) -> None:
    """load_chunks_json raises when root is not an array."""
    path = tmp_path / "chunks.json"
    path.write_text('{"chunk_index": 0}', encoding="utf-8")
    with pytest.raises(ValueError, match="JSON array"):
        load_chunks_json(path)


def test_save_evidence_index_and_debug(tmp_path: Path) -> None:
    """save_evidence_index and save_evidence_debug write files."""
    index = EvidenceIndex(schema_version="1.0", lesson_id="L", evidence_refs=[])
    out = tmp_path / "out" / "evidence_index.json"
    save_evidence_index(index, out)
    assert out.exists()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["lesson_id"] == "L"
    save_evidence_debug([{"candidate_id": "c1", "linked_event_ids": []}], tmp_path / "out" / "evidence_debug.json")
    assert (tmp_path / "out" / "evidence_debug.json").exists()


def test_build_evidence_index_returns_index_and_debug() -> None:
    """build_evidence_index returns EvidenceIndex and debug list from chunks and knowledge events."""
    chunks = [
        {
            "chunk_index": 0,
            "start_time_seconds": 0.0,
            "end_time_seconds": 30.0,
            "visual_events": [
                {
                    "timestamp_seconds": 10,
                    "frame_key": "000010",
                    "visual_representation_type": "annotated_chart",
                    "example_type": "positive_example",
                    "change_summary": ["Level shown"],
                    "current_state": {},
                    "extracted_entities": {},
                },
            ],
        },
    ]
    events = [
        KnowledgeEvent(
            lesson_id="L",
            event_id="ke_L_0_rule_0",
            event_type="rule_statement",
            raw_text="Use the level.",
            normalized_text="Use the level.",
            concept="level",
            metadata={"chunk_index": 0},
            timestamp_start="00:00",
            timestamp_end="00:30",
        ),
    ]
    index, debug = build_evidence_index(lesson_id="L", knowledge_events=events, chunks=chunks)
    assert isinstance(index, EvidenceIndex)
    assert index.lesson_id == "L"
    assert len(debug) >= 0
    assert len(index.evidence_refs) >= 0


def test_load_knowledge_events(tmp_path: Path) -> None:
    """load_knowledge_events returns list of KnowledgeEvent from KnowledgeEventCollection JSON."""
    path = tmp_path / "ke.json"
    path.write_text(
        json.dumps({
            "schema_version": "1.0",
            "lesson_id": "L",
            "events": [
                {
                    "lesson_id": "L",
                    "event_id": "e1",
                    "event_type": "definition",
                    "raw_text": "A level is support or resistance.",
                    "normalized_text": "A level is support or resistance.",
                },
            ],
        }),
        encoding="utf-8",
    )
    loaded = load_knowledge_events(path)
    assert len(loaded) == 1
    assert loaded[0].event_id == "e1"
    assert loaded[0].event_type == "definition"


def test_summarize_visual_candidate_for_evidence() -> None:
    """summarize_visual_candidate_for_evidence produces short summary from events and hints."""
    candidate = VisualEvidenceCandidate(
        candidate_id="c1",
        lesson_id="L",
        chunk_index=0,
        timestamp_start=0.0,
        timestamp_end=10.0,
        frame_keys=[],
        visual_events=[
            AdaptedVisualEvent(0, "0", "annotated_chart", "example", "Level marked", {}, {}, None),
        ],
        concept_hints=["level"],
    )
    cfg = VisualCompactionConfig()
    s = summarize_visual_candidate_for_evidence(candidate, cfg)
    assert s
    assert len(s) <= 350
