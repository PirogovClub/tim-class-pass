import { ResultList } from '@/components/search/ResultList'
import { Badge } from '@/components/ui/badge'
import type { BrowserResultCard } from '@/lib/api/types'

type ResultGroupProps = {
  title: string
  cards: BrowserResultCard[]
  groupIndex: number
}

export function ResultGroup({ title, cards, groupIndex }: ResultGroupProps) {
  const headingId = `search-group-${groupIndex}`
  return (
    <section className="space-y-3" aria-labelledby={headingId}>
      <div className="flex items-center gap-2">
        <h3 id={headingId} className="text-lg font-semibold text-slate-900">
          {title}
        </h3>
        <Badge className="border-slate-200 bg-white text-slate-600">{cards.length}</Badge>
      </div>
      <ResultList cards={cards} />
    </section>
  )
}
