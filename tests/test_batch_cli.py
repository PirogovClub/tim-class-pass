from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from pipeline.batch_cli import main


def _seed_video_root(root: Path) -> Path:
    lesson_root = root / "Lesson 1"
    lesson_root.mkdir(parents=True, exist_ok=True)
    (lesson_root / "Lesson 1.vtt").write_text("WEBVTT\n", encoding="utf-8")
    llm_queue = lesson_root / "llm_queue"
    llm_queue.mkdir(parents=True, exist_ok=True)
    (llm_queue / "frame_000001.jpg").write_bytes(b"fake")
    (llm_queue / "manifest.json").write_text(
        json.dumps(
            {
                "items": {
                    "000001": {
                        "source": "llm_queue/frame_000001.jpg",
                    }
                }
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return lesson_root


def test_batch_cli_help() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "discover" in result.output
    assert "retry-failed" in result.output


def test_batch_cli_discover_plan_status(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    _seed_video_root(data_root)
    db_path = tmp_path / "state.db"
    runner = CliRunner()

    discover_result = runner.invoke(main, ["--db-path", str(db_path), "discover", "--data-root", str(data_root)])
    plan_result = runner.invoke(main, ["--db-path", str(db_path), "plan"])
    status_result = runner.invoke(main, ["--db-path", str(db_path), "status"])

    assert discover_result.exit_code == 0
    assert plan_result.exit_code == 0
    assert status_result.exit_code == 0
    assert "Discovered videos=1 lessons=1" in discover_result.output
    assert "vision" in plan_result.output
    assert "Stage runs" in status_result.output


def test_batch_cli_spool_and_assemble_vision(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    _seed_video_root(data_root)
    db_path = tmp_path / "state.db"
    runner = CliRunner()

    runner.invoke(main, ["--db-path", str(db_path), "discover", "--data-root", str(data_root)])
    runner.invoke(main, ["--db-path", str(db_path), "plan"])
    spool_result = runner.invoke(main, ["--db-path", str(db_path), "spool", "--stage", "vision"])
    assemble_result = runner.invoke(main, ["--db-path", str(db_path), "assemble", "--stage", "vision"])

    assert spool_result.exit_code == 0
    assert assemble_result.exit_code == 0
    assert "Spooled 1 lesson fragment" in spool_result.output
    assert "Assembled 1 batch file" in assemble_result.output
