import { Navigate,useParams } from 'react-router-dom'

import { ErrorPanel } from '@/components/common/ErrorPanel'
import { NotFound } from '@/components/common/NotFound'
import { EvidenceDetailPage } from '@/components/evidence/EvidenceDetailPage'
import { PageContainer } from '@/components/layout/PageContainer'
import { LoadingState } from '@/components/search/LoadingState'
import { useEvidenceDetail } from '@/hooks/useEvidenceDetail'
import { isApiError } from '@/lib/api/errors'

export function EvidencePage() {
  const { docId } = useParams<{ docId: string }>()
  const q = useEvidenceDetail(docId)

  if (!docId) {return <Navigate to="/search" replace />}

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
          <NotFound title="Evidence not found" message="No evidence document exists for this id." />
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

  return <EvidenceDetailPage data={q.data} />
}
