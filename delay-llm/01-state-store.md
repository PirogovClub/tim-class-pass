# Phase 1 + Phase 4 -- State Store and Request Keys

Implementation spec for the SQLite orchestration state and deterministic
request-key helpers.

**New code:**
- `pipeline/orchestrator/__init__.py`
- `pipeline/orchestrator/models.py`
- `pipeline/orchestrator/state_store.py`

**Wraps:** Nothing (foundational)

**Artifact contract preserved:** None affected

---

## Phase 1 -- Persistent run state (SQLite)

Use `sqlite3` from stdlib. Database at `var/pipeline_state.db`. Migrations in
code, not Alembic.

### Schema

1) **videos** -- `video_id` TEXT PK, `video_root` TEXT, `title` TEXT, `config_hash` TEXT, `status` TEXT, `created_at` TEXT, `updated_at` TEXT

2) **lessons** -- `lesson_id` TEXT PK, `video_id` TEXT FK, `lesson_name` TEXT, `lesson_root` TEXT, `vtt_path` TEXT, `status` TEXT, `created_at` TEXT, `updated_at` TEXT

3) **stage_runs** -- `stage_run_id` TEXT PK, `lesson_id` TEXT FK, `stage_name` TEXT, `execution_mode` TEXT, `status` TEXT, `attempt` INT, `request_manifest_path` TEXT, `result_manifest_path` TEXT, `error_message` TEXT, `started_at` TEXT, `finished_at` TEXT, `created_at` TEXT, `updated_at` TEXT

4) **batch_jobs** -- `batch_job_name` TEXT PK, `provider` TEXT, `model` TEXT, `stage_name` TEXT, `local_request_file` TEXT, `uploaded_file_name` TEXT, `result_file_name` TEXT, `status` TEXT, `request_count` INT DEFAULT 0, `success_count` INT DEFAULT 0, `failure_count` INT DEFAULT 0, `created_at` TEXT, `updated_at` TEXT

5) **batch_requests** -- `request_key` TEXT PK, `batch_job_name` TEXT FK, `stage_run_id` TEXT FK, `video_id` TEXT, `lesson_id` TEXT, `stage_name` TEXT, `entity_kind` TEXT, `entity_index` TEXT, `payload_sha256` TEXT, `spool_file_path` TEXT, `parse_status` TEXT, `output_path` TEXT, `error_message` TEXT, `created_at` TEXT, `updated_at` TEXT

6) **artifacts** -- `artifact_id` TEXT PK, `owner_type` TEXT, `owner_id` TEXT, `artifact_type` TEXT, `path` TEXT, `sha256` TEXT, `size_bytes` INT, `created_at` TEXT

### Status enums (strings)

- `stage_runs.status`: PENDING, SPOOLING, READY, SUBMITTED, PROCESSING, DOWNLOADED, MATERIALIZING, SUCCEEDED, FAILED, SKIPPED
- `batch_jobs.status`: LOCAL_READY, UPLOADED, SUBMITTED, PROCESSING, SUCCEEDED, FAILED, CANCELLED, EXPIRED
- `batch_requests.parse_status`: PENDING, PARSED, FAILED

### StateStore requirements

- Auto-initialize schema on first connect
- Idempotent upserts
- Explicit transaction boundaries via `contextmanager`
- UTC ISO-8601 timestamps
- Indexes on: `lessons(video_id)`, `stage_runs(lesson_id, stage_name, status)`, `batch_requests(batch_job_name)`, `batch_requests(stage_run_id)`, `batch_jobs(status)`
- Methods: `ensure_video`, `ensure_lesson`, `create_or_reuse_stage_run`, `record_spool_request`, `create_batch_job`, `attach_requests_to_batch`, `update_batch_job_status`, `mark_request_parsed`, `mark_request_failed`, `summarize_status`, `get_retryable_requests`, `get_unfinished_batches`

### Skeleton: StateStore

```python
# pipeline/orchestrator/state_store.py
import sqlite3
from contextlib import contextmanager

class StateStore:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
```

---

## Phase 4 -- Stable request-key design

**New code:** Helpers in `pipeline/orchestrator/models.py`

**Wraps:** Nothing (new utility)

**Artifact contract preserved:** None

### Key formats

- vision: `{video_id}__{lesson_slug}__vision__frame__{frame_key}`
- knowledge extract: `{video_id}__{lesson_slug}__knowledge__chunk__{chunk_index}`
- markdown render: `{video_id}__{lesson_slug}__render__section__{section_index}`

Sanitize `lesson_name` to a safe slug (lowercase, non-alnum -> underscore).

### Skeleton: Request key helpers

```python
# pipeline/orchestrator/models.py
import re

def slugify_lesson_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")

def make_request_key(
    video_id: str, lesson_slug: str, stage_name: str,
    entity_kind: str, entity_index: str,
) -> str:
    return f"{video_id}__{lesson_slug}__{stage_name}__{entity_kind}__{entity_index}"

def parse_request_key(key: str) -> dict[str, str]:
    parts = key.split("__")
    if len(parts) != 5:
        raise ValueError(f"Invalid request key: {key}")
    return dict(zip(
        ["video_id", "lesson_slug", "stage_name", "entity_kind", "entity_index"],
        parts,
    ))
```

---

## Verification targets

| Test file | Coverage |
|-----------|----------|
| `tests/test_state_store.py` (new) | Schema auto-creates, upserts idempotent, attempt increments, summarize_status |
| `tests/test_request_keys.py` (new) | make_request_key -> parse_request_key round-trip |
