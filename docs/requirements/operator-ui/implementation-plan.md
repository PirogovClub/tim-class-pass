# Operator UI Implementation Plan

This single-file plan now has a split, maintained version under
[`plan/`](plan/).

Start with [`plan/00-index.md`](plan/00-index.md).

## Goal

Add a simple operator-facing web UI for the existing Python pipeline so a user can:

- create or import a video project into `data/<video_id>/`
- select which pipeline steps to run
- launch sync or batch-backed processing
- monitor progress and logs
- automatically poll remote Gemini Batch jobs through the backend
- trigger download/materialization when batch jobs complete
- optionally build corpus outputs for later RAG import

This UI should reuse the current pipeline and batch orchestration code rather than replacing it.

## Recommended Stack

Use:

- `FastAPI` for HTTP routes and backend orchestration
- `Jinja2` templates for server-rendered pages
- `HTMX` for partial refresh and status polling
- minimal plain JavaScript only where necessary
- `Playwright` for browser E2E tests

Rationale:

- the repo is already Python-first
- `fastapi` is already a dependency
- there is already an API pattern in `pipeline/rag/api.py`
- most complexity here is backend orchestration, not rich frontend state
- a server-rendered operator UI is faster to implement and easier to debug than a SPA

## Dependencies To Add

Backend/runtime:

- `jinja2` for template rendering
- `python-multipart` for local file upload handling in FastAPI forms

Testing:

- `playwright`
- `pytest-playwright` or a thin custom pytest wrapper around Playwright

Frontend/runtime assets:

- `htmx` loaded from CDN in V1

## App Bootstrap Details

The plan should explicitly include these startup concerns:

- create a FastAPI app dedicated to operator UI routes
- mount Jinja with `Jinja2Templates`
- mount static assets with `StaticFiles`
- support form posts and file uploads for local project creation
- keep the UI app local-only in V1 (localhost bind)
- keep UI run logs and run registry outside `data/` so lesson artifacts stay clean

## Product Scope

### Primary user flows

1. Create a project from a YouTube URL
2. Create a project from local files (`.mp4` and `.vtt`)
3. Open an existing `data/<video_id>/` project
4. Inspect discovered lessons and existing artifacts
5. Choose which steps to run
6. Start a run and watch progress/logs
7. Monitor batch jobs and let the backend reconcile remote status
8. Download/materialize batch results automatically when ready
9. Build corpus outputs after lesson artifacts are complete

### Explicit non-goals for V1

- multi-user auth
- permissions/roles
- distributed worker queue
- React/Vue SPA
- editing transcripts or artifacts in-browser
- managing Google credentials in the UI
- full replacement of the CLI

## Existing Code To Reuse

### Main sync pipeline

- `pipeline/main.py`
- supports `--url`
- supports `--video_id`
- creates `data/<video_id>/`
- runs Step 1 -> Step 2 -> Step 3

### Batch orchestration

- `pipeline/batch_cli.py`
- `pipeline/orchestrator/discovery.py`
- `pipeline/orchestrator/run_manager.py`
- `pipeline/orchestrator/state_store.py`

### Downstream lesson artifact generation

- `pipeline/component2/main.py`
- deterministic post-knowledge stages already exist here

### Corpus build for RAG prep

- `pipeline/corpus/cli.py`
- `pipeline/corpus/corpus_builder.py`

### Existing API pattern

- `pipeline/rag/api.py`

## High-Level Architecture

```text
Browser
  -> FastAPI routes
    -> UI service layer
      -> existing pipeline functions / subprocess wrappers
      -> local run state store
      -> batch state reconciliation
      -> artifact inspection helpers
```

The browser should never talk to Google directly.

The backend is responsible for:

- polling Gemini Batch state
- deciding when to download results
- deciding when to materialize outputs
- exposing current run state to the UI

## UI Structure

### 1. Project list page

Route:

- `GET /ui/projects`

Shows:

- all `data/<video_id>/` folders
- current status summary
- artifact availability summary
- last run timestamp if known
- links to open project details

### 2. New project page

Routes:

- `GET /ui/projects/new`
- `POST /ui/projects/new/from-url`
- `POST /ui/projects/new/from-files`

Modes:

- create from YouTube URL
- create from local video + local VTT
- create empty shell project if needed

Responsibilities:

- normalize and validate `video_id`
- create `data/<video_id>/`
- copy/upload local files into that folder
- optionally create a starter `pipeline.yml`

### 3. Project detail page

Route:

- `GET /ui/projects/{video_id}`

Shows:

- video metadata
- discovered lessons (`*.vtt`)
- key artifacts present/missing
- pipeline config summary
- run controls
- recent logs
- batch status if applicable

