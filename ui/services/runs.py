from __future__ import annotations

from pathlib import Path

from ui.models import ProjectRecord, RunEventRecord, RunRecord
from ui.services.dashboard import _row_to_project, _row_to_run
from ui.services.projects import inspect_artifacts, inspect_run_prerequisites
from ui.settings import UISettings
from ui.storage import UIStateStore


SUPPORTED_RUN_MODES = [
    "sync_full",
    "batch_vision_only",
    "batch_knowledge_only",
    "batch_full",
    "deterministic_postprocess_only",
    "corpus_only",
]

RUN_MODE_DETAILS = {
    "sync_full": {
        "title": "Full local pipeline",
        "summary": "Runs the whole single-project pipeline in one background worker without waiting for remote batch completion.",
        "when_to_use": "Use this when you want the fastest operator path for one project and the machine can do the vision step locally.",
        "steps": [
            "Run sync visual analysis if dense analysis is missing.",
            "Run component 2 extraction, evidence linking, graph building, and export generation.",
            "Refresh the project artifacts in the dashboard when processing finishes.",
        ],
        "outputs": "Expected outputs include dense analysis, intermediate exports, review markdown, and RAG-ready artifacts.",
    },
    "batch_vision_only": {
        "title": "Remote batch vision only",
        "summary": "Prepares and submits only the vision stage to the batch backend, then leaves the run waiting for remote completion until reconcile resumes it.",
        "when_to_use": "Use this when you only need dense visual analysis or want to split the remote vision stage from the later knowledge stage.",
        "steps": [
            "Build the batch request payloads for the vision stage.",
            "Submit the vision batch job and record the remote job name.",
            "Wait for operator reconcile or scheduled polling to download and materialize results.",
        ],
        "outputs": "Expected outputs are filtered visuals and dense analysis artifacts for the project.",
    },
    "batch_knowledge_only": {
        "title": "Remote batch knowledge only",
        "summary": "Submits only the knowledge extraction batch for a project that already has the required visual inputs.",
        "when_to_use": "Use this when dense analysis already exists and you want only the LLM extraction and materialization stages.",
        "steps": [
            "Build knowledge extraction queue items from the existing project artifacts.",
            "Submit the remote knowledge batch and track its status in the UI database.",
            "Reconcile later to download results, materialize them, and refresh project readiness.",
        ],
        "outputs": "Expected outputs include knowledge events, rule cards, evidence index, concept graph, and review markdown.",
    },
    "batch_full": {
        "title": "Remote batch pipeline",
        "summary": "Runs the batch-backed pipeline for the project, starting from the earliest missing remote stage and continuing through reconcile.",
        "when_to_use": "Use this when you want the operator flow to rely on remote batch processing instead of the fully local sync path.",
        "steps": [
            "If dense analysis is missing, submit the vision batch stage first.",
            "If dense analysis already exists, skip directly to the knowledge batch stage.",
            "Use reconcile to poll, download, materialize, and move the project toward completed exports.",
        ],
        "outputs": "Expected outputs depend on the starting point, but a full successful run should end with the same exported artifacts as the sync path.",
    },
    "deterministic_postprocess_only": {
        "title": "Deterministic post-processing only",
        "summary": "Runs only the non-LLM post-processing and export generation steps against artifacts that already exist in the project folder.",
        "when_to_use": "Use this after you already have the needed raw extraction outputs and want to rebuild downstream files without re-running provider calls.",
        "steps": [
            "Read the already available project artifacts.",
            "Rebuild deterministic outputs such as linked evidence, graphs, manifests, and exports.",
            "Refresh the project record so the dashboard shows the newly rebuilt outputs.",
        ],
        "outputs": "Expected outputs are regenerated downstream exports without creating a new remote job.",
    },
    "corpus_only": {
        "title": "Corpus build",
        "summary": "Builds corpus outputs from one or more ready projects and writes the consolidated corpus artifacts into the configured UI corpus output folder.",
        "when_to_use": "Use this when projects are already export-ready and you want to prepare corpus data for downstream RAG import or review.",
        "steps": [
            "Collect the selected ready project roots.",
            "Run corpus discovery, validation, and export generation.",
            "Write corpus outputs and validation summaries, then record the result in the UI status ledger.",
        ],
        "outputs": "Expected outputs include corpus files, summary metadata, and validation reports under the corpus output directory.",
    },
}


def _run_id_prefix(project_id: str, run_mode: str) -> str:
    safe_mode = run_mode.replace("/", "_")
    return f"{project_id}::{safe_mode}"


def _safe_run_token(run_id: str) -> str:
    return run_id.replace(":", "_").replace("/", "_").replace("\\", "_")


