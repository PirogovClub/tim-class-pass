# Phase 1 — Scaffold, API Client, Schemas

## Goal

A buildable, type-safe React+TS app with a fully typed API client layer and Zod-validated schemas. No UI screens yet — just the foundation.

## Prerequisites

- Node.js >=18 (LTS)
- The FastAPI backend with explorer endpoints running at `http://127.0.0.1:8000`

---

## Step 1.1 — Initialize Vite + React + TypeScript

```bash
cd ui
npm create vite@latest explorer -- --template react-ts
cd explorer
npm install
```

Verify: `npm run dev` starts the Vite dev server.

---

## Step 1.2 — Install Core Dependencies

```bash
# Runtime
npm install @tanstack/react-query react-router-dom zod

# Tailwind CSS v4 (Vite plugin)
npm install -D tailwindcss @tailwindcss/vite

# shadcn/ui (uses tailwind v4)
npx shadcn@latest init

# Dev / testing
npm install -D vitest @testing-library/react @testing-library/jest-dom jsdom
npm install -D @types/react @types/react-dom
npm install -D @playwright/test
npx playwright install --with-deps chromium
```

### Expected `package.json` scripts

```json
{
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview",
    "test": "vitest run",
    "test:watch": "vitest",
    "test:e2e": "playwright test",
    "lint": "eslint .",
    "typecheck": "tsc --noEmit"
  }
}
```

---

## Step 1.3 — Configure Tailwind CSS

For Tailwind v4 with the Vite plugin, update `vite.config.ts`:

```typescript
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/browser': {
        target: process.env.VITE_BROWSER_API_BASE || 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  resolve: {
    alias: {
      '@': '/src',
    },
  },
});
```

In `src/index.css`:

```css
@import "tailwindcss";
```

---

## Step 1.4 — shadcn/ui Init

Run `npx shadcn@latest init` and follow prompts. This creates `components.json` and sets up the `src/components/ui/` directory.

Add commonly needed shadcn components:

```bash
npx shadcn@latest add badge button card accordion tabs input separator sheet scroll-area collapsible
```

---

## Step 1.5 — Environment Configuration

Create `.env.example`:

```env
VITE_BROWSER_API_BASE=http://127.0.0.1:8000
VITE_APP_TITLE=Trading Explorer
```

Create `.env` (gitignored) with same values for local dev.

---

## Step 1.6 — Zod Schemas (`src/lib/api/schemas.ts`)

Define every schema to match `pipeline/explorer/contracts.py` exactly. Use real `browser_api_samples/` JSONs as reference.

### UnitType

```typescript
import { z } from 'zod';

export const UnitTypeSchema = z.enum([
  'rule_card',
  'knowledge_event',
  'evidence_ref',
  'concept_node',
  'concept_relation',
]);
```

### HealthResponse

```typescript
export const HealthResponseSchema = z.object({
  status: z.string(),
  rag_ready: z.boolean(),
  explorer_ready: z.boolean(),
  doc_count: z.number().int(),
  corpus_contract_version: z.string(),
});
```

### Timestamp

```typescript
export const TimestampSchema = z.object({
  start: z.string(),
  end: z.string(),
}).passthrough();
```

### BrowserResultCard

```typescript
export const BrowserResultCardSchema = z.object({
  doc_id: z.string(),
  unit_type: UnitTypeSchema,
  lesson_id: z.string().nullable().default(null),
  title: z.string(),
  subtitle: z.string().default(''),
  snippet: z.string().default(''),
  concept_ids: z.array(z.string()).default([]),
  support_basis: z.string().nullable().default(null),
  evidence_requirement: z.string().nullable().default(null),
  teaching_mode: z.string().nullable().default(null),
  confidence_score: z.number().nullable().default(null),
  timestamps: z.array(TimestampSchema).default([]),
  evidence_count: z.number().int().default(0),
  related_rule_count: z.number().int().default(0),
  related_event_count: z.number().int().default(0),
  score: z.number().nullable().default(null),
  why_retrieved: z.array(z.string()).default([]),
});
```

### BrowserSearchFilters (request-side)