### 4. Run configuration page/section

Displayed inline on project detail page or separate route:

- source mode
  - sync pipeline
  - batch-backed pipeline
- step checkboxes
  - import/download
  - dense capture
  - structural compare
  - queue/prompts
  - vision
  - knowledge extract
  - downstream deterministic artifacts
  - markdown render
  - corpus build
- advanced options
  - workers
  - batch size
  - max batches
  - force/recapture/recompare
  - batch submit limit

### 5. Run status page

Routes:

- `GET /ui/runs/{run_id}`
- `GET /ui/runs/{run_id}/status-fragment`
- `GET /ui/runs/{run_id}/logs-fragment`

Shows:

- current stage
- current local status
- batch status table
- latest logs
- artifact outputs written so far
- actionable errors

This page should use HTMX polling every 10-30 seconds.

### 6. Corpus build page

Routes:

- `GET /ui/corpus`
- `POST /ui/corpus/build`

Shows:

- eligible lessons
- last corpus build summary
- validation status
- output location

## Backend Modules To Add

Suggested new package:

- `pipeline/operator_ui/`

Suggested files:

- `pipeline/operator_ui/__init__.py`
- `pipeline/operator_ui/app.py`
- `pipeline/operator_ui/routes_projects.py`
- `pipeline/operator_ui/routes_runs.py`
- `pipeline/operator_ui/routes_corpus.py`
- `pipeline/operator_ui/services.py`
- `pipeline/operator_ui/project_loader.py`
- `pipeline/operator_ui/run_registry.py`
- `pipeline/operator_ui/reconcile.py`
- `pipeline/operator_ui/schemas.py`
- `pipeline/operator_ui/runner.py`
- `pipeline/operator_ui/logs.py`
- `pipeline/operator_ui/dependencies.py`

Optional:

- `pipeline/operator_ui/templates/...`
- `pipeline/operator_ui/static/...`

## Browser Testing Architecture

The UI should be tested with a real browser, not only `TestClient`.

Recommended structure:

- Fast backend tests with `TestClient` for route/service correctness
- Browser E2E tests with Playwright for operator workflows
- Use the screenplay pattern so browser tests stay readable and reusable

### Why screenplay pattern here

This UI will have:

- project creation
- staged run selection
- polling-based status updates
- log visibility
- remote-batch reconciliation behavior

Those flows become hard to maintain if Playwright tests are only long raw click
scripts. Screenplay keeps them structured around:

- actors
- abilities
- tasks
- questions
- assertions

## Suggested Playwright Screenplay Layout

Suggested test tree:

- `tests/ui_e2e/`
- `tests/ui_e2e/conftest.py`
- `tests/ui_e2e/screenplay/actor.py`
- `tests/ui_e2e/screenplay/abilities.py`
- `tests/ui_e2e/screenplay/tasks.py`
- `tests/ui_e2e/screenplay/questions.py`
- `tests/ui_e2e/screenplay/assertions.py`
- `tests/ui_e2e/test_project_creation.py`
- `tests/ui_e2e/test_sync_run.py`
- `tests/ui_e2e/test_batch_run.py`
- `tests/ui_e2e/test_resume_retry.py`
- `tests/ui_e2e/test_corpus_build.py`

### Screenplay concepts

#### Actor

Example:

- `Operator`

#### Abilities

Examples:

- browse the UI with Playwright page/context
- inspect downloaded/generated files on disk
- read run log output
- seed fixture projects
- stub batch backend state

#### Tasks

Examples:

- create project from local files
- create project from URL
- open project details
- choose stages to run
- start sync run
- start batch run
- wait for status refresh
- trigger corpus build
- retry failed run

#### Questions

Examples:

- what is the current run status?
- which artifacts exist?
- what lessons were discovered?
- what batch job state is shown?
- did logs contain the expected step marker?

#### Assertions

Examples:

- project folder exists
- run status eventually becomes `SUCCEEDED`
- result artifacts are present
- corpus output exists
- UI shows the same state that local files/db indicate

## Template Structure

Suggested Jinja templates:

- `templates/base.html`
- `templates/projects/index.html`
- `templates/projects/new.html`
- `templates/projects/detail.html`
- `templates/runs/detail.html`
- `templates/corpus/index.html`
- `templates/partials/project_summary.html`
- `templates/partials/run_status.html`
- `templates/partials/log_tail.html`
- `templates/partials/batch_jobs_table.html`
- `templates/partials/artifact_table.html`

## Data Model For UI State

Do not rely only on in-memory state.

Add a small local UI run registry, separate from lesson artifacts.

Suggested persisted file or SQLite table fields:

