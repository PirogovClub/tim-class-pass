import { useParams, Navigate } from 'react-router-dom'

import { ConceptDetailPage } from '@/components/concept/ConceptDetailPage'
import { ErrorPanel } from '@/components/common/ErrorPanel'
import { NotFound } from '@/components/common/NotFound'
import { PageContainer } from '@/components/layout/PageContainer'
import { LoadingState } from '@/components/search/LoadingState'
import { useConceptDetail } from '@/hooks/useConceptDetail'
import { useConceptNeighbors } from '@/hooks/useConceptNeighbors'
import { isApiError } from '@/lib/api/errors'

export function ConceptPage() {
  const { conceptId } = useParams<{ conceptId: string }>()
  const q = useConceptDetail(conceptId)
  const n = useConceptNeighbors(conceptId)

  if (!conceptId) return <Navigate to="/search" replace />

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
          <NotFound title="Concept not found" message="No concept exists for this id." />
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

  return <ConceptDetailPage data={q.data} neighborData={n.data} neighborError={n.isError ? n.error : undefined} />
}
