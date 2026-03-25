# Step 4.2 — Explorer UI Implementation Plan

## Overview

Build a **thin, read-only React+TypeScript SPA** (`ui/explorer/`) that consumes the accepted Step 4.1 `/browser/*` API. The UI is an analyst surface for inspecting rules, evidence, concepts, and lessons.

**Stack**: React 19, TypeScript, Vite, React Router v7, TanStack Query v5, Tailwind CSS v4, shadcn/ui, Zod, Vitest + React Testing Library, Playwright (Screenplay pattern).

**Existing state**: The repo has a Python-based operator UI in `ui/` (FastAPI+Jinja2). The new explorer SPA lives at `ui/explorer/` as an independent package with its own `package.json`, `vite.config.ts`, and build toolchain. It does NOT touch the existing `ui/` Python app.

---

## Phased Implementation

| Phase | Focus | Depends On | Deliverable |
|-------|-------|------------|-------------|
| 1 | Scaffold + API client + schemas | Nothing | Buildable empty app with typed API layer |
| 2 | Search page + filters + URL state | Phase 1 | Working search/browse with facets |
| 3 | Detail pages (rule, evidence, concept, lesson) | Phase 2 | All entity detail views |
| 4 | Testing (unit, integration, E2E Screenplay) | Phase 3 | Full test suite passing |
| 5 | Polish + README + accessibility | Phase 4 | Production-ready thin shell |

See per-phase help files:
- [`step42_phase1_scaffold.md`](step42_phase1_scaffold.md)
- [`step42_phase2_search_filters.md`](step42_phase2_search_filters.md)
- [`step42_phase3_detail_pages.md`](step42_phase3_detail_pages.md)
- [`step42_phase4_testing.md`](step42_phase4_testing.md)
- [`step42_phase5_polish.md`](step42_phase5_polish.md)

---

## Directory Structure (target)

