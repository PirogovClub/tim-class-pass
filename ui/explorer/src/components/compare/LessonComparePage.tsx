import { LessonCompareGrid } from '@/components/compare/LessonCompareGrid'
import { LessonOverlapPanel } from '@/components/compare/LessonOverlapPanel'
import { PageContainer } from '@/components/layout/PageContainer'
import { Skeleton } from '@/components/ui/skeleton'
import type { LessonCompareResponse } from '@/lib/api/types'

export function LessonComparePage({ data, loading = false }: { data?: LessonCompareResponse; loading?: boolean }) {
  if (loading || !data) {
    return <PageContainer><div className="space-y-4"><Skeleton className="h-28 w-full" /><Skeleton className="h-80 w-full" /></div></PageContainer>
  }

  return (
    <PageContainer>
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Lesson Compare</h1>
          <p className="mt-1 text-sm text-slate-600">Compare lesson coverage, support basis, and shared concepts across the selected lessons.</p>
        </div>
        <LessonOverlapPanel
          sharedConcepts={data.shared_concepts}
          uniqueConcepts={data.unique_concepts}
          sharedRuleFamilies={data.shared_rule_families}
        />
        <LessonCompareGrid lessons={data.lessons} />
      </div>
    </PageContainer>
  )
}
