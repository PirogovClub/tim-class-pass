import type { BrowserResultCard } from '@/lib/api/types'

import { ResultCard } from '@/components/search/ResultCard'

type ResultListProps = {
  cards: BrowserResultCard[]
}

export function ResultList({ cards }: ResultListProps) {
  return (
    <ul className="flex flex-col gap-4" aria-live="polite">
      {cards.map((card, i) => (
        <li key={`${card.doc_id}-${i}`}>
          <ResultCard card={card} />
        </li>
      ))}
    </ul>
  )
}
