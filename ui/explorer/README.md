# Trading Explorer UI

Read-only analyst browser for the Step 4 explorer backend.

## Prerequisites

- Node.js 18+
- Explorer backend serving `/browser/*`

## Backend

From the repo root:

```powershell
python -m pipeline.rag.cli serve --rag-root output_rag --corpus-root output_corpus --host 127.0.0.1 --port 8000
```

The same server exposes **`/browser/*`** (explorer) and **`/adjudication/*`** (Stage 5.2). In dev, Vite proxies both prefixes to `VITE_BROWSER_API_BASE`.

### Review workstation (Stage 5.3)

Routes:

| Path | Purpose |
| --- | --- |
| `/review/queue` | Unresolved queue, type filter, next item |
| `/review/item/:targetType/:targetId` | Review bundle, history, family, decision submit |
| `/review/compare?aType=&aId=&bType=&bId=` | Side-by-side bundles for duplicate/merge |

Set a stable **reviewer id** in the decision panel (stored in `localStorage` as `adjudication_reviewer_id`). The reviewer must exist in the adjudication DB (`reviewers` table) before submits succeed.

UI ↔ API mapping: `notes/stage5_3_ui_contract.md`.

## Setup

```powershell
cd ui/explorer
npm install
Copy-Item .env.example .env
```

## Development

```powershell
npm run dev
```

The app runs at `http://127.0.0.1:5173`. Browser requests stay on `/browser/*`; in dev, Vite proxies those calls to `VITE_BROWSER_API_BASE`.

## Validation

```powershell
npm run build
npm run typecheck
npm run test
$env:VITE_BROWSER_API_BASE='http://127.0.0.1:8000'; npm run test:e2e
```

## Linting

Run locally:

- `npm run lint`
- `npm run lint:fix`
- `npm run lint:ci`

Project linting focuses on:

- React correctness
- TypeScript async safety
- accessibility
- test hygiene
- import cleanup

## Environment

| Variable | Default | Purpose |
| --- | --- | --- |
| `VITE_BROWSER_API_BASE` | `http://127.0.0.1:8000` | Dev proxy target for the explorer backend |
| `VITE_APP_TITLE` | `Trading Explorer` | Header title |

## Stack

- React 19 + TypeScript + Vite
- React Router 7
- TanStack Query 5
- Tailwind CSS 4 + shadcn-style primitives
- Zod runtime validation
- Vitest + React Testing Library
- Playwright Screenplay E2E tests

## Structure

```text
src/
  app/          app shell, router, providers
  components/   reusable UI pieces
  hooks/        query and URL-state hooks
  lib/api/      schemas, client, typed browser API helpers
  lib/url/      URL <-> state serialization
  lib/utils/    formatting, badge, entity helpers
  pages/        route-level screens
  test/         test setup, fixtures, fetch mocks
tests/e2e/      Playwright Screenplay specs
```

## Proof Artifacts

Phase 5 validation outputs are saved in this folder:

- `build_output.txt`
- `typecheck_output.txt`
- `vitest_output.txt`
- `playwright_output.txt`
