# Phase 4 — Testing (Unit, Integration, E2E with Screenplay Pattern)

## Goal

Comprehensive test suite covering schemas, URL helpers, components, hooks, page integration, and end-to-end flows. E2E tests use the **Screenplay pattern** for clean separation of concerns.

---

## 4.1 — Test Infrastructure Setup

### Vitest Configuration

In `vite.config.ts` (or separate `vitest.config.ts`):

```typescript
/// <reference types="vitest" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
  },
  resolve: {
    alias: { '@': '/src' },
  },
});
```

### Test Setup (`src/test/setup.ts`)

```typescript
import '@testing-library/jest-dom/vitest';
```

### Custom Render (`src/test/test-utils.tsx`)

Wraps components with QueryClient and MemoryRouter for testing:

```typescript
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, type RenderOptions } from '@testing-library/react';
import { MemoryRouter, type MemoryRouterProps } from 'react-router-dom';
import type { ReactElement } from 'react';

interface CustomRenderOptions extends Omit<RenderOptions, 'wrapper'> {
  routerProps?: MemoryRouterProps;
  queryClient?: QueryClient;
}

export function renderWithProviders(
  ui: ReactElement,
  options: CustomRenderOptions = {},
) {
  const { routerProps, queryClient, ...renderOptions } = options;
  const client = queryClient ?? new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <QueryClientProvider client={client}>
        <MemoryRouter {...routerProps}>{children}</MemoryRouter>
      </QueryClientProvider>
    );
  }

  return { ...render(ui, { wrapper: Wrapper, ...renderOptions }), queryClient: client };
}

export { screen, waitFor, within, act } from '@testing-library/react';
export { default as userEvent } from '@testing-library/user-event';
```

### Test Fixtures

Copy the `browser_api_samples/` JSONs (from `audit/historical-bundles/audit_step4_1_bundle_rework2/browser_api_samples/`) into `src/test/fixtures/` as typed fixture files:

| Fixture file | Source sample |
|-------------|--------------|
| `health.json` | `health.json` |
| `search-stop-loss.json` | `search_stop_loss_example.json` |
| `search-timeframe.json` | `search_timeframe_rules.json` |
| `search-daily-level.json` | `search_daily_level.json` |
| `search-empty.json` | `search_empty_results.json` |
| `rule-detail.json` | `rule_detail_stop_loss.json` |
| `evidence-detail.json` | `evidence_detail_stop_loss.json` |
| `concept-detail.json` | `concept_detail_node_stop_loss.json` |
| `concept-neighbors.json` | `concept_neighbors_node_stop_loss.json` |
| `lesson-detail.json` | `lesson_detail_stop_loss_lesson.json` |
| `facets.json` | `facets.json` |

---

## 4.2 — Schema Tests (`src/lib/api/schemas.test.ts`)

### Tests

```
✓ HealthResponseSchema parses real health.json fixture
✓ BrowserSearchResponseSchema parses real search fixture
✓ BrowserResultCardSchema parses individual card from search fixture
✓ RuleDetailResponseSchema parses real rule-detail.json fixture
✓ EvidenceDetailResponseSchema parses real evidence-detail.json fixture
✓ ConceptDetailResponseSchema parses real concept-detail.json fixture
✓ ConceptNeighborListResponseSchema parses real concept-neighbors.json fixture
✓ LessonDetailResponseSchema parses real lesson-detail.json fixture
✓ FacetResponseSchema parses real facets.json fixture
✓ BrowserResultCardSchema rejects payload with missing doc_id
✓ BrowserResultCardSchema rejects payload with invalid unit_type
✓ BrowserSearchResponseSchema rejects payload with wrong facets shape
```

### Approach

```typescript
import { describe, it, expect } from 'vitest';
import * as S from './schemas';
import healthFixture from '@/test/fixtures/health.json';
import searchFixture from '@/test/fixtures/search-stop-loss.json';
// ... etc

describe('Schema validation against real API fixtures', () => {
  it('parses health response', () => {
    const result = S.HealthResponseSchema.safeParse(healthFixture);
    expect(result.success).toBe(true);
  });

  it('rejects card with missing doc_id', () => {
    const bad = { unit_type: 'rule_card', title: 'x' };
    const result = S.BrowserResultCardSchema.safeParse(bad);
    expect(result.success).toBe(false);
  });
});
```

---

## 4.3 — URL Helper Tests (`src/lib/url/search-params.test.ts`)

### Tests

