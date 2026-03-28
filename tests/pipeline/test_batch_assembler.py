from __future__ import annotations

import json
from pathlib import Path

from helpers.clients.gemini_batch_client import write_jsonl_lines
from pipeline.orchestrator.batch_assembler import assemble_batch_files
from pipeline.orchestrator.state_store import StateStore


def _seed_ready_fragment(
    *,
    store: StateStore,
    root: Path,
    lesson_id: str,
    video_id: str,
    lesson_name: str,
    fragment_name: str,
    request_key: str,
) -> None:
    store.ensure_video(video_id=video_id, video_root=root)
    store.ensure_lesson(
        lesson_id=lesson_id,
        video_id=video_id,
        lesson_name=lesson_name,
        lesson_root=root,
    )
    stage_run = store.create_or_reuse_stage_run(
        lesson_id=lesson_id,
        stage_name="knowledge_extract",
        status="READY",
    )
    spool_path = root / f"{fragment_name}.jsonl"
    manifest_path = root / f"{fragment_name}.manifest.json"
    write_jsonl_lines(
        spool_path,
        [
            {
                "key": request_key,
                "request": {"contents": [{"role": "user", "parts": [{"text": fragment_name}]}]},
            }
        ],
    )
    manifest_path.write_text(
        json.dumps(
            {
                "lesson_id": lesson_id,
                "provider": "gemini",
                "model": "gemini-2.5-flash-lite",
                "stage_name": "knowledge_extract",
                "spool_file_path": str(spool_path),
                "request_count": 1,
                "request_keys": [request_key],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    store.update_stage_run(stage_run["stage_run_id"], request_manifest_path=manifest_path)
    store.record_spool_request(
        request_key=request_key,
        stage_run_id=stage_run["stage_run_id"],
        video_id=video_id,
        lesson_id=lesson_id,
        stage_name="knowledge_extract",
        entity_kind="chunk",
        entity_index="0",
        payload_sha256=fragment_name,
        spool_file_path=spool_path,
    )


def test_assemble_batch_files_combines_compatible_fragments(tmp_path: Path) -> None:
    store = StateStore(tmp_path / "state.db")
    _seed_ready_fragment(
        store=store,
        root=tmp_path / "a",
        lesson_id="vid1::lesson1",
        video_id="vid1",
        lesson_name="lesson1",
        fragment_name="frag_a",
        request_key="vid1__lesson1__knowledge_extract__chunk__0",
    )
    _seed_ready_fragment(
        store=store,
        root=tmp_path / "b",
        lesson_id="vid2::lesson2",
        video_id="vid2",
        lesson_name="lesson2",
        fragment_name="frag_b",
        request_key="vid2__lesson2__knowledge_extract__chunk__0",
    )

    paths = assemble_batch_files(store, "knowledge_extract", batches_root=tmp_path / "batches")

    assert len(paths) == 1
    assembled_rows = [json.loads(line) for line in paths[0].read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(assembled_rows) == 2
    batch_jobs = store.list_batch_jobs(stage_name="knowledge_extract")
    assert len(batch_jobs) == 1
    assert batch_jobs[0]["request_count"] == 2
