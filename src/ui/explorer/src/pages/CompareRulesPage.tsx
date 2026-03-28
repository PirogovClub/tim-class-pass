import { useSearchParams } from 'react-router-dom'

import { ErrorPanel } from '@/components/common/ErrorPanel'
import { NotFound } from '@/components/common/NotFound'
import { RuleComparePage as RuleCompareView } from '@/components/compare/RuleComparePage'
import { useCompareRules } from '@/hooks/useCompareRules'
import { isApiError } from '@/lib/api/errors'
import { parseCompareIds } from '@/lib/url/compare-params'

export function CompareRulesPage() {
  const [searchParams] = useSearchParams()
  const ruleIds = parseCompareIds(searchParams)
  const q = useCompareRules(ruleIds)

  if (ruleIds.length < 2) {
    return <NotFound title="Need at least two rules" description="Add two to four rules to compare." />
  }
  if (q.isLoading) {return <RuleCompareView loading />}
  if (q.isError) {
    if (isApiError(q.error) && q.error.isNotFound) {
      return <NotFound title="Rule compare unavailable" description="One or more selected rules could not be found." />
    }
    return <ErrorPanel error={q.error} onRetry={() => void q.refetch()} />
  }
  return <RuleCompareView data={q.data} />
}