- `run_id`
- `video_id`
- `mode` (`sync`, `batch`, `hybrid`)
- `requested_steps`
- `status`
- `current_stage`
- `started_at`
- `finished_at`
- `last_error`
- `log_path`
- `db_path` for batch state if used
- `output_root`
- `triggered_by`

This should be distinct from `pipeline/orchestrator/StateStore`, which is for batch orchestration internals.

## First-Run Ingestion Behavior

Support these starting states explicitly:

### Fresh project

Inputs:

- local `.mp4` + `.vtt`, or
- YouTube URL

No `dense_analysis.json` exists.

Allowed run paths:

- full sync pipeline
- full batch-backed path where vision is included

### Reprocessing project

Inputs already exist under `data/<video_id>/`, especially:

- `.vtt`
- maybe `dense_analysis.json`

Allowed run paths:

- skip vision if `dense_analysis.json` already exists
- batch only `knowledge_extract`
- rerun downstream deterministic stages
- build corpus

## Step Mapping

The UI should map user-facing labels to real implementation units.

### Sync pipeline path

Backed by:

- `pipeline/main.py`

User-facing stages:

1. Download/import
2. Dense frame capture
3. Structural compare
4. Queue + prompts
5. Vision
6. Component 2 synthesis

### Batch-backed path

Backed by:

- `pipeline/batch_cli.py`
- `pipeline/component2/main.py`
- `pipeline/corpus/cli.py`

User-facing stages:

1. Discover
2. Plan
3. Batch spool
4. Batch assemble
5. Batch submit
6. Batch poll
7. Batch download
8. Batch materialize
9. Deterministic downstream artifact build
10. Corpus build

## Reconcile Loop Design

This is the key behavior for remote batch processing.

The UI backend should expose a reconcile function that:

1. reads local run state
2. checks whether the run has active batch jobs
3. polls Google indirectly through existing batch functions
4. if a job is `SUCCEEDED`, downloads results if not already downloaded
5. if results are downloaded, materializes them if not already materialized
6. if `knowledge_extract` finished, optionally triggers deterministic downstream local stages
7. updates local run state
8. returns the latest status snapshot

This can be triggered by:

- HTMX polling from the browser
- optional background scheduler later

### Important rule

The reconcile step must be idempotent.

Repeated calls should be safe.

## Recommended Execution Strategy

### V1

Keep execution simple:

- start long-running work as subprocesses
- write logs to per-run log files
- UI reads log tail and status

Why:

- least intrusive
- easiest to debug
- preserves CLI behavior

### V2

If needed later:

- move to direct function calls where stable
- or introduce a background task runner

## Commands/Functions To Wrap

### For sync pipeline

Wrap either:

- `uv run tim-class-pass ...`

or directly call:

- `pipeline.main.main`

For V1, subprocess wrapping is safer.

### For batch workflow

Wrap these logical operations:

- discover
- plan
- spool
- assemble
- submit
- poll
- download
- materialize

### For deterministic downstream after batch knowledge extraction

Use:

- `pipeline.component2.main`

with flags that run:

- evidence linking
- rule cards
- concept graph
- ML manifests
- exporters

without re-running knowledge extraction if batch already produced the knowledge artifacts.

### For corpus/RAG prep

Use:

- `python -m pipeline.corpus --input-root data --output-root output_corpus --strict`

## Functionality Checklist

The UI should support at minimum:

- select video source
- select VTT source
- create `data/<video_id>/`
- show found lessons
- show config summary
- show step checklist
- launch runs
- show logs
- show artifact presence
- show batch job status
- poll Google indirectly through backend
- auto-download results when jobs finish
- auto-materialize after download
- rerun failed steps
- build corpus

## Error Handling

Handle clearly:

- missing `GEMINI_API_KEY`
- missing `.vtt`
- no lessons discovered
- missing `dense_analysis.json` when skipping vision
- batch upload/download SDK quirks
- remote batch expiration
- parser failures on returned LLM content
- partial artifact generation

UI should present:

- current error
- likely next action
- log excerpt
- whether retry is safe

## Logging

Each run should have:

- a log file path stored in run registry
- visible live tail in UI
- links to full log if needed

Suggested location:

- `var/ui-runs/<run_id>.log`

## Security / Safety

For V1:

- local-only operator UI
- no auth if bound to localhost only
- no credential editing in browser
- no arbitrary shell command input from user

Constrain all actions to known pipeline operations.

## Testing Plan

### Unit tests

- project creation/import helpers
- run registry persistence
- artifact detection helpers
- reconcile decision logic
- route handlers for happy path and error path

### Backend integration tests

Use `fastapi.testclient.TestClient` for:

- route registration
- form validation
- file-upload handling
- project creation path
- run registry writes
- reconcile endpoint behavior
- error rendering for missing inputs

