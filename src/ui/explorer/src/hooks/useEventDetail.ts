import { useQuery } from '@tanstack/react-query'

import { getBrowserEvent } from '@/lib/api/browser'

export function useEventDetail(docId: string | undefined) {
  return useQuery({
    queryKey: ['browser-event', docId] as const,
    queryFn: () => getBrowserEvent(docId!),
    enabled: Boolean(docId),
    staleTime: 60_000,
  })
}
