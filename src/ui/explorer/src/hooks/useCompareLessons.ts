import { useQuery } from '@tanstack/react-query'

import { postCompareLessons } from '@/lib/api/browser'

export function useCompareLessons(lessonIds: string[]) {
  return useQuery({
    queryKey: ['browser-compare-lessons', lessonIds] as const,
    queryFn: () => postCompareLessons({ lesson_ids: lessonIds }),
    enabled: lessonIds.length >= 2,
    staleTime: 60_000,
  })
}
