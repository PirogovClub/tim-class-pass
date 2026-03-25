# Phase 5 -- Batch Spool + Materialize for Dense Vision Stage

Implementation spec for adding batch spool emission and result materialization
to `pipeline/dense_analyzer.py`.

**New code:** Functions added to `pipeline/dense_analyzer.py`

**Wraps:** `get_batch_prompt_independent()`, `_encode_image()`, `_parse_json_from_response()`, `PRODUCTION_PROMPT`

**Artifact contract preserved:** Final `dense_analysis.json` and per-frame `frames_dense/frame_<key>.json` must have identical shape to sync mode.

---

## New functions

### 1. `emit_batch_spool_for_analysis`

```
emit_batch_spool_for_analysis(
    *,
    video_root,
    lesson_context,
    queue_keys,
    frames_dir,
    config,
    state_store,
) -> Path
```

For each frame key:
- Read image, encode via `_encode_image()`
- Build contents payload compatible with GenerateContentRequest
- Create batch line via `gemini_batch_client.build_generate_content_batch_line()`
- Write lesson-local spool fragment JSONL
- Record `batch_requests` rows in SQLite with `parse_status=PENDING`

Write sidecar manifest JSON:

```json
{
  "video_id": "...",
  "lesson_id": "...",
  "stage_name": "vision",
  "request_count": 123,
  "request_keys": ["..."],
  "created_at": "..."
}
```

Do NOT write final `dense_analysis.json` here. Spooling only emits batch requests.

### 2. `materialize_batch_results_for_analysis`

```
materialize_batch_results_for_analysis(
    results_jsonl_path,
    ...,
    state_store,
) -> dict
```

For each result line:
- Parse request key
- Extract text via `gemini_batch_client.extract_result_text()`
- Pass through `_parse_json_from_response()` and `ensure_material_change()`
- Accumulate frame records
- Write `dense_analysis.json` and per-frame JSONs via `_write_analysis_outputs()`

> If `_parse_json_from_response` is too entangled with the API call path, extract
> a thin `parse_frame_analysis_text(text) -> dict` that both sync and batch call.

---

## Rules

- Do NOT break `run_analysis()` default behavior.
- Do NOT write final artifacts during spooling -- spooling only emits batch requests.
- Reuse the current prompt logic: `_encode_image()`, `get_batch_prompt()` / `get_batch_prompt_independent()`.
- Do not rewrite analysis prompt semantics.

---

## Verification targets

| Test file | Coverage |
|-----------|----------|
| `tests/test_dense_analyzer_batch.py` (new) | Materialized output matches sync parser path, artifact shape invariants |
| `tests/test_dense_analyzer.py` (existing) | Must not regress |
