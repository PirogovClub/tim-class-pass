from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any

STAGE_VISION = "vision"
STAGE_KNOWLEDGE_EXTRACT = "knowledge_extract"
STAGE_MARKDOWN_RENDER = "markdown_render"

STAGE_RUN_STATUS_PENDING = "PENDING"
STAGE_RUN_STATUS_SPOOLING = "SPOOLING"
STAGE_RUN_STATUS_READY = "READY"
STAGE_RUN_STATUS_SUBMITTED = "SUBMITTED"
STAGE_RUN_STATUS_PROCESSING = "PROCESSING"
STAGE_RUN_STATUS_DOWNLOADED = "DOWNLOADED"
STAGE_RUN_STATUS_MATERIALIZING = "MATERIALIZING"
STAGE_RUN_STATUS_SUCCEEDED = "SUCCEEDED"
STAGE_RUN_STATUS_FAILED = "FAILED"
STAGE_RUN_STATUS_SKIPPED = "SKIPPED"

BATCH_JOB_STATUS_LOCAL_READY = "LOCAL_READY"
BATCH_JOB_STATUS_UPLOADED = "UPLOADED"
BATCH_JOB_STATUS_SUBMITTED = "SUBMITTED"
BATCH_JOB_STATUS_PROCESSING = "PROCESSING"
BATCH_JOB_STATUS_SUCCEEDED = "SUCCEEDED"
BATCH_JOB_STATUS_FAILED = "FAILED"
BATCH_JOB_STATUS_CANCELLED = "CANCELLED"
BATCH_JOB_STATUS_EXPIRED = "EXPIRED"

REQUEST_PARSE_STATUS_PENDING = "PENDING"
REQUEST_PARSE_STATUS_PARSED = "PARSED"
REQUEST_PARSE_STATUS_FAILED = "FAILED"

TERMINAL_STAGE_RUN_STATUSES = {
    STAGE_RUN_STATUS_SUCCEEDED,
    STAGE_RUN_STATUS_FAILED,
    STAGE_RUN_STATUS_SKIPPED,
}

TERMINAL_BATCH_JOB_STATUSES = {
    BATCH_JOB_STATUS_SUCCEEDED,
    BATCH_JOB_STATUS_FAILED,
    BATCH_JOB_STATUS_CANCELLED,
    BATCH_JOB_STATUS_EXPIRED,
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def slugify_lesson_name(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", str(name or "").strip().lower()).strip("_")
    return slug or "lesson"


def make_request_key(
    video_id: str,
    lesson_slug: str,
    stage_name: str,
    entity_kind: str,
    entity_index: str,
) -> str:
    return "__".join(
        [
            str(video_id).strip(),
            str(lesson_slug).strip(),
            str(stage_name).strip(),
            str(entity_kind).strip(),
            str(entity_index).strip(),
        ]
    )


def parse_request_key(key: str) -> dict[str, str]:
    parts = str(key).split("__")
    if len(parts) != 5 or any(not part for part in parts):
        raise ValueError(f"Invalid request key: {key}")
    return {
        "video_id": parts[0],
        "lesson_slug": parts[1],
        "stage_name": parts[2],
        "entity_kind": parts[3],
        "entity_index": parts[4],
    }


def stable_sha256(payload: Any) -> str:
    if isinstance(payload, bytes):
        data = payload
    elif isinstance(payload, str):
        data = payload.encode("utf-8")
    else:
        data = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(data).hexdigest()
