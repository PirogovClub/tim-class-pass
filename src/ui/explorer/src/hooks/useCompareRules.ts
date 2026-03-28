import { useQuery } from '@tanstack/react-query'

import { postCompareRules } from '@/lib/api/browser'

export function useCompareRules(ruleIds: string[], includeRelatedContext = true) {
  return useQuery({
    queryKey: ['browser-compare-rules', ruleIds, includeRelatedContext] as const,
    queryFn: () => postCompareRules({ rule_ids: ruleIds, include_related_context: includeRelatedContext }),
    enabled: ruleIds.length >= 2,
    staleTime: 60_000,
  })
}
