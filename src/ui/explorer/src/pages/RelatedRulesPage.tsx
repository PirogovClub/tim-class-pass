import { Navigate, useParams } from 'react-router-dom'

import { ErrorPanel } from '@/components/common/ErrorPanel'
import { NotFound } from '@/components/common/NotFound'
import { RelatedRulesPage as RelatedRulesView } from '@/components/related/RelatedRulesPage'
import { useRelatedRules } from '@/hooks/useRelatedRules'
import { useRuleDetail } from '@/hooks/useRuleDetail'
import { isApiError } from '@/lib/api/errors'

export function RelatedRulesPage() {
  const { docId } = useParams<{ docId: string }>()
  const relatedQuery = useRelatedRules(docId)
  const ruleQuery = useRuleDetail(docId)

  if (!docId) {return <Navigate to="/search" replace />}
  if (relatedQuery.isLoading) {
    return <RelatedRulesView loading />
  }
  if (relatedQuery.isError) {
    if (isApiError(relatedQuery.error) && relatedQuery.error.isNotFound) {
      return <NotFound title="Related rules not found" description="No related-rules workflow exists for this document id." />
    }
    return <ErrorPanel error={relatedQuery.error} onRetry={() => void relatedQuery.refetch()} />
  }
  return <RelatedRulesView data={relatedQuery.data} sourceTitle={ruleQuery.data?.title} />
}