```
✓ encodes empty state to empty params
✓ encodes query to ?q=...
✓ encodes group=unit_type
✓ encodes multiple lesson filters
✓ encodes min_confidence_score
✓ decodes empty params to default state
✓ decodes ?q=test&group=unit_type
✓ round-trips: encode(decode(params)) === params (for non-default values)
```

---

## 4.4 — Utility Tests

### `src/lib/utils/format.test.ts`

```
✓ formatConfidence renders 0.9 as "90%"
✓ formatConfidence returns null for null input
✓ formatTimestampRange renders "00:36–00:40"
✓ formatTimestampRange renders "01:03" when start === end
```

### `src/lib/utils/badges.test.ts`

```
✓ unitTypeBadgeColor returns correct color for each unit type
✓ supportBasisLabel returns human-readable labels
```

### `src/lib/utils/entity.test.ts`

```
✓ entityRoute returns /rule/{id} for rule_card
✓ entityRoute returns /evidence/{id} for evidence_ref
✓ entityRoute returns /concept/{first_concept_id} for concept_node
✓ entityRoute returns /concept/{first_concept_id} for concept_relation
```

---

## 4.5 — Component Tests

### `src/components/search/ResultCard.test.tsx`

```
✓ renders title and snippet
✓ renders unit type badge
✓ renders confidence score when present
✓ renders support badges
✓ renders timestamps
✓ renders count pills (evidence_count, related_rule_count, related_event_count)
✓ title links to correct detail route
✓ does not render confidence when null
```

### `src/components/detail/SupportBadges.test.tsx`

```
✓ renders all three badges when all values present
✓ renders confidence as percentage
✓ omits badges when values are null
```

### `src/components/filters/FilterChips.test.tsx`

```
✓ renders one chip per active filter
✓ clicking × on a chip calls onRemove with correct key and value
✓ renders "Clear all" button when filters active
✓ "Clear all" calls onClearAll
```

### `src/components/filters/FiltersPanel.test.tsx`

```
✓ renders all facet sections
✓ facet section shows values with counts
✓ clicking a facet value calls onToggle
✓ confidence filter renders input
```

### `src/components/concept/ConceptNeighbors.test.tsx`

```
✓ renders each neighbor row
✓ neighbor concept_id is a link to /concept/{id}
✓ shows relation and direction
✓ shows weight when present
✓ renders empty state when no neighbors
```

### `src/components/lesson/LessonCounts.test.tsx`

```
✓ renders all four counts as pills
✓ renders support basis distribution
```

---

## 4.6 — Hook Tests

### Pattern

All hooks are tested using `renderHook` from RTL with `QueryClientProvider` wrapper and mocked `fetch`:

```typescript
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

function createWrapper() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}
```

### `src/hooks/useBrowserSearch.test.ts`

```
✓ returns search results on success
✓ handles loading state
✓ handles error state
✓ handles empty result set
✓ rejects malformed payload (Zod failure becomes error)
```

### `src/hooks/useBrowserFacets.test.ts`

```
✓ returns facets on success
✓ handles loading state
✓ handles error state
```

### `src/hooks/useRuleDetail.test.ts`

```
✓ returns rule detail on success
✓ returns error for 404
✓ returns error for 400 (wrong unit type)
✓ handles loading state
✓ rejects malformed payload
```

### `src/hooks/useEvidenceDetail.test.ts`

```
✓ returns evidence detail on success
✓ returns error for 404
✓ returns error for 400
```

### `src/hooks/useConceptDetail.test.ts`

```
✓ returns concept detail on success
✓ returns error for 404
✓ concept detail has correct rule_count and event_count (full totals)
```

### `src/hooks/useConceptNeighbors.test.ts`

```
✓ returns neighbor list on success
✓ returns empty array for concept with no neighbors
```

### `src/hooks/useLessonDetail.test.ts`

```
✓ returns lesson detail on success
✓ returns error for 404
✓ lesson detail has correct support_basis_counts
```

---

## 4.7 — Page Integration Tests

### Pattern

Mount the full page in `MemoryRouter` with mocked fetch. Assert that the page assembles data correctly, shows loading/error states, and links work.

### `src/pages/SearchPage.test.tsx`

```
✓ renders browse mode with empty query
✓ shows search results when query is set
✓ applies filters and updates URL
✓ clicking a result card navigates to detail route
✓ group toggle switches between flat and grouped view
✓ shows empty state when no results
✓ shows error panel on API error
```

### `src/pages/RulePage.test.tsx`

