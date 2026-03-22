from __future__ import annotations

from pathlib import Path

from ui.models import ProjectRecord, RunEventRecord, RunRecord
from ui.services.dashboard import _row_to_project, _row_to_run
from ui.services.projects import inspect_artifacts
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
    artifacts = inspect_artifacts(
        project.project_root,
        project.lesson_name,
        project.transcript_path,
        project.source_video_path,
    )
    return {
        "has_transcript": artifacts.transcript_exists,
        "has_dense_analysis": artifacts.dense_analysis_exists,
        "has_queue_manifest": (project.project_root / "llm_queue" / "manifest.json").exists(),
        "has_dense_index": (project.project_root / "dense_index.json").exists(),
        "corpus_ready": artifacts.corpus_ready,
    }

