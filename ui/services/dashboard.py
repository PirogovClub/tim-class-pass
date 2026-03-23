from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ui.models import (
    CorpusQueueRow,
    DashboardRow,
    ProjectFlowCheck,
    ProjectFlowGuide,
    ProjectFlowStage,
    ProjectRecord,
    RunRecord,
)
from ui.services.projects import derive_effective_status, derive_next_action, inspect_artifacts, inspect_run_prerequisites
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


FLOW_STATUS_LABELS = {
    "done": "Done",
    "running": "Running",
    "ready": "Ready",
    "blocked": "Blocked",
    "missing": "Missing",
}


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


def _relative_to_project(project_root: Path, path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return path.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _active_flow_stage_keys(latest_run: RunRecord | None) -> set[str]:
    if latest_run is None or not latest_run.is_active:
        return set()
    current_stage = str(latest_run.current_stage or "")
    if current_stage in {"vision_sync", "vision_submit", "vision_remote"}:
        return {"vision"}
    if current_stage in {"knowledge_submit", "knowledge_remote"}:
        return {"knowledge"}
    if current_stage == "component2":
        return {"knowledge", "exports"}
    if current_stage == "postprocess":
        return {"exports"}
    if current_stage == "corpus":
        return {"corpus"}
    return set()


def _current_stage_label(latest_run: RunRecord | None) -> str | None:
    if latest_run is None or not latest_run.current_stage:
        return None
    labels = {
        "vision_sync": "Vision sync",
        "vision_submit": "Vision batch submit",
        "vision_remote": "Vision remote wait",
        "knowledge_submit": "Knowledge batch submit",
        "knowledge_remote": "Knowledge remote wait",
        "component2": "Component 2",
        "postprocess": "Post-process",
        "corpus": "Corpus",
    }
    return labels.get(latest_run.current_stage, latest_run.current_stage.replace("_", " "))


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


def _recommend_run_modes(row: DashboardRow, prerequisites: dict[str, bool], corpus_status: str) -> tuple[list[str], str]:
    artifacts = row.artifacts
    latest_run = row.latest_run
    if latest_run is not None and latest_run.is_active:
        if latest_run.status == "WAITING_REMOTE":
            return ([], "A remote batch is already in progress. Use Reconcile now or wait for the automatic reconcile loop.")
        return ([], "A project run is already active. Let it finish or cancel it before starting another stage.")
    if not artifacts.transcript_exists:
        return ([], "Add a transcript first. No project run can start without a transcript file in the folder.")
    if not artifacts.dense_analysis_exists:
        missing_inputs = []
        if not prerequisites["has_dense_index"]:
            missing_inputs.append("dense_index.json")
        if not prerequisites["has_queue_manifest"]:
            missing_inputs.append("llm_queue/manifest.json")
        if missing_inputs:
            missing_text = ", ".join(missing_inputs)
            return ([], f"Prepare the vision inputs first. This project is still missing {missing_text}.")
        return (
            ["sync_full", "batch_full", "batch_vision_only"],
            "Start with the vision stage. `sync_full` goes local end-to-end, `batch_full` follows the remote batch path, and `batch_vision_only` stops after dense analysis.",
        )
    if not artifacts.corpus_ready:
        if artifacts.knowledge_events_exists:
            return (
                ["deterministic_postprocess_only", "sync_full"],
                "Knowledge extraction is partially present. Rebuild the downstream derived files with `deterministic_postprocess_only`, or rerun the local end-to-end path with `sync_full`.",
            )
        return (
            ["batch_knowledge_only", "sync_full", "batch_full"],
            "Dense analysis is ready. The next stage is knowledge extraction. Use `batch_knowledge_only` for a remote batch, `sync_full` for local completion, or `batch_full` to stay on the remote path.",
        )
    if not artifacts.exports_ready:
        return (
            ["deterministic_postprocess_only", "sync_full"],
            "Knowledge artifacts are ready. Run deterministic post-processing to generate review and RAG export files.",
        )
    if corpus_status in {"ready", "stale_since_last_export"}:
        return (["corpus_only"], "Project outputs are complete. The optional next step is adding this project to a corpus build.")
    if corpus_status == "running":
        return ([], "A corpus build that includes this project is already running.")
    return ([], "Project outputs are complete. Review the exported files or include the project in a future corpus build when needed.")


def _build_project_flow(store: UIStateStore, row: DashboardRow) -> ProjectFlowGuide:
    project = row.project
    artifacts = row.artifacts
    latest_run = row.latest_run
    active_keys = _active_flow_stage_keys(latest_run)
    prerequisites = inspect_run_prerequisites(project)
    corpus_status, latest_corpus_run = _corpus_status_for_project(store, project, artifacts)
    recommended_run_modes, recommendation_summary = _recommend_run_modes(row, prerequisites, corpus_status)

    inputs_status = "done" if artifacts.transcript_exists and (artifacts.video_exists or artifacts.dense_analysis_exists) else "missing"
    if artifacts.transcript_exists and not artifacts.video_exists and not artifacts.dense_analysis_exists:
        inputs_status = "blocked"
    inputs_summary = "Transcript and source assets are present." if inputs_status == "done" else "Add a transcript and either the source video or precomputed dense analysis before processing can continue."
    if artifacts.transcript_exists and not artifacts.video_exists and artifacts.dense_analysis_exists:
        inputs_summary = "Transcript is present and dense analysis already exists, so the remaining stages can continue without the original video file."
    elif artifacts.transcript_exists and not artifacts.video_exists:
        inputs_summary = "Transcript exists, but the project folder does not contain a source video yet."

    vision_status = "done" if artifacts.dense_analysis_exists else "blocked"
    if "vision" in active_keys:
        vision_status = "running"
    elif not artifacts.dense_analysis_exists and prerequisites["has_transcript"] and prerequisites["has_dense_index"] and prerequisites["has_queue_manifest"]:
        vision_status = "ready"
    vision_summary = "Dense analysis is already present in the project folder." if vision_status == "done" else "Prepare or run the vision stage to produce dense analysis."
    if vision_status == "running":
        vision_summary = "Vision processing is currently active or waiting on the remote provider."
    elif vision_status == "ready":
        vision_summary = "Vision can run now because the project has the queue manifest and dense index needed for processing."
    elif not prerequisites["has_transcript"]:
        vision_summary = "Vision is blocked until a transcript is added."
    elif not prerequisites["has_dense_index"] or not prerequisites["has_queue_manifest"]:
        vision_summary = "Vision is blocked until `dense_index.json` and `llm_queue/manifest.json` exist in the project folder."

    knowledge_status = "done" if artifacts.corpus_ready else "blocked"
    if "knowledge" in active_keys:
        knowledge_status = "running"
    elif artifacts.transcript_exists and artifacts.dense_analysis_exists and not artifacts.corpus_ready:
        knowledge_status = "ready"
    knowledge_summary = "Knowledge artifacts are complete." if knowledge_status == "done" else "Run knowledge extraction after dense analysis is available."
    if knowledge_status == "running":
        knowledge_summary = "Knowledge extraction is currently active or waiting on a remote batch."
    elif knowledge_status == "ready" and artifacts.knowledge_events_exists:
        knowledge_summary = "Some knowledge files already exist, but the stage is incomplete. Finish or rebuild the remaining derived artifacts."
    elif knowledge_status == "ready":
        knowledge_summary = "Dense analysis is ready. The next stage is generating knowledge events and derived graph artifacts."
    elif not artifacts.transcript_exists:
        knowledge_summary = "Knowledge extraction is blocked until a transcript is added."
    elif not artifacts.dense_analysis_exists:
        knowledge_summary = "Knowledge extraction is blocked until the vision stage produces dense analysis."

    exports_status = "done" if artifacts.exports_ready else "blocked"
    if "exports" in active_keys:
        exports_status = "running"
    elif artifacts.corpus_ready and not artifacts.exports_ready:
        exports_status = "ready"
    exports_summary = "Review markdown and RAG-ready exports are already available." if exports_status == "done" else "Exports are generated after knowledge artifacts are complete."
    if exports_status == "running":
        exports_summary = "Export generation is currently running."
    elif exports_status == "ready":
        exports_summary = "Knowledge artifacts are present. Run deterministic post-processing to generate review and RAG outputs."
    elif not artifacts.corpus_ready:
        exports_summary = "Exports are blocked until the knowledge stage is complete."

    corpus_stage_status = "blocked"
    if corpus_status == "exported":
        corpus_stage_status = "done"
    elif corpus_status == "running":
        corpus_stage_status = "running"
    elif corpus_status in {"ready", "stale_since_last_export"}:
        corpus_stage_status = "ready"
    corpus_summary = "Corpus build is optional and combines this project with other ready projects." if corpus_stage_status != "done" else "This project has already been included in a successful corpus build."
    if corpus_stage_status == "running":
        corpus_summary = "A corpus build that includes this project is currently in progress."
    elif corpus_status == "stale_since_last_export":
        corpus_summary = "Corpus was built before, but the project changed afterward. Rebuild the corpus when you are ready."
    elif corpus_stage_status == "ready":
        corpus_summary = "Project outputs are ready. Use the corpus queue or `corpus_only` to include it in a corpus export."
    elif corpus_stage_status == "blocked":
        corpus_summary = "Corpus build stays blocked until the knowledge stage is complete."

    def check(label: str, done: bool, path_hint: str | None = None) -> ProjectFlowCheck:
        return ProjectFlowCheck(label=label, done=done, path_hint=path_hint)

    stages = [
        ProjectFlowStage(
            key="inputs",
            title="1. Inputs",
            status=inputs_status,
            status_label=FLOW_STATUS_LABELS[inputs_status],
            summary=inputs_summary,
            checks=[
                check("Transcript (.vtt)", artifacts.transcript_exists, _relative_to_project(project.project_root, project.transcript_path)),
                check("Source video", artifacts.video_exists, _relative_to_project(project.project_root, project.source_video_path)),
            ],
            suggested_run_modes=[],
        ),
        ProjectFlowStage(
            key="vision",
            title="2. Vision",
            status=vision_status,
            status_label=FLOW_STATUS_LABELS[vision_status],
            summary=vision_summary,
            checks=[
                check("dense_index.json", prerequisites["has_dense_index"], "dense_index.json"),
                check("llm_queue/manifest.json", prerequisites["has_queue_manifest"], "llm_queue/manifest.json"),
                check("dense_analysis.json", artifacts.dense_analysis_exists, "dense_analysis.json"),
            ],
            suggested_run_modes=["sync_full", "batch_full", "batch_vision_only"] if vision_status == "ready" else [],
        ),
        ProjectFlowStage(
            key="knowledge",
            title="3. Knowledge",
            status=knowledge_status,
            status_label=FLOW_STATUS_LABELS[knowledge_status],
            summary=knowledge_summary,
            checks=[
                check("Knowledge events", artifacts.knowledge_events_exists),
                check("Rule cards", artifacts.rule_cards_exists),
                check("Evidence index", artifacts.evidence_index_exists),
                check("Concept graph", artifacts.concept_graph_exists),
            ],
            suggested_run_modes=(
                ["deterministic_postprocess_only", "sync_full"]
                if knowledge_status == "ready" and artifacts.knowledge_events_exists
                else ["batch_knowledge_only", "sync_full", "batch_full"] if knowledge_status == "ready" else []
            ),
        ),
        ProjectFlowStage(
            key="exports",
            title="4. Exports",
            status=exports_status,
            status_label=FLOW_STATUS_LABELS[exports_status],
            summary=exports_summary,
            checks=[
                check("Review markdown", artifacts.review_markdown_exists),
                check("RAG-ready output", artifacts.rag_ready_exists),
                check("Export manifest", artifacts.export_manifest_exists),
            ],
            suggested_run_modes=["deterministic_postprocess_only", "sync_full"] if exports_status == "ready" else [],
        ),
        ProjectFlowStage(
            key="corpus",
            title="5. Corpus",
            status=corpus_stage_status,
            status_label=FLOW_STATUS_LABELS[corpus_stage_status],
            summary=corpus_summary,
            checks=[
                check("Knowledge stage complete", artifacts.corpus_ready),
                check("Exports ready", artifacts.exports_ready),
                check("Latest corpus run succeeded", latest_corpus_run is not None and latest_corpus_run.status == "SUCCEEDED"),
            ],
            suggested_run_modes=["corpus_only"] if corpus_stage_status == "ready" else [],
        ),
    ]

    return ProjectFlowGuide(
        headline="Pipeline map",
        summary=recommendation_summary,
        current_stage_label=_current_stage_label(latest_run),
        recommended_run_modes=recommended_run_modes,
        stages=stages,
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


def get_project_detail(store: UIStateStore, project_id: str) -> tuple[DashboardRow, list[RunRecord], ProjectFlowGuide]:
    row = store.get_project(project_id)
    if row is None:
        raise KeyError(project_id)
    project = _row_to_project(row)
    dashboard_row = _build_dashboard_row(store, project)
    runs = [_row_to_run(entry) for entry in store.get_runs_for_target(project_id)]
    filtered_runs = [run for run in runs if run is not None]
    return dashboard_row, filtered_runs, _build_project_flow(store, dashboard_row)


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

