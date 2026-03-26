"""Tests for pipeline path contracts, io_utils, and export manifest."""

from pathlib import Path

import pytest


def test_pipeline_paths_deterministic(tmp_path: Path) -> None:
    from pipeline.path_contracts import PipelinePaths

    paths = PipelinePaths(video_root=tmp_path)
    lesson = "Lesson 2. Levels part 1"

    assert paths.lesson_chunks_path(lesson).name == "Lesson 2. Levels part 1.chunks.json"
    assert paths.knowledge_events_path(lesson).name == "Lesson 2. Levels part 1.knowledge_events.json"
    assert paths.evidence_index_path(lesson).name == "Lesson 2. Levels part 1.evidence_index.json"
    assert paths.rule_cards_path(lesson).name == "Lesson 2. Levels part 1.rule_cards.json"
    assert paths.review_markdown_path(lesson).name == "Lesson 2. Levels part 1.review_markdown.md"
    assert paths.rag_ready_export_path(lesson).name == "Lesson 2. Levels part 1.rag_ready.md"


def test_ensure_output_dirs(tmp_path: Path) -> None:
    from pipeline.path_contracts import PipelinePaths

    paths = PipelinePaths(video_root=tmp_path)
    paths.ensure_output_dirs()

    assert paths.output_intermediate_dir.exists()
    assert paths.output_review_dir.exists()
    assert paths.output_rag_ready_dir.exists()


def test_legacy_and_new_rag_paths_do_not_conflict(tmp_path: Path) -> None:
    from pipeline.path_contracts import PipelinePaths

    paths = PipelinePaths(video_root=tmp_path)
    lesson = "abc"

    legacy = paths.rag_ready_markdown_path(lesson)
    new = paths.rag_ready_export_path(lesson)

    assert legacy != new
    assert legacy.name == "abc.md"
    assert new.name == "abc.rag_ready.md"


def test_batch_paths_are_deterministic(tmp_path: Path) -> None:
    from pipeline.path_contracts import PipelinePaths

    paths = PipelinePaths(video_root=tmp_path)

    assert paths.batch_root_dir().name == "batch"
    assert paths.batch_spool_dir("vision").name == "spool"
    assert paths.batch_spool_requests_path("vision", "frag").name == "frag.jsonl"
    assert paths.batch_spool_manifest_path("vision", "frag").name == "frag.manifest.json"
    assert paths.batch_results_dir("vision").name == "results"
    assert paths.batch_result_download_path("vision", "job1").name == "job1.jsonl"
    assert paths.batch_materialization_debug_path("vision").name == "materialization_debug.json"


def test_ensure_batch_dirs(tmp_path: Path) -> None:
    from pipeline.path_contracts import PipelinePaths

    paths = PipelinePaths(video_root=tmp_path)
    paths.ensure_batch_dirs("vision", "knowledge_extract")

    assert paths.batch_spool_dir("vision").exists()
    assert paths.batch_results_dir("vision").exists()
    assert paths.batch_spool_dir("knowledge_extract").exists()
    assert paths.batch_results_dir("knowledge_extract").exists()


def test_atomic_write_json(tmp_path: Path) -> None:
    from pipeline.io_utils import atomic_write_json

    path = tmp_path / "out" / "x.json"
    atomic_write_json(path, {"a": 1})

    assert path.exists()
    assert path.read_text(encoding="utf-8").strip().startswith("{")


def test_build_export_manifest_only_existing(tmp_path: Path) -> None:
    from pipeline.io_utils import build_export_manifest

    existing = tmp_path / "a.txt"
    existing.parent.mkdir(parents=True, exist_ok=True)
    existing.write_text("ok", encoding="utf-8")

    missing = tmp_path / "missing.txt"

    payload = build_export_manifest(
        lesson_id="lesson1",
        video_root=tmp_path,
        artifact_paths={"existing": existing, "missing": missing},
        flags={"enable_exporters": True},
    )

    assert "existing" in payload["artifacts"]
    assert "missing" not in payload["artifacts"]
