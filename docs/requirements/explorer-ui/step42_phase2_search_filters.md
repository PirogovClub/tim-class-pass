# Phase 2 — Search Page, Filters, URL State

## Goal

A fully working search/browse page with facet-based filters, grouped or flat result display, and all state encoded in the URL.

---

## Step 2.1 — URL State Helpers (`src/lib/url/search-params.ts`)

Bidirectional serialization between URL search params and the typed search state.

### State Shape

```typescript
export interface SearchUrlState {
  q: string;
  group: 'none' | 'unit_type';
  lesson: string[];
  concept: string[];
  unit_type: string[];
  support_basis: string[];
  evidence_requirement: string[];
  teaching_mode: string[];
  min_confidence_score: number | null;
}

export const DEFAULT_SEARCH_STATE: SearchUrlState = {
  q: '',
  group: 'none',
  lesson: [],
  concept: [],
  unit_type: [],
  support_basis: [],
  evidence_requirement: [],
  teaching_mode: [],
  min_confidence_score: null,
};
```

### Encoder

```typescript
export function encodeSearchParams(state: SearchUrlState): URLSearchParams {
  const params = new URLSearchParams();
  if (state.q) params.set('q', state.q);
  if (state.group !== 'none') params.set('group', state.group);
  state.lesson.forEach(v => params.append('lesson', v));
  state.concept.forEach(v => params.append('concept', v));
  state.unit_type.forEach(v => params.append('unit_type', v));
  state.support_basis.forEach(v => params.append('support_basis', v));
  state.evidence_requirement.forEach(v => params.append('evidence_requirement', v));
  state.teaching_mode.forEach(v => params.append('teaching_mode', v));
  if (state.min_confidence_score != null)
    params.set('min_confidence_score', String(state.min_confidence_score));
  return params;
}
```

### Decoder

```typescript
export function decodeSearchParams(params: URLSearchParams): SearchUrlState {
  return {
    q: params.get('q') ?? '',
    group: params.get('group') === 'unit_type' ? 'unit_type' : 'none',
    lesson: params.getAll('lesson'),
    concept: params.getAll('concept'),
    unit_type: params.getAll('unit_type'),
    support_basis: params.getAll('support_basis'),
    evidence_requirement: params.getAll('evidence_requirement'),
    teaching_mode: params.getAll('teaching_mode'),
    min_confidence_score: params.has('min_confidence_score')
      ? Number(params.get('min_confidence_score'))
      : null,
  };
}
```

### Conversion to API request

```typescript
export function stateToSearchRequest(state: SearchUrlState, topK = 20): BrowserSearchRequest {
  return {
    query: state.q,
    top_k: topK,
    filters: {
      lesson_ids: state.lesson,
      concept_ids: state.concept,
      unit_types: state.unit_type as UnitType[],
      support_basis: state.support_basis,
      evidence_requirement: state.evidence_requirement,
      teaching_mode: state.teaching_mode,
      min_confidence_score: state.min_confidence_score,
    },
    return_groups: state.group === 'unit_type',
  };
}
```

---

## Step 2.2 — Hook: `useSearchUrlState`

Reads/writes search state from/to the URL. Uses `useSearchParams` from React Router.

```typescript
export function useSearchUrlState() {
  const [searchParams, setSearchParams] = useSearchParams();
  const state = useMemo(() => decodeSearchParams(searchParams), [searchParams]);

  const setState = useCallback(
    (updater: Partial<SearchUrlState> | ((prev: SearchUrlState) => SearchUrlState)) => {
      setSearchParams(prev => {
        const current = decodeSearchParams(prev);
        const next = typeof updater === 'function' ? updater(current) : { ...current, ...updater };
        return encodeSearchParams(next);
      });
    },
    [setSearchParams],
  );

  return { state, setState };
}
```

---

## Step 2.3 — Hook: `useBrowserSearch`

```typescript
export function useBrowserSearch(state: SearchUrlState) {
  const request = stateToSearchRequest(state);
  return useQuery({
    queryKey: ['browser-search', request],
    queryFn: () => searchBrowser(request),
    staleTime: 15_000,
  });
}
```

---

## Step 2.4 — Hook: `useBrowserFacets`

Fetches full-corpus facets for the current filters (uses `GET /browser/facets`).

```typescript
export function useBrowserFacets(state: SearchUrlState) {
  const filters: Partial<BrowserSearchFilters> = {
    lesson_ids: state.lesson,
    concept_ids: state.concept,
    unit_types: state.unit_type as UnitType[],
    support_basis: state.support_basis,
    evidence_requirement: state.evidence_requirement,
    teaching_mode: state.teaching_mode,
    min_confidence_score: state.min_confidence_score,
  };
  return useQuery({
    queryKey: ['browser-facets', state.q, filters],
    queryFn: () => getFacets(state.q || undefined, filters),
    staleTime: 15_000,
  });
}
```

---

## Step 2.5 — SearchPage

### Layout (desktop)