```
✓ renders rule detail for valid doc_id
✓ shows not-found for 404
✓ shows error for wrong unit type (400)
```

### `src/pages/ConceptPage.test.tsx`

```
✓ renders concept detail with neighbors
✓ shows linked rules and events
✓ clicking a neighbor navigates to that concept
```

### `src/pages/LessonPage.test.tsx`

```
✓ renders lesson counts and top entities
✓ shows not-found for unknown lesson
```

---

## 4.8 — End-to-End Tests with Screenplay Pattern

### What is the Screenplay Pattern?

The Screenplay pattern organizes test automation around **actors performing tasks and asking questions**, instead of procedural page-object scripts.

```
Actor → has Abilities → performs Tasks → asks Questions
```

| Concept | Role | Example |
|---------|------|---------|
| **Actor** | A persona with abilities | `Analyst` who can browse the web |
| **Ability** | What an actor can do | `BrowseTheWeb` wraps Playwright's `Page` |
| **Task** | A high-level business action | `SearchFor('стоп-лосс')`, `OpenRuleDetail(card)` |
| **Question** | A query about observable state | `SearchResults.displayed()`, `RuleDetailPage.title()` |
| **Interaction** | A low-level page action | `Click(locator)`, `Fill(locator, value)` |

### Why Screenplay for this project?

1. **Readability**: Tests read like analyst workflows: "The analyst searches for stop-loss, then opens the first rule, then inspects linked evidence."
2. **Reusability**: Tasks and questions are shared across specs without coupling to page structure.
3. **Maintainability**: If a component's DOM changes, only the interaction/question layer updates — specs remain stable.

---

### Screenplay Implementation

#### `tests/e2e/screenplay/actor.ts`

```typescript
import type { Page } from '@playwright/test';

export class Actor {
  constructor(
    public readonly name: string,
    private readonly page: Page,
  ) {}

  get browseTheWeb(): Page {
    return this.page;
  }

  async attemptsTo(...tasks: Array<(page: Page) => Promise<void>>): Promise<void> {
    for (const task of tasks) {
      await task(this.page);
    }
  }

  async asks<T>(question: (page: Page) => Promise<T>): Promise<T> {
    return question(this.page);
  }
}
```

#### `tests/e2e/screenplay/abilities/browse-the-web.ts`

```typescript
import type { Page } from '@playwright/test';

export function BrowseTheWeb(page: Page) {
  return page;
}
```

---

#### Tasks (`tests/e2e/screenplay/tasks/`)

##### `navigate-to.ts`

```typescript
import type { Page } from '@playwright/test';

export function NavigateTo(path: string) {
  return async (page: Page) => {
    await page.goto(path);
    await page.waitForLoadState('networkidle');
  };
}
```

##### `search-for.ts`

```typescript
import type { Page } from '@playwright/test';

export function SearchFor(query: string) {
  return async (page: Page) => {
    const input = page.getByRole('searchbox').or(page.getByPlaceholder(/search/i));
    await input.fill(query);
    await input.press('Enter');
    await page.waitForLoadState('networkidle');
  };
}
```

##### `apply-filter.ts`

```typescript
import type { Page } from '@playwright/test';

export function ApplyFilter(facetLabel: string, value: string) {
  return async (page: Page) => {
    const section = page.getByRole('region', { name: facetLabel });
    await section.getByLabel(value).check();
    await page.waitForLoadState('networkidle');
  };
}
```

##### `open-result.ts`

```typescript
import type { Page } from '@playwright/test';

export function OpenResultByIndex(index: number) {
  return async (page: Page) => {
    const cards = page.getByRole('article');
    await cards.nth(index).getByRole('link').first().click();
    await page.waitForLoadState('networkidle');
  };
}

export function OpenResultByTitle(titleSubstring: string) {
  return async (page: Page) => {
    await page.getByRole('link', { name: titleSubstring }).first().click();
    await page.waitForLoadState('networkidle');
  };
}
```

##### `open-rule-detail.ts`

```typescript
import type { Page } from '@playwright/test';

export function OpenRuleDetail(docId: string) {
  return async (page: Page) => {
    await page.goto(`/rule/${encodeURIComponent(docId)}`);
    await page.waitForLoadState('networkidle');
  };
}
```

##### `open-evidence-detail.ts`

```typescript
export function OpenEvidenceDetail(docId: string) {
  return async (page: Page) => {
    await page.goto(`/evidence/${encodeURIComponent(docId)}`);
    await page.waitForLoadState('networkidle');
  };
}
```

