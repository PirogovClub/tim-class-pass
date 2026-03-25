import { useQuery } from '@tanstack/react-query'

import { getConceptLessons } from '@/lib/api/browser'

export function useConceptLessons(conceptId: string | undefined) {
  return useQuery({
    queryKey: ['browser-concept-lessons', conceptId] as const,
    queryFn: () => getConceptLessons(conceptId!),
    enabled: Boolean(conceptId),
    staleTime: 60_000,
  })
}
