import { useQuery } from '@tanstack/react-query'

import { getBrowserConceptNeighbors } from '@/lib/api/browser'

export function useConceptNeighbors(conceptId: string | undefined) {
  return useQuery({
    queryKey: ['browser-concept-neighbors', conceptId] as const,
    queryFn: () => getBrowserConceptNeighbors(conceptId!),
    enabled: Boolean(conceptId),
    staleTime: 60_000,
  })
}
