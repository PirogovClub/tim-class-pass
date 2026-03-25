import { useParams, Navigate } from 'react-router-dom'

import { ErrorPanel } from '@/components/common/ErrorPanel'
import { NotFound } from '@/components/common/NotFound'
import { PageContainer } from '@/components/layout/PageContainer'
import { RuleDetailPage } from '@/components/rule/RuleDetailPage'
import { LoadingState } from '@/components/search/LoadingState'
import { useRuleDetail } from '@/hooks/useRuleDetail'
import { isApiError } from '@/lib/api/errors'

export function RulePage() {
  const { docId } = useParams<{ docId: string }>()
  const q = useRuleDetail(docId)

  if (!docId) return <Navigate to="/search" replace />

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
          <NotFound title="Rule not found" message="No rule exists for this document id." />
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

  return <RuleDetailPage data={q.data} />
}
