# Phase 11 + 14 + 15 + 16 -- Operations, Config, Acceptance, and Order

Implementation spec for sync compatibility, operational configuration,
acceptance criteria, implementation order, and deliverables.

---

## Phase 11 -- Keep sync mode intact

**Modified code:** Only where strictly necessary in existing files.

### Rules

- Existing sync functions remain the default path
- Batch functions are additive
- No existing test regresses
- Batch materialization calls the same parsers and downstream writers used by sync mode

If helpful, add a thin abstraction: `execution_mode: Literal["sync", "gemini_batch"]`.
Prefer adapters/wrappers over scattered conditionals.

**Verification targets:** Full existing test suite (`pytest tests/`)

---

## Phase 14 -- Operational details

### Config additions (in `helpers/config.py`)

| Key | Type | Default | Notes |
|-----|------|---------|-------|
| `batch_enabled` | bool | `false` | Does not affect sync runs when false |
| `batch_provider` | str | `"gemini"` | Provider-specific to Gemini for now |
| `batch_max_file_size_mb` | int | `500` | Well below 2 GB Gemini limit |
| `batch_max_requests_per_job` | int | `5000` | Per remote batch job |
| `batch_poll_interval_sec` | int | `15` | Polling cadence |
| `batch_submit_limit` | int | `3` | Max concurrent submitted jobs |
| `batch_watch_default_sec` | int | `10` | Default --watch interval |

These keys are optional. Omitting them has no effect on old sync runs.

### Failure handling

- Malformed result line -> mark request FAILED, continue
- Missing text in result -> mark request FAILED, continue
- Parser validation error -> record `error_message`, continue
- Only mark stage_run SUCCEEDED when all request_keys are PARSED and expected final artifacts exist

### Artifact manifests

For each materialized stage, write a manifest JSON listing:

- Source batch job
- Source result file
- Request count, parsed count, failed count
- Written artifact paths

### Remote retention and expiry

Gemini operational limits that matter for this design:

- Files API uploads are stored for **48 hours**
- Files API storage limit is **20 GB per project**
- Per-file upload limit for batch JSONL is **2 GB**
- Batch jobs that remain pending/running too long may move to
  `JOB_STATE_EXPIRED` after **48 hours**

Operational consequence:

- Download completed result files quickly
- Materialize them into local lesson artifacts quickly
- Do not treat Gemini Files API as durable storage
- Keep batch sizes below the practical retry/expiry threshold

### First-run prerequisites

Do not assume `dense_analysis.json` already exists.

There are two valid operational starting points:

- **Fresh lesson / first run:** raw video + transcript/VTT exist, but no visual
  analysis artifacts yet. Run vision first (sync or batch), then proceed to
  `knowledge_extract`.
- **Re-run / comparison / backfill:** `dense_analysis.json` already exists. Skip
  expensive vision recomputation and batch only the LLM-heavy stages.

### 100-video RAG-prep workflow

For a large corpus-prep run:

1. Discover all video roots under `data/`
2. Ensure each lesson has a transcript/VTT
3. If visual analysis is missing, produce `dense_analysis.json` first
4. Batch `knowledge_extract` across lessons/videos with controlled concurrency
5. Download + materialize results into normal per-lesson artifacts
6. Run deterministic downstream local stages:
   - evidence linking
   - rule cards
   - concept graph
   - ML manifests
   - exporters
7. Build corpus exports with `pipeline.corpus`

This is the recommended path for preparing many lessons for later RAG import.

---

## Phase 15 -- Acceptance criteria

Implementation is complete only when ALL of these hold:

1. Existing sync pipeline still runs unchanged.
2. All existing tests pass (`pytest tests/`).
3. New CLI can discover multiple videos and lessons.
4. Vision stage can emit Gemini batch spool fragments without calling the model.
5. Knowledge extraction stage can emit Gemini batch spool fragments without calling the model.
6. Batch assembler creates central JSONL files and registers them in SQLite.
7. Submit command uploads JSONL and creates remote Gemini batch jobs.
8. Poll command updates local status from remote jobs.
9. Download command fetches result JSONL.
10. Materialize command converts result JSONL into the same normal artifacts current downstream code expects.
11. Resume is idempotent and crash-safe.
12. All new batch tests pass.

---

## Phase 16 -- Implementation order

Execute in this exact order:

1. State store + models (Phase 1 + Phase 4) -> `01-state-store.md`
2. PipelinePaths batch dirs (Phase 2) -> `02-paths-and-client.md`
3. `gemini_batch_client` (Phase 3) -> `02-paths-and-client.md`
4. Dense analyzer batch spool + materialize (Phase 5) -> `03-vision-batch.md`
5. LLM processor batch spool + materialize (Phase 6) -> `04-text-llm-batch.md`
6. Batch assembler (Phase 7) -> `05-assembler.md`
7. Run manager submit/poll/download (Phase 8) -> `06-submit-poll.md`
8. Discovery + planning (Phase 9) -> `07-discovery-cli.md`
9. CLI commands (Phase 10) -> `07-discovery-cli.md`
10. Tests (Phase 13) -> `08-testing.md`
11. Final polish / status formatting (Phase 8 status_service) -> `06-submit-poll.md`

### Deliverables

At the end, provide:

- List of files added
- List of files modified
- Migration notes
- CLI examples
- Test command list
- Any open limitations

Do not stop after scaffolding. Implement the working end-to-end version.

---

## Design rationale

**Per-lesson spool fragments first, central batch assembly second.** This is the
critical architectural choice. It matches the existing layout where lesson
artifacts have a strong home under `PipelinePaths`, and downstream stages expect
normal per-lesson artifacts rather than one global batch blob. It makes retry,
resume, and multi-video processing tractable.

**Batch scope limited to LLM-heavy stages only.** The framework has many
deterministic/local stages after LLM extraction -- evidence linking, rule
reduction, concept graph, exporters, validations -- and those must keep
consuming the same saved artifacts they already expect. This preserves the
current tests and artifact contracts documented in
`docs/pipeline_structure_and_features.md`.

This means the repo can already run everything needed for corpus/RAG prep, but
the final all-in-one orchestration convenience layer is still split across:

- `pipeline.batch_cli` for batchable stages
- existing local artifact writers for deterministic downstream stages
- `pipeline.corpus` for corpus export

**Naming isolation.** The new `pipeline/orchestrator/` package is intentionally
separate from the existing `pipeline/component2/orchestrator.py` (which handles
preflight inspection only). The batch CLI is `pipeline/batch_cli.py`, not mixed
into the existing `pipeline/main.py` or `pipeline/component2/main.py`.