```typescript
export const BrowserSearchFiltersSchema = z.object({
  lesson_ids: z.array(z.string()).default([]),
  concept_ids: z.array(z.string()).default([]),
  unit_types: z.array(UnitTypeSchema).default([]),
  support_basis: z.array(z.string()).default([]),
  evidence_requirement: z.array(z.string()).default([]),
  teaching_mode: z.array(z.string()).default([]),
  min_confidence_score: z.number().nullable().default(null),
});
```

### BrowserSearchRequest

```typescript
export const BrowserSearchRequestSchema = z.object({
  query: z.string().default(''),
  top_k: z.number().int().default(20),
  filters: BrowserSearchFiltersSchema.default({}),
  return_groups: z.boolean().default(true),
});
```

### BrowserSearchResponse

```typescript
export const BrowserSearchResponseSchema = z.object({
  query: z.string(),
  cards: z.array(BrowserResultCardSchema).default([]),
  groups: z.record(z.string(), z.array(BrowserResultCardSchema)).default({}),
  facets: z.record(z.string(), z.record(z.string(), z.number())).default({}),
  hit_count: z.number().int().default(0),
});
```

### RuleDetailResponse

```typescript
export const RuleDetailResponseSchema = z.object({
  doc_id: z.string(),
  lesson_id: z.string(),
  lesson_slug: z.string().nullable().default(null),
  title: z.string(),
  concept: z.string().nullable().default(null),
  subconcept: z.string().nullable().default(null),
  canonical_concept_ids: z.array(z.string()).default([]),
  rule_text: z.string().default(''),
  rule_text_ru: z.string().default(''),
  conditions: z.array(z.string()).default([]),
  invalidation: z.array(z.string()).default([]),
  exceptions: z.array(z.string()).default([]),
  comparisons: z.array(z.string()).default([]),
  visual_summary: z.string().nullable().default(null),
  support_basis: z.string().nullable().default(null),
  evidence_requirement: z.string().nullable().default(null),
  teaching_mode: z.string().nullable().default(null),
  confidence_score: z.number().nullable().default(null),
  timestamps: z.array(TimestampSchema).default([]),
  evidence_refs: z.array(BrowserResultCardSchema).default([]),
  source_events: z.array(BrowserResultCardSchema).default([]),
  related_rules: z.array(BrowserResultCardSchema).default([]),
});
```

### EvidenceDetailResponse

```typescript
export const EvidenceDetailResponseSchema = z.object({
  doc_id: z.string(),
  lesson_id: z.string(),
  title: z.string(),
  snippet: z.string().default(''),
  timestamps: z.array(TimestampSchema).default([]),
  support_basis: z.string().nullable().default(null),
  confidence_score: z.number().nullable().default(null),
  evidence_strength: z.string().nullable().default(null),
  evidence_role_detail: z.string().nullable().default(null),
  visual_summary: z.string().nullable().default(null),
  source_rules: z.array(BrowserResultCardSchema).default([]),
  source_events: z.array(BrowserResultCardSchema).default([]),
});
```

### ConceptNeighbor + ConceptDetailResponse

```typescript
export const ConceptNeighborSchema = z.object({
  concept_id: z.string(),
  relation: z.string(),
  direction: z.string(),
  weight: z.number().nullable().default(null),
});

export const ConceptDetailResponseSchema = z.object({
  concept_id: z.string(),
  aliases: z.array(z.string()).default([]),
  top_rules: z.array(BrowserResultCardSchema).default([]),
  top_events: z.array(BrowserResultCardSchema).default([]),
  lessons: z.array(z.string()).default([]),
  neighbors: z.array(ConceptNeighborSchema).default([]),
  rule_count: z.number().int().default(0),
  event_count: z.number().int().default(0),
  evidence_count: z.number().int().default(0),
});

export const ConceptNeighborListResponseSchema = z.array(ConceptNeighborSchema);
```

### LessonDetailResponse

```typescript
export const LessonDetailResponseSchema = z.object({
  lesson_id: z.string(),
  lesson_title: z.string().nullable().default(null),
  rule_count: z.number().int().default(0),
  event_count: z.number().int().default(0),
  evidence_count: z.number().int().default(0),
  concept_count: z.number().int().default(0),
  support_basis_counts: z.record(z.string(), z.number()).default({}),
  top_concepts: z.array(z.string()).default([]),
  top_rules: z.array(BrowserResultCardSchema).default([]),
  top_evidence: z.array(BrowserResultCardSchema).default([]),
});
```

