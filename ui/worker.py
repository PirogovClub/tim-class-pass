from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import replace
from pathlib import Path

import click

from helpers.clients import gemini_client
from pipeline.batch_cli import _ensure_lesson_chunks, _load_queue_manifest
from pipeline.component2.main import run_component2_pipeline
from pipeline.contracts import PipelinePaths
from pipeline.dense_analyzer import emit_batch_spool_for_analysis, run_analysis
from pipeline.orchestrator import STAGE_KNOWLEDGE_EXTRACT, STAGE_VISION, StateStore
from pipeline.orchestrator.batch_assembler import assemble_batch_files
from pipeline.orchestrator.models import utc_now_iso
from pipeline.orchestrator.run_manager import download_completed_batches, poll_active_batches, submit_ready_batches
from ui.services.projects import refresh_project_record
from ui.services.runs import get_run_detail
from ui.settings import UISettings
from ui.storage import UIStateStore
from ui.testing import fake_batch_backend
from ui.testing.fake_provider import FakeProvider
from ui.services.runs import _safe_run_token


class RunCancelled(RuntimeError):
    pass


def _effective_settings(project_root: Path, ui_db_path: Path) -> UISettings:
    base = UISettings.default(project_root=project_root)
    return replace(base, state_db_path=ui_db_path)


class RunReporter:
    def __init__(self, store: UIStateStore, run_id: str) -> None:
        self.store = store
        self.run_id = run_id

    def event(self, event_type: str, message: str, *, stage: str | None = None) -> None:
        self.store.append_run_event(run_id=self.run_id, event_type=event_type, stage=stage, message=message)

    def _update(self, **fields) -> None:
        fields.setdefault("last_heartbeat_at", utc_now_iso())
        self.store.update_run(self.run_id, **fields)

    def running(self, stage: str, message: str) -> None:
        self._update(
            status="RUNNING",
            current_stage=stage,
            progress_message=message,
            pid=os.getpid(),
            started_at=self.store.get_run(self.run_id).get("started_at") or utc_now_iso(),
        )
        self.event("stage", message, stage=stage)

    def waiting_remote(self, stage: str, message: str, *, remote_job_name: str | None = None) -> None:
        self._update(
            status="WAITING_REMOTE",
            current_stage=stage,
            progress_message=message,
            remote_job_name=remote_job_name,
            pid=None,
            last_remote_poll_at=utc_now_iso(),
        )
        self.event("waiting_remote", message, stage=stage)

    def progress(self, stage: str, message: str, *, remote_poll: bool = False) -> None:
        fields = {
            "current_stage": stage,
            "progress_message": message,
        }
        if remote_poll:
            fields["last_remote_poll_at"] = utc_now_iso()
        self._update(**fields)
        self.event("progress", message, stage=stage)

    def succeeded(self, stage: str, message: str) -> None:
        self._update(
            status="SUCCEEDED",
            current_stage=stage,
            progress_message=message,
            pid=None,
            finished_at=utc_now_iso(),
            exit_code=0,
            error_message=None,
        )
        self.event("succeeded", message, stage=stage)

    def failed(self, stage: str, message: str) -> None:
        self._update(
            status="FAILED",
            current_stage=stage,
            progress_message=message,
            pid=None,
            finished_at=utc_now_iso(),
            exit_code=1,
            error_message=message,
        )
        self.event("failed", message, stage=stage)

    def cancelled(self, stage: str, message: str) -> None:
        self._update(
            status="CANCELLED",
            current_stage=stage,
            progress_message=message,
            pid=None,
            finished_at=utc_now_iso(),
            exit_code=130,
            error_message=message,
        )
        self.event("cancelled", message, stage=stage)

    def check_cancelled(self) -> None:
        row = self.store.get_run(self.run_id)
        if row is not None and row.get("cancel_requested_at"):
            raise RunCancelled("Run cancellation requested.")


def install_fake_provider() -> None:
    import helpers.clients.providers as providers_module
    import pipeline.component2.llm_processor as llm_processor_module
    import pipeline.component2.quant_reducer as quant_reducer_module

    def _fake_get_provider(name: str):
        return FakeProvider(name)

    providers_module.get_provider = _fake_get_provider
    llm_processor_module.get_provider = _fake_get_provider
    quant_reducer_module.get_provider = _fake_get_provider


def _project_paths(owner_project) -> tuple[Path, Path]:
    project_root = owner_project.project_root
    if owner_project.transcript_path is None:
        raise ValueError("Project is missing transcript.")
    transcript_path = owner_project.transcript_path
    return (project_root, transcript_path)


