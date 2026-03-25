import { useCallback, useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'

import {
  parseSearchUrlParams,
  serializeSearchUrlParams,
  type SearchUrlState,
} from '@/lib/url/search-params'

export function useSearchUrlState(): {
  state: SearchUrlState
  setState: (next: SearchUrlState | ((prev: SearchUrlState) => SearchUrlState)) => void
} {
  const [searchParams, setSearchParams] = useSearchParams()

  const state = useMemo(() => parseSearchUrlParams(searchParams), [searchParams])

  const setState = useCallback(
    (next: SearchUrlState | ((prev: SearchUrlState) => SearchUrlState)) => {
      setSearchParams(
        (prev) => {
          const current = parseSearchUrlParams(prev)
          const resolved = typeof next === 'function' ? next(current) : next
          return serializeSearchUrlParams(resolved)
        },
        { replace: true },
      )
    },
    [setSearchParams],
  )

  return { state, setState }
}
