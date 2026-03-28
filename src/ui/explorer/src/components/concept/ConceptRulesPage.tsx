import { EntityHeader } from '@/components/detail/EntityHeader'
import { LinkedEntityList } from '@/components/detail/LinkedEntityList'
import { PageContainer } from '@/components/layout/PageContainer'
import { Skeleton } from '@/components/ui/skeleton'
import type { ConceptRuleListResponse } from '@/lib/api/types'

export function ConceptRulesPage({ data, loading = false }: { data?: ConceptRuleListResponse; loading?: boolean }) {
  if (loading || !data) {
    return <PageContainer><div className="space-y-4"><Skeleton className="h-8 w-64" /><Skeleton className="h-56 w-full" /></div></PageContainer>
  }

  return (
    <PageContainer>
      <div className="space-y-6">
        <EntityHeader title={`${data.concept_id} rules`} unitType="concept_node" conceptIds={[data.concept_id]} />
        <LinkedEntityList
          title="Rules"
          cards={data.rules}
          emptyLabel="No rules found for this concept."
          testId="concept-rules-list"
        />
      </div>
    </PageContainer>
  )
}
