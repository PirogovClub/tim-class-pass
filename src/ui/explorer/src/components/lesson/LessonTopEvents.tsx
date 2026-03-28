import { LinkedEntityList } from '@/components/detail/LinkedEntityList'
import type { BrowserResultCard } from '@/lib/api/types'

export function LessonTopEvents({ cards }: { cards: BrowserResultCard[] }) {
  return (
    <LinkedEntityList
      title="Knowledge events"
      cards={cards}
      emptyLabel="No events indexed for this lesson."
      testId="lesson-top-events"
    />
  )
}
