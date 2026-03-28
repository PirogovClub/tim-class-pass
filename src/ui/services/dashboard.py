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
from ui.services.stages import get_stage_label
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
        source_mode=str(row.get("source_mode") or "upload"),
        source_url=None if not row.get("source_url") else str(row["source_url"]),
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
        force_overwrite=bool(row.get("force_overwrite")),
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
        next_action=derive_next_action(artifacts, latest_run, effective_status, project=project),
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
    if current_stage == "download":
        return {"step0"}
    if current_stage == "prepare_dense_capture":
        return {"step1"}
    if current_stage == "prepare_structural_compare":
        return {"step1_5"}
    if current_stage == "prepare_llm_queue":
        return {"step1_6"}
    if current_stage == "prepare_llm_prompts":
        return {"step1_7"}
    if current_stage in {"vision_sync", "vision_submit", "vision_remote"}:
        return {"step2"}
    if current_stage in {"knowledge_submit", "knowledge_remote", "component2", "postprocess"}:
        return {"step3"}
    if current_stage == "corpus":
        return {"corpus"}
    return set()


def _current_stage_label(latest_run: RunRecord | None) -> str | None:
    if latest_run is None or not latest_run.current_stage:
        return None
    return get_stage_label(latest_run.current_stage)


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
    project = row.project
    if latest_run is not None and latest_run.is_active:
        if latest_run.status == "WAITING_REMOTE":
            return ([], "A remote batch is already in progress. Use Reconcile now or wait for the automatic reconcile loop.")
        return ([], "A project run is already active. Let it finish or cancel it before starting another stage.")
    if project.source_url and (not artifacts.video_exists or not artifacts.transcript_exists):
        return (
            ["download_only", "run_all_local", "run_all_batch"],
            "This project starts from a URL. Run Step 0 download first, or use one of the full run-all actions to download and continue automatically.",
        )
    if not artifacts.transcript_exists:
        return ([], "Add a transcript first. The analysis stages cannot continue without a transcript file in the project folder.")
    if not artifacts.video_exists and not artifacts.dense_index_exists and not artifacts.dense_analysis_exists:
        return ([], "Add a source video first. The prepare stages cannot start until the project has video input or previously generated artifacts.")
    if not artifacts.dense_index_exists:
        return (
            ["prepare_dense_capture", "prepare_project", "run_all_local", "run_all_batch"],
            "Start with Step 1 dense capture so the project gets `dense_index.json` and frame files.",
        )
    if not artifacts.structural_index_exists:
        return (
            ["prepare_structural_compare", "prepare_project", "run_all_local", "run_all_batch"],
            "Step 1 is complete. Run Step 1.5 structural compare next so the UI can build the filtered frame queue.",
        )
    if not artifacts.queue_manifest_exists:
        return (
            ["prepare_llm_queue", "prepare_project", "run_all_local", "run_all_batch"],
            "Run Step 1.6 queue build next so the project gets `llm_queue/manifest.json`.",
        )
    if not artifacts.prompt_files_exist:
        return (
            ["prepare_llm_prompts", "prepare_project", "run_all_local", "run_all_batch"],
            "Run Step 1.7 prompt build next so the queued frames also get prompt files.",
        )
    if not artifacts.dense_analysis_exists:
        return (
            ["sync_full", "batch_full", "batch_vision_only", "run_all_local", "run_all_batch"],
            "Preparation is complete. Run Step 2 locally with `sync_full`, submit only remote vision with `batch_vision_only`, or use one of the grouped full flows.",
        )
    if not artifacts.corpus_ready:
        if artifacts.knowledge_events_exists:
            return (
                ["deterministic_postprocess_only", "sync_full"],
                "Step 3 is partially complete. Rebuild the downstream exports with `deterministic_postprocess_only`, or rerun the local completion path with `sync_full`.",
            )
        return (
            ["batch_knowledge_only", "sync_full", "batch_full"],
            "Dense analysis is ready. The next step is Step 3 knowledge extraction and export generation.",
        )
    if not artifacts.exports_ready:
        return (
            ["deterministic_postprocess_only", "sync_full"],
            "Knowledge artifacts are ready. Run deterministic post-processing to generate review and RAG-ready export files.",
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

    step0_status = "done"
    if "step0" in active_keys:
        step0_status = "running"
    elif project.source_url and (not artifacts.video_exists or not artifacts.transcript_exists):
        step0_status = "ready"
    step0_summary = "Download is optional because this project already starts from local files."
    if project.source_url and step0_status == "done":
        step0_summary = "Download source files are already present in the project folder."
    elif step0_status == "running":
        step0_summary = "Downloading source assets into the project folder now."
    elif project.source_url:
        step0_summary = "Run Step 0 to download the project video and transcript from the configured source URL."

    step1_status = "done" if artifacts.dense_index_exists else "blocked"
    if "step1" in active_keys:
        step1_status = "running"
    elif artifacts.video_exists and not artifacts.dense_index_exists:
        step1_status = "ready"
    step1_summary = "Dense capture already produced `dense_index.json` and extracted frame files." if step1_status == "done" else "Run dense capture to extract project frames and write `dense_index.json`."
    if step1_status == "running":
        step1_summary = "Dense frame capture is running."
    elif step1_status == "ready":
        step1_summary = "The project has a source video, so Step 1 can run now."
    elif project.source_url and not artifacts.video_exists:
        step1_summary = "Step 1 is blocked until Step 0 download finishes and the source video is present."
    elif not artifacts.video_exists:
        step1_summary = "Step 1 is blocked until the project has a source video."

    step15_status = "done" if artifacts.structural_index_exists else "blocked"
    if "step1_5" in active_keys:
        step15_status = "running"
    elif artifacts.dense_index_exists and not artifacts.structural_index_exists:
        step15_status = "ready"
    step15_summary = "Structural compare already wrote `structural_index.json`." if step15_status == "done" else "Run structural compare to annotate frame-to-frame differences."
    if step15_status == "running":
        step15_summary = "Structural compare is running."
    elif step15_status == "ready":
        step15_summary = "Step 1 is complete, so structural compare can run now."
    elif not artifacts.dense_index_exists:
        step15_summary = "Step 1.5 is blocked until Step 1 dense capture completes."

    step16_status = "done" if artifacts.queue_manifest_exists else "blocked"
    if "step1_6" in active_keys:
        step16_status = "running"
    elif artifacts.structural_index_exists and not artifacts.queue_manifest_exists:
        step16_status = "ready"
    step16_summary = "The project already has `llm_queue/manifest.json`." if step16_status == "done" else "Build the Step 1.6 LLM queue from the structural compare output."
    if step16_status == "running":
        step16_summary = "LLM queue selection is running."
    elif step16_status == "ready":
        step16_summary = "Structural compare is complete, so the queue can be built now."
    elif not artifacts.structural_index_exists:
        step16_summary = "Step 1.6 is blocked until Step 1.5 structural compare completes."

    step17_status = "done" if artifacts.prompt_files_exist else "blocked"
    if "step1_7" in active_keys:
        step17_status = "running"
    elif artifacts.queue_manifest_exists and not artifacts.prompt_files_exist:
        step17_status = "ready"
    step17_summary = "Prompt files already exist for queued frames." if step17_status == "done" else "Run Step 1.7 to create per-frame prompt files from the queue manifest."
    if step17_status == "running":
        step17_summary = "Prompt generation is running."
    elif step17_status == "ready":
        step17_summary = "The queue manifest exists, so prompt files can be generated now."
    elif not artifacts.queue_manifest_exists:
        step17_summary = "Step 1.7 is blocked until Step 1.6 queue build completes."

    step2_status = "done" if artifacts.dense_analysis_exists else "blocked"
    if "step2" in active_keys:
        step2_status = "running"
    elif artifacts.transcript_exists and artifacts.dense_index_exists and artifacts.queue_manifest_exists and not artifacts.dense_analysis_exists:
        step2_status = "ready"
    step2_summary = "Dense analysis is already present in the project folder." if step2_status == "done" else "Run Step 2 vision analysis locally or through Gemini batch."
    if step2_status == "running":
        step2_summary = "Step 2 vision analysis is active or waiting for remote batch completion."
    elif step2_status == "ready":
        step2_summary = "The project has the queue and transcript needed for Step 2."
    elif not artifacts.transcript_exists:
        step2_summary = "Step 2 is blocked until the project has a transcript."
    elif not artifacts.dense_index_exists or not artifacts.queue_manifest_exists:
        step2_summary = "Step 2 is blocked until dense capture and queue build outputs exist."

    step3_status = "done" if artifacts.corpus_ready and artifacts.exports_ready else "blocked"
    if "step3" in active_keys:
        step3_status = "running"
    elif artifacts.transcript_exists and artifacts.dense_analysis_exists and not (artifacts.corpus_ready and artifacts.exports_ready):
        step3_status = "ready"
    step3_summary = "Knowledge artifacts and exports are complete." if step3_status == "done" else "Run Step 3 to generate knowledge artifacts and exports from dense analysis."
    if step3_status == "running":
        step3_summary = "Step 3 knowledge extraction or export generation is running."
    elif step3_status == "ready" and artifacts.knowledge_events_exists:
        step3_summary = "Step 3 is partially complete. Finish the remaining deterministic exports or rerun the completion path."
    elif step3_status == "ready":
        step3_summary = "Dense analysis is ready. Step 3 can now build knowledge events, graphs, and exports."
    elif not artifacts.dense_analysis_exists:
        step3_summary = "Step 3 is blocked until Step 2 dense analysis exists."

    def check(label: str, done: bool, path_hint: str | None = None) -> ProjectFlowCheck:
        return ProjectFlowCheck(label=label, done=done, path_hint=path_hint)

    stages = [
        ProjectFlowStage(
            key="step0",
            title="Step 0. Download",
            status=step0_status,
            status_label=FLOW_STATUS_LABELS[step0_status],
            summary=step0_summary,
            checks=[
                check("Source URL configured", bool(project.source_url), project.source_url),
                check("Transcript (.vtt)", artifacts.transcript_exists, _relative_to_project(project.project_root, project.transcript_path)),
                check("Source video", artifacts.video_exists, _relative_to_project(project.project_root, project.source_video_path)),
            ],
            suggested_run_modes=["download_only"] if project.source_url else [],
        ),
        ProjectFlowStage(
            key="step1",
            title="Step 1. Dense Capture",
            status=step1_status,
            status_label=FLOW_STATUS_LABELS[step1_status],
            summary=step1_summary,
            checks=[
                check("Source video", artifacts.video_exists, _relative_to_project(project.project_root, project.source_video_path)),
                check("dense_index.json", artifacts.dense_index_exists, "dense_index.json"),
            ],
            suggested_run_modes=["prepare_dense_capture"] if step1_status == "ready" else [],
        ),
        ProjectFlowStage(
            key="step1_5",
            title="Step 1.5. Structural Compare",
            status=step15_status,
            status_label=FLOW_STATUS_LABELS[step15_status],
            summary=step15_summary,
            checks=[
                check("dense_index.json", artifacts.dense_index_exists, "dense_index.json"),
                check("structural_index.json", artifacts.structural_index_exists, "structural_index.json"),
            ],
            suggested_run_modes=["prepare_structural_compare"] if step15_status == "ready" else [],
        ),
        ProjectFlowStage(
            key="step1_6",
            title="Step 1.6. Queue Build",
            status=step16_status,
            status_label=FLOW_STATUS_LABELS[step16_status],
            summary=step16_summary,
            checks=[
                check("structural_index.json", artifacts.structural_index_exists, "structural_index.json"),
                check("llm_queue/manifest.json", artifacts.queue_manifest_exists, "llm_queue/manifest.json"),
            ],
            suggested_run_modes=["prepare_llm_queue"] if step16_status == "ready" else [],
        ),
        ProjectFlowStage(
            key="step1_7",
            title="Step 1.7. Prompt Build",
            status=step17_status,
            status_label=FLOW_STATUS_LABELS[step17_status],
            summary=step17_summary,
            checks=[
                check("llm_queue/manifest.json", artifacts.queue_manifest_exists, "llm_queue/manifest.json"),
                check("Prompt files", artifacts.prompt_files_exist, "llm_queue/*_prompt.txt"),
            ],
            suggested_run_modes=["prepare_llm_prompts"] if step17_status == "ready" else [],
        ),
        ProjectFlowStage(
            key="step2",
            title="Step 2. Vision Analysis",
            status=step2_status,
            status_label=FLOW_STATUS_LABELS[step2_status],
            summary=step2_summary,
            checks=[
                check("Transcript (.vtt)", artifacts.transcript_exists, _relative_to_project(project.project_root, project.transcript_path)),
                check("dense_index.json", artifacts.dense_index_exists, "dense_index.json"),
                check("llm_queue/manifest.json", artifacts.queue_manifest_exists, "llm_queue/manifest.json"),
                check("dense_analysis.json", artifacts.dense_analysis_exists, "dense_analysis.json"),
            ],
            suggested_run_modes=["sync_full", "batch_vision_only", "batch_full"] if step2_status == "ready" else [],
        ),
        ProjectFlowStage(
            key="step3",
            title="Step 3. Component 2 And Exports",
            status=step3_status,
            status_label=FLOW_STATUS_LABELS[step3_status],
            summary=step3_summary,
            checks=[
                check("Knowledge events", artifacts.knowledge_events_exists),
                check("Rule cards", artifacts.rule_cards_exists),
                check("Evidence index", artifacts.evidence_index_exists),
                check("Concept graph", artifacts.concept_graph_exists),
                check("Review markdown", artifacts.review_markdown_exists),
                check("RAG-ready output", artifacts.rag_ready_exists),
            ],
            suggested_run_modes=(
                ["deterministic_postprocess_only", "sync_full"]
                if step3_status == "ready" and artifacts.knowledge_events_exists
                else ["batch_knowledge_only", "sync_full", "batch_full"] if step3_status == "ready" else []
            ),
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

