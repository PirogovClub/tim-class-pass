# Testing With Playwright And Screenplay

## Testing goal

The UI should be testable at three levels:

- unit tests for state and decision logic
- backend integration tests for routes and service wiring
- browser E2E tests for real operator flows

The browser layer should use Playwright with a screenplay-style structure.

## Why screenplay pattern fits

This UI has long operator journeys:

- create/import project
- inspect readiness
- start a run
- wait for state changes
- reconcile remote work
- confirm downstream outputs

Screenplay keeps those journeys readable and reusable as the surface grows.

## Test layers

### Unit tests

Cover:

- project detection helpers
- dashboard row aggregation
- status rollup logic
- allowed-action computation
- run lock/concurrency rules
- reconcile decision logic
- corpus readiness rules

### Backend integration tests

Use `fastapi.testclient.TestClient` for:

- dashboard render
- project creation/import
- run creation validation
- partial status refresh endpoints
- reconcile endpoints
- corpus build endpoints

Mock heavy execution so these tests stay fast and deterministic.

### Browser E2E tests

Use Playwright for:

- dashboard loads with many projects
- filters/search/sort work correctly
- project can be created/imported
- run can be launched from detail page
- dashboard counters update after state changes
- reconcile flow updates run/project status
- ready projects can be selected for corpus build

## Screenplay structure

Suggested layout:

- `tests/ui_screenplay/actors.py`
- `tests/ui_screenplay/abilities.py`
- `tests/ui_screenplay/tasks.py`
- `tests/ui_screenplay/questions.py`
- `tests/ui_screenplay/assertions.py`
- `tests/ui_screenplay/test_dashboard_flow.py`
- `tests/ui_screenplay/test_project_run_flow.py`
- `tests/ui_screenplay/test_corpus_flow.py`

## Screenplay concepts

### Actor

Represents the operator, for example `Operator`.

### Abilities

Examples:

- browse the UI
- read dashboard state
- inspect filesystem fixtures

### Tasks

Examples:

- create a project from a video and transcript
- filter dashboard to blocked projects
- start batch knowledge extraction
- reconcile all pending runs
- open corpus page and export selected projects

### Questions

Examples:

- what status is shown for project X
- how many projects are ready for corpus
- is run Y waiting on remote

### Assertions

Examples:

- project appears as `ready_to_run`
- dashboard counter increments
- failed project exposes retry action

## Concrete high-value E2E scenarios

1. Create project from inputs and verify it appears on dashboard.
2. Launch a batch-backed run and verify dashboard + detail pages show pending remote state.
3. Trigger reconcile and verify successful download/materialization updates the project to next ready state.
4. Load 100 seeded projects and verify search, filters, and pagination keep the dashboard usable.
5. Select multiple ready projects and launch corpus build.

## Multi-project dashboard test requirement

Because the dashboard is now a V1 feature, include a dedicated seeded-data test:

- seed 100 projects with mixed states
- verify summary counters
- filter to failed projects
- search by lesson name
- sort by latest update
- confirm the visible rows match expected order/status

This test protects the main operator workflow for real-scale use.

## Batch testing strategy

Use fake adapters for most automated tests:

- fake remote pending state
- fake remote success state
- fake remote failure state
- fake download payload
- fake materialized artifacts

This keeps the majority of tests local and deterministic.

## Live-provider smoke tests

Keep a small optional suite for provider smoke validation:

- submit one known-small job
- poll until terminal state
- verify download works
- verify materialization succeeds

These should not block normal local development.

## Acceptance from a testing perspective

The UI plan is not complete unless it includes:

- backend tests for core routes
- screenplay E2E for main operator journeys
- at least one scale-oriented dashboard test with many seeded projects
- fake-provider reconcile coverage
