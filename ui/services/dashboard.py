from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ui.models import CorpusQueueRow, DashboardRow, ProjectRecord, RunRecord
from ui.services.projects import derive_effective_status, derive_next_action, inspect_artifacts
from ui.settings import UISettings
from ui.storage import UIStateStore


@dataclass(frozen=True)
class DashboardPage:
    rows: list[DashboardRow]
    total_rows: int
    page: int
    total_pages: int
    status_counts: dict[str, int]


@dataclass(frozen=True)
class CorpusQueuePage:
    rows: list[CorpusQueueRow]
    counts: dict[str, int]


def _row_to_project(row: dict) -> ProjectRecord:
    return ProjectRecord(
        project_id=str(row["project_id"]),
        slug=str(row["slug"]),
        title=str(row["title"]),
        lesson_name=str(row["lesson_name"]),
        project_root=Path(str(row["project_root"])),
        source_video_path=None if not row.get("source_video_path") else Path(str(row["source_video_path"])),
        transcript_path=None if not row.get("transcript_path") else Path(str(row["transcript_path"])),
        status=str(row["status"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def _row_to_run(row: dict | None) -> RunRecord | None:
    if row is None:
        return None
    pid_value = row.get("pid")
    exit_code_value = row.get("exit_code")
    return RunRecord(
        run_id=str(row["run_id"]),
        project_id=str(row["project_id"]),
        run_kind=str(row.get("run_kind") or "PROJECT"),
        run_mode=str(row["run_mode"]),
        status=str(row["status"]),
        current_stage=row.get("current_stage"),
        progress_message=row.get("progress_message"),
        log_path=None if not row.get("log_path") else Path(str(row["log_path"])),
        pipeline_db_path=None if not row.get("pipeline_db_path") else Path(str(row["pipeline_db_path"])),
        remote_job_name=row.get("remote_job_name"),
        pid=None if pid_value is None else int(pid_value),
        command=row.get("command"),
        last_heartbeat_at=row.get("last_heartbeat_at"),
        last_remote_poll_at=row.get("last_remote_poll_at"),
        started_at=row.get("started_at"),
        finished_at=row.get("finished_at"),
        exit_code=None if exit_code_value is None else int(exit_code_value),
        error_message=row.get("error_message"),
        cancel_requested_at=row.get("cancel_requested_at"),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def _build_dashboard_row(store: UIStateStore, project: ProjectRecord) -> DashboardRow:
    latest_run = _row_to_run(store.get_latest_run(project.project_id))
    artifacts = inspect_artifacts(
        project.project_root,
        project.lesson_name,
        project.transcript_path,
        project.source_video_path,
    )
    effective_status = derive_effective_status(artifacts, latest_run)
    if effective_status != project.status:
        updated_row = store.update_project_status(project.project_id, effective_status)
        project = _row_to_project(updated_row)
    updated_at = max(project.updated_at, latest_run.updated_at) if latest_run is not None else project.updated_at
    return DashboardRow(
        project=project,
        artifacts=artifacts,
        latest_run=latest_run,
        effective_status=effective_status,
        next_action=derive_next_action(artifacts, latest_run, effective_status),
        updated_at=updated_at,
    )


def get_dashboard_page(
    store: UIStateStore,
    settings: UISettings,
    *,
    query: str = "",
    status: str = "",
    sort: str = "updated_desc",
    page: int = 1,
) -> DashboardPage:
    projects = [_row_to_project(row) for row in store.list_projects()]
    rows = [_build_dashboard_row(store, project) for project in projects]

    filtered_rows = rows
    normalized_query = query.strip().lower()
    if normalized_query:
        filtered_rows = [
            row
            for row in filtered_rows
            if normalized_query in row.project.title.lower()
            or normalized_query in row.project.slug.lower()
            or normalized_query in row.project.lesson_name.lower()
            or normalized_query in row.project.project_root.as_posix().lower()
        ]
    normalized_status = status.strip()
    if normalized_status:
        filtered_rows = [row for row in filtered_rows if row.effective_status == normalized_status]

    status_counts: dict[str, int] = {"all": len(rows)}
    for row in rows:
        status_counts[row.effective_status] = status_counts.get(row.effective_status, 0) + 1

    if sort == "title_asc":
        filtered_rows = sorted(filtered_rows, key=lambda row: (row.project.title.lower(), row.updated_at))
    elif sort == "status_asc":
        filtered_rows = sorted(filtered_rows, key=lambda row: (row.effective_status, row.project.title.lower()))
    else:
        filtered_rows = sorted(filtered_rows, key=lambda row: (row.updated_at, row.project.title.lower()), reverse=True)

    safe_page = max(1, page)
    page_size = max(1, settings.page_size)
    total_rows = len(filtered_rows)
    total_pages = max(1, (total_rows + page_size - 1) // page_size)
    if safe_page > total_pages:
        safe_page = total_pages
    start = (safe_page - 1) * page_size
    end = start + page_size
    return DashboardPage(
        rows=filtered_rows[start:end],
        total_rows=total_rows,
        page=safe_page,
        total_pages=total_pages,
        status_counts=status_counts,
    )


def get_project_detail(store: UIStateStore, project_id: str) -> tuple[DashboardRow, list[RunRecord]]:
    row = store.get_project(project_id)
    if row is None:
        raise KeyError(project_id)
    project = _row_to_project(row)
    dashboard_row = _build_dashboard_row(store, project)
    runs = [_row_to_run(entry) for entry in store.get_runs_for_target(project_id)]
    return dashboard_row, [run for run in runs if run is not None]


def _corpus_status_for_project(store: UIStateStore, project: ProjectRecord, artifacts) -> tuple[str, RunRecord | None]:
    corpus_runs = [
        _row_to_run(row)
        for row in store.get_runs_for_target(project.project_id)
        if (row.get("run_kind") or "PROJECT") == "CORPUS"
    ]
    corpus_runs = [run for run in corpus_runs if run is not None]
    latest = corpus_runs[0] if corpus_runs else None
    if latest is not None and latest.is_active:
        return ("running", latest)
    if not artifacts.corpus_ready:
        return ("blocked", latest)
    if latest is None or latest.status not in {"SUCCEEDED", "CANCELLED"}:
        return ("ready", latest)
    if latest.finished_at and project.updated_at > latest.finished_at:
        return ("stale_since_last_export", latest)
    return ("exported", latest)


def get_corpus_queue_page(store: UIStateStore) -> CorpusQueuePage:
    rows: list[CorpusQueueRow] = []
    counts: dict[str, int] = {}
    for project_row in store.list_projects():
        project = _row_to_project(project_row)
        artifacts = inspect_artifacts(
            project.project_root,
            project.lesson_name,
            project.transcript_path,
            project.source_video_path,
        )
        corpus_status, latest_run = _corpus_status_for_project(store, project, artifacts)
        counts[corpus_status] = counts.get(corpus_status, 0) + 1
        output_root = latest_run.log_path.parent if latest_run and latest_run.log_path else None
        rows.append(
            CorpusQueueRow(
                project=project,
                artifacts=artifacts,
                corpus_status=corpus_status,
                latest_corpus_run=latest_run,
                output_root=output_root,
            )
        )
    rows.sort(key=lambda row: (row.corpus_status, row.project.title.lower()))
    return CorpusQueuePage(rows=rows, counts=counts)

