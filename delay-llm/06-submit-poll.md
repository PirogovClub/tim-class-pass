# Phase 8 -- Submit, Poll, Download, Retry

Implementation spec for the remote batch lifecycle manager and status service.

**New code:** `pipeline/orchestrator/run_manager.py`, `pipeline/orchestrator/status_service.py`

**Wraps:** `helpers/clients/gemini_batch_client.py` (upload, create, get, download)

**Artifact contract preserved:** Downloaded result JSONL is the raw Gemini output; no artifact contract affected until materialize.

---

## Submission

- Scan LOCAL_READY `batch_jobs`
- Upload JSONL via `gemini_batch_client.upload_jsonl()`
- Create remote job via `create_batch_job()`
- Persist: `uploaded_file_name`, remote batch job name, status = SUBMITTED

---

## Polling

Map Gemini states to local states:

| Gemini state | Local state |
|-------------|-------------|
| `JOB_STATE_PENDING` | SUBMITTED |
| `JOB_STATE_RUNNING` / `PROCESSING` | PROCESSING |
| `JOB_STATE_SUCCEEDED` | SUCCEEDED |
| `JOB_STATE_FAILED` | FAILED |
| `JOB_STATE_CANCELLED` | CANCELLED |
| `JOB_STATE_EXPIRED` | EXPIRED |

---

## Download

- When SUCCEEDED and `dest.file_name` exists: download result bytes, save to `batch_results_dir(...)`, update stage_runs to DOWNLOADED

---

## Retry

- For FAILED/EXPIRED/CANCELLED jobs: identify affected `request_keys` from local manifest, re-spool only those requests, bump `stage_run` attempt
- Do NOT regenerate all lesson payloads

---

## Verification targets

| Test file | Coverage |
|-----------|----------|
| `tests/test_batch_cli.py` (new) | Smoke tests for submit/poll/download idempotency |
