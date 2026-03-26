from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from helpers.clients import gemini_batch_client
from pipeline.path_contracts import PipelinePaths
from pipeline.io_utils import atomic_write_json
from pipeline.orchestrator import (
    BATCH_JOB_STATUS_CANCELLED,
    BATCH_JOB_STATUS_EXPIRED,
    BATCH_JOB_STATUS_FAILED,
    BATCH_JOB_STATUS_LOCAL_READY,
    BATCH_JOB_STATUS_PROCESSING,
    BATCH_JOB_STATUS_SUBMITTED,
    BATCH_JOB_STATUS_SUCCEEDED,
    BATCH_JOB_STATUS_UPLOADED,
    STAGE_RUN_STATUS_DOWNLOADED,
    STAGE_RUN_STATUS_FAILED,
    STAGE_RUN_STATUS_PROCESSING,
    STAGE_RUN_STATUS_READY,
    STAGE_RUN_STATUS_SUBMITTED,
    make_request_key,
    stable_sha256,
    utc_now_iso,
)


def _remote_state_name(job: Any) -> str:
    state = getattr(job, "state", None)
    if state is None and isinstance(job, dict):
        state = job.get("state") or job.get("status")
    if hasattr(state, "name"):
        return str(state.name)
    if state is None:
        return ""
    return str(state)


def _result_file_name(job: Any) -> str | None:
    dest = getattr(job, "dest", None)
    if dest is None and isinstance(job, dict):
        dest = job.get("dest") or {}
    if hasattr(dest, "file_name"):
        return str(dest.file_name)
    if isinstance(dest, dict):
        file_name = dest.get("file_name")
        if file_name:
            return str(file_name)
    return None


def _map_batch_state(remote_state: str) -> str:
    upper = remote_state.upper()
    if "PENDING" in upper:
        return BATCH_JOB_STATUS_SUBMITTED
    if "RUNNING" in upper or "PROCESSING" in upper:
        return BATCH_JOB_STATUS_PROCESSING
    if "SUCCEEDED" in upper:
        return BATCH_JOB_STATUS_SUCCEEDED
    if "FAILED" in upper:
        return BATCH_JOB_STATUS_FAILED
    if "CANCELLED" in upper:
        return BATCH_JOB_STATUS_CANCELLED
    if "EXPIRED" in upper:
        return BATCH_JOB_STATUS_EXPIRED
    return BATCH_JOB_STATUS_SUBMITTED


def _update_stage_runs_for_batch(state_store, batch_job_name: str, status: str) -> None:
    requests = state_store.list_batch_requests(batch_job_name=batch_job_name)
    stage_run_ids = sorted({req["stage_run_id"] for req in requests if req.get("stage_run_id")})
    for stage_run_id in stage_run_ids:
        state_store.update_stage_run(stage_run_id, status=status)


def submit_ready_batches(
    state_store,
    *,
    stage_name: str | None = None,
    max_batches: int = 3,
) -> list[str]:
    ready_jobs = state_store.list_batch_jobs(
        stage_name=stage_name,
        status=BATCH_JOB_STATUS_LOCAL_READY,
    )
    submitted: list[str] = []
    for job in ready_jobs[: max(0, max_batches)]:
        local_request_file = Path(job["local_request_file"])
        uploaded = gemini_batch_client.upload_jsonl(local_request_file, display_name=local_request_file.name)
        uploaded_name = getattr(uploaded, "name", None) or getattr(uploaded, "file", None) or str(uploaded)
        state_store.update_batch_job_status(
            job["batch_job_name"],
            status=BATCH_JOB_STATUS_UPLOADED,
            uploaded_file_name=str(uploaded_name),
        )
        remote_job = gemini_batch_client.create_batch_job(
            model=job["model"],
            uploaded_file_name=str(uploaded_name),
            display_name=job["batch_job_name"],
        )
        remote_name = getattr(remote_job, "name", None) or job["batch_job_name"]
        state_store.update_batch_job_status(
            job["batch_job_name"],
            status=BATCH_JOB_STATUS_SUBMITTED,
            remote_job_name=str(remote_name),
        )
        _update_stage_runs_for_batch(state_store, job["batch_job_name"], STAGE_RUN_STATUS_SUBMITTED)
        submitted.append(job["batch_job_name"])
    return submitted


