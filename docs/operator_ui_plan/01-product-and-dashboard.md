# Product Scope And Dashboard

## Goal

Build a local operator UI that lets a user manage many lesson/video projects from
one place, choose which pipeline steps to run, track sync and batch progress,
inspect artifacts, and prepare outputs for corpus/RAG import.

The UI should reduce manual CLI work, but it must still wrap the existing Python
pipeline rather than reimplementing it.

## Core product position

This is a **multi-project operations UI**, not a single-project helper page.

That matters because the real workload is not "open one lesson and click run."
The real workload is "track 100 projects, know which ones are waiting on inputs,
which are running, which failed, and which are ready for corpus build."

## Primary user flows

1. Import or create many projects from available media/transcript inputs.
2. View all projects in a dashboard with current status and next action.
3. Open one project to inspect detected inputs and available artifacts.
4. Select which steps to run for that project.
5. Launch sync or batch-backed runs.
6. Watch progress live and refresh status without using the terminal.
7. Automatically reconcile remote batch jobs and materialize outputs.
8. Build corpus outputs for selected ready projects.

## V1 scope

V1 should include:

- multi-project dashboard
- project creation/import page
- project detail page
- per-project run configuration
- run history and log tail
- batch status reconciliation
- artifact presence detection
- downstream lesson artifact generation after batch completion
- corpus build trigger for ready projects

## Explicit non-goals for V1

Do not include in V1:

- multi-user auth or permissions
- cloud deployment
- arbitrary shell access in the browser
- editing transcript text inside the UI
- replacing the existing CLI and Python functions

## Dashboard-first requirement

The dashboard must be the landing page. It is the main operator surface.

For 100+ projects, the dashboard needs:

- search by lesson title, project slug, or source filename
- filters for status, run type, missing inputs, failed runs, ready-for-corpus, and in-progress items
- sortable columns for updated time, run state, stage, and completion percentage
- summary counters for total projects, running, blocked, failed, ready for corpus, and completed
- pagination or incremental loading so large project sets stay usable
- a visible "next action" column so operators can quickly see what each project needs

## Suggested dashboard table

Each row should show:

- project name
- source video or lesson identifier
- transcript status
- dense analysis status
- knowledge extract status
- markdown/export readiness
- latest run type (`sync`, `batch_vision`, `batch_text`, `mixed`)
- current state (`new`, `ready`, `running`, `waiting_remote`, `failed`, `complete`)
- last update time
- next action
- quick actions (`Open`, `Run`, `Reconcile`, `View logs`)

## Recommended status model

Use a simple operator-facing rollup per project:

- `new`
- `missing_inputs`
- `ready_to_run`
- `running_sync`
- `running_batch`
- `waiting_for_remote`
- `materializing`
- `failed`
- `ready_for_corpus`
- `complete`

These statuses are for the UI. Internally, the run registry can still keep more
granular stage-level states.

## Project detail page

The detail page should answer:

- What inputs were detected?
- What artifacts already exist?
- What was the last run and its result?
- Which steps can be run now?
- Is this project blocked on a remote batch job?
- Is it safe to re-run only one subset of steps?

## Step selection model

The operator should be able to choose:

- sync path
- batch vision only
- batch knowledge extract only
- full batch-backed path
- deterministic downstream generation only
- corpus export only

This keeps first-run and reprocessing workflows in one surface.

## Why the dashboard must exist from day one

Without the dashboard, the UI becomes a thin wrapper over the CLI for one project
at a time, which does not solve the real coordination problem.

For 100 projects, the operator needs:

- a queue view
- exception detection
- resumability
- progress visibility across the whole set

That makes the dashboard a foundational requirement, not a polish item.