### FacetResponse

```typescript
export const FacetResponseSchema = z.record(
  z.string(),
  z.record(z.string(), z.number()),
);
```

### ApiError

```typescript
export const ApiErrorResponseSchema = z.object({
  detail: z.union([z.string(), z.array(z.any())]),
});
```

---

## Step 1.7 — Inferred Types (`src/lib/api/types.ts`)

```typescript
import { z } from 'zod';
import * as S from './schemas';

export type UnitType = z.infer<typeof S.UnitTypeSchema>;
export type HealthResponse = z.infer<typeof S.HealthResponseSchema>;
export type BrowserResultCard = z.infer<typeof S.BrowserResultCardSchema>;
export type BrowserSearchFilters = z.infer<typeof S.BrowserSearchFiltersSchema>;
export type BrowserSearchRequest = z.infer<typeof S.BrowserSearchRequestSchema>;
export type BrowserSearchResponse = z.infer<typeof S.BrowserSearchResponseSchema>;
export type RuleDetailResponse = z.infer<typeof S.RuleDetailResponseSchema>;
export type EvidenceDetailResponse = z.infer<typeof S.EvidenceDetailResponseSchema>;
export type ConceptNeighbor = z.infer<typeof S.ConceptNeighborSchema>;
export type ConceptDetailResponse = z.infer<typeof S.ConceptDetailResponseSchema>;
export type LessonDetailResponse = z.infer<typeof S.LessonDetailResponseSchema>;
export type FacetResponse = z.infer<typeof S.FacetResponseSchema>;
```

---

## Step 1.8 — Error Model (`src/lib/api/errors.ts`)

```typescript
export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: string,
    public readonly raw?: unknown,
  ) {
    super(`API ${status}: ${detail}`);
    this.name = 'ApiError';
  }

  get isNotFound(): boolean { return this.status === 404; }
  get isBadRequest(): boolean { return this.status === 400; }
  get isValidationError(): boolean { return this.status === 422; }
  get isServerError(): boolean { return this.status >= 500; }
  get isNetworkError(): boolean { return this.status === 0; }
}
```

---

## Step 1.9 — Base HTTP Client (`src/lib/api/client.ts`)

```typescript
import { ZodSchema } from 'zod';
import { ApiError } from './errors';

const BASE_URL = import.meta.env.VITE_BROWSER_API_BASE ?? '';

export async function apiGet<T>(path: string, schema: ZodSchema<T>): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE_URL}${path}`);
  } catch {
    throw new ApiError(0, 'Network error');
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    throw new ApiError(response.status, body?.detail ?? response.statusText, body);
  }
  const json = await response.json();
  return schema.parse(json);
}

export async function apiPost<T>(path: string, body: unknown, schema: ZodSchema<T>): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, 'Network error');
  }
  if (!response.ok) {
    const data = await response.json().catch(() => ({ detail: response.statusText }));
    throw new ApiError(response.status, data?.detail ?? response.statusText, data);
  }
  const json = await response.json();
  return schema.parse(json);
}
```

---

## Step 1.10 — Typed API Functions (`src/lib/api/browser.ts`)

```typescript
import { apiGet, apiPost } from './client';
import * as S from './schemas';
import type {
  BrowserSearchFilters,
  BrowserSearchRequest,
  BrowserSearchResponse,
  ConceptDetailResponse,
  ConceptNeighbor,
  EvidenceDetailResponse,
  FacetResponse,
  HealthResponse,
  LessonDetailResponse,
  RuleDetailResponse,
} from './types';

export function healthCheck(): Promise<HealthResponse> {
  return apiGet('/browser/health', S.HealthResponseSchema);
}

export function searchBrowser(request: BrowserSearchRequest): Promise<BrowserSearchResponse> {
  return apiPost('/browser/search', request, S.BrowserSearchResponseSchema);
}

export function getRuleDetail(docId: string): Promise<RuleDetailResponse> {
  return apiGet(`/browser/rule/${encodeURIComponent(docId)}`, S.RuleDetailResponseSchema);
}