def _prepare_pipeline_store(run: dict) -> StateStore:
    pipeline_db_path = run.get("pipeline_db_path")
    if not pipeline_db_path:
        raise ValueError("Run is missing pipeline_db_path.")
    store = StateStore(Path(str(pipeline_db_path)))
    return store


def _ensure_project_registered_in_pipeline(store: StateStore, owner_project) -> tuple[str, dict]:
    video_id = owner_project.project_root.name
    lesson_id = f"{video_id}::{owner_project.lesson_name}"
    store.ensure_video(video_id=video_id, video_root=owner_project.project_root, title=owner_project.title, status="DISCOVERED")
    lesson_row = store.ensure_lesson(
        lesson_id=lesson_id,
        video_id=video_id,
        lesson_name=owner_project.lesson_name,
        lesson_root=owner_project.project_root,
        vtt_path=owner_project.transcript_path,
        status="DISCOVERED",
    )
    return (video_id, lesson_row)


def _fake_mode(settings: UISettings) -> bool:
    return settings.test_mode or os.getenv("UI_TEST_MODE", "0") == "1"


def _write_log(run, message: str) -> None:
    log_path = Path(str(run["log_path"])) if run.get("log_path") else None
    if log_path is None:
        return
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as handle:
        handle.write(message.rstrip() + "\n")


def _run_postprocess(owner_project, reporter: RunReporter) -> None:
    reporter.running("postprocess", "Running deterministic post-processing.")
    outputs = run_component2_pipeline(
        vtt_path=owner_project.transcript_path,
        visuals_json_path=owner_project.project_root / "dense_analysis.json",
        output_root=owner_project.project_root,
        video_id=owner_project.project_root.name,
        enable_knowledge_events=False,
        enable_evidence_linking=True,
        enable_rule_cards=True,
        enable_concept_graph=True,
        enable_ml_prep=True,
        preserve_legacy_markdown=False,
        enable_new_markdown_render=False,
        enable_exporters=True,
        use_llm_review_render=False,
        use_llm_rag_render=False,
        progress_callback=lambda message: reporter.progress("postprocess", message),
    )
    reporter.progress("postprocess", f"Post-process complete with {len(outputs)} output(s).")


def _run_sync_full(owner_project, reporter: RunReporter, settings: UISettings) -> None:
    project_root, transcript_path = _project_paths(owner_project)
    dense_analysis_path = project_root / "dense_analysis.json"
    if not dense_analysis_path.exists():
        queue_manifest = project_root / "llm_queue" / "manifest.json"
        dense_index = project_root / "dense_index.json"
        if not queue_manifest.exists() or not dense_index.exists():
            raise ValueError(
                "Sync vision prerequisites are missing. Expected dense_index.json and llm_queue/manifest.json."
            )
        reporter.running("vision_sync", "Running dense analysis.")
        if _fake_mode(settings):
            install_fake_provider()
        run_analysis(
            project_root.name,
            batch_size=10,
            agent="gemini",
            parallel_batches=False,
        )
        reporter.progress("vision_sync", "Dense analysis complete.")

    if _fake_mode(settings):
        install_fake_provider()
    reporter.running("component2", "Running Component 2 pipeline.")
    run_component2_pipeline(
        vtt_path=transcript_path,
        visuals_json_path=dense_analysis_path,
        output_root=project_root,
        video_id=project_root.name,
        enable_knowledge_events=True,
        enable_evidence_linking=True,
        enable_rule_cards=True,
        enable_concept_graph=True,
        enable_ml_prep=True,
        preserve_legacy_markdown=True,
        enable_new_markdown_render=False,
        enable_exporters=True,
        use_llm_review_render=False,
        use_llm_rag_render=False,
        progress_callback=lambda message: reporter.progress("component2", message),
    )


