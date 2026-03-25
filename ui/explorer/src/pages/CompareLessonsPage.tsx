import { useSearchParams } from 'react-router-dom'

import { ErrorPanel } from '@/components/common/ErrorPanel'
import { NotFound } from '@/components/common/NotFound'
import { LessonComparePage as LessonCompareView } from '@/components/compare/LessonComparePage'
import { useCompareLessons } from '@/hooks/useCompareLessons'
import { isApiError } from '@/lib/api/errors'
import { parseCompareIds } from '@/lib/url/compare-params'

export function CompareLessonsPage() {
  const [searchParams] = useSearchParams()
  const lessonIds = parseCompareIds(searchParams)
  const q = useCompareLessons(lessonIds)

  if (lessonIds.length < 2) {
    return <NotFound title="Need at least two lessons" description="Add two to four lessons to compare." />
  }
  if (q.isLoading) {return <LessonCompareView loading />}
  if (q.isError) {
    if (isApiError(q.error) && q.error.isNotFound) {
      return <NotFound title="Lesson compare unavailable" description="One or more selected lessons could not be found." />
    }
    return <ErrorPanel error={q.error} onRetry={() => void q.refetch()} />
  }
  return <LessonCompareView data={q.data} />
}
