import { ResultCard } from '@/components/search/ResultCard'
import type { RelatedRuleItem, RelationReason } from '@/lib/api/types'

import { RelationReasonBadge } from './RelationReasonBadge'

export function RelatedRuleGroup({ reason, items }: { reason: RelationReason; items: RelatedRuleItem[] }) {
  return (
    <section className="space-y-3" data-testid={`related-group-${reason}`}>
      <div className="flex items-center gap-2">
        <h2 className="text-lg font-semibold text-slate-900">{items.length}</h2>
        <RelationReasonBadge reason={reason} />
      </div>
      <div className="space-y-4">
        {items.map((item) => (
          <ResultCard key={`${reason}-${item.card.doc_id}`} card={item.card} />
        ))}
      </div>
    </section>
  )
}
