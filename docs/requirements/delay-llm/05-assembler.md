# Phase 7 -- Batch Assembler

Implementation spec for merging per-lesson spool fragments into central
Gemini batch files.

**New code:** `pipeline/orchestrator/batch_assembler.py`

**Wraps:** Spool fragments written by Phases 5-6

**Artifact contract preserved:** None (new orchestration artifact)

---

## Responsibilities

- Discover lesson-local spool fragments with status READY and not yet attached to a remote batch
- Merge compatible fragments into one assembled JSONL file

### Compatibility grouping key

```
(provider, model, stage_name)
```

Never mix stage names in one remote batch.

### Assembly rules

- Keep assembled file size under configurable threshold (default 500 MB, well below 2 GB hard max)
- Keep request counts under configurable threshold (default 5000 per job)
- Preserve line order for determinism
- Output assembled files under: `var/batches/{timestamp}/gemini_{stage_name}_{n}.jsonl`
- Write sidecar manifest JSON
- Create `batch_jobs` row with `status=LOCAL_READY`
- Attach constituent `batch_requests` rows to the local batch entry

---

## Verification targets

| Test file | Coverage |
|-----------|----------|
| `tests/test_batch_assembler.py` (new) | Combines compatible fragments, does not mix stages, respects size/count thresholds, deterministic ordering |
