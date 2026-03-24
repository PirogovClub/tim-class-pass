from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import replace
from pathlib import Path

import click

from helpers import config as pipeline_config
from helpers.clients import gemini_client
from pipeline.batch_cli import _ensure_lesson_chunks, _load_queue_manifest
from pipeline import build_llm_prompts, dense_capturer, downloader, select_llm_frames, structural_compare
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


def _configure_stdio() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None or not hasattr(stream, "reconfigure"):
            continue
        try:
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
        except Exception:
            continue


def _effective_settings(project_root: Path, ui_db_path: Path) -> UISettings:
    base = UISettings.default(project_root=project_root)
    return replace(base, state_db_path=ui_db_path)


class RunReporter:
    def __init__(self, store: UIStateStore, run_id: str) -> None:
        self.store = store
        self.run_id = run_id

    def event(self, event_type: str, message: str, *, stage: str | None = None) -> None:
        self.store.append_run_event(run_id=self.run_id, event_type=event_type, stage=stage, message=message)
        self.log(message, stage=stage, kind=event_type)

    def log(self, message: str, *, stage: str | None = None, kind: str = "debug") -> None:
        run = self.store.get_run(self.run_id)
        if run is None:
            return
        stage_label = stage or "-"
        _write_log(run, f"[{kind}] stage={stage_label} {message}")

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
    timestamp = utc_now_iso()
    lines = str(message).splitlines() or [""]
    for line in lines:
        encoded = f"{timestamp} {line.rstrip()}\n".encode("utf-8", errors="backslashreplace")
        buffer = getattr(sys.stdout, "buffer", None)
        if buffer is not None:
            buffer.write(encoded)
        else:
            sys.stdout.write(encoded.decode("utf-8", errors="replace"))
    if getattr(sys.stdout, "buffer", None) is not None:
        sys.stdout.buffer.flush()
    else:
        sys.stdout.flush()


def _project_state_snapshot(owner_project) -> dict[str, object]:
    project_root = owner_project.project_root
    lesson_name = owner_project.lesson_name
    paths = PipelinePaths(video_root=project_root)
    prompt_files = sorted((project_root / "llm_queue").glob("*_prompt.txt")) if (project_root / "llm_queue").exists() else []
    return {
        "project_root": str(project_root),
        "title": owner_project.title,
        "lesson_name": lesson_name,
        "source_mode": owner_project.source_mode,
        "source_url": owner_project.source_url,
        "transcript_path": None if owner_project.transcript_path is None else str(owner_project.transcript_path),
        "source_video_path": None if owner_project.source_video_path is None else str(owner_project.source_video_path),
        "dense_index_exists": (project_root / "dense_index.json").exists(),
        "structural_index_exists": (project_root / "structural_index.json").exists(),
        "queue_manifest_exists": (project_root / "llm_queue" / "manifest.json").exists(),
        "prompt_file_count": len(prompt_files),
        "dense_analysis_exists": (project_root / "dense_analysis.json").exists(),
        "knowledge_events_exists": paths.knowledge_events_path(lesson_name).exists(),
        "rule_cards_exists": paths.rule_cards_path(lesson_name).exists(),
        "evidence_index_exists": paths.evidence_index_path(lesson_name).exists(),
        "concept_graph_exists": paths.concept_graph_path(lesson_name).exists(),
        "review_markdown_exists": paths.review_markdown_path(lesson_name).exists(),
        "rag_ready_exists": paths.rag_ready_export_path(lesson_name).exists() or paths.rag_ready_markdown_path(lesson_name).exists(),
    }


def _missing_files_error(*, context: str, missing_paths: list[Path], recommendation: str) -> ValueError:
    joined = "; ".join(str(path) for path in missing_paths)
    return ValueError(f"Missing required files for {context}: {joined}. {recommendation}")


def _log_prerequisite_snapshot(reporter: RunReporter, stage: str, *, heading: str, values: dict[str, object]) -> None:
    reporter.log(
        f"{heading}: {json.dumps(values, ensure_ascii=False, sort_keys=True)}",
        stage=stage,
        kind="preflight",
    )


def _project_video_id(owner_project) -> str:
    return owner_project.project_root.name


