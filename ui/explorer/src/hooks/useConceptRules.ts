import { useQuery } from '@tanstack/react-query'

import { getConceptRules } from '@/lib/api/browser'

export function useConceptRules(conceptId: string | undefined) {
  return useQuery({
    queryKey: ['browser-concept-rules', conceptId] as const,
    queryFn: () => getConceptRules(conceptId!),
    enabled: Boolean(conceptId),
    staleTime: 60_000,
  })
}
