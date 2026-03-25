import { PageContainer } from '@/components/layout/PageContainer'
import { RelatedRuleGroup } from '@/components/related/RelatedRuleGroup'
import { Skeleton } from '@/components/ui/skeleton'
import type { RelatedRulesResponse, RelationReason } from '@/lib/api/types'

export function RelatedRulesPage({
  data,
  sourceTitle,
  loading = false,
}: {
  data?: RelatedRulesResponse
  sourceTitle?: string
  loading?: boolean
}) {
  if (loading || !data) {
    return <PageContainer><div className="space-y-4"><Skeleton className="h-12 w-80" /><Skeleton className="h-80 w-full" /></div></PageContainer>
  }

  const groups = Object.entries(data.groups)

  return (
    <PageContainer>
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Related Rules</h1>
          <p className="mt-1 text-sm text-slate-600">
            {sourceTitle ? `Next rules to inspect from ${sourceTitle}.` : 'Next rules to inspect from this source rule.'}
          </p>
        </div>
        {groups.length ? (
          <div className="space-y-8">
            {groups.map(([reason, items]) => (
              <RelatedRuleGroup key={reason} reason={reason as RelationReason} items={items} />
            ))}
          </div>
        ) : (
          <p className="text-sm text-slate-500">No related rules found.</p>
        )}
      </div>
    </PageContainer>
  )
}
