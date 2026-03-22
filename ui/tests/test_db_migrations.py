from __future__ import annotations

import sqlite3
from pathlib import Path

from ui.storage import UIStateStore


def test_fresh_db_initialization_creates_latest_schema(tmp_path: Path):
    db_path = tmp_path / "ui_state.db"

    store = UIStateStore(db_path)

    assert store.schema_version() >= 2
    with store.connect() as conn:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(runs)").fetchall()}
    assert "current_stage" in columns
    assert "pipeline_db_path" in columns
    assert "cancel_requested_at" in columns


def test_existing_db_upgrades_with_added_run_fields(tmp_path: Path):
    db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE projects (
            project_id TEXT PRIMARY KEY,
            slug TEXT NOT NULL,
            title TEXT NOT NULL,
            lesson_name TEXT NOT NULL,
            project_root TEXT NOT NULL,
            source_video_path TEXT,
            transcript_path TEXT,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE runs (
            run_id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            run_mode TEXT NOT NULL,
            status TEXT NOT NULL,
            log_path TEXT,
            remote_job_name TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """
    )
    conn.commit()
    conn.close()

    store = UIStateStore(db_path)

    with store.connect() as connection:
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(runs)").fetchall()}
    assert "run_kind" in columns
    assert "current_stage" in columns
    assert "project_root_snapshot" in columns

