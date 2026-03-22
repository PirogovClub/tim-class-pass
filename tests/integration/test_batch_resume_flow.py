from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from pipeline.batch_cli import (
    run_assemble,
    run_discover,
    run_download,
    run_materialize,
    run_plan,
    run_poll,
    run_spool,
    run_submit,
)


def _seed_video_root(root: Path) -> Path:
    lesson_root = root / "Lesson 1"
    lesson_root.mkdir(parents=True, exist_ok=True)
    (lesson_root / "Lesson 1.vtt").write_text("WEBVTT\n", encoding="utf-8")
    (lesson_root / "frames_dense").mkdir(parents=True, exist_ok=True)
    llm_queue = lesson_root / "llm_queue"
    llm_queue.mkdir(parents=True, exist_ok=True)
    (llm_queue / "frame_000001.jpg").write_bytes(b"fake")
    (llm_queue / "manifest.json").write_text(
        json.dumps(
            {"items": {"000001": {"source": "llm_queue/frame_000001.jpg"}}},
            indent=2,
        ),
        encoding="utf-8",
    )
    return lesson_root


@pytest.mark.integration
def test_batch_resume_flow_for_vision(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    data_root = tmp_path / "data"
    lesson_root = _seed_video_root(data_root)
    db_path = tmp_path / "state.db"

    run_discover(data_root=data_root, db_path=db_path)
    run_plan(db_path=db_path)
    assert run_spool(stage="vision", db_path=db_path) == 1
    assembled_paths = run_assemble(stage="vision", db_path=db_path)
    assert len(assembled_paths) == 1

    assembled_rows = [json.loads(line) for line in assembled_paths[0].read_text(encoding="utf-8").splitlines() if line.strip()]
    request_key = assembled_rows[0]["key"]

    monkeypatch.setattr(
        "pipeline.orchestrator.run_manager.gemini_batch_client.upload_jsonl",
        lambda path, display_name: SimpleNamespace(name=f"uploaded:{display_name}"),
    )
    monkeypatch.setattr(
        "pipeline.orchestrator.run_manager.gemini_batch_client.create_batch_job",
        lambda **kwargs: SimpleNamespace(name="remote-job-1"),
    )
    monkeypatch.setattr(
        "pipeline.orchestrator.run_manager.gemini_batch_client.get_batch_job",
        lambda name: SimpleNamespace(
            state=SimpleNamespace(name="JOB_STATE_SUCCEEDED"),
            dest=SimpleNamespace(file_name="remote-results-1"),
        ),
    )
    monkeypatch.setattr(
        "pipeline.orchestrator.run_manager.gemini_batch_client.download_result_file",
        lambda file_name: (
            json.dumps(
                {
                    "key": request_key,
                    "response": {
                        "candidates": [
                            {
                                "content": {
                                    "parts": [
                                        {
                                            "text": json.dumps(
                                                {
                                                    "frame_timestamp": "00:00:01",
                                                    "material_change": True,
                                                    "visual_representation_type": "text_slide",
                                                    "change_summary": ["slide appears"],
                                                    "current_state": {},
                                                    "extracted_entities": {},
                                                }
                                            )
                                        }
                                    ]
                                }
                            }
                        ]
                    },
                }
            )
            + "\n"
        ).encode("utf-8"),
    )

    assert len(run_submit(stage="vision", db_path=db_path, max_batches=3)) == 1
    polled = run_poll(db_path=db_path)
    assert list(polled.values()) == ["SUCCEEDED"]
    downloaded = run_download(db_path=db_path)
    assert len(downloaded) == 1
    assert run_materialize(stage="vision", db_path=db_path) == 1
    assert (lesson_root / "dense_analysis.json").exists()

    # Rerun should stay safe and keep produced output.
    assert run_materialize(stage="vision", db_path=db_path) >= 1
