import { useQuery } from '@tanstack/react-query'

import { getRelatedRules } from '@/lib/api/browser'

export function useRelatedRules(docId: string | undefined) {
  return useQuery({
    queryKey: ['browser-related-rules', docId] as const,
    queryFn: () => getRelatedRules(docId!),
    enabled: Boolean(docId),
    staleTime: 60_000,
  })
}