export function getEvidenceDetail(docId: string): Promise<EvidenceDetailResponse> {
  return apiGet(`/browser/evidence/${encodeURIComponent(docId)}`, S.EvidenceDetailResponseSchema);
}

export function getConceptDetail(conceptId: string): Promise<ConceptDetailResponse> {
  return apiGet(`/browser/concept/${encodeURIComponent(conceptId)}`, S.ConceptDetailResponseSchema);
}

export function getConceptNeighbors(conceptId: string): Promise<ConceptNeighbor[]> {
  return apiGet(
    `/browser/concept/${encodeURIComponent(conceptId)}/neighbors`,
    S.ConceptNeighborListResponseSchema,
  );
}

export function getLessonDetail(lessonId: string): Promise<LessonDetailResponse> {
  return apiGet(`/browser/lesson/${encodeURIComponent(lessonId)}`, S.LessonDetailResponseSchema);
}

export function getFacets(
  query?: string,
  filters?: Partial<BrowserSearchFilters>,
): Promise<FacetResponse> {
  const params = new URLSearchParams();
  if (query) params.set('query', query);
  if (filters) {
    filters.lesson_ids?.forEach(v => params.append('lesson_ids', v));
    filters.concept_ids?.forEach(v => params.append('concept_ids', v));
    filters.unit_types?.forEach(v => params.append('unit_types', v));
    filters.support_basis?.forEach(v => params.append('support_basis', v));
    filters.evidence_requirement?.forEach(v => params.append('evidence_requirement', v));
    filters.teaching_mode?.forEach(v => params.append('teaching_mode', v));
    if (filters.min_confidence_score != null)
      params.set('min_confidence_score', String(filters.min_confidence_score));
  }
  const qs = params.toString();
  return apiGet(`/browser/facets${qs ? `?${qs}` : ''}`, S.FacetResponseSchema);
}
```

---

## Step 1.11 — App Shell Skeleton

### `src/app/query-client.ts`

```typescript
import { QueryClient } from '@tanstack/react-query';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});
```

### `src/app/router.tsx`

```typescript
import { createBrowserRouter, Navigate } from 'react-router-dom';
import { AppShell } from '@/components/layout/AppShell';
// pages imported in Phase 2+3

export const router = createBrowserRouter([
  {
    element: <AppShell />,
    children: [
      { index: true, element: <Navigate to="/search" replace /> },
      { path: 'search', element: <div>Search (Phase 2)</div> },
      { path: 'rule/:docId', element: <div>Rule (Phase 3)</div> },
      { path: 'evidence/:docId', element: <div>Evidence (Phase 3)</div> },
      { path: 'concept/:conceptId', element: <div>Concept (Phase 3)</div> },
      { path: 'lesson/:lessonId', element: <div>Lesson (Phase 3)</div> },
      { path: '*', element: <div>Not Found</div> },
    ],
  },
]);
```

### `src/app/providers.tsx`

```typescript
import { QueryClientProvider } from '@tanstack/react-query';
import { RouterProvider } from 'react-router-dom';
import { queryClient } from './query-client';
import { router } from './router';

export function Providers() {
  return (
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  );
}
```

### `src/main.tsx`

```typescript
import React from 'react';
import ReactDOM from 'react-dom/client';
import { Providers } from './app/providers';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <Providers />
  </React.StrictMode>,
);
```

### `src/components/layout/AppShell.tsx`

```typescript
import { Outlet } from 'react-router-dom';

export function AppShell() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="border-b px-6 py-3">
        <h1 className="text-lg font-semibold">Trading Explorer</h1>
      </header>
      <main className="flex-1">
        <Outlet />
      </main>
    </div>
  );
}
```

---

## Phase 1 Validation Checklist

- [ ] `npm run build` succeeds with zero type errors
- [ ] `npm run typecheck` passes
- [ ] `npm run dev` opens the app in browser
- [ ] Proxy forwards `/browser/health` to FastAPI backend
- [ ] All Zod schemas are defined and exported
- [ ] All inferred types are exported
- [ ] `browser.ts` exports all 8 API functions
- [ ] Error model has `isNotFound`, `isBadRequest`, `isValidationError` helpers