##### `open-concept-detail.ts`

```typescript
export function OpenConceptDetail(conceptId: string) {
  return async (page: Page) => {
    await page.goto(`/concept/${encodeURIComponent(conceptId)}`);
    await page.waitForLoadState('networkidle');
  };
}
```

##### `open-lesson-detail.ts`

```typescript
export function OpenLessonDetail(lessonId: string) {
  return async (page: Page) => {
    await page.goto(`/lesson/${encodeURIComponent(lessonId)}`);
    await page.waitForLoadState('networkidle');
  };
}
```

##### `click-neighbor.ts`

```typescript
export function ClickNeighbor(neighborConceptId: string) {
  return async (page: Page) => {
    await page.getByRole('link', { name: neighborConceptId }).click();
    await page.waitForLoadState('networkidle');
  };
}
```

---

#### Questions (`tests/e2e/screenplay/questions/`)

##### `search-results.ts`

```typescript
import type { Page } from '@playwright/test';

export const SearchResults = {
  async count(page: Page): Promise<number> {
    return page.getByRole('article').count();
  },

  async titles(page: Page): Promise<string[]> {
    const cards = page.getByRole('article');
    const count = await cards.count();
    const titles: string[] = [];
    for (let i = 0; i < count; i++) {
      const heading = cards.nth(i).getByRole('heading').first();
      titles.push((await heading.textContent()) ?? '');
    }
    return titles;
  },

  async firstCardUnitType(page: Page): Promise<string> {
    const badge = page.getByRole('article').first().getByTestId('unit-type-badge');
    return (await badge.textContent()) ?? '';
  },

  async isDisplayed(page: Page): Promise<boolean> {
    return (await page.getByRole('article').count()) > 0;
  },

  async isEmptyStateVisible(page: Page): Promise<boolean> {
    return page.getByText(/no results/i).isVisible();
  },

  async isBrowseMode(page: Page): Promise<boolean> {
    return page.getByText(/browsing/i).isVisible();
  },
};
```

##### `rule-detail-page.ts`

```typescript
export const RuleDetailPage = {
  async title(page: Page): Promise<string> {
    return (await page.getByRole('heading', { level: 1 }).textContent()) ?? '';
  },

  async ruleTextRu(page: Page): Promise<string> {
    return (await page.getByTestId('rule-text-ru').textContent()) ?? '';
  },

  async linkedEvidenceCount(page: Page): Promise<number> {
    return page.getByTestId('linked-evidence').getByRole('article').count();
  },

  async isVisible(page: Page): Promise<boolean> {
    return page.getByRole('heading', { level: 1 }).isVisible();
  },
};
```

##### `evidence-detail-page.ts`

```typescript
export const EvidenceDetailPage = {
  async title(page: Page): Promise<string> {
    return (await page.getByRole('heading', { level: 1 }).textContent()) ?? '';
  },

  async snippet(page: Page): Promise<string> {
    return (await page.getByTestId('evidence-snippet').textContent()) ?? '';
  },

  async sourceRulesCount(page: Page): Promise<number> {
    return page.getByTestId('source-rules').getByRole('article').count();
  },

  async isVisible(page: Page): Promise<boolean> {
    return page.getByRole('heading', { level: 1 }).isVisible();
  },
};
```

##### `concept-detail-page.ts`

```typescript
export const ConceptDetailPage = {
  async conceptId(page: Page): Promise<string> {
    return (await page.getByTestId('concept-id').textContent()) ?? '';
  },

  async aliasCount(page: Page): Promise<number> {
    return page.getByTestId('concept-aliases').getByRole('listitem').count();
  },

  async neighborCount(page: Page): Promise<number> {
    return page.getByTestId('concept-neighbors').getByRole('link').count();
  },

  async topRulesCount(page: Page): Promise<number> {
    return page.getByTestId('top-rules').getByRole('article').count();
  },

  async isVisible(page: Page): Promise<boolean> {
    return page.getByTestId('concept-id').isVisible();
  },
};
```

##### `lesson-detail-page.ts`

```typescript
export const LessonDetailPage = {
  async lessonId(page: Page): Promise<string> {
    return (await page.getByTestId('lesson-id').textContent()) ?? '';
  },

  async ruleCount(page: Page): Promise<string> {
    return (await page.getByTestId('rule-count').textContent()) ?? '';
  },

  async topConceptCount(page: Page): Promise<number> {
    return page.getByTestId('top-concepts').getByRole('link').count();
  },

  async isVisible(page: Page): Promise<boolean> {
    return page.getByTestId('lesson-id').isVisible();
  },
};
```

