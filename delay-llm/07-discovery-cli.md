# Phase 9 + Phase 10 -- Discovery, Planning, and CLI

Implementation spec for multi-video discovery/planning and the Click-based
batch CLI that wires all orchestrator modules together.

---

## Phase 9 -- Multi-video discovery and planning

**New code:** `pipeline/orchestrator/discovery.py`

**Wraps:** `pipeline/corpus/lesson_registry.py` (`discover_lessons`) for discovery conventions; `helpers/config.py` (`get_config_for_video`) for config loading; `PipelinePaths` for artifact existence checks

**Artifact contract preserved:** Uses but does not modify any artifacts

### Discovery rules

- Each immediate child of the data root is one video root
- Infer `video_id` from directory name
- Discover lessons by VTT naming conventions already used in the framework
- Use `pipeline.yml` via `get_config_for_video()` where available
- Compute `config_hash` to detect changed settings

### Planner behavior

- For each lesson, determine which stages are already complete from existing artifacts via `PipelinePaths`
- Only plan missing or invalid stages
- Do not rerun stages whose final artifacts exist and validate, unless `--force` is given

### Planner stage names

(Matching `pipeline/stage_registry.py` where possible)

- `vision` (batch-eligible)
- `invalidation_filter` (local)
- `lesson_chunks` (local)
- `knowledge_extract` (batch-eligible)
- `evidence_link` (local)
- `rule_reduce` (local)
- `concept_graph` (local)
- `exporters` (local)
- `markdown_render` (batch-eligible, only when LLM render is enabled)

---

## Phase 10 -- CLI

**New code:** `pipeline/batch_cli.py`

**Wraps:** All orchestrator modules + existing stage logic

**Artifact contract preserved:** All downstream artifacts are written by the same code paths as sync mode.

Use Click (already in `pyproject.toml`).

### Commands

1. **discover** -- `python -m pipeline.batch_cli discover --data-root data`
   Populate videos/lessons in SQLite, print summary counts.

2. **plan** -- `python -m pipeline.batch_cli plan --data-root data`
   Create stage_runs for pending work, print pending by stage.

3. **spool** -- `python -m pipeline.batch_cli spool --stage vision [--limit-videos 5]`
   Call batch spool emitters for pending lessons, persist manifests and request rows, mark stage_runs READY.

4. **assemble** -- `python -m pipeline.batch_cli assemble --stage vision`
   Merge spool fragments into central batch files, create batch_jobs rows with LOCAL_READY.

5. **submit** -- `python -m pipeline.batch_cli submit --stage vision [--max-batches 3]`
   Upload + create remote jobs, persist remote names, print created jobs.

6. **poll** -- `python -m pipeline.batch_cli poll`
   Refresh statuses for active jobs, print counts by state.

7. **download** -- `python -m pipeline.batch_cli download`
   Download completed batch result files not yet downloaded.

8. **materialize** -- `python -m pipeline.batch_cli materialize --stage vision`
   Convert downloaded result JSONL into normal framework artifacts.

9. **resume** -- `python -m pipeline.batch_cli resume`
   Convenience: discover -> plan -> spool -> assemble -> submit -> poll -> download -> materialize. Idempotent; only executes safe pending steps.

10. **status** -- `python -m pipeline.batch_cli status [--watch 10]`
    Print aggregated tables: videos by status, lessons by status, stage_runs by stage/status, batch_jobs by remote state. `--watch N` refreshes every N seconds.

11. **retry-failed** -- `python -m pipeline.batch_cli retry-failed --stage knowledge_extract`
    Create new attempts for failed stage_runs/batch_jobs, only for incomplete requests.

### CLI output

Plain text tables, concise, non-zero exit on fatal errors, zero on no-op.

---

## Verification targets

| Test file | Coverage |
|-----------|----------|
| `tests/test_batch_cli.py` (new) | discover/plan/status no-op safely, spool/assemble/submit idempotent |
