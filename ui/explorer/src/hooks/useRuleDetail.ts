import { useQuery } from '@tanstack/react-query'

import { getBrowserRule } from '@/lib/api/browser'

export function useRuleDetail(docId: string | undefined) {
  return useQuery({
    queryKey: ['browser-rule', docId] as const,
    queryFn: () => getBrowserRule(docId!),
    enabled: Boolean(docId),
    staleTime: 60_000,
  })
}