##### `error-state.ts`

```typescript
export const ErrorState = {
  async isNotFoundVisible(page: Page): Promise<boolean> {
    return page.getByText(/not found/i).isVisible();
  },

  async isErrorPanelVisible(page: Page): Promise<boolean> {
    return page.getByRole('alert').isVisible();
  },
};
```

---

### E2E Spec Files

#### Playwright Config (`playwright.config.ts`)

```typescript
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'html',
  use: {
    baseURL: 'http://127.0.0.1:5173',
    trace: 'on-first-retry',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
  webServer: [
    {
      command: 'npm run dev',
      url: 'http://127.0.0.1:5173',
      reuseExistingServer: !process.env.CI,
    },
  ],
});
```

**Note**: The FastAPI backend must be running separately at `http://127.0.0.1:8000` before E2E tests execute. Document this in the README.

---

#### `tests/e2e/search.spec.ts`

```typescript
import { test, expect } from '@playwright/test';
import { Actor } from './screenplay/actor';
import { NavigateTo } from './screenplay/tasks/navigate-to';
import { SearchFor } from './screenplay/tasks/search-for';
import { SearchResults } from './screenplay/questions/search-results';

test.describe('Search page', () => {
  let analyst: Actor;

  test.beforeEach(async ({ page }) => {
    analyst = new Actor('Analyst', page);
  });

  test('1. health smoke — app loads', async () => {
    await analyst.attemptsTo(NavigateTo('/search'));
    const isBrowse = await analyst.asks(SearchResults.isBrowseMode);
    expect(isBrowse).toBe(true);
  });

  test('2. browse mode shows results with empty query', async () => {
    await analyst.attemptsTo(NavigateTo('/search'));
    const count = await analyst.asks(SearchResults.count);
    expect(count).toBeGreaterThan(0);
  });

  test('3. search "Пример постановки стоп-лосса" — evidence-first', async () => {
    await analyst.attemptsTo(
      NavigateTo('/search'),
      SearchFor('Пример постановки стоп-лосса'),
    );
    const firstType = await analyst.asks(SearchResults.firstCardUnitType);
    expect(firstType).toContain('evidence');
  });

  test('4. search "Правила торговли на разных таймфреймах" — rule-card-first', async () => {
    await analyst.attemptsTo(
      NavigateTo('/search'),
      SearchFor('Правила торговли на разных таймфреймах'),
    );
    const firstType = await analyst.asks(SearchResults.firstCardUnitType);
    expect(firstType).toContain('rule');
  });

  test('5. search "Как определить дневной уровень?" — actionable-first', async () => {
    await analyst.attemptsTo(
      NavigateTo('/search'),
      SearchFor('Как определить дневной уровень?'),
    );
    const count = await analyst.asks(SearchResults.count);
    expect(count).toBeGreaterThan(0);
    const firstType = await analyst.asks(SearchResults.firstCardUnitType);
    expect(['rule', 'evidence'].some(t => firstType.includes(t))).toBe(true);
  });
});
```

#### `tests/e2e/detail-rule.spec.ts`

```typescript
import { test, expect } from '@playwright/test';
import { Actor } from './screenplay/actor';
import { NavigateTo } from './screenplay/tasks/navigate-to';
import { SearchFor } from './screenplay/tasks/search-for';
import { OpenResultByIndex } from './screenplay/tasks/open-result';
import { RuleDetailPage } from './screenplay/questions/rule-detail-page';

test.describe('Rule detail page', () => {
  let analyst: Actor;

  test.beforeEach(async ({ page }) => {
    analyst = new Actor('Analyst', page);
  });

  test('6. open rule detail from search', async () => {
    await analyst.attemptsTo(
      NavigateTo('/search'),
      SearchFor('Правила торговли на разных таймфреймах'),
      OpenResultByIndex(0),
    );
    const isVisible = await analyst.asks(RuleDetailPage.isVisible);
    expect(isVisible).toBe(true);
    const title = await analyst.asks(RuleDetailPage.title);
    expect(title.length).toBeGreaterThan(0);
  });
});
```

#### `tests/e2e/detail-evidence.spec.ts`

