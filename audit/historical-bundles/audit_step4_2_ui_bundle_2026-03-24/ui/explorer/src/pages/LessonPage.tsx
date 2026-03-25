import { useParams, Navigate } from 'react-router-dom'

import { ErrorPanel } from '@/components/common/ErrorPanel'
import { LessonDetailPage } from '@/components/lesson/LessonDetailPage'
import { NotFound } from '@/components/common/NotFound'
import { PageContainer } from '@/components/layout/PageContainer'
import { LoadingState } from '@/components/search/LoadingState'
import { useLessonDetail } from '@/hooks/useLessonDetail'
import { isApiError } from '@/lib/api/errors'

export function LessonPage() {
  const { lessonId } = useParams<{ lessonId: string }>()
  const q = useLessonDetail(lessonId)

  if (!lessonId) return <Navigate to="/search" replace />

  if (q.isLoading) {
    return (
      <PageContainer>
        <LoadingState />
      </PageContainer>
    )
  }

  if (q.isError) {
    if (isApiError(q.error) && q.error.isNotFound) {
      return (
        <PageContainer>
          <NotFound title="Lesson not found" message="No lesson exists for this id." />
        </PageContainer>
      )
    }
    return (
      <PageContainer>
        <ErrorPanel error={q.error} onRetry={() => void q.refetch()} />
      </PageContainer>
    )
  }

  if (!q.data) {
    return null
  }

  return <LessonDetailPage data={q.data} />
}
