from __future__ import annotations

import json
from pathlib import Path

from pipeline.dense_analyzer import (
    emit_batch_spool_for_analysis,
    materialize_batch_results_for_analysis,
)
from pipeline.orchestrator.state_store import StateStore


def test_dense_analyzer_batch_emit_and_materialize(tmp_path: Path) -> None:
    video_root = tmp_path / "video"
    frames_dir = video_root / "frames_dense"
    frames_dir.mkdir(parents=True, exist_ok=True)
    (frames_dir / "frame_000001.jpg").write_bytes(b"fake-jpeg")

    store = StateStore(tmp_path / "state.db")
    store.ensure_video(video_id="video1", video_root=video_root)
    store.ensure_lesson(
        lesson_id="video1::lesson1",
        video_id="video1",
        lesson_name="lesson1",
        lesson_root=video_root,
    )

    spool_path = emit_batch_spool_for_analysis(
        video_root=video_root,
        lesson_context={"lesson_id": "video1::lesson1", "lesson_name": "lesson1", "video_id": "video1"},
        queue_keys=["000001"],
        frames_dir=frames_dir,
        config={},
        state_store=store,
    )
    rows = [json.loads(line) for line in spool_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == 1
    assert rows[0]["key"] == "video1__lesson1__vision__frame__000001"

    result_path = tmp_path / "result.jsonl"
    result_path.write_text(
        json.dumps(
            {
                "key": rows[0]["key"],
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
        + "\n",
        encoding="utf-8",
    )

    analysis = materialize_batch_results_for_analysis(
        result_path,
        video_root=video_root,
        lesson_context={"lesson_id": "video1::lesson1", "lesson_name": "lesson1", "video_id": "video1"},
        frames_dir=frames_dir,
        state_store=store,
    )

    assert "000001" in analysis
    assert (video_root / "dense_analysis.json").exists()
    assert (frames_dir / "frame_000001.json").exists()
