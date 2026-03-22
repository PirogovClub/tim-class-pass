# Project Ingestion And Runs

## Project creation/import

The UI should support two ways to create projects:

1. Create from known source inputs
   The operator points to a video or lesson source, and the backend searches for
   matching transcript and known artifacts.

2. Import existing project directory
   The operator points to an existing `data/...` project folder and the backend
   inspects what is already present.

## First-run behavior

For a fresh project, the backend should:

- resolve canonical project folder under `data/`
- create the directory if it does not exist
- detect source video path
- search for matching `.vtt` transcript
- inspect whether dense analysis or later artifacts already exist
- save the project registry entry
- compute allowed next steps

This lets the operator see whether the project is truly fresh or already partly
prepared.

## Reprocessing behavior

For an existing project, the UI should not assume "run everything."

It should detect:

- transcript exists
- dense analysis exists
- knowledge extraction exists
- markdown/export exists
- corpus-ready outputs exist

Then it should offer targeted runs so the user can rerun only what is needed.

## Run configuration

Each project should have a run form with:

- run mode selector
- checkboxes for stages
- provider settings if needed
- output root preview
- dry summary of what will happen

Suggested run modes:

- `sync_full`
- `sync_partial`
- `batch_vision_only`
- `batch_knowledge_only`
- `batch_full`
- `deterministic_postprocess_only`
- `corpus_only`

## Stage groups

The UI should present stages in operator language:

- Inputs
- Visual analysis
- LLM extraction
- Lesson markdown/export
- Corpus prep

Under the hood these map to real pipeline functions and artifacts.

## Allowed actions logic

Before creating a run, validate:

- required inputs exist
- selected stages are consistent
- project is not already locked by another active run
- downstream-only actions have the required upstream artifacts

Examples:

- `batch_knowledge_only` requires transcript plus dense analysis
- `deterministic_postprocess_only` requires knowledge extraction output
- `corpus_only` requires lesson outputs that satisfy corpus contract inputs

## Run history

Each project detail page should show recent runs with:

- started time
- finished time
- mode
- selected stages
- state
- remote batch state if any
- failure summary if any
- link to logs

## Run status page

The run page should show:

- current stage
- per-stage status chips
- remote batch job identifiers
- last poll time
- next scheduled reconcile
- recent log tail
- available actions (`Cancel`, `Retry`, `Reconcile now`, `Open project`)

## Logging

Each run should get a dedicated log file, for example:

- `var/ui-runs/<run_id>.log`

The UI should store the log path in the run registry and expose:

- recent tail on the run page
- full log download/open path if needed

## Mapping UI actions to execution

Prefer controlled Python wrappers like:

- `run_sync_pipeline(project, selection)`
- `submit_batch_stage(project, selection)`
- `download_and_materialize(run)`
- `build_corpus_for_projects(project_ids)`

This keeps the web layer small and testable.

## Operator experience for large queues

When tracking 100 projects, the operator should not have to open every detail
page to act. The dashboard must expose quick actions driven by allowed-action
logic, such as:

- start next ready step
- reconcile pending remote run
- retry failed materialization
- open only blocked projects

That means run eligibility must be computed centrally, not hidden inside detail
pages only.
