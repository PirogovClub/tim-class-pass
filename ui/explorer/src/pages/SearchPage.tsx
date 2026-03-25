import { Filter } from 'lucide-react'
import { useMemo, useState } from 'react'

import { CopyLinkButton } from '@/components/common/CopyLinkButton'
import { ErrorPanel } from '@/components/common/ErrorPanel'
import { type FilterChip,FilterChips } from '@/components/filters/FilterChips'
import { FiltersPanel } from '@/components/filters/FiltersPanel'
import { PageContainer } from '@/components/layout/PageContainer'
import { SidePanel } from '@/components/layout/SidePanel'
import { EmptyState } from '@/components/search/EmptyState'
import { LoadingState } from '@/components/search/LoadingState'
import { ResultGroup } from '@/components/search/ResultGroup'
import { ResultList } from '@/components/search/ResultList'
import { SearchBar } from '@/components/search/SearchBar'
import { SearchModeToggle } from '@/components/search/SearchModeToggle'
import { Button } from '@/components/ui/button'
import { useBrowserFacets } from '@/hooks/useBrowserFacets'
import { useBrowserSearch } from '@/hooks/useBrowserSearch'
import { useSearchUrlState } from '@/hooks/useSearchUrlState'
import { defaultSearchUrlState } from '@/lib/url/search-params'

function buildFilterChips(state: ReturnType<typeof useSearchUrlState>['state'], setState: ReturnType<typeof useSearchUrlState>['setState']): FilterChip[] {
  const chips: FilterChip[] = []
  const { filters } = state
  for (const id of filters.lesson_ids) {
    chips.push({
      key: `lesson:${id}`,
      label: `Lesson ${id}`,
      onRemove: () =>
        setState((prev) => ({
          ...prev,
          filters: { ...prev.filters, lesson_ids: prev.filters.lesson_ids.filter((x) => x !== id) },
        })),
    })
  }
  for (const id of filters.concept_ids) {
    chips.push({
      key: `concept:${id}`,
      label: `Concept ${id}`,
      onRemove: () =>
        setState((prev) => ({
          ...prev,
          filters: { ...prev.filters, concept_ids: prev.filters.concept_ids.filter((x) => x !== id) },
        })),
    })
  }
  for (const u of filters.unit_types) {
    chips.push({
      key: `unit:${u}`,
      label: `Type ${u}`,
      onRemove: () =>
        setState((prev) => ({
          ...prev,
          filters: { ...prev.filters, unit_types: prev.filters.unit_types.filter((x) => x !== u) },
        })),
    })
  }
  for (const s of filters.support_basis) {
    chips.push({
      key: `sb:${s}`,
      label: `Support ${s}`,
      onRemove: () =>
        setState((prev) => ({
          ...prev,
          filters: { ...prev.filters, support_basis: prev.filters.support_basis.filter((x) => x !== s) },
        })),
    })
  }
  for (const e of filters.evidence_requirement) {
    chips.push({
      key: `er:${e}`,
      label: `Evidence req. ${e}`,
      onRemove: () =>
        setState((prev) => ({
          ...prev,
          filters: {
            ...prev.filters,
            evidence_requirement: prev.filters.evidence_requirement.filter((x) => x !== e),
          },
        })),
    })
  }
  for (const t of filters.teaching_mode) {
    chips.push({
      key: `tm:${t}`,
      label: `Teaching ${t}`,
      onRemove: () =>
        setState((prev) => ({
          ...prev,
          filters: { ...prev.filters, teaching_mode: prev.filters.teaching_mode.filter((x) => x !== t) },
        })),
    })
  }
  if (filters.min_confidence_score != null) {
    chips.push({
      key: 'minc',
      label: `Min confidence ≥ ${filters.min_confidence_score}`,
      onRemove: () =>
        setState((prev) => ({
          ...prev,
          filters: { ...prev.filters, min_confidence_score: null },
        })),
    })
  }
  return chips
}

