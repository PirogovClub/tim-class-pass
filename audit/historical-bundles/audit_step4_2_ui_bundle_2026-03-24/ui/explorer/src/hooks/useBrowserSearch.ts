import { useQuery } from '@tanstack/react-query'
import { useMemo } from 'react'

import { postBrowserSearch } from '@/lib/api/browser'
import { searchStateToRequest, type SearchUrlState } from '@/lib/url/search-params'

export function useBrowserSearch(state: SearchUrlState) {
  const request = useMemo(() => searchStateToRequest(state), [state])

  return useQuery({
    queryKey: ['browser-search', request] as const,
    queryFn: () => postBrowserSearch(request),
    staleTime: 15_000,
  })
}
