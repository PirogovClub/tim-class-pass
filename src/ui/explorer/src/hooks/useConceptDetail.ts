import { useQuery } from '@tanstack/react-query'

import { getBrowserConcept } from '@/lib/api/browser'

export function useConceptDetail(conceptId: string | undefined) {
  return useQuery({
    queryKey: ['browser-concept', conceptId] as const,
    queryFn: () => getBrowserConcept(conceptId!),
    enabled: Boolean(conceptId),
    staleTime: 60_000,
  })
}
