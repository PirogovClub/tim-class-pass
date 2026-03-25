# Phase 2 + Phase 3 -- PipelinePaths Batch Dirs and Gemini Batch Client

Implementation spec for extending `PipelinePaths` with batch artifact paths
and creating the native Gemini Batch API client.

---

## Phase 2 -- Extend PipelinePaths for batch artifacts

**New code:** Additional methods on `PipelinePaths` in `pipeline/contracts.py`

**Wraps:** `PipelinePaths` (frozen dataclass)

**Artifact contract preserved:** All existing path methods unchanged; new batch dirs nested under existing `output_intermediate/`

### New methods

- `batch_root_dir()` -> `output_intermediate/batch/`
- `batch_spool_dir(stage_name)` -> `output_intermediate/batch/<stage>/spool/`
- `batch_spool_requests_path(stage_name, fragment_name)` -> `...spool/<fragment>.jsonl`
- `batch_spool_manifest_path(stage_name, fragment_name)` -> `...spool/<fragment>.manifest.json`
- `batch_results_dir(stage_name)` -> `output_intermediate/batch/<stage>/results/`
- `batch_result_download_path(stage_name, batch_job_name)` -> `...results/<batch_job_name>.jsonl`
- `batch_materialization_debug_path(stage_name)` -> `...batch/<stage>/materialization_debug.json`
- `ensure_batch_dirs()` -> create spool + results dirs for named stages

### Target layout per lesson

```
output_intermediate/
  batch/
    vision/
      spool/
      results/
    knowledge_extract/
      spool/
      results/
    markdown_render/
      spool/
      results/
```

---

## Phase 3 -- Native Gemini batch client

**New code:** `helpers/clients/gemini_batch_client.py`

**Wraps:** `helpers/clients/gemini_client.py` (`get_client()` reuse)

**Artifact contract preserved:** None (new I/O layer)

### Functions to implement

1. `get_client()` -- reuse or re-import from `gemini_client`
2. `build_generate_content_batch_line(*, request_key, contents, system_instruction=None, generation_config=None, safety_settings=None) -> dict`
3. `write_jsonl_lines(path, lines) -> int`
4. `upload_jsonl(path, display_name) -> object`
5. `create_batch_job(*, model, uploaded_file_name, display_name) -> object`
6. `get_batch_job(name) -> object`
7. `download_result_file(file_name) -> bytes`
8. `extract_result_text(response_line) -> str | None`
9. `iter_result_jsonl(decoded_text) -> Iterator[dict]`

### Skeleton: Batch line builder

```python
# helpers/clients/gemini_batch_client.py
from __future__ import annotations
from typing import Any

def _system_instruction_content(text: str) -> dict[str, Any]:
    return {"parts": [{"text": text}]}

def build_generate_content_batch_line(
    *,
    request_key: str,
    contents: list,
    system_instruction: str | None = None,
    generation_config: dict | None = None,
    safety_settings: list | None = None,
) -> dict[str, Any]:
    request: dict[str, Any] = {"contents": contents}
    if system_instruction:
        request["systemInstruction"] = _system_instruction_content(system_instruction)
    if generation_config:
        request["generationConfig"] = generation_config
    if safety_settings:
        request["safetySettings"] = safety_settings
    return {"key": request_key, "request": request}
```

### Skeleton: Result text extraction

```python
# helpers/clients/gemini_batch_client.py
def extract_result_text(result_line: dict) -> str | None:
    response = result_line.get("response") or {}
    candidates = response.get("candidates") or []
    if not candidates:
        return None
    content = (candidates[0] or {}).get("content") or {}
    parts = content.get("parts") or []
    texts = [p.get("text") for p in parts if p.get("text")]
    joined = "\n".join(t.strip() for t in texts if t.strip()).strip()
    return joined or None
```

### Live SDK compatibility notes

The implementation must match the current `google-genai` SDK behavior observed in
real batch runs:

- Batch JSONL uploads should set an explicit MIME type. In practice,
  `mime_type="text/plain"` is the safest choice for `.jsonl` batch request
  files.
- Batch result downloads should call the SDK with `client.files.download(file=...)`
  rather than `name=...`.
- Result files returned by Gemini must be downloaded and stored locally as soon as
  practical; Files API objects are not durable project storage.

---

## Verification targets

| Test file | Coverage |
|-----------|----------|
| `tests/test_output_layout.py` (extend existing) | New `batch_*` path methods return expected paths |
| `tests/test_gemini_batch_client.py` (new) | Batch line shape, systemInstruction omission, key stability, result text extraction |
