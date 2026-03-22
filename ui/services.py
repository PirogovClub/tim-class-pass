from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from pipeline.contracts import PipelinePaths
from pipeline.orchestrator.models import slugify_lesson_name, stable_sha256
from ui.models import (
    ArtifactSnapshot,
    DashboardRow,
    ProjectRecord,
    RUN_STATUS_FAILED,
    RUN_STATUS_QUEUED,
    RUN_STATUS_RUNNING,
    RUN_STATUS_SUCCEEDED,
    RUN_STATUS_WAITING_REMOTE,
    RunRecord,
)
from ui.settings import UISettings
from ui.storage import UIStateStore


VIDEO_EXTENSIONS = (".mp4", ".mov", ".mkv", ".webm")


@dataclass(frozen=True)
class DashboardPage:
    rows: list[DashboardRow]
    total_rows: int
    page: int
    total_pages: int
    status_counts: dict[str, int]


def _row_to_project(row: dict) -> ProjectRecord:
    return ProjectRecord(
        project_id=str(row["project_id"]),
        slug=str(row["slug"]),
        title=str(row["title"]),
        lesson_name=str(row["lesson_name"]),
        project_root=Path(row["project_root"]),
        source_video_path=None if not row.get("source_video_path") else Path(str(row["source_video_path"])),
        transcript_path=None if not row.get("transcript_path") else Path(str(row["transcript_path"])),
        status=str(row["status"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def _row_to_run(row: dict | None) -> RunRecord | None:
    if row is None:
        return None
    return RunRecord(
        run_id=str(row["run_id"]),
        project_id=str(row["project_id"]),
        run_mode=str(row["run_mode"]),
        status=str(row["status"]),
        log_path=None if not row.get("log_path") else Path(str(row["log_path"])),
        remote_job_name=row.get("remote_job_name"),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def resolve_path(settings: UISettings, raw_path: str | None) -> Path | None:
    value = str(raw_path or "").strip()
    if not value:
        return None
    path = Path(value)
    if not path.is_absolute():
        path = settings.project_root / path
    return path.resolve()


def _pick_matching_file(root: Path, names: Iterable[str]) -> Path | None:
    for name in names:
        candidate = root / name
        if candidate.exists():
            return candidate
    return None


def detect_transcript(project_root: Path, requested: Path | None, title: str) -> Path | None:
    if requested is not None:
        return requested
    preferred = _pick_matching_file(project_root, [f"{title}.vtt", f"{project_root.name}.vtt"])
    if preferred is not None:
        return preferred
    transcripts = sorted(project_root.glob("*.vtt"))
    return transcripts[0] if transcripts else None


def detect_video(project_root: Path, requested: Path | None) -> Path | None:
    if requested is not None:
        return requested
    for ext in VIDEO_EXTENSIONS:
        matches = sorted(project_root.glob(f"*{ext}"))
        if matches:
            return matches[0]
    return None


def inspect_artifacts(project_root: Path, lesson_name: str, transcript_path: Path | None, video_path: Path | None) -> ArtifactSnapshot:
    paths = PipelinePaths(video_root=project_root)
    return ArtifactSnapshot(
        transcript_exists=bool(transcript_path and transcript_path.exists()),
        video_exists=bool(video_path and video_path.exists()),
        filtered_visuals_exists=paths.filtered_visuals_path.exists(),
        dense_analysis_exists=(project_root / "dense_analysis.json").exists(),
        knowledge_events_exists=paths.knowledge_events_path(lesson_name).exists(),
        rule_cards_exists=paths.rule_cards_path(lesson_name).exists(),
        evidence_index_exists=paths.evidence_index_path(lesson_name).exists(),
        concept_graph_exists=paths.concept_graph_path(lesson_name).exists(),
        review_markdown_exists=paths.review_markdown_path(lesson_name).exists(),
        rag_ready_exists=(
            paths.rag_ready_export_path(lesson_name).exists()
            or paths.rag_ready_markdown_path(lesson_name).exists()
        ),
        export_manifest_exists=paths.export_manifest_path(lesson_name).exists(),
    )


def derive_effective_status(artifacts: ArtifactSnapshot, latest_run: RunRecord | None) -> str:
    if latest_run is not None:
        if latest_run.status == RUN_STATUS_WAITING_REMOTE:
            return "waiting_for_remote"
        if latest_run.status in {RUN_STATUS_QUEUED, RUN_STATUS_RUNNING}:
            if "batch" in latest_run.run_mode:
                return "running_batch"
            return "running_sync"
        if latest_run.status == RUN_STATUS_FAILED:
            return "failed"
        if latest_run.status == RUN_STATUS_SUCCEEDED and artifacts.corpus_ready and artifacts.exports_ready:
            return "complete"

    if not artifacts.transcript_exists:
        return "missing_inputs"
    if artifacts.corpus_ready and artifacts.exports_ready:
        return "complete"
    if artifacts.corpus_ready:
        return "ready_for_corpus"
    if artifacts.dense_analysis_exists and not artifacts.knowledge_events_exists:
        return "ready_for_knowledge_extract"
    if artifacts.transcript_exists:
        return "ready_to_run"
    return "new"


def derive_next_action(artifacts: ArtifactSnapshot, latest_run: RunRecord | None, effective_status: str) -> str:
    if effective_status == "missing_inputs":
        return "Add transcript"
    if effective_status == "waiting_for_remote":
        return "Reconcile remote batch"
    if effective_status == "failed":
        return "Inspect logs and retry"
    if effective_status == "running_batch":
        return "Monitor batch progress"
    if effective_status == "running_sync":
        return "Monitor sync run"
    if effective_status == "ready_for_corpus":
        return "Build corpus"
    if effective_status == "complete":
        return "Review outputs"
    if artifacts.dense_analysis_exists and not artifacts.knowledge_events_exists:
        return "Run knowledge extract"
    if artifacts.transcript_exists and not artifacts.dense_analysis_exists:
        return "Run sync or batch vision"
    if artifacts.transcript_exists and artifacts.knowledge_events_exists and not artifacts.exports_ready:
        return "Run post-process"
    if latest_run is not None and latest_run.status == RUN_STATUS_SUCCEEDED:
        return "Refresh project"
    return "Inspect project"


def make_project_id(project_root: Path, title: str) -> str:
    slug = slugify_lesson_name(title or project_root.name)
    digest = stable_sha256(str(project_root.resolve()))[:8]
    return f"{slug}-{digest}"


def import_project(
    store: UIStateStore,
    settings: UISettings,
    *,
    title: str,
    project_root_raw: str | None,
    source_video_raw: str | None,
    transcript_raw: str | None,
) -> ProjectRecord:
    normalized_title = str(title or "").strip()
    if not normalized_title and not str(project_root_raw or "").strip():
        raise ValueError("Provide a project title or project root.")

    project_root = resolve_path(settings, project_root_raw)
    if project_root is None:
        project_root = (settings.data_root / normalized_title).resolve()
    project_root.mkdir(parents=True, exist_ok=True)

    source_video_path = detect_video(project_root, resolve_path(settings, source_video_raw))
    transcript_path = detect_transcript(project_root, resolve_path(settings, transcript_raw), normalized_title or project_root.name)
    lesson_name = transcript_path.stem if transcript_path is not None else (normalized_title or project_root.name)
    final_title = normalized_title or lesson_name
    artifacts = inspect_artifacts(project_root, lesson_name, transcript_path, source_video_path)
    effective_status = derive_effective_status(artifacts, latest_run=None)
    row = store.upsert_project(
        project_id=make_project_id(project_root, final_title),
        slug=slugify_lesson_name(final_title),
        title=final_title,
        lesson_name=lesson_name,
        project_root=project_root,
        source_video_path=source_video_path,
        transcript_path=transcript_path,
        status=effective_status,
    )
    return _row_to_project(row)


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
        filtered_rows = sorted(filtered_rows, key=lambda row: (row.project.title.lower(), row.updated_at), reverse=False)
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
    runs = [_row_to_run(entry) for entry in store.list_runs(project_id=project_id)]
    return dashboard_row, [run for run in runs if run is not None]