These should not require a browser.

### Browser E2E tests (Playwright + screenplay)

Run the UI against a local FastAPI app and test the real rendered pages.

Core browser scenarios:

1. create project from local files
2. open project page and confirm lesson discovery
3. select sync stages and launch a run
4. watch run status/logs update in browser
5. select batch stages and launch a run
6. simulate remote batch progression and verify UI polling updates state
7. verify completed batch causes automatic download/materialization
8. trigger corpus build and verify completion state in UI

### Screenplay-specific test design

Each E2E test should be expressed in screenplay style:

- Actor: `operator`
- Ability: `BrowseTheOperatorUI`
- Tasks:
  - `CreateProjectFromFiles`
  - `RunSyncStages`
  - `RunBatchStages`
  - `WaitForStatus`
  - `BuildCorpus`
- Questions:
  - `CurrentRunStatus`
  - `VisibleArtifacts`
  - `VisibleLessons`
  - `VisibleBatchState`

This avoids brittle raw click scripts and makes flows composable.

### Batch testing strategy

Do not rely on live Google Batch for normal browser E2E.

Instead:

- inject a fake batch adapter or monkeypatched service layer
- simulate `SUBMITTED -> PROCESSING -> SUCCEEDED`
- simulate failed and expired jobs
- simulate downloadable result payloads

Keep live-provider UI tests optional and separately marked.

### Live-provider smoke tests

Optional, manually gated tests may verify:

- a real batch submit can be triggered from the UI
- polling reflects real remote state
- completed job can be downloaded/materialized from the UI

These should be excluded from normal CI and run only when credentials exist.

### Integration tests

- create project from local files
- start a run and capture log output
- simulate batch state transitions
- verify reconcile triggers download/materialize
- verify corpus build action

### Manual validation

1. create fresh project from local files
2. run selected sync stages
3. run selected batch stages
4. leave page open and confirm status auto-refreshes
5. confirm completed batch causes local download/materialization
6. confirm corpus build produces outputs

## Implementation Phases

### Phase 1 - App skeleton

- add `pipeline/operator_ui/app.py`
- mount Jinja templates
- mount static assets
- add base layout
- add project list page

### Phase 2 - Project ingestion

- add create-from-URL flow
- add create-from-local-files flow
- add `video_id` normalization
- add project directory creation
- add upload/form handling

### Phase 3 - Project inspection

- detect lessons from `*.vtt`
- detect existing artifacts
- show current config and available run modes

### Phase 4 - Run registry

- add local persistent run records
- add run detail page
- add log tail support
- add single-run concurrency guard so the same project is not launched twice accidentally

### Phase 5 - Sync pipeline launch

- launch sync pipeline runs
- stream/refresh logs
- update local status

### Phase 6 - Batch workflow launch

- wrap batch discover/plan/spool/assemble/submit
- store batch DB path
- show batch jobs table

### Phase 7 - Reconcile loop

- implement status poll endpoint
- poll Google via backend
- auto-download when complete
- auto-materialize when downloaded

### Phase 8 - Downstream deterministic build

- after batch knowledge extraction, run deterministic downstream stages
- write evidence/rules/graph/export artifacts

### Phase 9 - Corpus build

- add corpus build page/action
- show corpus counts and validation status

### Phase 10 - Polish

- better error reporting
- retry actions
- resume actions
- cleaner operator UX
- Playwright screenplay suite
- optional live-provider smoke coverage

## Acceptance Criteria

Implementation is done when all of the following are true:

1. A user can create `data/<video_id>/` from URL or local files in the UI.
2. The UI can discover lessons from `*.vtt`.
3. A user can choose which pipeline steps to run.
4. The backend can launch sync runs.
5. The backend can launch batch runs.
6. The UI can show current logs and status.
7. The backend can poll Gemini Batch indirectly and safely.
8. Completed batch jobs trigger download/materialization without manual CLI use.
9. The UI can run deterministic downstream stages after batch knowledge extraction.
10. The UI can trigger corpus build for RAG prep.
11. Existing CLI flows remain fully usable.
12. Backend route/service tests pass.
13. Playwright E2E tests using the screenplay structure pass against a local app instance.

## Recommended V1 Deliverable

For the first release, keep the promise small and strong:

- local-only operator UI
- one project at a time
- create/import project
- select steps
- launch sync or batch flow
- automatic reconcile for batch jobs
- corpus build button

This delivers the core operator experience without turning the repo into a large web app.

## Future Enhancements

- multi-project dashboard with filtering
- batch queue across many projects
- scheduled background reconcile worker
- artifact previews in browser
- usage/cost dashboard
- project templates / default configs
- per-step estimated runtime and token cost
