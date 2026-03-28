import { Navigate, useParams } from 'react-router-dom'

import { ErrorPanel } from '@/components/common/ErrorPanel'
import { NotFound } from '@/components/common/NotFound'
import { EventDetailPage } from '@/components/event/EventDetailPage'
import { PageContainer } from '@/components/layout/PageContainer'
import { LoadingState } from '@/components/search/LoadingState'
import { useEventDetail } from '@/hooks/useEventDetail'
import { isApiError } from '@/lib/api/errors'

export function EventPage() {
  const { docId } = useParams<{ docId: string }>()
  const q = useEventDetail(docId)

  if (!docId) {
    return <Navigate to="/search" replace />
  }

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
          <NotFound title="Event not found" message="No knowledge event exists for this document id." />
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

  return <EventDetailPage data={q.data} />
}
