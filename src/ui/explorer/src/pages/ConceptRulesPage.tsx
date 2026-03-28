import { Navigate, useParams } from 'react-router-dom'

import { ErrorPanel } from '@/components/common/ErrorPanel'
import { NotFound } from '@/components/common/NotFound'
import { ConceptRulesPage as ConceptRulesView } from '@/components/concept/ConceptRulesPage'
import { useConceptRules } from '@/hooks/useConceptRules'
import { isApiError } from '@/lib/api/errors'

export function ConceptRulesPage() {
  const { conceptId } = useParams<{ conceptId: string }>()
  const q = useConceptRules(conceptId)

  if (!conceptId) {return <Navigate to="/search" replace />}
  if (q.isLoading) {return <ConceptRulesView loading />}
  if (q.isError) {
    if (isApiError(q.error) && q.error.isNotFound) {
      return <NotFound title="Concept rules not found" description="No concept rule listing exists for this concept id." />
    }
    return <ErrorPanel error={q.error} onRetry={() => void q.refetch()} />
  }
  return <ConceptRulesView data={q.data} />
}
