from __future__ import annotations

from pathlib import Path

from ui.models import ProjectRecord, RunEventRecord, RunRecord
from ui.services.dashboard import _row_to_project, _row_to_run
from ui.services.projects import inspect_artifacts, inspect_run_prerequisites, refresh_project_record
from ui.settings import UISettings
from ui.storage import UIStateStore


SUPPORTED_RUN_MODES = [
    "download_only",
    "prepare_dense_capture",
    "prepare_structural_compare",
    "prepare_llm_queue",
    "prepare_llm_prompts",
    "prepare_project",
    "sync_full",
    "batch_vision_only",
    "batch_knowledge_only",
    "batch_full",
    "run_all_local",
    "run_all_batch",
    "deterministic_postprocess_only",
    "corpus_only",
]

RUN_MODE_DETAILS = {
    "download_only": {
        "title": "Step 0 download",
        "summary": "Downloads the project video and transcript from the configured source URL into the project folder.",
        "when_to_use": "Use this when the project was created from a URL and the source files are not present yet, or when you need to re-download them.",
        "steps": [
            "Resolve the project URL into its expected video ID folder.",
            "Download the source video and any available VTT transcript files.",
            "Refresh the project record so later UI steps see the downloaded files.",
        ],
        "outputs": "Expected outputs are the source video file and transcript files under the project folder.",
    },
    "prepare_dense_capture": {
        "title": "Step 1 dense capture",
        "summary": "Runs dense frame extraction and writes `dense_index.json` plus the `frames_dense/` directory.",
        "when_to_use": "Use this when the project has a source video but has not started frame preparation yet.",
        "steps": [
            "Read the project video and capture dense frames.",
            "Write extracted frame files into `frames_dense/`.",
            "Write `dense_index.json` so later prep steps can continue.",
        ],
        "outputs": "Expected outputs are `frames_dense/` and `dense_index.json`.",
    },
    "prepare_structural_compare": {
        "title": "Step 1.5 structural compare",
        "summary": "Runs the structural compare step that scores visual differences between dense frames.",
        "when_to_use": "Use this after Step 1 when you need the diff metadata used by queue selection.",
        "steps": [
            "Read the dense frame index.",
            "Compare neighboring frames to calculate material visual differences.",
            "Write `structural_index.json` and update frame diff metadata.",
        ],
        "outputs": "Expected outputs are `structural_index.json` and diff-tagged frame metadata.",
    },
    "prepare_llm_queue": {
        "title": "Step 1.6 queue build",
        "summary": "Builds `llm_queue/manifest.json` and copies the selected frames for Step 2 analysis.",
        "when_to_use": "Use this after structural compare when the project still lacks the LLM queue manifest.",
        "steps": [
            "Select material-change frames from the dense index.",
            "Copy the chosen frame files into `llm_queue/`.",
            "Write `llm_queue/manifest.json`.",
        ],
        "outputs": "Expected outputs are `llm_queue/`, copied frame files, and `llm_queue/manifest.json`.",
    },
    "prepare_llm_prompts": {
        "title": "Step 1.7 prompt build",
        "summary": "Creates one prompt file per queued frame so the project is fully prepared through the CLI prep sequence.",
        "when_to_use": "Use this after Step 1.6 when the project should be fully prepared before Step 2.",
        "steps": [
            "Read `llm_queue/manifest.json`.",
            "Build a prompt text file for each selected frame.",
            "Write `*_prompt.txt` files back into `llm_queue/`.",
        ],
        "outputs": "Expected outputs are per-frame `*_prompt.txt` files in `llm_queue/`.",
    },
    "prepare_project": {
        "title": "Prepare project",
        "summary": "Runs the missing prep stages from Step 1 through Step 1.7 so the project reaches UI parity with the CLI preparation path.",
        "when_to_use": "Use this when a fresh project should be brought to a ready-for-analysis state without manually running each prep step.",
        "steps": [
            "Start from the earliest missing prep artifact.",
            "Run dense capture, structural compare, queue build, and prompt build as needed.",
            "Stop when the project has prompt files and the queue manifest.",
        ],
        "outputs": "Expected outputs are `dense_index.json`, `structural_index.json`, `llm_queue/manifest.json`, and prompt files.",
    },
    "sync_full": {
        "title": "Analyze project locally",
        "summary": "Runs Step 2 locally and then completes Step 3 in one background worker.",
        "when_to_use": "Use this when prep is complete and you want the machine to finish the project without using remote Gemini batch.",
        "steps": [
            "Run Step 2 local visual analysis if dense analysis is missing.",
            "Run Step 3 extraction, evidence linking, graph building, and export generation.",
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
        "title": "Analyze project with batch",
        "summary": "Runs the batch-backed Step 2 and Step 3 path for the project, starting from the earliest missing remote stage and continuing through reconcile.",
        "when_to_use": "Use this when prep is complete and you want Step 2 and Step 3 to follow the remote Gemini batch path.",
        "steps": [
            "If dense analysis is missing, submit the vision batch stage first.",
            "If dense analysis already exists, skip directly to the knowledge batch stage.",
            "Use reconcile to poll, download, materialize, and move the project toward completed exports.",
        ],
        "outputs": "Expected outputs depend on the starting point, but a full successful run should end with the same exported artifacts as the sync path.",
    },
    "run_all_local": {
        "title": "Run all locally",
        "summary": "Starts from the current project state, optionally downloads source files, prepares the project, and then finishes locally through Step 3.",
        "when_to_use": "Use this for the simplest one-click local path from a fresh or partially prepared project.",
        "steps": [
            "Run Step 0 first when the project starts from a URL and source files are still missing.",
            "Run the missing prep stages from Step 1 through Step 1.7.",
            "Run the local Step 2 and Step 3 completion path.",
        ],
        "outputs": "Expected outputs are the full local project outputs from source files through exports.",
    },
    "run_all_batch": {
        "title": "Run all with batch",
        "summary": "Starts from the current project state, optionally downloads source files, prepares the project, and then enters the Gemini batch Step 2 and Step 3 flow.",
        "when_to_use": "Use this for the simplest one-click remote batch path from a fresh or partially prepared project.",
        "steps": [
            "Run Step 0 first when needed for download-based projects.",
            "Run the missing prep stages from Step 1 through Step 1.7.",
            "Submit batch-backed Step 2 and Step 3 work, then reconcile until completion.",
        ],
        "outputs": "Expected outputs match the batch-backed end-to-end project flow once reconcile finishes.",
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

FLOW_STAGE_RUN_MODES = {
    "step0": ["download_only"],
    "step1": ["prepare_dense_capture"],
    "step1_5": ["prepare_structural_compare"],
    "step1_6": ["prepare_llm_queue"],
    "step1_7": ["prepare_llm_prompts"],
    "step2": ["sync_full", "batch_vision_only", "batch_full"],
    "step3": ["batch_knowledge_only", "deterministic_postprocess_only", "sync_full", "batch_full"],
}

RUN_ACTION_GROUPS = [
    {
        "key": "prepare",
        "title": "Prepare project",
        "summary": "Bring the project through Steps 1 to 1.7 from its current state.",
        "modes": ["prepare_project"],
    },
    {
        "key": "analyze",
        "title": "Analyze project",
        "summary": "Run Steps 2 and 3 after prep is ready.",
        "modes": ["sync_full", "batch_full"],
    },
    {
        "key": "run_all",
        "title": "Run all",
        "summary": "Go from current inputs to completed project outputs in one action.",
        "modes": ["run_all_local", "run_all_batch"],
    },
    {
        "key": "optional",
        "title": "Optional",
        "summary": "Run these only when the main project pipeline is already complete enough.",
        "modes": ["corpus_only"],
    },
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


def _first_prepare_stage(project: ProjectRecord) -> str:
    artifacts = inspect_artifacts(
        project.project_root,
        project.lesson_name,
        project.transcript_path,
        project.source_video_path,
    )
    if not artifacts.dense_index_exists:
        return "prepare_dense_capture"
    if not artifacts.structural_index_exists:
        return "prepare_structural_compare"
    if not artifacts.queue_manifest_exists:
        return "prepare_llm_queue"
    return "prepare_llm_prompts"


def _initial_stage(run_mode: str, project: ProjectRecord, settings: UISettings, *, force_overwrite: bool = False) -> str:
    artifacts = inspect_artifacts(
        project.project_root,
        project.lesson_name,
        project.transcript_path,
        project.source_video_path,
    )
    if run_mode == "download_only":
        return "download"
    if run_mode == "prepare_dense_capture":
        return "prepare_dense_capture"
    if run_mode == "prepare_structural_compare":
        return "prepare_structural_compare"
    if run_mode == "prepare_llm_queue":
        return "prepare_llm_queue"
    if run_mode == "prepare_llm_prompts":
        return "prepare_llm_prompts"
    if run_mode == "prepare_project":
        return _first_prepare_stage(project)
    if run_mode == "sync_full":
        if artifacts.dense_analysis_exists and not force_overwrite:
            return "component2"
        return "vision_sync"
    if run_mode == "batch_vision_only":
        return "vision_submit"
    if run_mode == "batch_knowledge_only":
        return "knowledge_submit"
    if run_mode == "batch_full":
        return "vision_submit" if force_overwrite or not artifacts.dense_analysis_exists else "knowledge_submit"
    if run_mode == "run_all_local":
        if project.source_url and (not artifacts.video_exists or not artifacts.transcript_exists):
            return "download"
        if force_overwrite:
            return "download" if project.source_url else "prepare_dense_capture"
        if not artifacts.dense_index_exists or not artifacts.structural_index_exists or not artifacts.queue_manifest_exists or not artifacts.prompt_files_exist:
            return _first_prepare_stage(project)
        if artifacts.dense_analysis_exists and not force_overwrite:
            return "component2"
        return "vision_sync"
    if run_mode == "run_all_batch":
        if project.source_url and (not artifacts.video_exists or not artifacts.transcript_exists):
            return "download"
        if force_overwrite:
            return "download" if project.source_url else "prepare_dense_capture"
        if not artifacts.dense_index_exists or not artifacts.structural_index_exists or not artifacts.queue_manifest_exists or not artifacts.prompt_files_exist:
            return _first_prepare_stage(project)
        if artifacts.corpus_ready and not artifacts.exports_ready:
            return "postprocess"
        return "vision_submit" if force_overwrite or not artifacts.dense_analysis_exists else "knowledge_submit"
    if run_mode == "deterministic_postprocess_only":
        return "postprocess"
    if run_mode == "corpus_only":
        return "corpus"
    raise ValueError(f"Unsupported run mode: {run_mode}")


def get_project_run_mode_controls(
    project: ProjectRecord,
    latest_run: RunRecord | None = None,
    *,
    force_overwrite: bool = False,
) -> dict[str, dict[str, str | bool | None]]:
    artifacts = inspect_artifacts(
        project.project_root,
        project.lesson_name,
        project.transcript_path,
        project.source_video_path,
    )

    def control(enabled: bool, reason: str | None = None) -> dict[str, str | bool | None]:
        return {"enabled": enabled, "reason": reason}

    if latest_run is not None and latest_run.is_active:
        reason = (
            "A remote batch is already in progress. Reconcile or cancel it before starting another run."
            if latest_run.status == "WAITING_REMOTE"
            else "This project already has active background work."
        )
        return {mode: control(False, reason) for mode in SUPPORTED_RUN_MODES}

    controls: dict[str, dict[str, str | bool | None]] = {}
    missing_video_reason = "Run Step 0 download first." if project.source_url else "Add a source video first."

    controls["download_only"] = (
        control(True)
        if project.source_url
        else control(False, "This project was not created from a download URL.")
    )
    controls["prepare_dense_capture"] = (
        control(True)
        if artifacts.video_exists
        else control(False, missing_video_reason)
    )
    controls["prepare_structural_compare"] = (
        control(True)
        if artifacts.dense_index_exists
        else control(False, "Run Step 1 dense capture first.")
    )
    controls["prepare_llm_queue"] = (
        control(True)
        if artifacts.structural_index_exists
        else control(False, "Run Step 1.5 structural compare first.")
    )
    controls["prepare_llm_prompts"] = (
        control(True)
        if artifacts.queue_manifest_exists
        else control(False, "Run Step 1.6 queue build first.")
    )
    controls["prepare_project"] = (
        control(True)
        if any(
            [
                artifacts.video_exists,
                artifacts.dense_index_exists,
                artifacts.structural_index_exists,
                artifacts.queue_manifest_exists,
                artifacts.prompt_files_exist,
            ]
        )
        else control(False, missing_video_reason)
    )

    if not artifacts.transcript_exists:
        analyze_reason = "Add a transcript first."
    elif artifacts.dense_analysis_exists:
        analyze_reason = None
    elif not artifacts.dense_index_exists:
        analyze_reason = "Run Step 1 dense capture first."
    elif not artifacts.queue_manifest_exists:
        analyze_reason = "Run Step 1.6 queue build first."
    else:
        analyze_reason = None

    controls["sync_full"] = control(analyze_reason is None, analyze_reason)
    batch_vision_reason = analyze_reason
    if batch_vision_reason is None and artifacts.dense_analysis_exists and not force_overwrite:
        batch_vision_reason = "Dense analysis already exists. Enable force overwrite to rerun Step 2 vision."
    controls["batch_vision_only"] = control(batch_vision_reason is None, batch_vision_reason)
    controls["batch_full"] = control(analyze_reason is None, analyze_reason)

    knowledge_reason: str | None = None
    if not artifacts.transcript_exists:
        knowledge_reason = "Add a transcript first."
    elif not artifacts.dense_analysis_exists:
        knowledge_reason = "Finish Step 2 vision first."
    controls["batch_knowledge_only"] = control(knowledge_reason is None, knowledge_reason)

    if project.source_url and (not artifacts.video_exists or not artifacts.transcript_exists):
        run_all_reason = None
    elif not artifacts.transcript_exists:
        run_all_reason = "Add a transcript first."
    elif any(
        [
            artifacts.video_exists,
            artifacts.dense_index_exists,
            artifacts.structural_index_exists,
            artifacts.queue_manifest_exists,
            artifacts.prompt_files_exist,
            artifacts.dense_analysis_exists,
        ]
    ):
        run_all_reason = None
    else:
        run_all_reason = missing_video_reason
    controls["run_all_local"] = control(run_all_reason is None, run_all_reason)
    controls["run_all_batch"] = control(run_all_reason is None, run_all_reason)

    postprocess_reason: str | None = None
    if not artifacts.transcript_exists:
        postprocess_reason = "Add a transcript first."
    elif not artifacts.dense_analysis_exists:
        postprocess_reason = "Finish Step 2 vision first."
    elif not artifacts.knowledge_events_exists:
        postprocess_reason = "Finish Step 3 knowledge extraction first."
    controls["deterministic_postprocess_only"] = control(postprocess_reason is None, postprocess_reason)

    corpus_reason: str | None = None
    if not artifacts.corpus_ready:
        corpus_reason = "Finish Step 3 knowledge extraction first."
    elif not artifacts.exports_ready:
        corpus_reason = "Generate Step 3 exports first."
    controls["corpus_only"] = control(corpus_reason is None, corpus_reason)
    return controls


def create_project_run(
    store: UIStateStore,
    settings: UISettings,
    *,
    project_id: str,
    run_mode: str,
    force_overwrite: bool = False,
) -> RunRecord:
    if run_mode not in SUPPORTED_RUN_MODES:
        raise ValueError(f"Unsupported run mode: {run_mode}")
    project = refresh_project_record(store, project_id)
    project_row = store.get_project(project.project_id)
    if project_row is None:
        raise KeyError(project_id)
    project = _row_to_project(project_row)
    latest_run = _row_to_run(store.get_latest_run(project.project_id))
    controls = get_project_run_mode_controls(project, latest_run=latest_run, force_overwrite=force_overwrite)
    selected = controls.get(run_mode)
    if not selected or not bool(selected.get("enabled")):
        raise ValueError(str((selected or {}).get("reason") or f"Run mode `{run_mode}` is not available for this project right now."))
    run_id = _next_run_id(store, project_id, run_mode)
    run_token = _safe_run_token(run_id)
    log_path = settings.log_root / f"{run_token}.log"
    pipeline_db_path = settings.pipeline_db_root / f"{run_token}.db"
    row = store.create_run(
        run_id=run_id,
        project_id=project_id,
        run_kind="PROJECT",
        run_mode=run_mode,
        force_overwrite=force_overwrite,
        status="QUEUED",
        current_stage=_initial_stage(run_mode, project, settings, force_overwrite=force_overwrite),
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