def poll_active_batches(state_store) -> dict[str, str]:
    active_jobs = [
        job for job in state_store.get_unfinished_batches()
        if job.get("status") != BATCH_JOB_STATUS_LOCAL_READY
    ]
    status_map: dict[str, str] = {}
    for job in active_jobs:
        remote_name = job.get("remote_job_name") or job["batch_job_name"]
        remote_job = gemini_batch_client.get_batch_job(str(remote_name))
        remote_state = _remote_state_name(remote_job)
        local_status = _map_batch_state(remote_state)
        result_file_name = _result_file_name(remote_job)
        state_store.update_batch_job_status(
            job["batch_job_name"],
            status=local_status,
            result_file_name=result_file_name,
        )
        if local_status == BATCH_JOB_STATUS_PROCESSING:
            _update_stage_runs_for_batch(state_store, job["batch_job_name"], STAGE_RUN_STATUS_PROCESSING)
        elif local_status == BATCH_JOB_STATUS_FAILED:
            _update_stage_runs_for_batch(state_store, job["batch_job_name"], STAGE_RUN_STATUS_FAILED)
        status_map[job["batch_job_name"]] = local_status
    return status_map


def download_completed_batches(state_store) -> list[Path]:
    completed_jobs = state_store.list_batch_jobs(status=BATCH_JOB_STATUS_SUCCEEDED)
    downloaded_paths: list[Path] = []
    for job in completed_jobs:
        result_file_name = job.get("result_file_name")
        if not result_file_name:
            continue
        destination = Path(job["local_request_file"]).with_name(f"{job['batch_job_name']}.results.jsonl")
        if not destination.exists():
            payload = gemini_batch_client.download_result_file(str(result_file_name))
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(payload)
        downloaded_paths.append(destination)
        _update_stage_runs_for_batch(state_store, job["batch_job_name"], STAGE_RUN_STATUS_DOWNLOADED)
    return downloaded_paths


def retry_failed_requests(state_store, stage_name: str) -> int:
    retryable_requests = state_store.get_retryable_requests(stage_name=stage_name)
    if not retryable_requests:
        return 0

    lessons_by_id = {lesson["lesson_id"]: lesson for lesson in state_store.list_lessons()}
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for request in retryable_requests:
        key = (request["stage_run_id"], request["spool_file_path"])
        grouped.setdefault(key, []).append(request)

    recreated = 0
    for (old_stage_run_id, original_spool_path), requests in grouped.items():
        original_stage_run = state_store.get_stage_run(old_stage_run_id)
        if original_stage_run is None:
            continue
        lesson = lessons_by_id.get(requests[0]["lesson_id"])
        if lesson is None:
            continue
        lesson_name = lesson["lesson_name"]
        lesson_root = Path(lesson["lesson_root"])
        paths = PipelinePaths(video_root=lesson_root)
        paths.ensure_batch_dirs(stage_name)
        retry_fragment = f"{lesson_name}.retry_{utc_now_iso().replace(':', '-')}"
        retry_spool_path = paths.batch_spool_requests_path(stage_name, retry_fragment)
        retry_manifest_path = paths.batch_spool_manifest_path(stage_name, retry_fragment)
        original_lines = list(
            gemini_batch_client.iter_result_jsonl(Path(original_spool_path).read_text(encoding="utf-8"))
        )
        request_keys = {request["request_key"] for request in requests}
        retry_lines = [line for line in original_lines if str(line.get("key")) in request_keys]
        if not retry_lines:
            continue
        new_stage_run = state_store.create_or_reuse_stage_run(
            lesson_id=lesson["lesson_id"],
            stage_name=stage_name,
            execution_mode="gemini_batch",
            status=STAGE_RUN_STATUS_READY,
            force_new_attempt=True,
        )
        gemini_batch_client.write_jsonl_lines(retry_spool_path, retry_lines)
        source_manifest = {}
        manifest_path = original_stage_run.get("request_manifest_path")
        if manifest_path and Path(manifest_path).exists():
            source_manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
        atomic_write_json(
            retry_manifest_path,
            {
                **source_manifest,
                "spool_file_path": str(retry_spool_path),
                "request_count": len(retry_lines),
                "request_keys": [str(line.get("key")) for line in retry_lines],
                "retry_of_stage_run_id": old_stage_run_id,
                "created_at": utc_now_iso(),
            },
        )
        state_store.update_stage_run(
            new_stage_run["stage_run_id"],
            status=STAGE_RUN_STATUS_READY,
            request_manifest_path=retry_manifest_path,
        )
        for line in retry_lines:
            parsed_key = line.get("key")
            request = next((item for item in requests if item["request_key"] == parsed_key), None)
            if request is None:
                continue
            state_store.record_spool_request(
                request_key=request["request_key"],
                stage_run_id=new_stage_run["stage_run_id"],
                video_id=request["video_id"],
                lesson_id=request["lesson_id"],
                stage_name=request["stage_name"],
                entity_kind=request["entity_kind"],
                entity_index=request["entity_index"],
                payload_sha256=stable_sha256(line),
                spool_file_path=retry_spool_path,
            )
            recreated += 1
    return recreated
