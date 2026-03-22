from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from helpers.clients import gemini_batch_client
from pipeline.io_utils import atomic_write_json
from pipeline.orchestrator import BATCH_JOB_STATUS_LOCAL_READY, utc_now_iso


def _load_manifest(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def assemble_batch_files(
    state_store,
    stage_name: str,
    *,
    max_file_size_mb: int = 500,
    max_requests: int = 5000,
    batches_root: str | Path = "var/batches",
) -> list[Path]:
    ready_runs = state_store.list_stage_runs(
        stage_name=stage_name,
        status="READY",
        execution_mode="gemini_batch",
    )
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for stage_run in ready_runs:
        manifest_path = stage_run.get("request_manifest_path")
        if not manifest_path:
            continue
        manifest = _load_manifest(manifest_path)
        key = (
            str(manifest.get("provider") or "gemini"),
            str(manifest.get("model") or ""),
            str(manifest.get("stage_name") or stage_name),
        )
        manifest["stage_run_id"] = stage_run["stage_run_id"]
        groups[key].append(manifest)

    if not groups:
        return []

    created_paths: list[Path] = []
    timestamp = utc_now_iso().replace(":", "-")
    batch_dir = Path(batches_root) / timestamp
    batch_dir.mkdir(parents=True, exist_ok=True)

    for (provider, model, grouped_stage), manifests in sorted(groups.items()):
        manifests.sort(
            key=lambda item: (
                str(item.get("lesson_id") or ""),
                str(item.get("spool_file_path") or ""),
            )
        )
        assembled_lines: list[dict[str, Any]] = []
        assembled_request_keys: list[str] = []
        assembled_sources: list[dict[str, Any]] = []
        file_index = 1

        def flush_current() -> None:
            nonlocal assembled_lines, assembled_request_keys, assembled_sources, file_index
            if not assembled_lines:
                return
            batch_job_name = f"local_{grouped_stage}_{timestamp}_{file_index:03d}"
            assembled_path = batch_dir / f"gemini_{grouped_stage}_{file_index:03d}.jsonl"
            manifest_path = assembled_path.with_suffix(".manifest.json")
            gemini_batch_client.write_jsonl_lines(assembled_path, assembled_lines)
            atomic_write_json(
                manifest_path,
                {
                    "batch_job_name": batch_job_name,
                    "provider": provider,
                    "model": model,
                    "stage_name": grouped_stage,
                    "request_count": len(assembled_request_keys),
                    "request_keys": assembled_request_keys,
                    "source_fragments": assembled_sources,
                    "created_at": utc_now_iso(),
                },
            )
            state_store.create_batch_job(
                batch_job_name=batch_job_name,
                provider=provider,
                model=model,
                stage_name=grouped_stage,
                local_request_file=assembled_path,
                status=BATCH_JOB_STATUS_LOCAL_READY,
                request_count=len(assembled_request_keys),
            )
            state_store.attach_requests_to_batch(batch_job_name, assembled_request_keys)
            created_paths.append(assembled_path)
            file_index += 1
            assembled_lines = []
            assembled_request_keys = []
            assembled_sources = []

        max_bytes = max_file_size_mb * 1024 * 1024
        current_bytes = 0
        for manifest in manifests:
            spool_path = Path(manifest["spool_file_path"])
            fragment_lines = list(
                gemini_batch_client.iter_result_jsonl(spool_path.read_text(encoding="utf-8"))
            )
            fragment_bytes = spool_path.stat().st_size if spool_path.exists() else 0
            fragment_request_keys = [str(line.get("key")) for line in fragment_lines]
            if assembled_lines and (
                len(assembled_request_keys) + len(fragment_request_keys) > max_requests
                or current_bytes + fragment_bytes > max_bytes
            ):
                flush_current()
                current_bytes = 0

            assembled_lines.extend(fragment_lines)
            assembled_request_keys.extend(fragment_request_keys)
            assembled_sources.append(
                {
                    "lesson_id": manifest.get("lesson_id"),
                    "spool_file_path": str(spool_path),
                    "request_count": len(fragment_request_keys),
                    "stage_run_id": manifest.get("stage_run_id"),
                }
            )
            current_bytes += fragment_bytes

        flush_current()
    return created_paths