```typescript
import { test, expect } from '@playwright/test';
import { Actor } from './screenplay/actor';
import { NavigateTo } from './screenplay/tasks/navigate-to';
import { SearchFor } from './screenplay/tasks/search-for';
import { OpenResultByIndex } from './screenplay/tasks/open-result';
import { EvidenceDetailPage } from './screenplay/questions/evidence-detail-page';

test.describe('Evidence detail page', () => {
  let analyst: Actor;

  test.beforeEach(async ({ page }) => {
    analyst = new Actor('Analyst', page);
  });

  test('7. open evidence detail from search', async () => {
    await analyst.attemptsTo(
      NavigateTo('/search'),
      SearchFor('Пример постановки стоп-лосса'),
      OpenResultByIndex(0),
    );
    const isVisible = await analyst.asks(EvidenceDetailPage.isVisible);
    expect(isVisible).toBe(true);
  });
});
```

#### `tests/e2e/concept.spec.ts`

```typescript
import { test, expect } from '@playwright/test';
import { Actor } from './screenplay/actor';
import { OpenConceptDetail } from './screenplay/tasks/open-concept-detail';
import { ClickNeighbor } from './screenplay/tasks/click-neighbor';
import { ConceptDetailPage } from './screenplay/questions/concept-detail-page';

test.describe('Concept detail page', () => {
  let analyst: Actor;

  test.beforeEach(async ({ page }) => {
    analyst = new Actor('Analyst', page);
  });

  test('8. open concept detail and click neighbor', async () => {
    await analyst.attemptsTo(
      OpenConceptDetail('node:stop_loss'),
    );
    const isVisible = await analyst.asks(ConceptDetailPage.isVisible);
    expect(isVisible).toBe(true);

    const neighborCount = await analyst.asks(ConceptDetailPage.neighborCount);
    if (neighborCount > 0) {
      // Get first neighbor link text
      const page = analyst.browseTheWeb;
      const firstNeighborLink = page.getByTestId('concept-neighbors').getByRole('link').first();
      const neighborId = await firstNeighborLink.textContent();
      await analyst.attemptsTo(ClickNeighbor(neighborId!));
      const newConceptVisible = await analyst.asks(ConceptDetailPage.isVisible);
      expect(newConceptVisible).toBe(true);
    }
  });
});
```

#### `tests/e2e/lesson.spec.ts`

```typescript
import { test, expect } from '@playwright/test';
import { Actor } from './screenplay/actor';
import { OpenLessonDetail } from './screenplay/tasks/open-lesson-detail';
import { LessonDetailPage } from './screenplay/questions/lesson-detail-page';

test.describe('Lesson detail page', () => {
  let analyst: Actor;

  test.beforeEach(async ({ page }) => {
    analyst = new Actor('Analyst', page);
  });

  test('9. open lesson detail', async () => {
    await analyst.attemptsTo(
      OpenLessonDetail('2025-09-29-sviatoslav-chornyi'),
    );
    const isVisible = await analyst.asks(LessonDetailPage.isVisible);
    expect(isVisible).toBe(true);
    const lessonId = await analyst.asks(LessonDetailPage.lessonId);
    expect(lessonId).toContain('2025-09-29');
  });
});
```

#### `tests/e2e/regressions.spec.ts`

```typescript
import { test, expect } from '@playwright/test';
import { Actor } from './screenplay/actor';
import { NavigateTo } from './screenplay/tasks/navigate-to';
import { ErrorState } from './screenplay/questions/error-state';

test.describe('Regression: error states', () => {
  let analyst: Actor;

  test.beforeEach(async ({ page }) => {
    analyst = new Actor('Analyst', page);
  });

  test('10. invalid entity route shows not-found', async () => {
    await analyst.attemptsTo(
      NavigateTo('/rule/nonexistent-doc-id-12345'),
    );
    const isNotFound = await analyst.asks(ErrorState.isNotFoundVisible);
    expect(isNotFound).toBe(true);
  });
});
```

---

## Phase 4 Validation Checklist

- [ ] `npm run test` — all Vitest unit/component/hook/integration tests pass
- [ ] Schema tests validate all 11 real API fixtures
- [ ] URL helper tests cover encode/decode round-trip
- [ ] Component tests cover all 6 specified components
- [ ] Hook tests cover all 7 hooks with success/loading/error/empty/malformed
- [ ] Page integration tests cover all 4 page types
- [ ] `npm run test:e2e` — all 10 Playwright Screenplay specs pass
- [ ] E2E tests preserve Step 3.1 regression behaviors (#3, #4, #5)
- [ ] Screenplay tasks/questions/interactions are reusable across specs