def _next_run_id(store: UIStateStore, project_id: str, run_mode: str) -> str:
    prefix = _run_id_prefix(project_id, run_mode)
    counter = 1
    existing = {row["run_id"] for row in store.list_runs()}
    while True:
        candidate = f"{prefix}::{counter:03d}"
        if candidate not in existing:
            return candidate
        counter += 1


def _initial_stage(run_mode: str, project: ProjectRecord, settings: UISettings) -> str:
    if run_mode == "sync_full":
        if (project.project_root / "dense_analysis.json").exists():
            return "component2"
        return "vision_sync"
    if run_mode == "batch_vision_only":
        return "vision_submit"
    if run_mode == "batch_knowledge_only":
        return "knowledge_submit"
    if run_mode == "batch_full":
        return "vision_submit" if not (project.project_root / "dense_analysis.json").exists() else "knowledge_submit"
    if run_mode == "deterministic_postprocess_only":
        return "postprocess"
    if run_mode == "corpus_only":
        return "corpus"
    raise ValueError(f"Unsupported run mode: {run_mode}")


def create_project_run(
    store: UIStateStore,
    settings: UISettings,
    *,
    project_id: str,
    run_mode: str,
) -> RunRecord:
    if run_mode not in SUPPORTED_RUN_MODES:
        raise ValueError(f"Unsupported run mode: {run_mode}")
    active = store.get_active_run_for_project(project_id)
    if active is not None:
        raise ValueError("This project already has active background work.")
    project_row = store.get_project(project_id)
    if project_row is None:
        raise KeyError(project_id)
    project = _row_to_project(project_row)
    run_id = _next_run_id(store, project_id, run_mode)
    run_token = _safe_run_token(run_id)
    log_path = settings.log_root / f"{run_token}.log"
    pipeline_db_path = settings.pipeline_db_root / f"{run_token}.db"
    row = store.create_run(
        run_id=run_id,
        project_id=project_id,
        run_kind="PROJECT",
        run_mode=run_mode,
        status="QUEUED",
        current_stage=_initial_stage(run_mode, project, settings),
        progress_message="Queued",
        log_path=log_path,
        pipeline_db_path=pipeline_db_path,
        project_root_snapshot=project.project_root,
    )
    store.attach_run_targets(run_id, [project_id])
    store.append_run_event(run_id=run_id, event_type="queued", stage=row.get("current_stage"), message="Run queued.")
    created = _row_to_run(row)
    assert created is not None
    return created


def create_corpus_run(
    store: UIStateStore,
    settings: UISettings,
    *,
    project_ids: list[str],
) -> RunRecord:
    if not project_ids:
        raise ValueError("Select at least one project for corpus build.")
    owner_id = project_ids[0]
    active = store.get_active_run_for_project(owner_id)
    if active is not None and (active.get("run_kind") or "PROJECT") == "CORPUS":
        raise ValueError("A corpus build is already active for the selected set.")
    run_id = _next_run_id(store, owner_id, "corpus_only")
    row = store.create_run(
        run_id=run_id,
        project_id=owner_id,
        run_kind="CORPUS",
        run_mode="corpus_only",
        status="QUEUED",
        current_stage="corpus",
        progress_message="Queued corpus build.",
        log_path=settings.log_root / f"{_safe_run_token(run_id)}.log",
        pipeline_db_path=None,
        project_root_snapshot=settings.data_root,
    )
    store.attach_run_targets(run_id, project_ids)
    store.append_run_event(run_id=run_id, event_type="queued", stage="corpus", message="Corpus build queued.")
    created = _row_to_run(row)
    assert created is not None
    return created


def get_run_detail(
    store: UIStateStore,
    run_id: str,
) -> tuple[RunRecord, ProjectRecord | None, list[RunEventRecord], list[ProjectRecord]]:
    run_row = store.get_run(run_id)
    if run_row is None:
        raise KeyError(run_id)
    run = _row_to_run(run_row)
    assert run is not None
    owner_project = None
    project_row = store.get_project(run.project_id)
    if project_row is not None:
        owner_project = _row_to_project(project_row)
    events = []
    for row in store.list_run_events(run_id):
        events.append(
            RunEventRecord(
                event_id=int(row["event_id"]),
                run_id=str(row["run_id"]),
                event_type=str(row["event_type"]),
                stage=row.get("stage"),
                message=str(row["message"]),
                created_at=str(row["created_at"]),
            )
        )
    targets = []
    for project_id in store.list_run_targets(run_id):
        row = store.get_project(project_id)
        if row is not None:
            targets.append(_row_to_project(row))
    return (run, owner_project, events, targets)


def validate_run_prerequisites(project: ProjectRecord) -> dict[str, bool]:
    return inspect_run_prerequisites(project)

