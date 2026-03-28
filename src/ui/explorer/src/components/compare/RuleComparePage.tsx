import { RuleCompareSummary } from '@/components/compare/RuleCompareSummary'
import { RuleCompareTable } from '@/components/compare/RuleCompareTable'
import { PageContainer } from '@/components/layout/PageContainer'
import { Skeleton } from '@/components/ui/skeleton'
import type { RuleCompareResponse } from '@/lib/api/types'

export function RuleComparePage({ data, loading = false }: { data?: RuleCompareResponse; loading?: boolean }) {
  if (loading || !data) {
    return <PageContainer><div className="space-y-4"><Skeleton className="h-28 w-full" /><Skeleton className="h-80 w-full" /></div></PageContainer>
  }

  return (
    <PageContainer>
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Rule Compare</h1>
          <p className="mt-1 text-sm text-slate-600">Compare rule structure, support basis, and linked context side by side.</p>
        </div>
        <RuleCompareSummary summary={data.summary} />
        <RuleCompareTable rules={data.rules} />
      </div>
    </PageContainer>
  )
}
