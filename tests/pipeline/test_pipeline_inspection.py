"""Tests for Task 1: pipeline inspection and backward-compatible extension points."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pipeline.path_contracts import PipelineFeatureFlags, PipelinePaths
from pipeline.inspection import build_report, inspect_stages
from pipeline.component2.orchestrator import Component2RunConfig, prepare_component2_run
from pipeline.component2.main import run_component2_pipeline
from pipeline.component2.models import EnrichedMarkdownChunk


def test_inspect_stages_resolves_core_modules() -> None:
    """Stage inspection resolves main pipeline and Step 3 callables."""
    results = inspect_stages()
    by_id = {r.stage_id: r for r in results}

    core = [
        "step2_dense_analysis",
        "step3_invalidation_filter",
        "step3_parse_and_sync",
        "step3_markdown_llm",
        "step3_reducer",
    ]
    for stage_id in core:
        assert stage_id in by_id, f"Missing stage {stage_id}"
        r = by_id[stage_id]
        assert r.import_ok, f"{stage_id}: import failed: {r.notes}"
        assert r.callable_exists, f"{stage_id}: not callable: {r.notes}"


def test_pipeline_paths_matches_output_structure(tmp_path: Path) -> None:
    """Path contract matches current output_intermediate/ and output_rag_ready/ layout."""
    video_root = tmp_path / "data" / "test_video"
    paths = PipelinePaths(video_root=video_root)

    assert paths.output_intermediate_dir == video_root / "output_intermediate"
    assert paths.output_rag_ready_dir == video_root / "output_rag_ready"
    assert paths.filtered_visuals_path == video_root / "filtered_visual_events.json"
    assert paths.filtered_visuals_debug_path == video_root / "filtered_visual_events.debug.json"

    assert paths.lesson_chunks_path("Lesson 1") == video_root / "output_intermediate" / "Lesson 1.chunks.json"
    assert paths.knowledge_events_path("Lesson 1") == video_root / "output_intermediate" / "Lesson 1.knowledge_events.json"
    assert paths.knowledge_debug_path("Lesson 1") == video_root / "output_intermediate" / "Lesson 1.knowledge_debug.json"
    assert paths.rag_ready_markdown_path("Lesson 1") == video_root / "output_rag_ready" / "Lesson 1.md"


def test_preflight_report_generation(tmp_path: Path) -> None:
    """prepare_component2_run writes pipeline_inspection.json with expected keys."""
    config = Component2RunConfig(
        vtt_path=tmp_path / "dummy.vtt",
        visuals_json_path=tmp_path / "dense.json",
        output_root=tmp_path,
    )
    prepare_component2_run(config, "fake_lesson")

    report_path = tmp_path / "pipeline_inspection.json"
    assert report_path.is_file()

    data = json.loads(report_path.read_text(encoding="utf-8"))
    assert "stage_results" in data
    assert "artifact_results" in data
    assert "backward_compatible" in data
    assert "warnings" in data
    assert "video_root" in data

    assert isinstance(data["stage_results"], list)
    assert isinstance(data["artifact_results"], list)
    assert isinstance(data["backward_compatible"], bool)


def test_build_report_includes_artifact_checks(tmp_path: Path) -> None:
    """build_report with lesson_name includes lesson-specific artifact paths."""
    report = build_report(tmp_path, lesson_name="MyLesson")
    artifact_names = {a.artifact_name for a in report.artifact_results}

    assert "filtered_visual_events" in artifact_names
    assert "filtered_visual_events_debug" in artifact_names
    assert "lesson_chunks" in artifact_names
    assert "pass1_markdown" in artifact_names
    assert "llm_debug" in artifact_names
    assert "reducer_usage" in artifact_names
    assert "rag_ready_markdown" in artifact_names


def test_feature_flags_default_to_legacy() -> None:
    """All new feature flags default to legacy/disabled behavior."""
    flags = PipelineFeatureFlags()
    assert flags.preserve_legacy_markdown is True
    assert flags.enable_structured_outputs is False
    assert flags.enable_knowledge_events is False
    assert flags.enable_rule_cards is False
    assert flags.enable_evidence_index is False
    assert flags.enable_concept_graph is False


def test_run_component2_pipeline_creates_inspection_and_same_output_keys(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Preflight runs and run_component2_pipeline still returns the same output dict keys."""
    vtt_path = tmp_path / "lesson.vtt"
    visuals_path = tmp_path / "dense.json"
    vtt_path.write_text(
        "WEBVTT\n\n1\n00:00:01.000 --> 00:00:03.000\nHello.\n",
        encoding="utf-8",
    )
    visuals_path.write_text(
        json.dumps({
            "000001": {
                "frame_timestamp": "000001",
                "material_change": True,
                "visual_representation_type": "text_slide",
                "example_type": "conceptual_only",
                "change_summary": ["Slide"],
                "current_state": {},
                "extracted_entities": {},
            },
        }),
        encoding="utf-8",
    )

    async def fake_process_chunks(chunks, **kwargs):
        progress_callback = kwargs.get("progress_callback")
        if progress_callback is not None:
            for i, c in enumerate(chunks, start=1):
                progress_callback(i, len(chunks), c, 0.1)
        return [
            (
                c,
                EnrichedMarkdownChunk(synthesized_markdown="md", metadata_tags=[]),
                [{"provider": "gemini", "model": "gemini-2.5-flash", "attempt": 1, "status": "succeeded", "prompt_tokens": 1, "output_tokens": 1, "total_tokens": 2}],
            )
            for c in chunks
        ]

    def fake_synthesize(*args, **kwargs):
        return "# RAG\n\nContent.", [{"provider": "gemini", "model": "gemini-2.5-pro", "attempt": 1, "status": "succeeded", "prompt_tokens": 1, "output_tokens": 1, "total_tokens": 2}]

    monkeypatch.setattr("pipeline.component2.main.process_chunks", fake_process_chunks)
    monkeypatch.setattr("pipeline.component2.main.synthesize_full_document", fake_synthesize)

    outputs = run_component2_pipeline(
        vtt_path=vtt_path,
        visuals_json_path=visuals_path,
        output_root=tmp_path,
        progress_callback=None,
    )

    expected_keys = {
        "inspection_report_path",
        "filtered_events_path",
        "filtered_debug_path",
        "chunk_debug_path",
        "llm_debug_path",
        "reducer_usage_path",
        "intermediate_markdown_path",
        "rag_ready_markdown_path",
        "markdown_path",
    }
    assert set(outputs.keys()) == expected_keys

    inspection_path = tmp_path / "pipeline_inspection.json"
    assert inspection_path.is_file()
    data = json.loads(inspection_path.read_text(encoding="utf-8"))
    assert data.get("backward_compatible") is True
