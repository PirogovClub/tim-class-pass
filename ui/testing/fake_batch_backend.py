from __future__ import annotations

import json
import os
from pathlib import Path

from pipeline.component2.llm_processor import materialize_batch_results_for_knowledge_extract, materialize_batch_results_for_markdown_render
from pipeline.component2.knowledge_builder import adapt_chunks, load_chunks_json
from pipeline.component2.exporters import load_evidence_index, load_rule_cards
from pipeline.contracts import PipelinePaths
from pipeline.dense_analyzer import materialize_batch_results_for_analysis
from pipeline.orchestrator import (
    BATCH_JOB_STATUS_FAILED,
    BATCH_JOB_STATUS_PROCESSING,
    BATCH_JOB_STATUS_SUBMITTED,
    BATCH_JOB_STATUS_SUCCEEDED,
    STAGE_KNOWLEDGE_EXTRACT,
    STAGE_MARKDOWN_RENDER,
    STAGE_VISION,
)
from ui.testing.fake_payloads import fake_batch_result_text_for_request_key


def _state_path_for_job(job: dict) -> Path:
    return Path(job["local_request_file"]).with_suffix(".fake_state.json")


def _default_polls_before_success() -> int:
    raw_value = os.getenv("UI_FAKE_BATCH_POLLS_BEFORE_SUCCESS", "1")
    try:
        return max(0, int(raw_value))
    except ValueError:
        return 1


def _scenario_for_stage(stage_name: str) -> str:
    env_key = f"UI_FAKE_BATCH_SCENARIO_{stage_name.upper()}"
    return os.getenv(env_key) or os.getenv("UI_FAKE_BATCH_SCENARIO", "success")


def submit_ready_batches(state_store, *, stage_name: str | None = None, max_batches: int = 3) -> list[str]:
    ready_jobs = state_store.list_batch_jobs(stage_name=stage_name, status="LOCAL_READY")
    submitted: list[str] = []
    for job in ready_jobs[: max(0, max_batches)]:
        remote_name = f"fake/{job['batch_job_name']}"
        result_file_name = f"{job['batch_job_name']}.remote.jsonl"
        state_store.update_batch_job_status(
            job["batch_job_name"],
            status=BATCH_JOB_STATUS_SUBMITTED,
            remote_job_name=remote_name,
            uploaded_file_name=f"fake-upload/{job['batch_job_name']}.jsonl",
            result_file_name=result_file_name,
        )
        _state_path_for_job(job).write_text(
            json.dumps(
                {
                    "scenario": _scenario_for_stage(job["stage_name"]),
                    "polls_remaining": _default_polls_before_success(),
                    "result_file_name": result_file_name,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        submitted.append(job["batch_job_name"])
    return submitted


def poll_active_batches(state_store) -> dict[str, str]:
    active_jobs = [
        job
        for job in state_store.get_unfinished_batches()
        if job.get("status") in {BATCH_JOB_STATUS_SUBMITTED, BATCH_JOB_STATUS_PROCESSING}
    ]
    status_map: dict[str, str] = {}
    for job in active_jobs:
        state_path = _state_path_for_job(job)
        payload = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {
            "scenario": "success",
            "polls_remaining": 0,
            "result_file_name": f"{job['batch_job_name']}.remote.jsonl",
        }
        polls_remaining = int(payload.get("polls_remaining", 0))
        scenario = str(payload.get("scenario", "success"))
        if scenario == "fail":
            status = BATCH_JOB_STATUS_FAILED
        elif polls_remaining > 0:
            payload["polls_remaining"] = polls_remaining - 1
            state_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            status = BATCH_JOB_STATUS_PROCESSING
        else:
            status = BATCH_JOB_STATUS_SUCCEEDED
        state_store.update_batch_job_status(
            job["batch_job_name"],
            status=status,
            result_file_name=str(payload.get("result_file_name") or f"{job['batch_job_name']}.remote.jsonl"),
        )
        status_map[job["batch_job_name"]] = status
    return status_map


def download_completed_batches(state_store) -> list[Path]:
    downloaded_paths: list[Path] = []
    for job in state_store.list_batch_jobs(status=BATCH_JOB_STATUS_SUCCEEDED):
        destination = Path(job["local_request_file"]).with_name(f"{job['batch_job_name']}.results.jsonl")
        if destination.exists():
            downloaded_paths.append(destination)
            continue
        rows = []
        for raw_line in Path(job["local_request_file"]).read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            payload = json.loads(line)
            request_key = str(payload.get("key") or "")
            rows.append(
                {
                    "key": request_key,
                    "response": {
                        "candidates": [
                            {
                                "content": {
                                    "parts": [{"text": fake_batch_result_text_for_request_key(request_key)}]
                                }
                            }
                        ]
                    },
                }
            )
        destination.write_text(
            "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + ("\n" if rows else ""),
            encoding="utf-8",
        )
        downloaded_paths.append(destination)
    return downloaded_paths


def materialize_stage_results(state_store, *, stage_name: str) -> int:
    jobs = [
        job for job in state_store.list_batch_jobs(stage_name=stage_name)
        if Path(job["local_request_file"]).with_name(f"{job['batch_job_name']}.results.jsonl").exists()
    ]
    lessons_by_id = {lesson["lesson_id"]: lesson for lesson in state_store.list_lessons()}
    materialized = 0
    for job in jobs:
        result_path = Path(job["local_request_file"]).with_name(f"{job['batch_job_name']}.results.jsonl")
        request_rows = state_store.list_batch_requests(batch_job_name=job["batch_job_name"])
        lesson_ids = sorted({row["lesson_id"] for row in request_rows})
        for lesson_id in lesson_ids:
            lesson = lessons_by_id.get(lesson_id)
            if lesson is None:
                continue
            video_root = Path(lesson["lesson_root"])
            paths = PipelinePaths(video_root=video_root)
            if stage_name == STAGE_VISION:
                materialize_batch_results_for_analysis(
                    result_path,
                    video_root=video_root,
                    lesson_context={
                        "lesson_id": lesson["lesson_id"],
                        "lesson_name": lesson["lesson_name"],
                        "video_id": lesson["video_id"],
                    },
                    frames_dir=video_root / "frames_dense",
                    state_store=state_store,
                )
            elif stage_name == STAGE_KNOWLEDGE_EXTRACT:
                raw_chunks = load_chunks_json(paths.lesson_chunks_path(lesson["lesson_name"]))
                adapted = adapt_chunks(raw_chunks, lesson_id=lesson["lesson_name"], lesson_title=None)
                materialize_batch_results_for_knowledge_extract(
                    result_path,
                    adapted,
                    lesson["lesson_id"],
                    paths,
                    state_store,
                )
            elif stage_name == STAGE_MARKDOWN_RENDER:
                materialize_batch_results_for_markdown_render(
                    result_path,
                    lesson["lesson_id"],
                    paths,
                    state_store,
                )
            materialized += 1
    return materialized