def _submit_batch_stage(owner_project, reporter: RunReporter, run: dict, *, stage_name: str, settings: UISettings) -> None:
    pipeline_store = _prepare_pipeline_store(run)
    video_id, lesson_row = _ensure_project_registered_in_pipeline(pipeline_store, owner_project)
    paths = PipelinePaths(video_root=owner_project.project_root)
    if stage_name == STAGE_VISION:
        queue_keys, frames_dir = _load_queue_manifest(owner_project.project_root)
        reporter.running("vision_submit", "Preparing vision batch spool.")
        emit_batch_spool_for_analysis(
            video_root=owner_project.project_root,
            lesson_context={
                "lesson_id": lesson_row["lesson_id"],
                "lesson_name": lesson_row["lesson_name"],
                "video_id": video_id,
            },
            queue_keys=queue_keys,
            frames_dir=frames_dir,
            config={},
            state_store=pipeline_store,
        )
    elif stage_name == STAGE_KNOWLEDGE_EXTRACT:
        if owner_project.transcript_path is None:
            raise ValueError("Project is missing transcript.")
        if not (owner_project.project_root / "dense_analysis.json").exists():
            raise ValueError("Knowledge batch requires dense_analysis.json.")
        reporter.running("knowledge_submit", "Preparing knowledge extraction batch spool.")
        raw_chunks = _ensure_lesson_chunks(lesson_row, paths, {})
        from pipeline.component2.knowledge_builder import adapt_chunks
        from pipeline.component2.llm_processor import emit_batch_spool_for_knowledge_extract

        adapted = adapt_chunks(raw_chunks, lesson_id=owner_project.lesson_name, lesson_title=None)
        emit_batch_spool_for_knowledge_extract(
            chunks=adapted,
            lesson_id=lesson_row["lesson_id"],
            video_id=video_id,
            paths=paths,
            state_store=pipeline_store,
        )
    else:
        raise ValueError(f"Unsupported batch stage: {stage_name}")

    assemble_batch_files(pipeline_store, stage_name=stage_name)
    if _fake_mode(settings):
        batch_names = fake_batch_backend.submit_ready_batches(pipeline_store, stage_name=stage_name, max_batches=3)
    else:
        batch_names = submit_ready_batches(pipeline_store, stage_name=stage_name, max_batches=3)
    if not batch_names:
        raise ValueError(f"No batch jobs were submitted for stage={stage_name}.")
    job = pipeline_store.get_batch_job(batch_names[0])
    remote_name = None if job is None else job.get("remote_job_name")
    remote_stage = "vision_remote" if stage_name == STAGE_VISION else "knowledge_remote"
    reporter.waiting_remote(remote_stage, f"Submitted {len(batch_names)} batch job(s).", remote_job_name=remote_name)


def _continue_batch_run(owner_project, reporter: RunReporter, run: dict, *, settings: UISettings) -> None:
    current_stage = str(run.get("current_stage") or "")
    pipeline_store = _prepare_pipeline_store(run)
    reporter.running(current_stage or "reconcile", "Reconciling remote batch state.")
    if _fake_mode(settings):
        status_map = fake_batch_backend.poll_active_batches(pipeline_store)
    else:
        status_map = poll_active_batches(pipeline_store)
    reporter.progress(current_stage or "reconcile", json.dumps(status_map, ensure_ascii=False), remote_poll=True)
    if any(status == "FAILED" for status in status_map.values()):
        raise ValueError("Remote batch reported failure.")
    if not status_map or any(status in {"SUBMITTED", "PROCESSING"} for status in status_map.values()):
        reporter.waiting_remote(
            current_stage or "reconcile",
            "Remote batch still processing.",
            remote_job_name=run.get("remote_job_name"),
        )
        return

    if _fake_mode(settings):
        fake_batch_backend.download_completed_batches(pipeline_store)
    else:
        download_completed_batches(pipeline_store)

    if current_stage == "vision_remote":
        materialized = fake_batch_backend.materialize_stage_results(pipeline_store, stage_name=STAGE_VISION) if _fake_mode(settings) else 0
        if not _fake_mode(settings):
            from pipeline.batch_cli import run_materialize

            materialized = run_materialize(stage=STAGE_VISION, db_path=run["pipeline_db_path"])
        reporter.progress("vision_remote", f"Materialized {materialized} vision batch result(s).")
        if run["run_mode"] == "batch_vision_only":
            refresh_project_record(reporter.store, run["project_id"])
            reporter.succeeded("vision_remote", "Vision batch completed.")
            return
        _submit_batch_stage(owner_project, reporter, run, stage_name=STAGE_KNOWLEDGE_EXTRACT, settings=settings)
        return

    if current_stage == "knowledge_remote":
        materialized = fake_batch_backend.materialize_stage_results(pipeline_store, stage_name=STAGE_KNOWLEDGE_EXTRACT) if _fake_mode(settings) else 0
        if not _fake_mode(settings):
            from pipeline.batch_cli import run_materialize

            materialized = run_materialize(stage=STAGE_KNOWLEDGE_EXTRACT, db_path=run["pipeline_db_path"])
        reporter.progress("knowledge_remote", f"Materialized {materialized} knowledge batch result(s).")
        _run_postprocess(owner_project, reporter)
        refresh_project_record(reporter.store, run["project_id"])
        reporter.succeeded("postprocess", "Knowledge batch and deterministic post-process completed.")
        return

    reporter.waiting_remote(current_stage or "reconcile", "No further action taken.", remote_job_name=run.get("remote_job_name"))