```text
ui/explorer/
├── package.json
├── vite.config.ts
├── tsconfig.json
├── tsconfig.app.json
├── tsconfig.node.json
├── postcss.config.js
├── tailwind.config.ts          (if needed by shadcn; Tailwind v4 may use CSS-only)
├── components.json             (shadcn/ui config)
├── index.html
├── .env.example                (VITE_BROWSER_API_BASE=http://127.0.0.1:8000)
├── playwright.config.ts
├── README.md
├── src/
│   ├── main.tsx
│   ├── index.css               (Tailwind directives)
│   ├── app/
│   │   ├── App.tsx
│   │   ├── router.tsx
│   │   ├── query-client.ts
│   │   └── providers.tsx
│   ├── lib/
│   │   ├── api/
│   │   │   ├── client.ts       (base fetch wrapper)
│   │   │   ├── browser.ts      (typed API functions)
│   │   │   ├── schemas.ts      (Zod parsers)
│   │   │   ├── types.ts        (inferred TS types)
│   │   │   └── errors.ts       (normalized error model)
│   │   ├── url/
│   │   │   └── search-params.ts (URL ↔ state helpers)
│   │   └── utils/
│   │       ├── format.ts
│   │       ├── badges.ts
│   │       └── entity.ts
│   ├── components/
│   │   ├── layout/
│   │   │   ├── AppShell.tsx
│   │   │   ├── TopBar.tsx
│   │   │   ├── SidePanel.tsx
│   │   │   └── PageContainer.tsx
│   │   ├── search/
│   │   │   ├── SearchBar.tsx
│   │   │   ├── SearchModeToggle.tsx
│   │   │   ├── ResultList.tsx
│   │   │   ├── ResultCard.tsx
│   │   │   ├── ResultGroup.tsx
│   │   │   ├── EmptyState.tsx
│   │   │   └── LoadingState.tsx
│   │   ├── filters/
│   │   │   ├── FiltersPanel.tsx
│   │   │   ├── FilterChips.tsx
│   │   │   ├── FacetSection.tsx
│   │   │   └── ConfidenceFilter.tsx
│   │   ├── detail/
│   │   │   ├── EntityHeader.tsx
│   │   │   ├── SupportBadges.tsx
│   │   │   ├── TimestampList.tsx
│   │   │   ├── LinkedEntityList.tsx
│   │   │   └── CountPills.tsx
│   │   ├── rule/
│   │   │   ├── RuleDetailPage.tsx
│   │   │   ├── RuleConditions.tsx
│   │   │   ├── RuleExceptions.tsx
│   │   │   ├── RuleLinkedEvidence.tsx
│   │   │   ├── RuleSourceEvents.tsx
│   │   │   └── RelatedRules.tsx
│   │   ├── evidence/
│   │   │   ├── EvidenceDetailPage.tsx
│   │   │   ├── EvidenceContext.tsx
│   │   │   ├── EvidenceLinkedRules.tsx
│   │   │   └── EvidenceLinkedEvents.tsx
│   │   ├── concept/
│   │   │   ├── ConceptDetailPage.tsx
│   │   │   ├── ConceptNeighbors.tsx
│   │   │   ├── ConceptAliases.tsx
│   │   │   └── ConceptCoverage.tsx
│   │   ├── lesson/
│   │   │   ├── LessonDetailPage.tsx
│   │   │   ├── LessonCounts.tsx
│   │   │   ├── LessonTopConcepts.tsx
│   │   │   ├── LessonTopRules.tsx
│   │   │   └── LessonTopEvidence.tsx
│   │   └── common/
│   │       ├── ErrorPanel.tsx
│   │       ├── NotFound.tsx
│   │       ├── CopyLinkButton.tsx
│   │       └── JsonPreviewDialog.tsx
│   ├── pages/
│   │   ├── SearchPage.tsx
│   │   ├── RulePage.tsx
│   │   ├── EvidencePage.tsx
│   │   ├── ConceptPage.tsx
│   │   └── LessonPage.tsx
│   ├── hooks/
│   │   ├── useBrowserSearch.ts
│   │   ├── useBrowserFacets.ts
│   │   ├── useRuleDetail.ts
│   │   ├── useEvidenceDetail.ts
│   │   ├── useConceptDetail.ts
│   │   ├── useConceptNeighbors.ts
│   │   ├── useLessonDetail.ts
│   │   └── useSearchUrlState.ts
│   └── test/
│       ├── setup.ts
│       ├── test-utils.tsx        (custom render with providers)
│       ├── fixtures/             (copy of browser_api_samples JSONs)
│       │   ├── health.json
│       │   ├── search-stop-loss.json
│       │   ├── search-timeframe.json
│       │   ├── search-daily-level.json
│       │   ├── search-empty.json
│       │   ├── rule-detail.json
│       │   ├── evidence-detail.json
│       │   ├── concept-detail.json
│       │   ├── concept-neighbors.json
│       │   ├── lesson-detail.json
│       │   └── facets.json
│       └── mocks/
│           └── handlers.ts       (MSW or manual fetch mocks)
├── tests/
│   └── e2e/
│       ├── screenplay/           (Screenplay pattern abstractions)
│       │   ├── actor.ts
│       │   ├── abilities/
│       │   │   └── browse-the-web.ts
│       │   ├── tasks/
│       │   │   ├── navigate-to.ts
│       │   │   ├── search-for.ts
│       │   │   ├── apply-filter.ts
│       │   │   ├── open-result.ts
│       │   │   ├── open-rule-detail.ts
│       │   │   ├── open-evidence-detail.ts
│       │   │   ├── open-concept-detail.ts
│       │   │   ├── open-lesson-detail.ts
│       │   │   └── click-neighbor.ts
│       │   ├── questions/
│       │   │   ├── search-results.ts
│       │   │   ├── rule-detail-page.ts
│       │   │   ├── evidence-detail-page.ts
│       │   │   ├── concept-detail-page.ts
│       │   │   ├── lesson-detail-page.ts
│       │   │   ├── filter-state.ts
│       │   │   ├── page-heading.ts
│       │   │   └── error-state.ts
│       │   └── interactions/
│       │       ├── click.ts
│       │       ├── fill.ts
│       │       ├── navigate.ts
│       │       └── wait-for.ts
│       ├── search.spec.ts
│       ├── detail-rule.spec.ts
│       ├── detail-evidence.spec.ts
│       ├── concept.spec.ts
│       ├── lesson.spec.ts
│       └── regressions.spec.ts
```

---

## Route Map

| Route | Page | Behavior |
|-------|------|----------|
| `/` | — | Redirect to `/search` |
| `/search` | `SearchPage` | Search + browse; query params encode all state |
| `/search?q=...&group=unit_type&lesson=...` | `SearchPage` | Filtered/grouped search |
| `/rule/:docId` | `RulePage` | Rule detail |
| `/evidence/:docId` | `EvidencePage` | Evidence detail |
| `/concept/:conceptId` | `ConceptPage` | Concept detail |
| `/lesson/:lessonId` | `LessonPage` | Lesson detail |

**Reserved for future steps**: `/compare/...`, `/export/...`

### URL Query Parameters (search page)

| Param | Type | Notes |
|-------|------|-------|
| `q` | string | Free-text query; empty = browse mode |
| `group` | `none` \| `unit_type` | Grouping mode |
| `lesson` | string (repeatable) | Filter: lesson_ids |
| `concept` | string (repeatable) | Filter: concept_ids |
| `unit_type` | string (repeatable) | Filter: unit_types |
| `support_basis` | string (repeatable) | Filter: support_basis |
| `evidence_requirement` | string (repeatable) | Filter: evidence_requirement |
| `teaching_mode` | string (repeatable) | Filter: teaching_mode |
| `min_confidence_score` | number | Minimum confidence |
| `mode` | `search` \| `browse` | (optional, derived from `q`) |

---

## API Client Contract

The typed API client in `src/lib/api/browser.ts` exposes exactly these functions:

