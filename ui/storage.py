from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from pipeline.orchestrator.models import utc_now_iso


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}


class UIStateStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _initialize(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS projects (
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

                CREATE INDEX IF NOT EXISTS idx_projects_slug ON projects(slug);
                CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);
                CREATE INDEX IF NOT EXISTS idx_projects_updated_at ON projects(updated_at);

                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    run_mode TEXT NOT NULL,
                    status TEXT NOT NULL,
                    log_path TEXT,
                    remote_job_name TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(project_id) REFERENCES projects(project_id)
                );

                CREATE INDEX IF NOT EXISTS idx_runs_project_id ON runs(project_id);
                CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status);
                CREATE INDEX IF NOT EXISTS idx_runs_updated_at ON runs(updated_at);
                """
            )

    def upsert_project(
        self,
        *,
        project_id: str,
        slug: str,
        title: str,
        lesson_name: str,
        project_root: str | Path,
        source_video_path: str | Path | None,
        transcript_path: str | Path | None,
        status: str,
    ) -> dict[str, Any]:
        now = utc_now_iso()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO projects(
                    project_id, slug, title, lesson_name, project_root,
                    source_video_path, transcript_path, status, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(project_id) DO UPDATE SET
                    slug = excluded.slug,
                    title = excluded.title,
                    lesson_name = excluded.lesson_name,
                    project_root = excluded.project_root,
                    source_video_path = excluded.source_video_path,
                    transcript_path = excluded.transcript_path,
                    status = excluded.status,
                    updated_at = excluded.updated_at
                """,
                (
                    project_id,
                    slug,
                    title,
                    lesson_name,
                    str(project_root),
                    None if source_video_path is None else str(source_video_path),
                    None if transcript_path is None else str(transcript_path),
                    status,
                    now,
                    now,
                ),
            )
            row = conn.execute("SELECT * FROM projects WHERE project_id = ?", (project_id,)).fetchone()
        return _row_to_dict(row) or {}

    def list_projects(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM projects ORDER BY updated_at DESC, title ASC").fetchall()
        return [_row_to_dict(row) or {} for row in rows]

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM projects WHERE project_id = ?", (project_id,)).fetchone()
        return _row_to_dict(row)

    def update_project_status(self, project_id: str, status: str) -> dict[str, Any]:
        now = utc_now_iso()
        with self.connect() as conn:
            conn.execute(
                "UPDATE projects SET status = ?, updated_at = ? WHERE project_id = ?",
                (status, now, project_id),
            )
            row = conn.execute("SELECT * FROM projects WHERE project_id = ?", (project_id,)).fetchone()
        return _row_to_dict(row) or {}

    def create_run(
        self,
        *,
        run_id: str,
        project_id: str,
        run_mode: str,
        status: str,
        log_path: str | Path | None = None,
        remote_job_name: str | None = None,
    ) -> dict[str, Any]:
        now = utc_now_iso()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO runs(
                    run_id, project_id, run_mode, status, log_path, remote_job_name, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    project_id,
                    run_mode,
                    status,
                    None if log_path is None else str(log_path),
                    remote_job_name,
                    now,
                    now,
                ),
            )
            row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        return _row_to_dict(row) or {}

    def update_run_status(
        self,
        run_id: str,
        *,
        status: str,
        remote_job_name: str | None = None,
        log_path: str | Path | None = None,
    ) -> dict[str, Any]:
        now = utc_now_iso()
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE runs
                SET status = ?,
                    remote_job_name = COALESCE(?, remote_job_name),
                    log_path = COALESCE(?, log_path),
                    updated_at = ?
                WHERE run_id = ?
                """,
                (status, remote_job_name, None if log_path is None else str(log_path), now, run_id),
            )
            row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        return _row_to_dict(row) or {}

    def list_runs(self, *, project_id: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM runs"
        params: list[Any] = []
        if project_id is not None:
            query += " WHERE project_id = ?"
            params.append(project_id)
        query += " ORDER BY updated_at DESC, created_at DESC"
        with self.connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [_row_to_dict(row) or {} for row in rows]

    def get_latest_run(self, project_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM runs
                WHERE project_id = ?
                ORDER BY updated_at DESC, created_at DESC
                LIMIT 1
                """,
                (project_id,),
            ).fetchone()
        return _row_to_dict(row)