def _run_corpus(owner_targets, reporter: RunReporter, settings: UISettings) -> None:
    from pipeline.corpus.corpus_builder import build_corpus

    reporter.running("corpus", "Building corpus for selected projects.")
    selected_roots = [project.project_root for project in owner_targets]
    output_root = settings.corpus_output_root / f"corpus_{_safe_run_token(reporter.run_id)}"
    output_root.mkdir(parents=True, exist_ok=True)
    summary = build_corpus(
        input_root=settings.data_root,
        output_root=output_root,
        strict=False,
        selected_project_roots=selected_roots,
    )
    reporter.progress("corpus", f"Corpus build wrote outputs to {output_root}. Summary keys: {sorted(summary.keys())}")
    reporter.succeeded("corpus", f"Corpus build completed in {output_root}.")


def run_worker(*, project_root: Path, ui_db_path: Path, run_id: str, action: str) -> None:
    settings = _effective_settings(project_root, ui_db_path)
    store = UIStateStore(settings.state_db_path)
    reporter = RunReporter(store, run_id)
    run_row = store.get_run(run_id)
    if run_row is None:
        raise click.ClickException(f"Unknown run_id: {run_id}")
    _write_log(run_row, f"[worker] start action={action} run_id={run_id}")
    run, owner_project, _events, targets = get_run_detail(store, run_id)

    try:
        reporter.check_cancelled()
        if run.run_kind == "CORPUS":
            _run_corpus(targets, reporter, settings)
            return
        if owner_project is None:
            raise ValueError("Run owner project not found.")
        if action == "start":
            if run.run_mode == "sync_full":
                _run_sync_full(owner_project, reporter, settings)
                refresh_project_record(store, owner_project.project_id)
                reporter.succeeded("component2", "Sync pipeline completed.")
                return
            if run.run_mode == "batch_vision_only":
                _submit_batch_stage(owner_project, reporter, run_row, stage_name=STAGE_VISION, settings=settings)
                return
            if run.run_mode == "batch_knowledge_only":
                _submit_batch_stage(owner_project, reporter, run_row, stage_name=STAGE_KNOWLEDGE_EXTRACT, settings=settings)
                return
            if run.run_mode == "batch_full":
                stage_name = STAGE_VISION if not (owner_project.project_root / "dense_analysis.json").exists() else STAGE_KNOWLEDGE_EXTRACT
                _submit_batch_stage(owner_project, reporter, run_row, stage_name=stage_name, settings=settings)
                return
            if run.run_mode == "deterministic_postprocess_only":
                _run_postprocess(owner_project, reporter)
                refresh_project_record(store, owner_project.project_id)
                reporter.succeeded("postprocess", "Deterministic post-processing completed.")
                return
            if run.run_mode == "corpus_only":
                _run_corpus(targets, reporter, settings)
                return
            raise ValueError(f"Unsupported run mode: {run.run_mode}")

        if action == "continue":
            _continue_batch_run(owner_project, reporter, run_row, settings=settings)
            refresh_project_record(store, owner_project.project_id)
            return
        raise click.ClickException(f"Unsupported action: {action}")
    except RunCancelled as exc:
        reporter.cancelled(run.current_stage or "cancelled", str(exc))
    except Exception as exc:
        reporter.failed(run.current_stage or "failed", str(exc))
        _write_log(run_row, f"[worker] failed: {exc}")
        raise
    finally:
        latest = store.get_run(run_id)
        if latest is not None and latest.get("status") in {"RUNNING", "FAILED", "SUCCEEDED", "CANCELLED", "INTERRUPTED"}:
            store.update_run(run_id, pid=None)


@click.command(help="Run background UI work for one run ID.")
@click.option("--project-root", required=True, type=click.Path(file_okay=False, path_type=Path), help="Workspace root used by the UI.")
@click.option("--ui-db-path", required=True, type=click.Path(dir_okay=False, path_type=Path), help="UI SQLite state DB path.")
@click.option("--run-id", required=True, help="Run identifier.")
@click.option("--action", required=True, type=click.Choice(["start", "continue"]), help="Worker action.")
def main(project_root: Path, ui_db_path: Path, run_id: str, action: str) -> None:
    run_worker(project_root=project_root, ui_db_path=ui_db_path, run_id=run_id, action=action)


if __name__ == "__main__":
    main()

