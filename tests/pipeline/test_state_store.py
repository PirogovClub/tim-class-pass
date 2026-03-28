from __future__ import annotations

from pathlib import Path

from pipeline.orchestrator.models import REQUEST_PARSE_STATUS_FAILED, REQUEST_PARSE_STATUS_PARSED
from pipeline.orchestrator.state_store import StateStore


def test_state_store_initializes_schema_and_upserts(tmp_path: Path) -> None:
    db_path = tmp_path / "state.db"
    store = StateStore(db_path)

    store.ensure_video(video_id="vid1", video_root=tmp_path / "vid1", title="Video 1")
    store.ensure_video(video_id="vid1", video_root=tmp_path / "vid1", title="Video 1")
    store.ensure_lesson(
        lesson_id="vid1::lesson1",
        video_id="vid1",
        lesson_name="lesson1",
        lesson_root=tmp_path / "vid1",
        vtt_path=tmp_path / "vid1" / "lesson1.vtt",
    )

    assert db_path.exists()
    videos = store.list_videos()
    lessons = store.list_lessons()
    assert len(videos) == 1
    assert len(lessons) == 1


def test_create_or_reuse_stage_run_and_force_new_attempt(tmp_path: Path) -> None:
    store = StateStore(tmp_path / "state.db")
    store.ensure_video(video_id="vid1", video_root=tmp_path / "vid1")
    store.ensure_lesson(
        lesson_id="vid1::lesson1",
        video_id="vid1",
        lesson_name="lesson1",
        lesson_root=tmp_path / "vid1",
    )

    first = store.create_or_reuse_stage_run(
        lesson_id="vid1::lesson1",
        stage_name="knowledge_extract",
    )
    reused = store.create_or_reuse_stage_run(
        lesson_id="vid1::lesson1",
        stage_name="knowledge_extract",
    )
    second = store.create_or_reuse_stage_run(
        lesson_id="vid1::lesson1",
        stage_name="knowledge_extract",
        force_new_attempt=True,
    )

    assert first["stage_run_id"] == reused["stage_run_id"]
    assert second["attempt"] == first["attempt"] + 1


def test_record_spool_request_and_mark_statuses(tmp_path: Path) -> None:
    store = StateStore(tmp_path / "state.db")
    store.ensure_video(video_id="vid1", video_root=tmp_path / "vid1")
    store.ensure_lesson(
        lesson_id="vid1::lesson1",
        video_id="vid1",
        lesson_name="lesson1",
        lesson_root=tmp_path / "vid1",
    )
    stage_run = store.create_or_reuse_stage_run(
        lesson_id="vid1::lesson1",
        stage_name="vision",
    )

    store.record_spool_request(
        request_key="vid1__lesson1__vision__frame__001",
        stage_run_id=stage_run["stage_run_id"],
        video_id="vid1",
        lesson_id="vid1::lesson1",
        stage_name="vision",
        entity_kind="frame",
        entity_index="001",
        payload_sha256="abc",
        spool_file_path=tmp_path / "spool.jsonl",
    )
    parsed = store.mark_request_parsed(
        "vid1__lesson1__vision__frame__001",
        output_path=tmp_path / "frame_001.json",
    )
    failed = store.mark_request_failed(
        "vid1__lesson1__vision__frame__001",
        "boom",
    )

    assert parsed["parse_status"] == REQUEST_PARSE_STATUS_PARSED
    assert failed["parse_status"] == REQUEST_PARSE_STATUS_FAILED


def test_summarize_status_reports_counts(tmp_path: Path) -> None:
    store = StateStore(tmp_path / "state.db")
    store.ensure_video(video_id="vid1", video_root=tmp_path / "vid1")
    summary = store.summarize_status()
    assert summary["videos"]["PENDING"] == 1