def _project_config(owner_project) -> dict:
    return pipeline_config.get_config_for_video(_project_video_id(owner_project))


def _resolved_max_workers(cfg: dict) -> int:
    requested_workers = cfg.get("workers")
    default_workers = min(max((os.cpu_count() or 1) // 2, 1), 8)
    if requested_workers is None:
        return default_workers
    try:
        value = int(requested_workers)
    except (TypeError, ValueError):
        return default_workers
    return min(max(value, 1), 8)


def _fake_write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _fake_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _run_download_step(
    owner_project,
    reporter: RunReporter,
    settings: UISettings,
    *,
    force_overwrite: bool = False,
) -> None:
    stage = "download"
    reporter.log(
        f"download_only starting with project state: {json.dumps(_project_state_snapshot(owner_project), ensure_ascii=False, sort_keys=True)}",
        stage=stage,
        kind="context",
    )
    if not owner_project.source_url:
        raise ValueError("Project does not have a source URL configured for Step 0 download.")
    resolved_video_id = downloader.extract_video_id(owner_project.source_url)
    _log_prerequisite_snapshot(
        reporter,
        stage,
        heading="download prerequisites",
        values={
            "source_url": owner_project.source_url,
            "project_root": str(owner_project.project_root),
            "expected_video_id": _project_video_id(owner_project),
            "resolved_video_id": resolved_video_id,
            "force_overwrite": force_overwrite,
        },
    )
    if not resolved_video_id:
        raise ValueError("Could not extract a video ID from the configured source URL.")
    if resolved_video_id != _project_video_id(owner_project):
        raise ValueError(
            f"Configured source URL resolves to `{resolved_video_id}`, but this project expects `{_project_video_id(owner_project)}`."
        )
    reporter.running(stage, "Downloading source video and transcripts.")
    if _fake_mode(settings):
        _fake_write_text(owner_project.project_root / f"{resolved_video_id}.mp4", "fake-video")
        _fake_write_text(
            owner_project.project_root / f"{resolved_video_id}.vtt",
            "WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nDownloaded transcript\n",
        )
    else:
        if not downloader.download_video_and_transcript(
            owner_project.source_url,
            resolved_video_id,
            overwrite=force_overwrite,
        ):
            raise ValueError("Download step failed. See the worker log for downloader output.")
    reporter.progress(stage, "Download step completed.")


def _run_dense_capture_step(
    owner_project,
    reporter: RunReporter,
    settings: UISettings,
    *,
    force_overwrite: bool = False,
) -> None:
    stage = "prepare_dense_capture"
    cfg = _project_config(owner_project)
    capture_fps = float(cfg.get("capture_fps", 1.0))
    max_workers = _resolved_max_workers(cfg)
    video_path = owner_project.source_video_path
    _log_prerequisite_snapshot(
        reporter,
        stage,
        heading="dense capture prerequisites",
        values={
            "video_path": None if video_path is None else str(video_path),
            "video_exists": bool(video_path and video_path.exists()),
            "capture_fps": capture_fps,
            "max_workers": max_workers,
            "force_overwrite": force_overwrite,
        },
    )
    if video_path is None or not video_path.exists():
        raise _missing_files_error(
            context="Step 1 dense capture",
            missing_paths=[owner_project.project_root],
            recommendation="Add a source video first, or run Step 0 download for URL-backed projects.",
        )
    reporter.running(stage, "Running Step 1 dense capture.")
    if _fake_mode(settings):
        frame_rel_path = "frames_dense/frame_000001.jpg"
        _fake_write_text(owner_project.project_root / frame_rel_path, "fake-jpg")
        _fake_write_json(owner_project.project_root / "dense_index.json", {"000001": frame_rel_path})
    else:
        dense_capturer.extract_dense_frames(
            _project_video_id(owner_project),
            video_file_override=video_path.name,
            max_workers=max_workers,
            capture_fps=capture_fps,
        )
    reporter.progress(stage, "Step 1 dense capture completed.")


def _run_structural_compare_step(
    owner_project,
    reporter: RunReporter,
    settings: UISettings,
    *,
    force_overwrite: bool = False,
) -> None:
    stage = "prepare_structural_compare"
    cfg = _project_config(owner_project)
    max_workers = _resolved_max_workers(cfg)
    dense_index_path = owner_project.project_root / "dense_index.json"
    _log_prerequisite_snapshot(
        reporter,
        stage,
        heading="structural compare prerequisites",
        values={
            "dense_index_path": str(dense_index_path),
            "dense_index_exists": dense_index_path.exists(),
            "max_workers": max_workers,
            "force_overwrite": force_overwrite,
        },
    )
    if not dense_index_path.exists():
        raise _missing_files_error(
            context="Step 1.5 structural compare",
            missing_paths=[dense_index_path],
            recommendation="Run Step 1 dense capture first.",
        )
    reporter.running(stage, "Running Step 1.5 structural compare.")
    if _fake_mode(settings):
        _fake_write_json(
            owner_project.project_root / "structural_index.json",
            {
                "video_id": _project_video_id(owner_project),
                "results": {"000001": {"previous_key": None, "score": 0.5, "is_significant": True}},
            },
        )
    else:
        structural_compare.run_structural_compare(
            _project_video_id(owner_project),
            force=force_overwrite,
            max_workers=max_workers,
            progress_callback=lambda message: reporter.progress(stage, message),
        )
    reporter.progress(stage, "Step 1.5 structural compare completed.")


def _run_llm_queue_step(owner_project, reporter: RunReporter, settings: UISettings) -> None:
    stage = "prepare_llm_queue"
    dense_index_path = owner_project.project_root / "dense_index.json"
    structural_index_path = owner_project.project_root / "structural_index.json"
    cfg = _project_config(owner_project)
    threshold = float(cfg.get("llm_queue_diff_threshold", 0.14))
    _log_prerequisite_snapshot(
        reporter,
        stage,
        heading="llm queue prerequisites",
        values={
            "dense_index_path": str(dense_index_path),
            "dense_index_exists": dense_index_path.exists(),
            "structural_index_path": str(structural_index_path),
            "structural_index_exists": structural_index_path.exists(),
            "threshold": threshold,
        },
    )
    missing_paths = [path for path in [dense_index_path, structural_index_path] if not path.exists()]
    if missing_paths:
        raise _missing_files_error(
            context="Step 1.6 queue build",
            missing_paths=missing_paths,
            recommendation="Run Steps 1 and 1.5 first.",
        )
    reporter.running(stage, "Running Step 1.6 queue build.")
    if _fake_mode(settings):
        queue_dir = owner_project.project_root / "llm_queue"
        queue_dir.mkdir(parents=True, exist_ok=True)
        _fake_write_text(queue_dir / "frame_000001.jpg", "fake-jpg")
        _fake_write_json(
            queue_dir / "manifest.json",
            {
                "video_id": _project_video_id(owner_project),
                "threshold": threshold,
                "total_selected": 1,
                "copied": 1,
                "items": {
                    "000001": {
                        "reason": "above_threshold",
                        "diff": 0.5,
                        "source": "frames_dense/frame_000001.jpg",
                    }
                },
            },
        )
    else:
        queue_dir = select_llm_frames.build_llm_queue(_project_video_id(owner_project), threshold=threshold)
    reporter.progress(stage, f"Step 1.6 queue build completed: {queue_dir}")


def _run_prompt_build_step(owner_project, reporter: RunReporter) -> None:
    stage = "prepare_llm_prompts"
    manifest_path = owner_project.project_root / "llm_queue" / "manifest.json"
    _log_prerequisite_snapshot(
        reporter,
        stage,
        heading="prompt build prerequisites",
        values={
            "queue_manifest_path": str(manifest_path),
            "queue_manifest_exists": manifest_path.exists(),
        },
    )
    if not manifest_path.exists():
        raise _missing_files_error(
            context="Step 1.7 prompt build",
            missing_paths=[manifest_path],
            recommendation="Run Step 1.6 queue build first.",
        )
    reporter.running(stage, "Running Step 1.7 prompt build.")
    queue_dir = build_llm_prompts.build_llm_prompts(_project_video_id(owner_project))
    reporter.progress(stage, f"Step 1.7 prompt build completed: {queue_dir}")


def _run_prepare_project(
    owner_project,
    reporter: RunReporter,
    settings: UISettings,
    store: UIStateStore,
    *,
    force_overwrite: bool = False,
):
    project = owner_project
    snapshot = _project_state_snapshot(project)
    reporter.log(
        f"prepare_project starting with project state: {json.dumps(snapshot, ensure_ascii=False, sort_keys=True)}",
        stage="prepare_dense_capture",
        kind="context",
    )
    if force_overwrite or not snapshot["dense_index_exists"]:
        _run_dense_capture_step(project, reporter, settings, force_overwrite=force_overwrite)
        project = refresh_project_record(store, project.project_id)
    if force_overwrite or not _project_state_snapshot(project)["structural_index_exists"]:
        _run_structural_compare_step(project, reporter, settings, force_overwrite=force_overwrite)
        project = refresh_project_record(store, project.project_id)
    if force_overwrite or not _project_state_snapshot(project)["queue_manifest_exists"]:
        _run_llm_queue_step(project, reporter, settings)
        project = refresh_project_record(store, project.project_id)
    if force_overwrite or not _project_state_snapshot(project)["prompt_file_count"]:
        _run_prompt_build_step(project, reporter)
        project = refresh_project_record(store, project.project_id)
    return project


def _run_all_local(
    owner_project,
    reporter: RunReporter,
    settings: UISettings,
    store: UIStateStore,
    *,
    force_overwrite: bool = False,
) -> None:
    project = owner_project
    if project.source_url and (force_overwrite or project.source_video_path is None or project.transcript_path is None):
        _run_download_step(project, reporter, settings, force_overwrite=force_overwrite)
        project = refresh_project_record(store, project.project_id)
    project = _run_prepare_project(project, reporter, settings, store, force_overwrite=force_overwrite)
    _run_sync_full(project, reporter, settings, force_overwrite=force_overwrite)


def _run_all_batch(
    owner_project,
    reporter: RunReporter,
    run: dict,
    settings: UISettings,
    store: UIStateStore,
    *,
    force_overwrite: bool = False,
) -> None:
    project = owner_project
    if project.source_url and (force_overwrite or project.source_video_path is None or project.transcript_path is None):
        _run_download_step(project, reporter, settings, force_overwrite=force_overwrite)
        project = refresh_project_record(store, project.project_id)
    project = _run_prepare_project(project, reporter, settings, store, force_overwrite=force_overwrite)
    if not force_overwrite and (project.project_root / "dense_analysis.json").exists():
        if project.transcript_path is None:
            raise ValueError("Project is missing transcript after preparation.")
        paths = PipelinePaths(video_root=project.project_root)
        if paths.knowledge_events_path(project.lesson_name).exists():
            _run_postprocess(project, reporter)
            return
    _submit_batch_stage(
        project,
        reporter,
        run,
        stage_name=STAGE_VISION if force_overwrite or not (project.project_root / "dense_analysis.json").exists() else STAGE_KNOWLEDGE_EXTRACT,
        settings=settings,
    )


def _run_postprocess(owner_project, reporter: RunReporter) -> None:
    dense_analysis_path = owner_project.project_root / "dense_analysis.json"
    _log_prerequisite_snapshot(
        reporter,
        "postprocess",
        heading="postprocess prerequisites",
        values={
            "transcript_path": None if owner_project.transcript_path is None else str(owner_project.transcript_path),
            "dense_analysis_path": str(dense_analysis_path),
            "dense_analysis_exists": dense_analysis_path.exists(),
        },
    )
    if owner_project.transcript_path is None:
        raise ValueError(f"Missing transcript for post-process stage in {owner_project.project_root}.")
    if not dense_analysis_path.exists():
        raise _missing_files_error(
            context="deterministic post-process stage",
            missing_paths=[dense_analysis_path],
            recommendation="Generate dense_analysis.json first by finishing the vision stage.",
        )
    reporter.running("postprocess", "Running deterministic post-processing.")
    outputs = run_component2_pipeline(
        vtt_path=owner_project.transcript_path,
        visuals_json_path=dense_analysis_path,
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


def _run_sync_full(
    owner_project,
    reporter: RunReporter,
    settings: UISettings,
    *,
    force_overwrite: bool = False,
) -> None:
    project_root, transcript_path = _project_paths(owner_project)
    dense_analysis_path = project_root / "dense_analysis.json"
    reporter.log(
        f"sync_full starting with project state: {json.dumps(_project_state_snapshot(owner_project), ensure_ascii=False, sort_keys=True)}",
        stage="vision_sync",
        kind="context",
    )
    if force_overwrite or not dense_analysis_path.exists():
        queue_manifest = project_root / "llm_queue" / "manifest.json"
        dense_index = project_root / "dense_index.json"
        _log_prerequisite_snapshot(
            reporter,
            "vision_sync",
            heading="sync vision prerequisites",
            values={
                "dense_analysis_exists": dense_analysis_path.exists(),
                "dense_index_path": str(dense_index),
                "dense_index_exists": dense_index.exists(),
                "queue_manifest_path": str(queue_manifest),
                "queue_manifest_exists": queue_manifest.exists(),
                "transcript_path": str(transcript_path),
                "force_overwrite": force_overwrite,
            },
        )
        missing_paths = [path for path in [dense_index, queue_manifest] if not path.exists()]
        if missing_paths:
            reporter.log(
                "Sync vision cannot start because required queue-building outputs are missing.",
                stage="vision_sync",
                kind="preflight",
            )
            raise _missing_files_error(
                context="sync vision stage",
                missing_paths=missing_paths,
                recommendation="Build the queue first with the existing Step 1.6 flow.",
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
        queue_manifest = owner_project.project_root / "llm_queue" / "manifest.json"
        _log_prerequisite_snapshot(
            reporter,
            "vision_submit",
            heading="batch vision prerequisites",
            values={
                "queue_manifest_path": str(queue_manifest),
                "queue_manifest_exists": queue_manifest.exists(),
            },
        )
        if not queue_manifest.exists():
            raise _missing_files_error(
                context="batch vision submit stage",
                missing_paths=[queue_manifest],
                recommendation="Build the queue first with the existing Step 1.6 flow.",
            )
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
        dense_analysis_path = owner_project.project_root / "dense_analysis.json"
        _log_prerequisite_snapshot(
            reporter,
            "knowledge_submit",
            heading="knowledge batch prerequisites",
            values={
                "transcript_path": None if owner_project.transcript_path is None else str(owner_project.transcript_path),
                "dense_analysis_path": str(dense_analysis_path),
                "dense_analysis_exists": dense_analysis_path.exists(),
            },
        )
        if owner_project.transcript_path is None:
            raise ValueError(f"Project is missing transcript for knowledge batch stage in {owner_project.project_root}.")
        if not dense_analysis_path.exists():
            raise _missing_files_error(
                context="knowledge batch stage",
                missing_paths=[dense_analysis_path],
                recommendation="Finish the vision stage first so dense_analysis.json exists.",
            )
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
    batch_stage_name = STAGE_VISION if current_stage == "vision_remote" else STAGE_KNOWLEDGE_EXTRACT if current_stage == "knowledge_remote" else None
    stage_jobs = pipeline_store.list_batch_jobs(stage_name=batch_stage_name) if batch_stage_name else []
    reporter.running(current_stage or "reconcile", "Reconciling remote batch state.")
    if _fake_mode(settings):
        status_map = fake_batch_backend.poll_active_batches(pipeline_store)
    else:
        status_map = poll_active_batches(pipeline_store)
    reporter.progress(current_stage or "reconcile", json.dumps(status_map, ensure_ascii=False), remote_poll=True)
    if any(status == "FAILED" for status in status_map.values()):
        raise ValueError("Remote batch reported failure.")
    if any(str(job.get("status") or "") in {"FAILED", "CANCELLED", "EXPIRED"} for job in stage_jobs):
        raise ValueError("Remote batch reported failure.")
    if any(status in {"SUBMITTED", "PROCESSING"} for status in status_map.values()):
        reporter.waiting_remote(
            current_stage or "reconcile",
            "Remote batch still processing.",
            remote_job_name=run.get("remote_job_name"),
        )
        return
    if not status_map and any(str(job.get("status") or "") not in {"SUCCEEDED"} for job in stage_jobs):
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
    _configure_stdio()
    settings = _effective_settings(project_root, ui_db_path)
    store = UIStateStore(settings.state_db_path)
    reporter = RunReporter(store, run_id)
    run_row = store.get_run(run_id)
    if run_row is None:
        raise click.ClickException(f"Unknown run_id: {run_id}")
    _write_log(run_row, f"[worker] start action={action} run_id={run_id}")
    run, owner_project, _events, targets = get_run_detail(store, run_id)
    _write_log(
        run_row,
        "[worker] run metadata "
        + json.dumps(
            {
                "run_id": run.run_id,
                "run_kind": run.run_kind,
                "run_mode": run.run_mode,
                "force_overwrite": run.force_overwrite,
                "action": action,
                "pipeline_db_path": None if run.pipeline_db_path is None else str(run.pipeline_db_path),
                "log_path": None if run.log_path is None else str(run.log_path),
                "fake_mode": _fake_mode(settings),
                "target_count": len(targets),
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
    )
    if owner_project is not None:
        _write_log(
            run_row,
            "[worker] owner project snapshot "
            + json.dumps(_project_state_snapshot(owner_project), ensure_ascii=False, sort_keys=True),
        )

    try:
        reporter.check_cancelled()
        if run.run_kind == "CORPUS":
            _run_corpus(targets, reporter, settings)
            return
        if owner_project is None:
            raise ValueError("Run owner project not found.")
        owner_project = refresh_project_record(store, owner_project.project_id)
        force_overwrite = run.force_overwrite
        if action == "start":
            if run.run_mode == "download_only":
                _run_download_step(owner_project, reporter, settings, force_overwrite=force_overwrite)
                refresh_project_record(store, owner_project.project_id)
                reporter.succeeded("download", "Download step completed.")
                return
            if run.run_mode == "prepare_dense_capture":
                _run_dense_capture_step(owner_project, reporter, settings, force_overwrite=force_overwrite)
                refresh_project_record(store, owner_project.project_id)
                reporter.succeeded("prepare_dense_capture", "Step 1 dense capture completed.")
                return
            if run.run_mode == "prepare_structural_compare":
                _run_structural_compare_step(owner_project, reporter, settings, force_overwrite=force_overwrite)
                refresh_project_record(store, owner_project.project_id)
                reporter.succeeded("prepare_structural_compare", "Step 1.5 structural compare completed.")
                return
            if run.run_mode == "prepare_llm_queue":
                _run_llm_queue_step(owner_project, reporter, settings)
                refresh_project_record(store, owner_project.project_id)
                reporter.succeeded("prepare_llm_queue", "Step 1.6 queue build completed.")
                return
            if run.run_mode == "prepare_llm_prompts":
                _run_prompt_build_step(owner_project, reporter)
                refresh_project_record(store, owner_project.project_id)
                reporter.succeeded("prepare_llm_prompts", "Step 1.7 prompt build completed.")
                return
            if run.run_mode == "prepare_project":
                _run_prepare_project(owner_project, reporter, settings, store, force_overwrite=force_overwrite)
                refresh_project_record(store, owner_project.project_id)
                reporter.succeeded("prepare_llm_prompts", "Project preparation completed through Step 1.7.")
                return
            if run.run_mode == "sync_full":
                _run_sync_full(owner_project, reporter, settings, force_overwrite=force_overwrite)
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
                stage_name = (
                    STAGE_VISION
                    if force_overwrite or not (owner_project.project_root / "dense_analysis.json").exists()
                    else STAGE_KNOWLEDGE_EXTRACT
                )
                _submit_batch_stage(owner_project, reporter, run_row, stage_name=stage_name, settings=settings)
                return
            if run.run_mode == "run_all_local":
                _run_all_local(owner_project, reporter, settings, store, force_overwrite=force_overwrite)
                refresh_project_record(store, owner_project.project_id)
                reporter.succeeded("component2", "Run-all local pipeline completed.")
                return
            if run.run_mode == "run_all_batch":
                _run_all_batch(owner_project, reporter, run_row, settings, store, force_overwrite=force_overwrite)
                refresh_project_record(store, owner_project.project_id)
                if store.get_run(run_id).get("status") == "WAITING_REMOTE":
                    return
                reporter.succeeded("postprocess", "Run-all batch pipeline completed.")
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

