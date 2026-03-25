# Phase 5 — Polish, Accessibility, README

## Goal

Finalize loading/empty/error states, tighten accessibility, and produce the `README.md` and build/test proof artifacts.

---

## Step 5.1 — Loading States

Every data-dependent view must show a loading skeleton or spinner while the TanStack Query is in `isLoading` state.

### Components to update

| Component | Loading behavior |
|-----------|-----------------|
| SearchPage | Skeleton cards (3–5 placeholder card outlines) |
| RuleDetailPage | Skeleton header + placeholder sections |
| EvidenceDetailPage | Skeleton header + placeholder sections |
| ConceptDetailPage | Skeleton header + neighbor placeholder |
| LessonDetailPage | Skeleton header + count placeholder |

### Implementation

Use the shadcn `Skeleton` component:

```tsx
import { Skeleton } from '@/components/ui/skeleton';

function ResultCardSkeleton() {
  return (
    <div className="rounded-lg border p-4 space-y-3">
      <Skeleton className="h-5 w-3/4" />
      <Skeleton className="h-4 w-1/2" />
      <Skeleton className="h-3 w-full" />
      <Skeleton className="h-3 w-2/3" />
    </div>
  );
}
```

---

## Step 5.2 — Empty States

### SearchPage empty state

When `cards.length === 0` and not loading:

```
┌──────────────────────────────────┐
│     🔍  No results found         │
│                                  │
│  Try adjusting your filters or   │
│  broadening your search query.   │
│                                  │
│  [Clear filters]                 │
└──────────────────────────────────┘
```

### Detail page empty sections

When linked entities are empty (e.g., no evidence_refs), show:
- "No linked evidence found" (subtle text, not an error)

---

## Step 5.3 — Error States

### Error categories and display

| Status | Display |
|--------|---------|
| 404 | Full-page `NotFound` component: "Entity not found. It may have been removed or the ID is incorrect." |
| 400 | Inline error: "This document is not a {expected_type}." with link to correct detail page if possible |
| 422 | "Invalid request. Check the URL parameters." |
| Network (status 0) | "Connection error. Is the backend running at {VITE_BROWSER_API_BASE}?" |
| Zod parse failure | Dev mode: show schema mismatch details. Prod: "Unexpected response format." |
| 500+ | "Server error. Please try again later." |

### Implementation pattern

```tsx
function ErrorPanel({ error }: { error: ApiError }) {
  if (error.isNotFound) return <NotFound />;
  return (
    <div role="alert" className="rounded-lg border border-destructive bg-destructive/10 p-4">
      <h2 className="font-semibold text-destructive">
        {error.isNetworkError ? 'Connection Error' : 'Error'}
      </h2>
      <p className="text-sm text-muted-foreground mt-1">{error.detail}</p>
    </div>
  );
}
```

---

## Step 5.4 — Accessibility Audit

### Required checks

- [ ] All interactive elements are keyboard-accessible
- [ ] All cards have proper semantic structure (`<article>`, `<heading>`, `<link>`)
- [ ] Color is not the only way to distinguish unit types (text labels + colors)
- [ ] Focus indicators are visible
- [ ] Screen reader labels on filter checkboxes include facet counts
- [ ] Error states use `role="alert"`
- [ ] Loading states announce to screen readers (`aria-live="polite"` on result container)
- [ ] Skip-to-content link present in AppShell

### Specific attributes to add

| Element | Attribute |
|---------|-----------|
| Search input | `role="searchbox"`, `aria-label="Search entities"` |
| Filters panel | `role="region"`, `aria-label="Filters"` |
| Each FacetSection | `role="group"`, `aria-label="{Section name}"` |
| Result list | `aria-live="polite"` |
| Result card | `<article>` |
| Error panel | `role="alert"` |
| Loading skeleton | `aria-busy="true"` on parent container |

---

## Step 5.5 — Responsive Layout

### Desktop (≥1024px)

Two-panel layout:
- Left: 280px filters sidebar
- Right: flexible content area

### Tablet (768px–1023px)

- Filters collapse into a sheet (slide-in from left)
- "Filters" button in header opens the sheet
- Content area is full-width

### Mobile (<768px)

- Single column
- Filters in a bottom sheet
- Cards stack vertically
- Detail pages are single-column, full-width

Use shadcn `Sheet` component for the filter drawer on smaller screens.

---

## Step 5.6 — README.md

Create `ui/explorer/README.md`:

```markdown
# Trading Explorer UI

Read-only analyst browser for the Step 4 explorer backend.

## Prerequisites

- Node.js ≥18
- FastAPI backend running at `http://127.0.0.1:8000` with explorer endpoints

## Setup

    cd ui/explorer
    npm install
    cp .env.example .env

## Development

    npm run dev

Opens at http://127.0.0.1:5173. Proxies `/browser/*` to the backend.

## Build

    npm run build

## Type Check

    npm run typecheck

## Tests

### Unit + Component + Integration

    npm run test

### End-to-End (Playwright)

Requires the backend to be running.

    npm run test:e2e

### All Tests

    npm run test && npm run test:e2e

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_BROWSER_API_BASE` | `http://127.0.0.1:8000` | Explorer API base URL |
| `VITE_APP_TITLE` | `Trading Explorer` | App title in header |

## Architecture

- React + TypeScript + Vite
- TanStack Query for server state
- React Router for navigation (URL is source of truth)
- Tailwind CSS + shadcn/ui for styling
- Zod for runtime response validation
- Vitest + React Testing Library for unit/component/integration tests
- Playwright with Screenplay pattern for E2E tests

## Project Structure

    src/
      app/         Application shell, router, providers
      lib/api/     Typed API client, Zod schemas, error model
      lib/url/     URL ↔ state serialization
      lib/utils/   Formatting, badge helpers, entity routing
      components/  Reusable UI components
      pages/       Route-level page components
      hooks/       TanStack Query hooks
      test/        Test setup, fixtures, mocks
    tests/e2e/     Playwright Screenplay E2E tests
```

---

## Step 5.7 — Build and Test Proof Artifacts

After all phases are complete, produce:

1. **Build output proof**: `npm run build 2>&1 | tee build_output.txt`
2. **Type check proof**: `npm run typecheck 2>&1 | tee typecheck_output.txt`
3. **Unit test proof**: `npm run test 2>&1 | tee vitest_output.txt`
4. **E2E test proof**: `npm run test:e2e 2>&1 | tee playwright_output.txt`

---

## Phase 5 Validation Checklist

- [ ] Every data view has a loading skeleton
- [ ] Every data view has an empty state
- [ ] Every data view has an error state
- [ ] 404 shows full-page NotFound
- [ ] 400 shows inline error with guidance
- [ ] Network error shows connection error message
- [ ] All accessibility checks pass
- [ ] Responsive layout works at desktop/tablet/mobile breakpoints
- [ ] `README.md` is complete and accurate
- [ ] `npm run build` succeeds
- [ ] `npm run typecheck` passes
- [ ] `npm run test` passes
- [ ] `npm run test:e2e` passes
- [ ] Build/test proof artifacts are saved

---

## Final Deliverables (Step 4.2 audit package)

- All new frontend source code in `ui/explorer/`
- `package.json` + lockfile
- `vite.config.ts`
- Tailwind/shadcn config files
- `README.md`
- Unit/component/integration tests (`src/**/*.test.{ts,tsx}`)
- E2E Screenplay tests (`tests/e2e/`)
- `build_output.txt`
- `typecheck_output.txt`
- `vitest_output.txt`
- `playwright_output.txt`
