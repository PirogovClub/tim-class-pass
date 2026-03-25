# Implementation Phases

## Phase 1 - App skeleton and dashboard shell

Build:

- FastAPI app bootstrap
- template/layout base
- project registry storage
- dashboard route
- empty dashboard with seeded rows

This phase must already assume a multi-project landing page.

## Phase 2 - Project ingestion

Build:

- create/import project form
- input detection for video and `.vtt`
- project folder creation under `data/`
- artifact inspection
- project registry persistence

## Phase 3 - Project detail and allowed actions

Build:

- project detail page
- artifact status view
- allowed-action computation
- run configuration form

## Phase 4 - Run registry and logging

Build:

- run persistence
- per-project concurrency guard
- log file allocation
- run status page
- HTMX partial refresh for live state

## Phase 5 - Sync execution path

Build:

- sync run launcher
- stage-level status updates
- success/failure reporting in dashboard and detail page

## Phase 6 - Batch submission path

Build:

- batch stage selection
- spool/assemble/submit integration
- remote job id persistence
- dashboard remote-wait states

## Phase 7 - Reconcile loop

Build:

- periodic server-side reconcile
- manual reconcile actions
- download/materialize transitions
- retry-safe failure handling

## Phase 8 - Downstream deterministic generation

Build:

- post-batch deterministic steps
- final lesson artifact detection
- ready-for-corpus rollup

## Phase 9 - Corpus queue

Build:

- corpus page
- ready-project filtering
- multi-select build
- export result visibility

## Phase 10 - Dashboard scale polish

Build:

- search
- filters
- sort
- pagination or incremental loading
- summary counters
- quick actions for common next steps

Although listed late, the dashboard itself is not late-stage work. This phase is
for scale polish on top of the already-existing dashboard foundation.

## Acceptance criteria

V1 is acceptable when all of the following are true:

- operator can manage many projects from one landing page
- project creation/import works and detects existing inputs/artifacts
- project detail page shows current readiness and allowed actions
- sync and batch-backed runs can be launched from UI
- remote batch work can be reconciled without terminal use
- dashboard clearly shows blocked, running, failed, and ready projects
- ready projects can be selected for corpus build
- backend tests pass
- Playwright screenplay tests pass

## Recommended V1 deliverable

The first usable release should contain:

- multi-project dashboard as default home page
- project creation/import
- project detail and run creation
- run status page with log tail
- reconcile-now action and periodic reconcile
- corpus queue for ready projects

## Notes on managing 100 files

If the operator needs to track 100 files, success depends less on "can a run be
started" and more on "can the whole queue be understood quickly."

So V1 should optimize for:

- queue visibility
- filtering
- clear next actions
- persistence after restarts
- resumable batch work

Those are the features that make the UI operationally better than a CLI-only
workflow for large sets.
