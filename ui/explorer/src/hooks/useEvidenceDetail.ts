import { useQuery } from '@tanstack/react-query'

import { getBrowserEvidence } from '@/lib/api/browser'

export function useEvidenceDetail(docId: string | undefined) {
  return useQuery({
    queryKey: ['browser-evidence', docId] as const,
    queryFn: () => getBrowserEvidence(docId!),
    enabled: Boolean(docId),
    staleTime: 60_000,
  })
}
