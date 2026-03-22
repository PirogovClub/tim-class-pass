from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from pipeline.orchestrator.models import (
    BATCH_JOB_STATUS_CANCELLED,
    BATCH_JOB_STATUS_EXPIRED,
    BATCH_JOB_STATUS_FAILED,
    REQUEST_PARSE_STATUS_FAILED,
    REQUEST_PARSE_STATUS_PARSED,
    REQUEST_PARSE_STATUS_PENDING,
    STAGE_RUN_STATUS_FAILED,
    STAGE_RUN_STATUS_SKIPPED,
    STAGE_RUN_STATUS_SUCCEEDED,
    TERMINAL_BATCH_JOB_STATUSES,
    TERMINAL_STAGE_RUN_STATUSES,
    utc_now_iso,
)


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}


class StateStore:
    def __init__(self, db_path: str | Path = "var/pipeline_state.db") -> None:
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

    def _create_schema(self, conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS videos (
                video_id TEXT PRIMARY KEY,
                video_root TEXT NOT NULL,
                title TEXT,
                config_hash TEXT,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS lessons (
                lesson_id TEXT PRIMARY KEY,
                video_id TEXT NOT NULL,
                lesson_name TEXT NOT NULL,
                lesson_root TEXT NOT NULL,
                vtt_path TEXT,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(video_id) REFERENCES videos(video_id)
            );

            CREATE TABLE IF NOT EXISTS stage_runs (
                stage_run_id TEXT PRIMARY KEY,
                lesson_id TEXT NOT NULL,
                stage_name TEXT NOT NULL,
                execution_mode TEXT NOT NULL,
                status TEXT NOT NULL,
                attempt INTEGER NOT NULL,
                request_manifest_path TEXT,
                result_manifest_path TEXT,
                error_message TEXT,
                started_at TEXT,
                finished_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(lesson_id) REFERENCES lessons(lesson_id)
            );

            CREATE TABLE IF NOT EXISTS batch_jobs (
                batch_job_name TEXT PRIMARY KEY,
                remote_job_name TEXT,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                stage_name TEXT NOT NULL,
                local_request_file TEXT NOT NULL,
                uploaded_file_name TEXT,
                result_file_name TEXT,
                status TEXT NOT NULL,
                request_count INTEGER NOT NULL DEFAULT 0,
                success_count INTEGER NOT NULL DEFAULT 0,
                failure_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS batch_requests (
                request_key TEXT PRIMARY KEY,
                batch_job_name TEXT,
                stage_run_id TEXT NOT NULL,
                video_id TEXT NOT NULL,
                lesson_id TEXT NOT NULL,
                stage_name TEXT NOT NULL,
                entity_kind TEXT NOT NULL,
                entity_index TEXT NOT NULL,
                payload_sha256 TEXT NOT NULL,
                spool_file_path TEXT NOT NULL,
                parse_status TEXT NOT NULL,
                output_path TEXT,
                error_message TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(batch_job_name) REFERENCES batch_jobs(batch_job_name),
                FOREIGN KEY(stage_run_id) REFERENCES stage_runs(stage_run_id),
                FOREIGN KEY(lesson_id) REFERENCES lessons(lesson_id)
            );

            CREATE TABLE IF NOT EXISTS artifacts (
                artifact_id TEXT PRIMARY KEY,
                owner_type TEXT NOT NULL,
                owner_id TEXT NOT NULL,
                artifact_type TEXT NOT NULL,
                path TEXT NOT NULL,
                sha256 TEXT,
                size_bytes INTEGER,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_lessons_video_id
                ON lessons(video_id);
            CREATE INDEX IF NOT EXISTS idx_stage_runs_lesson_stage_status
                ON stage_runs(lesson_id, stage_name, status);
            CREATE INDEX IF NOT EXISTS idx_batch_requests_batch_job_name
                ON batch_requests(batch_job_name);
            CREATE INDEX IF NOT EXISTS idx_batch_requests_stage_run_id
                ON batch_requests(stage_run_id);
            CREATE INDEX IF NOT EXISTS idx_batch_jobs_status
                ON batch_jobs(status);
            """
        )

    def ensure_video(
        self,
        *,
        video_id: str,
        video_root: str | Path,
        title: str | None = None,
        config_hash: str | None = None,
        status: str = "PENDING",
    ) -> dict[str, Any]:
        now = utc_now_iso()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO videos(video_id, video_root, title, config_hash, status, created_at, updated_at)
                VALUES(?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(video_id) DO UPDATE SET
                    video_root=excluded.video_root,
                    title=COALESCE(excluded.title, videos.title),
                    config_hash=COALESCE(excluded.config_hash, videos.config_hash),
                    status=excluded.status,
                    updated_at=excluded.updated_at
                """,
                (video_id, str(video_root), title, config_hash, status, now, now),
            )
            row = conn.execute("SELECT * FROM videos WHERE video_id = ?", (video_id,)).fetchone()
        return _row_to_dict(row) or {}

    def ensure_lesson(
        self,
        *,
        lesson_id: str,
        video_id: str,
        lesson_name: str,
        lesson_root: str | Path,
        vtt_path: str | Path | None = None,
        status: str = "PENDING",
    ) -> dict[str, Any]:
        now = utc_now_iso()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO lessons(lesson_id, video_id, lesson_name, lesson_root, vtt_path, status, created_at, updated_at)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(lesson_id) DO UPDATE SET
                    video_id=excluded.video_id,
                    lesson_name=excluded.lesson_name,
                    lesson_root=excluded.lesson_root,
                    vtt_path=excluded.vtt_path,
                    status=excluded.status,
                    updated_at=excluded.updated_at
                """,
                (lesson_id, video_id, lesson_name, str(lesson_root), None if vtt_path is None else str(vtt_path), status, now, now),
            )
            row = conn.execute("SELECT * FROM lessons WHERE lesson_id = ?", (lesson_id,)).fetchone()
        return _row_to_dict(row) or {}

    def create_or_reuse_stage_run(
        self,
        *,
        lesson_id: str,
        stage_name: str,
        execution_mode: str = "gemini_batch",
        status: str = "PENDING",
        request_manifest_path: str | Path | None = None,
        result_manifest_path: str | Path | None = None,
        error_message: str | None = None,
        started_at: str | None = None,
        finished_at: str | None = None,
        force_new_attempt: bool = False,
    ) -> dict[str, Any]:
        now = utc_now_iso()
        with self.connect() as conn:
            latest = conn.execute(
                """
                SELECT * FROM stage_runs
                WHERE lesson_id = ? AND stage_name = ? AND execution_mode = ?
                ORDER BY attempt DESC, created_at DESC
                LIMIT 1
                """,
                (lesson_id, stage_name, execution_mode),
            ).fetchone()
            if latest is not None and not force_new_attempt and latest["status"] not in TERMINAL_STAGE_RUN_STATUSES:
                conn.execute(
                    """
                    UPDATE stage_runs
                    SET status = ?,
                        request_manifest_path = COALESCE(?, request_manifest_path),
                        result_manifest_path = COALESCE(?, result_manifest_path),
                        error_message = ?,
                        started_at = COALESCE(?, started_at),
                        finished_at = COALESCE(?, finished_at),
                        updated_at = ?
                    WHERE stage_run_id = ?
                    """,
                    (
                        status,
                        None if request_manifest_path is None else str(request_manifest_path),
                        None if result_manifest_path is None else str(result_manifest_path),
                        error_message,
                        started_at,
                        finished_at,
                        now,
                        latest["stage_run_id"],
                    ),
                )
                row = conn.execute(
                    "SELECT * FROM stage_runs WHERE stage_run_id = ?",
                    (latest["stage_run_id"],),
                ).fetchone()
                return _row_to_dict(row) or {}

            next_attempt = 1 if latest is None else int(latest["attempt"]) + 1
            stage_run_id = f"{lesson_id}::{stage_name}::{execution_mode}::{next_attempt:03d}"
            conn.execute(
                """
                INSERT INTO stage_runs(
                    stage_run_id, lesson_id, stage_name, execution_mode, status, attempt,
                    request_manifest_path, result_manifest_path, error_message,
                    started_at, finished_at, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    stage_run_id,
                    lesson_id,
                    stage_name,
                    execution_mode,
                    status,
                    next_attempt,
                    None if request_manifest_path is None else str(request_manifest_path),
                    None if result_manifest_path is None else str(result_manifest_path),
                    error_message,
                    started_at,
                    finished_at,
                    now,
                    now,
                ),
            )
            row = conn.execute("SELECT * FROM stage_runs WHERE stage_run_id = ?", (stage_run_id,)).fetchone()
        return _row_to_dict(row) or {}

    def update_stage_run(
        self,
        stage_run_id: str,
        *,
        status: str | None = None,
        request_manifest_path: str | Path | None = None,
        result_manifest_path: str | Path | None = None,
        error_message: str | None = None,
        started_at: str | None = None,
        finished_at: str | None = None,
    ) -> dict[str, Any]:
        current = self.get_stage_run(stage_run_id)
        if current is None:
            raise KeyError(f"Unknown stage_run_id: {stage_run_id}")
        updates = {
            "status": current["status"] if status is None else status,
            "request_manifest_path": current["request_manifest_path"] if request_manifest_path is None else str(request_manifest_path),
            "result_manifest_path": current["result_manifest_path"] if result_manifest_path is None else str(result_manifest_path),
            "error_message": error_message,
            "started_at": current["started_at"] if started_at is None else started_at,
            "finished_at": current["finished_at"] if finished_at is None else finished_at,
            "updated_at": utc_now_iso(),
        }
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE stage_runs
                SET status = ?,
                    request_manifest_path = ?,
                    result_manifest_path = ?,
                    error_message = ?,
                    started_at = ?,
                    finished_at = ?,
                    updated_at = ?
                WHERE stage_run_id = ?
                """,
                (
                    updates["status"],
                    updates["request_manifest_path"],
                    updates["result_manifest_path"],
                    updates["error_message"],
                    updates["started_at"],
                    updates["finished_at"],
                    updates["updated_at"],
                    stage_run_id,
                ),
            )
            row = conn.execute("SELECT * FROM stage_runs WHERE stage_run_id = ?", (stage_run_id,)).fetchone()
        return _row_to_dict(row) or {}

    def record_spool_request(
        self,
        *,
        request_key: str,
        batch_job_name: str | None = None,
        stage_run_id: str,
        video_id: str,
        lesson_id: str,
        stage_name: str,
        entity_kind: str,
        entity_index: str,
        payload_sha256: str,
        spool_file_path: str | Path,
        parse_status: str = REQUEST_PARSE_STATUS_PENDING,
        output_path: str | Path | None = None,
        error_message: str | None = None,
    ) -> dict[str, Any]:
        now = utc_now_iso()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO batch_requests(
                    request_key, batch_job_name, stage_run_id, video_id, lesson_id, stage_name,
                    entity_kind, entity_index, payload_sha256, spool_file_path, parse_status,
                    output_path, error_message, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(request_key) DO UPDATE SET
                    batch_job_name = COALESCE(excluded.batch_job_name, batch_requests.batch_job_name),
                    stage_run_id = excluded.stage_run_id,
                    video_id = excluded.video_id,
                    lesson_id = excluded.lesson_id,
                    stage_name = excluded.stage_name,
                    entity_kind = excluded.entity_kind,
                    entity_index = excluded.entity_index,
                    payload_sha256 = excluded.payload_sha256,
                    spool_file_path = excluded.spool_file_path,
                    parse_status = excluded.parse_status,
                    output_path = excluded.output_path,
                    error_message = excluded.error_message,
                    updated_at = excluded.updated_at
                """,
                (
                    request_key,
                    batch_job_name,
                    stage_run_id,
                    video_id,
                    lesson_id,
                    stage_name,
                    entity_kind,
                    entity_index,
                    payload_sha256,
                    str(spool_file_path),
                    parse_status,
                    None if output_path is None else str(output_path),
                    error_message,
                    now,
                    now,
                ),
            )
            row = conn.execute("SELECT * FROM batch_requests WHERE request_key = ?", (request_key,)).fetchone()
        return _row_to_dict(row) or {}

    def create_batch_job(
        self,
        *,
        batch_job_name: str,
        provider: str,
        model: str,
        stage_name: str,
        local_request_file: str | Path,
        remote_job_name: str | None = None,
        uploaded_file_name: str | None = None,
        result_file_name: str | None = None,
        status: str = "LOCAL_READY",
        request_count: int = 0,
        success_count: int = 0,
        failure_count: int = 0,
    ) -> dict[str, Any]:
        now = utc_now_iso()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO batch_jobs(
                    batch_job_name, remote_job_name, provider, model, stage_name,
                    local_request_file, uploaded_file_name, result_file_name, status,
                    request_count, success_count, failure_count, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(batch_job_name) DO UPDATE SET
                    remote_job_name = COALESCE(excluded.remote_job_name, batch_jobs.remote_job_name),
                    provider = excluded.provider,
                    model = excluded.model,
                    stage_name = excluded.stage_name,
                    local_request_file = excluded.local_request_file,
                    uploaded_file_name = COALESCE(excluded.uploaded_file_name, batch_jobs.uploaded_file_name),
                    result_file_name = COALESCE(excluded.result_file_name, batch_jobs.result_file_name),
                    status = excluded.status,
                    request_count = excluded.request_count,
                    success_count = excluded.success_count,
                    failure_count = excluded.failure_count,
                    updated_at = excluded.updated_at
                """,
                (
                    batch_job_name,
                    remote_job_name,
                    provider,
                    model,
                    stage_name,
                    str(local_request_file),
                    uploaded_file_name,
                    result_file_name,
                    status,
                    request_count,
                    success_count,
                    failure_count,
                    now,
                    now,
                ),
            )
            row = conn.execute("SELECT * FROM batch_jobs WHERE batch_job_name = ?", (batch_job_name,)).fetchone()
        return _row_to_dict(row) or {}

    def attach_requests_to_batch(self, batch_job_name: str, request_keys: list[str]) -> None:
        if not request_keys:
            return
        now = utc_now_iso()
        placeholders = ", ".join("?" for _ in request_keys)
        with self.connect() as conn:
            conn.execute(
                f"""
                UPDATE batch_requests
                SET batch_job_name = ?, updated_at = ?
                WHERE request_key IN ({placeholders})
                """,
                (batch_job_name, now, *request_keys),
            )

    def update_batch_job_status(
        self,
        batch_job_name: str,
        *,
        status: str,
        remote_job_name: str | None = None,
        uploaded_file_name: str | None = None,
        result_file_name: str | None = None,
        request_count: int | None = None,
        success_count: int | None = None,
        failure_count: int | None = None,
    ) -> dict[str, Any]:
        current = self.get_batch_job(batch_job_name)
        if current is None:
            raise KeyError(f"Unknown batch job: {batch_job_name}")
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE batch_jobs
                SET status = ?,
                    remote_job_name = COALESCE(?, remote_job_name),
                    uploaded_file_name = COALESCE(?, uploaded_file_name),
                    result_file_name = COALESCE(?, result_file_name),
                    request_count = COALESCE(?, request_count),
                    success_count = COALESCE(?, success_count),
                    failure_count = COALESCE(?, failure_count),
                    updated_at = ?
                WHERE batch_job_name = ?
                """,
                (
                    status,
                    remote_job_name,
                    uploaded_file_name,
                    result_file_name,
                    request_count,
                    success_count,
                    failure_count,
                    utc_now_iso(),
                    batch_job_name,
                ),
            )
            row = conn.execute("SELECT * FROM batch_jobs WHERE batch_job_name = ?", (batch_job_name,)).fetchone()
        return _row_to_dict(row) or {}

    def mark_request_parsed(
        self,
        request_key: str,
        *,
        output_path: str | Path | None = None,
    ) -> dict[str, Any]:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE batch_requests
                SET parse_status = ?, output_path = ?, error_message = NULL, updated_at = ?
                WHERE request_key = ?
                """,
                (
                    REQUEST_PARSE_STATUS_PARSED,
                    None if output_path is None else str(output_path),
                    utc_now_iso(),
                    request_key,
                ),
            )
            row = conn.execute("SELECT * FROM batch_requests WHERE request_key = ?", (request_key,)).fetchone()
        return _row_to_dict(row) or {}

    def mark_request_failed(self, request_key: str, error_message: str) -> dict[str, Any]:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE batch_requests
                SET parse_status = ?, error_message = ?, updated_at = ?
                WHERE request_key = ?
                """,
                (REQUEST_PARSE_STATUS_FAILED, error_message, utc_now_iso(), request_key),
            )
            row = conn.execute("SELECT * FROM batch_requests WHERE request_key = ?", (request_key,)).fetchone()
        return _row_to_dict(row) or {}

    def record_artifact(
        self,
        *,
        artifact_id: str,
        owner_type: str,
        owner_id: str,
        artifact_type: str,
        path: str | Path,
        sha256: str | None = None,
        size_bytes: int | None = None,
    ) -> dict[str, Any]:
        created_at = utc_now_iso()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO artifacts(artifact_id, owner_type, owner_id, artifact_type, path, sha256, size_bytes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(artifact_id) DO UPDATE SET
                    owner_type = excluded.owner_type,
                    owner_id = excluded.owner_id,
                    artifact_type = excluded.artifact_type,
                    path = excluded.path,
                    sha256 = excluded.sha256,
                    size_bytes = excluded.size_bytes
                """,
                (artifact_id, owner_type, owner_id, artifact_type, str(path), sha256, size_bytes, created_at),
            )
            row = conn.execute("SELECT * FROM artifacts WHERE artifact_id = ?", (artifact_id,)).fetchone()
        return _row_to_dict(row) or {}

    def summarize_status(self) -> dict[str, dict[str, int]]:
        summary: dict[str, dict[str, int]] = {}
        with self.connect() as conn:
            for table, status_column in (
                ("videos", "status"),
                ("lessons", "status"),
                ("stage_runs", "status"),
                ("batch_jobs", "status"),
                ("batch_requests", "parse_status"),
            ):
                rows = conn.execute(
                    f"SELECT {status_column} AS status, COUNT(*) AS count FROM {table} GROUP BY {status_column}"
                ).fetchall()
                summary[table] = {str(row["status"]): int(row["count"]) for row in rows}
        return summary

    def get_retryable_requests(self, stage_name: str | None = None) -> list[dict[str, Any]]:
        where = [
            "(br.parse_status = ? OR bj.status IN (?, ?, ?))",
        ]
        params: list[Any] = [
            REQUEST_PARSE_STATUS_FAILED,
            BATCH_JOB_STATUS_FAILED,
            BATCH_JOB_STATUS_CANCELLED,
            BATCH_JOB_STATUS_EXPIRED,
        ]
        if stage_name is not None:
            where.append("br.stage_name = ?")
            params.append(stage_name)
        query = f"""
            SELECT br.*
            FROM batch_requests br
            LEFT JOIN batch_jobs bj ON bj.batch_job_name = br.batch_job_name
            WHERE {" AND ".join(where)}
            ORDER BY br.updated_at ASC
        """
        with self.connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [_row_to_dict(row) or {} for row in rows]

    def get_unfinished_batches(self) -> list[dict[str, Any]]:
        placeholders = ", ".join("?" for _ in TERMINAL_BATCH_JOB_STATUSES)
        query = f"""
            SELECT *
            FROM batch_jobs
            WHERE status NOT IN ({placeholders})
            ORDER BY created_at ASC
        """
        with self.connect() as conn:
            rows = conn.execute(query, tuple(sorted(TERMINAL_BATCH_JOB_STATUSES))).fetchall()
        return [_row_to_dict(row) or {} for row in rows]

    def list_videos(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM videos ORDER BY video_id ASC").fetchall()
        return [_row_to_dict(row) or {} for row in rows]

    def list_lessons(self, *, video_id: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM lessons"
        params: list[Any] = []
        if video_id is not None:
            query += " WHERE video_id = ?"
            params.append(video_id)
        query += " ORDER BY lesson_name ASC"
        with self.connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [_row_to_dict(row) or {} for row in rows]

    def list_stage_runs(
        self,
        *,
        lesson_id: str | None = None,
        stage_name: str | None = None,
        status: str | None = None,
        execution_mode: str | None = None,
    ) -> list[dict[str, Any]]:
        where: list[str] = []
        params: list[Any] = []
        if lesson_id is not None:
            where.append("lesson_id = ?")
            params.append(lesson_id)
        if stage_name is not None:
            where.append("stage_name = ?")
            params.append(stage_name)
        if status is not None:
            where.append("status = ?")
            params.append(status)
        if execution_mode is not None:
            where.append("execution_mode = ?")
            params.append(execution_mode)
        query = "SELECT * FROM stage_runs"
        if where:
            query += " WHERE " + " AND ".join(where)
        query += " ORDER BY created_at ASC, attempt ASC"
        with self.connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [_row_to_dict(row) or {} for row in rows]

    def list_batch_jobs(
        self,
        *,
        stage_name: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        where: list[str] = []
        params: list[Any] = []
        if stage_name is not None:
            where.append("stage_name = ?")
            params.append(stage_name)
        if status is not None:
            where.append("status = ?")
            params.append(status)
        query = "SELECT * FROM batch_jobs"
        if where:
            query += " WHERE " + " AND ".join(where)
        query += " ORDER BY created_at ASC"
        with self.connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [_row_to_dict(row) or {} for row in rows]

    def list_batch_requests(
        self,
        *,
        stage_run_id: str | None = None,
        batch_job_name: str | None = None,
        parse_status: str | None = None,
        stage_name: str | None = None,
    ) -> list[dict[str, Any]]:
        where: list[str] = []
        params: list[Any] = []
        if stage_run_id is not None:
            where.append("stage_run_id = ?")
            params.append(stage_run_id)
        if batch_job_name is not None:
            where.append("batch_job_name = ?")
            params.append(batch_job_name)
        if parse_status is not None:
            where.append("parse_status = ?")
            params.append(parse_status)
        if stage_name is not None:
            where.append("stage_name = ?")
            params.append(stage_name)
        query = "SELECT * FROM batch_requests"
        if where:
            query += " WHERE " + " AND ".join(where)
        query += " ORDER BY created_at ASC"
        with self.connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [_row_to_dict(row) or {} for row in rows]

    def get_stage_run(self, stage_run_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM stage_runs WHERE stage_run_id = ?", (stage_run_id,)).fetchone()
        return _row_to_dict(row)

    def get_batch_job(self, batch_job_name: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM batch_jobs WHERE batch_job_name = ?", (batch_job_name,)).fetchone()
        return _row_to_dict(row)
