import json
from pathlib import Path

from helpers.usage_report import build_video_usage_summary, write_video_usage_summary


def test_build_video_usage_summary_collects_records(tmp_path: Path) -> None:
    video_dir = tmp_path / "data" / "video"
    intermediate_dir = video_dir / "output_intermediate"
    intermediate_dir.mkdir(parents=True)

    (video_dir / "dense_analysis.json").write_text(
        json.dumps(
            {
                "000001": {
                    "material_change": True,
                    "request_usage": [
                        {
                            "provider": "openai",
                            "model": "gpt-4o",
                            "attempt": 1,
                            "status": "succeeded",
                            "prompt_tokens": 11,
                            "output_tokens": 4,
                            "total_tokens": 15,
                        }
                    ],
                }
            }
        ),
        encoding="utf-8",
    )
    (intermediate_dir / "lesson.llm_debug.json").write_text(
        json.dumps(
            [
                {
                    "chunk_index": 0,
                    "request_usage": [
                        {
                            "provider": "gemini",
                            "model": "gemini-2.5-flash",
                            "attempt": 1,
                            "status": "succeeded",
                            "prompt_tokens": 20,
                            "output_tokens": 10,
                            "total_tokens": 30,
                        }
                    ],
                }
            ]
        ),
        encoding="utf-8",
    )
    (intermediate_dir / "lesson.reducer_usage.json").write_text(
        json.dumps(
            [
                {
                    "provider": "gemini",
                    "model": "gemini-2.5-pro",
                    "attempt": 1,
                    "status": "succeeded",
                    "prompt_tokens": 40,
                    "output_tokens": 12,
                    "total_tokens": 52,
                }
            ]
        ),
        encoding="utf-8",
    )

    summary = build_video_usage_summary(video_dir)

    assert summary["totals"]["request_count"] == 3
    assert summary["totals"]["total_tokens"] == 97
    assert summary["by_provider"]["gemini"]["total_tokens"] == 82
    assert summary["by_provider"]["openai"]["total_tokens"] == 15


def test_write_video_usage_summary_writes_default_file(tmp_path: Path) -> None:
    video_dir = tmp_path / "data" / "video"
    video_dir.mkdir(parents=True)
    (video_dir / "dense_analysis.json").write_text("{}", encoding="utf-8")

    destination = write_video_usage_summary(video_dir)

    assert destination == video_dir / "ai_usage_summary.json"
    assert destination.is_file()
