import { useQuery } from '@tanstack/react-query'

import { getBrowserLesson } from '@/lib/api/browser'

export function useLessonDetail(lessonId: string | undefined) {
  return useQuery({
    queryKey: ['browser-lesson', lessonId] as const,
    queryFn: () => getBrowserLesson(lessonId!),
    enabled: Boolean(lessonId),
    staleTime: 60_000,
  })
}