```typescript
healthCheck(): Promise<HealthResponse>
searchBrowser(request: BrowserSearchRequest): Promise<BrowserSearchResponse>
getRuleDetail(docId: string): Promise<RuleDetailResponse>
getEvidenceDetail(docId: string): Promise<EvidenceDetailResponse>
getConceptDetail(conceptId: string): Promise<ConceptDetailResponse>
getConceptNeighbors(conceptId: string): Promise<ConceptNeighborListResponse>
getLessonDetail(lessonId: string): Promise<LessonDetailResponse>
getFacets(query?: string, filters?: BrowserSearchFilters): Promise<FacetResponse>
```

Every response MUST be parsed through the corresponding Zod schema before returning. Parsing failures are normalized into the standard `ApiError` shape.

---

## Zod Schema ↔ Backend Contract Mapping

The Zod schemas in `src/lib/api/schemas.ts` must exactly mirror the Pydantic models in `pipeline/explorer/contracts.py`:

| Zod Schema | Pydantic Model | Notes |
|------------|---------------|-------|
| `HealthResponseSchema` | (inline dict) | `{status, rag_ready, explorer_ready, doc_count, corpus_contract_version}` |
| `BrowserSearchFiltersSchema` | `BrowserSearchFilters` | All filter fields |
| `BrowserSearchRequestSchema` | `BrowserSearchRequest` | `{query, top_k, filters, return_groups}` |
| `BrowserResultCardSchema` | `BrowserResultCard` | 16 fields, `unit_type` is `Literal["rule_card","knowledge_event","evidence_ref","concept_node","concept_relation"]` |
| `BrowserSearchResponseSchema` | `BrowserSearchResponse` | `{query, cards, groups, facets, hit_count}` |
| `RuleDetailResponseSchema` | `RuleDetailResponse` | Nested `evidence_refs`, `source_events`, `related_rules` as `BrowserResultCard[]` |
| `EvidenceDetailResponseSchema` | `EvidenceDetailResponse` | Nested `source_rules`, `source_events` as `BrowserResultCard[]` |
| `ConceptNeighborSchema` | `ConceptNeighbor` | `{concept_id, relation, direction, weight}` |
| `ConceptDetailResponseSchema` | `ConceptDetailResponse` | `rule_count` and `event_count` are full totals |
| `LessonDetailResponseSchema` | `LessonDetailResponse` | `support_basis_counts` is `Record<string, number>` |
| `FacetResponseSchema` | (inline dict) | Same shape as `BrowserSearchResponse.facets` |
| `ApiErrorResponseSchema` | — | `{detail: string}` (FastAPI default for HTTPException) |

---

## Backend Integration Points

The explorer backend runs as part of the existing FastAPI app at `http://127.0.0.1:8000`. The Vite dev server proxies `/browser/*` to this backend. In production, both would be behind the same reverse proxy or the SPA is served as static files.

**Vite proxy config** (`vite.config.ts`):
```typescript
server: {
  proxy: {
    '/browser': {
      target: process.env.VITE_BROWSER_API_BASE || 'http://127.0.0.1:8000',
      changeOrigin: true,
    },
  },
}
```

---

## Testing Strategy Summary

| Layer | Tool | What | Count Target |
|-------|------|------|--------------|
| Zod schemas | Vitest | Parse real fixtures, reject malformed | ~12 tests |
| URL helpers | Vitest | Encode/decode search params | ~8 tests |
| Utility fns | Vitest | `format.ts`, `badges.ts`, `entity.ts` | ~10 tests |
| Components | Vitest + RTL | `ResultCard`, `SupportBadges`, `FilterChips`, `FiltersPanel`, `ConceptNeighbors`, `LessonCounts` | ~18 tests |
| Hooks | Vitest + RTL | All 8 hooks: success, loading, error, empty, malformed | ~40 tests |
| Page integration | Vitest + RTL | 6 page-level tests with mocked API | ~12 tests |
| E2E (Screenplay) | Playwright | 10 scenarios from spec section 13.4 | 10 specs |

**Total target**: ~110 tests.

**Screenplay pattern for E2E**: see [`step42_phase4_testing.md`](step42_phase4_testing.md) for full Screenplay architecture.

---

## Acceptance Criteria (from spec §18)

### Functional
- [ ] Search page works for query and browse mode
- [ ] Filters work and survive refresh
- [ ] Result cards are clean and usable
- [ ] Rule detail works
- [ ] Evidence detail works
- [ ] Concept detail works
- [ ] Neighbor navigation works
- [ ] Lesson detail works

### Quality
- [ ] UI only calls `/browser/*`
- [ ] No raw retrieval JSON is rendered directly
- [ ] URL is shareable and reproducible
- [ ] Loading/empty/error states are present
- [ ] Step 3.1 regression cases visible in UI behavior

### Testing
- [ ] Unit/component tests pass (`npm run test`)
- [ ] Route-level integration tests pass
- [ ] Playwright E2E tests pass (`npm run test:e2e`)
- [ ] Existing backend tests remain untouched

### Documentation
- [ ] `ui/explorer/README.md` documents local startup, env vars, test commands
