# Batch Reconcile And Corpus

## Batch-backed workflow

The batch-backed path should support these stages:

1. spool requests
2. assemble JSONL
3. submit remote batch job
4. poll remote state
5. download result file
6. materialize standard pipeline artifacts
7. run deterministic downstream steps

The UI should show this as one coherent flow even though the underlying pipeline
uses multiple commands/functions.

## Reconcile loop

The UI needs a periodic reconcile loop so operators do not manually poll Google
or remember when to download results.

The reconcile service should:

- find active runs waiting on remote completion
- poll provider state
- persist updated status
- if job succeeded, trigger download
- if download succeeded, trigger materialization
- if materialization succeeded, trigger downstream deterministic steps when configured
- if any step fails, mark the run failed with a resumable error summary

## Important rule

Remote batch status must be persisted in local state. The UI cannot rely on a
single browser tab staying open.

That is essential for managing long-running jobs across many projects.

## Reconcile triggers

Support all three:

1. Background periodic reconcile on server side.
2. Manual "Reconcile now" action on one run/project.
3. Dashboard-level reconcile for all pending remote runs.

## Project-level batch statuses

For dashboard tracking, batch-related statuses should include:

- `queued_remote`
- `running_remote`
- `remote_succeeded_waiting_download`
- `downloading`
- `materializing`
- `postprocessing`
- `remote_failed`

These can roll up into a simpler operator-facing project state, but the finer
states are useful for the run page and filters.

## Failure handling

When a batch run fails, the UI should capture:

- local stage that failed
- remote job id
- remote status if available
- short error summary
- whether retry is safe

Retry options should be explicit:

- retry polling only
- retry download/materialization only
- resubmit the batch stage from scratch

## Corpus build page

The corpus page should serve as the "ready queue" for downstream preparation.

It should show projects that are:

- valid for corpus export
- missing one or more prerequisites
- already exported
- changed since last export

## Multi-project corpus workflow

To support 100 projects, the corpus page should allow:

- filtering ready projects
- selecting multiple projects
- launching a build for a selected set
- viewing build status and output paths

Bulk corpus actions are much more important than bulk project creation because
RAG prep is naturally a batch operation across many lessons.

## Retention and operator reminders

The UI should surface provider retention constraints near remote runs so the
operator understands why reconcile matters.

At minimum, the UI should display:

- remote job age
- last poll time
- warning if the remote result file is nearing provider expiry

## Dashboard implications

For 100-project tracking, the dashboard must make remote backlog visible at a
glance. Add counters such as:

- waiting on remote
- ready to materialize
- failed remote
- ready for corpus

Without this, the operator still has to inspect projects one by one, which is
the exact workflow the dashboard is meant to replace.