```
┌─────────────────────────────────────────────────┐
│ [TopBar with app title]                         │
├────────────┬────────────────────────────────────┤
│ Filters    │ SearchBar                          │
│ Panel      │ [mode: search|browse] [group toggle]│
│            │ FilterChips (active filters)        │
│ - Unit Type│ ResultList / ResultGroups           │
│ - Lesson   │   ResultCard                       │
│ - Concept  │   ResultCard                       │
│ - Support  │   …                                │
│ - Evidence │ EmptyState | LoadingState           │
│ - Teaching │                                    │
│ - Confid.  │                                    │
└────────────┴────────────────────────────────────┘
```

On mobile: filters collapse into a sheet/drawer.

### Component Breakdown

1. **SearchPage** — orchestrator. Reads URL state, triggers hooks, passes data down.
2. **SearchBar** — input with debounced `q` update. Pressing Enter or blur updates URL.
3. **SearchModeToggle** — displays "Searching for: {q}" or "Browsing all entities".
4. **FilterChips** — horizontal strip of active filter badges with × to remove.
5. **FiltersPanel** — left sidebar. Each `FacetSection` is collapsible, shows facet counts from `useBrowserFacets`.
6. **FacetSection** — checkboxes for each facet value. Shows count badge.
7. **ConfidenceFilter** — slider or number input for `min_confidence_score`.
8. **ResultList** — maps `cards[]` to `ResultCard` when `group=none`.
9. **ResultGroup** — when `group=unit_type`, groups cards into sections (Rules, Events, Evidence, Concepts, Relations).
10. **ResultCard** — displays: title, unit_type badge, snippet, lesson_id, confidence, support_basis, evidence_requirement, timestamps, click → navigates to detail page.
11. **EmptyState** — when `cards.length === 0` and not loading.
12. **LoadingState** — skeleton/spinner.

### Navigation from ResultCard

| `unit_type` | Target route |
|-------------|--------------|
| `rule_card` | `/rule/{doc_id}` |
| `knowledge_event` | `/rule/{doc_id}` (or concept if no rule) |
| `evidence_ref` | `/evidence/{doc_id}` |
| `concept_node` | `/concept/{first_concept_id}` |
| `concept_relation` | `/concept/{first_concept_id}` |

---

## Step 2.6 — ResultCard Component

### Props

```typescript
interface ResultCardProps {
  card: BrowserResultCard;
}
```

### Must display

- **Title** (`card.title`) — clickable link to detail page
- **Unit type badge** — colored badge (rule=blue, event=green, evidence=amber, concept=purple, relation=slate)
- **Snippet** — first ~200 chars of `card.snippet`
- **Lesson ID** — as subtle label
- **Confidence** — if present, as percentage or decimal
- **Support basis** — badge
- **Evidence requirement** — badge
- **Teaching mode** — badge if present
- **Timestamps** — compact list if available
- **Related counts** — `evidence_count`, `related_rule_count`, `related_event_count` as small pills

### Accessibility

- Card is a `<article>` element
- Title is a `<Link>` (React Router) so it's keyboard-navigable
- Badges use appropriate contrast ratios

---

## Step 2.7 — FiltersPanel + FacetSection

### FacetSection Props

```typescript
interface FacetSectionProps {
  label: string;
  facetKey: string;           // e.g., "by_unit_type"
  facets: Record<string, number>;
  selected: string[];
  onToggle: (value: string) => void;
}
```

### Behavior

- Collapsible accordion
- Each value row: `[x] value_name (count)`
- Clicking toggles that value in the URL filter
- Selected values appear as FilterChips at the top of the main area

### Filter ↔ facetKey mapping

| Filter param | Facet key |
|-------------|-----------|
| `unit_type` | `by_unit_type` |
| `lesson` | `by_lesson` |
| `concept` | `by_concept` |
| `support_basis` | `by_support_basis` |
| `evidence_requirement` | `by_evidence_requirement` |
| `teaching_mode` | `by_teaching_mode` |

### ConfidenceFilter

- Input type number, range 0.0–1.0, step 0.1
- Updates `min_confidence_score` in URL
- Shows current value

---

## Step 2.8 — Grouping

When `group=unit_type`:
- `BrowserSearchResponse.groups` is already keyed by `rules`, `events`, `evidence`, `concepts`, `relations`
- Render each non-empty group as a section with heading and count
- Groups appear in this order: Rules → Events → Evidence → Concepts → Relations

When `group=none`:
- Render `BrowserSearchResponse.cards` as a flat list

Toggle: a segmented control or dropdown in the search header that writes `group` to URL.

---

## Phase 2 Validation Checklist

- [ ] `/search` renders browse mode (empty query) with all entities
- [ ] Typing a query and pressing Enter updates `?q=...` in URL
- [ ] Results render as cards with all required fields
- [ ] Clicking a result card navigates to the correct detail route
- [ ] Group toggle switches between flat and grouped view
- [ ] Filters panel loads facets from `GET /browser/facets`
- [ ] Clicking a facet value updates the URL and re-triggers search
- [ ] Active filter chips display above results, each removable
- [ ] "Clear all" removes all filters from URL
- [ ] Refreshing the page restores all state from URL
- [ ] Empty state shows when no results match
- [ ] Loading state shows during fetch
- [ ] Network error shows error panel
