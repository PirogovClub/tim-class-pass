import { Navigate, useParams } from 'react-router-dom'

import { ErrorPanel } from '@/components/common/ErrorPanel'
import { NotFound } from '@/components/common/NotFound'
import { ConceptLessonsPage as ConceptLessonsView } from '@/components/concept/ConceptLessonsPage'
import { useConceptLessons } from '@/hooks/useConceptLessons'
import { isApiError } from '@/lib/api/errors'

export function ConceptLessonsPage() {
  const { conceptId } = useParams<{ conceptId: string }>()
  const q = useConceptLessons(conceptId)

  if (!conceptId) {return <Navigate to="/search" replace />}
  if (q.isLoading) {return <ConceptLessonsView loading />}
  if (q.isError) {
    if (isApiError(q.error) && q.error.isNotFound) {
      return <NotFound title="Concept lessons not found" description="No concept lesson listing exists for this concept id." />
    }
    return <ErrorPanel error={q.error} onRetry={() => void q.refetch()} />
  }
  return <ConceptLessonsView data={q.data} />
}