export function SearchPage() {
  const { state, setState } = useSearchUrlState()
  const [filtersOpen, setFiltersOpen] = useState(false)
  const searchQuery = useBrowserSearch(state)
  const facetsQuery = useBrowserFacets(state)

  const chips = useMemo(() => buildFilterChips(state, setState), [state, setState])

  const data = searchQuery.data
  const showGrouped = state.returnGroups && data != null && Object.keys(data.groups).length > 0

  const filtersHeadingId = 'filters-heading'

  const filtersBody = (
    <>
      <h2 id={filtersHeadingId} className="text-sm font-semibold text-slate-900">
        Filters
      </h2>
      <FiltersPanel facets={facetsQuery.data} state={state} setState={setState} />
    </>
  )

  return (
    <PageContainer>
      <div className="flex flex-col gap-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0 flex-1 space-y-3">
            <SearchBar
              id="explorer-search"
              value={state.q}
              onSearch={(q) => setState((prev) => ({ ...prev, q }))}
            />
            <div className="flex flex-wrap items-center gap-3">
              <SearchModeToggle
                returnGroups={state.returnGroups}
                onChange={(returnGroups) => setState((prev) => ({ ...prev, returnGroups }))}
              />
              <label className="flex items-center gap-2 text-sm text-slate-600">
                <span className="whitespace-nowrap">Top K</span>
                <input
                  type="number"
                  min={1}
                  className="w-20 rounded-md border border-slate-300 px-2 py-1 text-sm"
                  value={state.topK}
                  onChange={(e) => {
                    const n = Number.parseInt(e.target.value, 10)
                    setState((prev) => ({ ...prev, topK: Number.isFinite(n) && n > 0 ? n : prev.topK }))
                  }}
                  aria-label="Maximum number of results"
                />
              </label>
              <Button
                type="button"
                variant="outline"
                className="md:hidden"
                onClick={() => setFiltersOpen(true)}
                aria-expanded={filtersOpen}
                aria-controls="search-filters-drawer"
              >
                <Filter className="mr-2 h-4 w-4" aria-hidden />
                Filters
              </Button>
              <CopyLinkButton label="Copy search URL" />
            </div>
          </div>
        </div>

        <FilterChips chips={chips} />

        <div className="flex flex-col gap-6 md:flex-row md:items-start">
          <SidePanel
            id="search-filters-desktop"
            labelledBy={filtersHeadingId}
            className="hidden md:flex"
            aria-label="Search filters"
          >
            {filtersBody}
          </SidePanel>

          {filtersOpen ? (
            <div className="fixed inset-0 z-40 md:hidden" role="presentation">
              <button
                type="button"
                className="absolute inset-0 bg-black/40"
                aria-label="Close filters"
                onClick={() => setFiltersOpen(false)}
              />
              <aside
                id="search-filters-drawer"
                className="absolute right-0 top-0 flex h-full w-[min(100%,20rem)] flex-col gap-4 overflow-y-auto border-l border-slate-200 bg-white p-4 shadow-xl"
                aria-labelledby={filtersHeadingId}
                aria-label="Search filters"
              >
                {filtersBody}
                <Button type="button" onClick={() => setFiltersOpen(false)}>
                  Done
                </Button>
              </aside>
            </div>
          ) : null}

          <div className="min-w-0 flex-1 space-y-4" role="region" aria-label="Search results" aria-live="polite">
            {searchQuery.isLoading ? <LoadingState /> : null}
            {searchQuery.isError ? (
              <ErrorPanel error={searchQuery.error} onRetry={() => void searchQuery.refetch()} />
            ) : null}
            {searchQuery.isSuccess && data ? (
              <>
                <p className="text-sm text-slate-600">
                  {data.hit_count} hit{data.hit_count === 1 ? '' : 's'}
                  {facetsQuery.isError ? <span className="text-amber-700"> (facets unavailable)</span> : null}
                </p>
                {data.hit_count === 0 ? (
                  <EmptyState
                    title="No results"
                    description="Try a different query or relax filters."
                    onClearFilters={() => setState(defaultSearchUrlState())}
                  />
                ) : showGrouped ? (
                  <div className="space-y-8">
                    {Object.entries(data.groups).map(([title, cards], i) => (
                      <ResultGroup key={`${title}-${i}`} groupIndex={i} title={title} cards={cards} />
                    ))}
                  </div>
                ) : (
                  <ResultList cards={data.cards} />
                )}
              </>
            ) : null}
          </div>
        </div>

        <div className="flex justify-end">
          <Button type="button" variant="ghost" size="sm" onClick={() => setState(defaultSearchUrlState())}>
            Reset search & filters
          </Button>
        </div>
      </div>
    </PageContainer>
  )
}
