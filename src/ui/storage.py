from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from pipeline.orchestrator.models import utc_now_iso


SCHEMA_VERSION = 4


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}


def _table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {str(row["name"]) for row in rows}


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
            self._create_schema(conn)
            self._migrate_schema(conn)

    def _create_schema(self, conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS schema_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS projects (
                project_id TEXT PRIMARY KEY,
                slug TEXT NOT NULL,
                title TEXT NOT NULL,
                lesson_name TEXT NOT NULL,
                project_root TEXT NOT NULL,
                source_mode TEXT NOT NULL DEFAULT 'upload',
                source_url TEXT,
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
                run_kind TEXT NOT NULL DEFAULT 'PROJECT',
                run_mode TEXT NOT NULL,
                force_overwrite INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL,
                current_stage TEXT,
                progress_message TEXT,
                log_path TEXT,
                pipeline_db_path TEXT,
                remote_job_name TEXT,
                pid INTEGER,
                command TEXT,
                last_heartbeat_at TEXT,
                last_remote_poll_at TEXT,
                started_at TEXT,
                finished_at TEXT,
                exit_code INTEGER,
                error_message TEXT,
                cancel_requested_at TEXT,
                project_root_snapshot TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(project_id) REFERENCES projects(project_id)
            );

            CREATE INDEX IF NOT EXISTS idx_runs_project_id ON runs(project_id);
            CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status);
            CREATE INDEX IF NOT EXISTS idx_runs_updated_at ON runs(updated_at);

            CREATE TABLE IF NOT EXISTS run_targets (
                run_id TEXT NOT NULL,
                project_id TEXT NOT NULL,
                PRIMARY KEY (run_id, project_id),
                FOREIGN KEY(run_id) REFERENCES runs(run_id) ON DELETE CASCADE,
                FOREIGN KEY(project_id) REFERENCES projects(project_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS run_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                stage TEXT,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(run_id) REFERENCES runs(run_id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_run_events_run_id ON run_events(run_id, created_at DESC);
            """
        )
        conn.execute(
            """
            INSERT INTO schema_meta(key, value)
            VALUES ('schema_version', ?)
            ON CONFLICT(key) DO NOTHING
            """,
            (str(SCHEMA_VERSION),),
        )

    def _migrate_schema(self, conn: sqlite3.Connection) -> None:
        project_columns = _table_columns(conn, "projects")
        project_additions = {
            "source_mode": "TEXT NOT NULL DEFAULT 'upload'",
            "source_url": "TEXT",
        }
        for name, ddl in project_additions.items():
            if name not in project_columns:
                conn.execute(f"ALTER TABLE projects ADD COLUMN {name} {ddl}")

        run_columns = _table_columns(conn, "runs")
        additions = {
            "run_kind": "TEXT NOT NULL DEFAULT 'PROJECT'",
            "force_overwrite": "INTEGER NOT NULL DEFAULT 0",
            "current_stage": "TEXT",
            "progress_message": "TEXT",
            "pipeline_db_path": "TEXT",
            "pid": "INTEGER",
            "command": "TEXT",
            "last_heartbeat_at": "TEXT",
            "last_remote_poll_at": "TEXT",
            "started_at": "TEXT",
            "finished_at": "TEXT",
            "exit_code": "INTEGER",
            "error_message": "TEXT",
            "cancel_requested_at": "TEXT",
            "project_root_snapshot": "TEXT",
        }
        for name, ddl in additions.items():
            if name not in run_columns:
                conn.execute(f"ALTER TABLE runs ADD COLUMN {name} {ddl}")

        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS run_targets (
                run_id TEXT NOT NULL,
                project_id TEXT NOT NULL,
                PRIMARY KEY (run_id, project_id),
                FOREIGN KEY(run_id) REFERENCES runs(run_id) ON DELETE CASCADE,
                FOREIGN KEY(project_id) REFERENCES projects(project_id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS run_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                stage TEXT,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(run_id) REFERENCES runs(run_id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_runs_run_kind ON runs(run_kind);
            CREATE INDEX IF NOT EXISTS idx_run_events_run_id ON run_events(run_id, created_at DESC);
            """
        )
        conn.execute(
            """
            INSERT INTO schema_meta(key, value)
            VALUES ('schema_version', ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (str(SCHEMA_VERSION),),
        )

    def schema_version(self) -> int:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT value FROM schema_meta WHERE key = 'schema_version'"
            ).fetchone()
        return int(row["value"]) if row is not None else 0

    def upsert_project(
        self,
        *,
        project_id: str,
        slug: str,
        title: str,
        lesson_name: str,
        project_root: str | Path,
        source_mode: str,
        source_url: str | None,
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
                    source_mode, source_url, source_video_path, transcript_path, status, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(project_id) DO UPDATE SET
                    slug = excluded.slug,
                    title = excluded.title,
                    lesson_name = excluded.lesson_name,
                    project_root = excluded.project_root,
                    source_mode = excluded.source_mode,
                    source_url = excluded.source_url,
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
                    source_mode,
                    source_url,
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
        force_overwrite: bool = False,
        status: str,
        run_kind: str = "PROJECT",
        current_stage: str | None = None,
        progress_message: str | None = None,
        log_path: str | Path | None = None,
        pipeline_db_path: str | Path | None = None,
        remote_job_name: str | None = None,
        pid: int | None = None,
        command: str | None = None,
        last_heartbeat_at: str | None = None,
        last_remote_poll_at: str | None = None,
        started_at: str | None = None,
        finished_at: str | None = None,
        exit_code: int | None = None,
        error_message: str | None = None,
        cancel_requested_at: str | None = None,
        project_root_snapshot: str | Path | None = None,
    ) -> dict[str, Any]:
        now = utc_now_iso()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO runs(
                    run_id, project_id, run_kind, run_mode, force_overwrite, status, current_stage, progress_message,
                    log_path, pipeline_db_path, remote_job_name, pid, command, last_heartbeat_at,
                    last_remote_poll_at, started_at, finished_at, exit_code, error_message,
                    cancel_requested_at, project_root_snapshot, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    project_id,
                    run_kind,
                    run_mode,
                    1 if force_overwrite else 0,
                    status,
                    current_stage,
                    progress_message,
                    None if log_path is None else str(log_path),
                    None if pipeline_db_path is None else str(pipeline_db_path),
                    remote_job_name,
                    pid,
                    command,
                    last_heartbeat_at,
                    last_remote_poll_at,
                    started_at,
                    finished_at,
                    exit_code,
                    error_message,
                    cancel_requested_at,
                    None if project_root_snapshot is None else str(project_root_snapshot),
                    now,
                    now,
                ),
            )
            row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        return _row_to_dict(row) or {}

    def update_run(
        self,
        run_id: str,
        **updates: Any,
    ) -> dict[str, Any]:
        if not updates:
            current = self.get_run(run_id)
            if current is None:
                raise KeyError(run_id)
            return current
        allowed = {
            "status",
            "run_kind",
            "run_mode",
            "force_overwrite",
            "current_stage",
            "progress_message",
            "log_path",
            "pipeline_db_path",
            "remote_job_name",
            "pid",
            "command",
            "last_heartbeat_at",
            "last_remote_poll_at",
            "started_at",
            "finished_at",
            "exit_code",
            "error_message",
            "cancel_requested_at",
            "project_root_snapshot",
            "project_id",
        }
        fields = {key: value for key, value in updates.items() if key in allowed}
        if not fields:
            current = self.get_run(run_id)
            if current is None:
                raise KeyError(run_id)
            return current
        fields["updated_at"] = utc_now_iso()
        assignments = ", ".join(f"{key} = ?" for key in fields.keys())
        values = [
            None if key in {"log_path", "pipeline_db_path", "project_root_snapshot"} and value is not None else value
            for key, value in fields.items()
        ]
        normalized_values: list[Any] = []
        for key, value in fields.items():
            if key in {"log_path", "pipeline_db_path", "project_root_snapshot"} and value is not None:
                normalized_values.append(str(value))
            else:
                normalized_values.append(value)
        with self.connect() as conn:
            conn.execute(
                f"UPDATE runs SET {assignments} WHERE run_id = ?",
                (*normalized_values, run_id),
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
        fields: dict[str, Any] = {"status": status}
        if remote_job_name is not None:
            fields["remote_job_name"] = remote_job_name
        if log_path is not None:
            fields["log_path"] = log_path
        return self.update_run(run_id, **fields)

    def append_run_event(
        self,
        *,
        run_id: str,
        event_type: str,
        message: str,
        stage: str | None = None,
    ) -> dict[str, Any]:
        created_at = utc_now_iso()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO run_events(run_id, event_type, stage, message, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (run_id, event_type, stage, message, created_at),
            )
            row = conn.execute(
                "SELECT * FROM run_events WHERE event_id = last_insert_rowid()"
            ).fetchone()
        return _row_to_dict(row) or {}

    def list_run_events(self, run_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM run_events
                WHERE run_id = ?
                ORDER BY event_id DESC
                LIMIT ?
                """,
                (run_id, limit),
            ).fetchall()
        ordered = list(reversed(rows))
        return [_row_to_dict(row) or {} for row in ordered]

    def attach_run_targets(self, run_id: str, project_ids: list[str]) -> None:
        with self.connect() as conn:
            for project_id in project_ids:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO run_targets(run_id, project_id)
                    VALUES (?, ?)
                    """,
                    (run_id, project_id),
                )

    def list_run_targets(self, run_id: str) -> list[str]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT project_id FROM run_targets WHERE run_id = ? ORDER BY project_id ASC",
                (run_id,),
            ).fetchall()
        return [str(row["project_id"]) for row in rows]

    def get_runs_for_target(self, project_id: str) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT r.*
                FROM runs r
                LEFT JOIN run_targets rt ON rt.run_id = r.run_id
                WHERE r.project_id = ? OR rt.project_id = ?
                ORDER BY r.updated_at DESC, r.created_at DESC
                """,
                (project_id, project_id),
            ).fetchall()
        return [_row_to_dict(row) or {} for row in rows]

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        return _row_to_dict(row)

    def list_runs(
        self,
        *,
        project_id: str | None = None,
        run_kind: str | None = None,
        statuses: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        where: list[str] = []
        params: list[Any] = []
        if project_id is not None:
            where.append("project_id = ?")
            params.append(project_id)
        if run_kind is not None:
            where.append("run_kind = ?")
            params.append(run_kind)
        if statuses:
            placeholders = ", ".join("?" for _ in statuses)
            where.append(f"status IN ({placeholders})")
            params.extend(statuses)
        query = "SELECT * FROM runs"
        if where:
            query += " WHERE " + " AND ".join(where)
        query += " ORDER BY updated_at DESC, created_at DESC"
        with self.connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [_row_to_dict(row) or {} for row in rows]

    def get_latest_run(self, project_id: str) -> dict[str, Any] | None:
        rows = self.get_runs_for_target(project_id)
        return rows[0] if rows else None

    def get_active_run_for_project(self, project_id: str) -> dict[str, Any] | None:
        active_statuses = ["QUEUED", "RUNNING", "WAITING_REMOTE", "CANCEL_REQUESTED"]
        with self.connect() as conn:
            placeholders = ", ".join("?" for _ in active_statuses)
            row = conn.execute(
                f"""
                SELECT DISTINCT r.*
                FROM runs r
                LEFT JOIN run_targets rt ON rt.run_id = r.run_id
                WHERE (r.project_id = ? OR rt.project_id = ?)
                  AND r.status IN ({placeholders})
                ORDER BY r.updated_at DESC
                LIMIT 1
                """,
                (project_id, project_id, *active_statuses),
            ).fetchone()
        return _row_to_dict(row)

    def mark_cancel_requested(self, run_id: str) -> dict[str, Any]:
        return self.update_run(run_id, cancel_requested_at=utc_now_iso(), status="CANCEL_REQUESTED")

    def list_waiting_remote_runs(self) -> list[dict[str, Any]]:
        return self.list_runs(statuses=["WAITING_REMOTE"])

