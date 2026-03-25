# Operator UI Plan Index

This directory contains the split implementation plan for the operator UI.

The plan is intentionally broken into focused files so implementation can follow
them phase by phase without keeping one large document open.

## Key decision

The UI must support a **multi-project dashboard from V1**. This is not deferred.
If the goal is to manage 100+ videos, the dashboard must exist at the start so
operators can:

- see all projects in one place
- filter and sort by status
- identify blocked/running/ready projects
- trigger resume/reconcile actions without opening every project manually

## File map

1. `01-product-and-dashboard.md`
   Product scope, user flows, and the multi-project dashboard design.

2. `02-architecture-and-backend.md`
   Stack, modules, routes, storage, and backend orchestration approach.

3. `03-project-ingestion-and-runs.md`
   Project creation/import, step selection, run creation, and log handling.

4. `04-batch-reconcile-and-corpus.md`
   Remote Gemini Batch polling, automatic download/materialization, and corpus build flow.

5. `05-testing-playwright-screenplay.md`
   Unit/integration/browser testing strategy, including Playwright with screenplay structure.

6. `06-implementation-phases.md`
   Ordered implementation phases, acceptance criteria, and V1 deliverable.

## Recommended reading order

Read in order:

1. `01-product-and-dashboard.md`
2. `02-architecture-and-backend.md`
3. `03-project-ingestion-and-runs.md`
4. `04-batch-reconcile-and-corpus.md`
5. `05-testing-playwright-screenplay.md`
6. `06-implementation-phases.md`
