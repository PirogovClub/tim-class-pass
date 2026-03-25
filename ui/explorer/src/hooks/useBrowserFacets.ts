import { useQuery } from '@tanstack/react-query'

import { getBrowserFacets } from '@/lib/api/browser'
import type { SearchUrlState } from '@/lib/url/search-params'

export function useBrowserFacets(state: SearchUrlState) {
  return useQuery({
    queryKey: ['browser-facets', state.q, state.filters] as const,
    queryFn: () =>
      getBrowserFacets({
        query: state.q.trim() ? state.q : null,
        filters: state.filters,
      }),
    staleTime: 15_000,
  })
}
