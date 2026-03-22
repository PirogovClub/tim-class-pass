# Architecture And Backend

## Recommended stack

- `FastAPI` for HTTP routes and server lifecycle
- `Jinja2` for server-rendered templates
- `HTMX` for partial page refresh and polling
- small vanilla JS only where HTMX is not enough
- existing pipeline Python modules for the real work

## Why this stack

This keeps the implementation Python-first, easy to test, and lightweight enough
for an internal operator tool.

`Django` would work, but it adds more framework surface than needed here. The UI
does not need an ORM-heavy product app; it needs thin orchestration over existing
pipeline code and local state.

## App bootstrap

The UI app should live under a dedicated package, for example:

- `operator_ui/app.py`
- `operator_ui/routes_dashboard.py`
- `operator_ui/routes_projects.py`
- `operator_ui/routes_runs.py`
- `operator_ui/routes_corpus.py`
- `operator_ui/services/`
- `operator_ui/templates/`
- `operator_ui/static/`

Bootstrap details:

- create `FastAPI()` app
- mount static assets
- configure `Jinja2Templates`
- bind to localhost only for V1
- initialize registry/state storage on startup
- optionally start a background reconcile scheduler on startup

## Existing code to reuse

Reuse existing pipeline modules instead of duplicating logic:

- sync pipeline entrypoints
- batch CLI/service helpers
- path resolution helpers
- lesson/project artifact detection helpers
- batch state and run state persistence
- corpus builder functionality

Where possible, call Python functions directly instead of shelling out to CLI
commands. Keep CLI wrappers only where direct import would be awkward or unsafe.

## High-level architecture

The system should have four layers:

1. Web layer
   FastAPI routes and HTML responses.

2. Service layer
   Validates requests, resolves paths, creates project records, and starts runs.

3. Execution layer
   Calls existing pipeline functions or a controlled subprocess wrapper.

4. State layer
   Stores projects, runs, stage status, and log locations in local persistence.

## Backend modules

Recommended modules:

- `operator_ui/models.py`
  Pydantic view models for projects, runs, and dashboard rows.

- `operator_ui/storage.py`
  Local persistence for project registry and UI-specific state.

- `operator_ui/services/projects.py`
  Import/create project logic and artifact inspection.

- `operator_ui/services/runs.py`
  Run creation, concurrency guard, and log setup.

- `operator_ui/services/reconcile.py`
  Poll remote batch state and trigger download/materialization when ready.

- `operator_ui/services/corpus.py`
  Discover ready projects and launch corpus build.

- `operator_ui/services/dashboard.py`
  Aggregate multi-project summaries, filters, and quick-action availability.

## Routes

Recommended routes:

- `GET /`
  Redirect to dashboard.

- `GET /dashboard`
  Render multi-project dashboard.

- `GET /projects/new`
  Render import/create form.

- `POST /projects`
  Create or import project.

- `GET /projects/{project_id}`
  Render project detail.

- `POST /projects/{project_id}/runs`
  Create a run with selected steps.

- `GET /runs/{run_id}`
  Render run status page.

- `GET /runs/{run_id}/partial`
  HTMX partial for live status refresh.

- `POST /runs/{run_id}/reconcile`
  Force reconcile now.

- `POST /dashboard/reconcile-ready`
  Reconcile all projects that have remote work pending.

- `GET /corpus`
  Show ready-for-corpus projects.

- `POST /corpus/build`
  Launch corpus build for selected projects.

## Storage model

Use two related registries:

1. Project registry
   One row per lesson/video project, with stable identity and known paths.

2. Run registry
   One row per execution attempt, with per-stage status, timestamps, remote job
   identifiers, and log location.

The UI should not infer project state only from transient HTML state. It must be
persisted so a restart does not lose track of 100 projects.

## Dashboard query model

The dashboard service should build a denormalized row per project containing:

- basic identifiers
- artifact presence summary
- last run summary
- current effective status
- remote wait flag
- readiness for next actions

This lets filters and sorting stay fast and predictable.

## Concurrency rules

Apply a single-run lock per project:

- do not launch two active runs for the same project
- allow different projects to run concurrently if resources permit
- prevent duplicate reconcile/download/materialize work for the same run

For 100-project tracking, the UI should allow breadth across projects, but each
project still needs internal execution safety.
