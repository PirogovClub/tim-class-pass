import { ProvenanceSection } from '@/components/common/ProvenanceSection'
import { EntityHeader } from '@/components/detail/EntityHeader'
import { LinkedEntityList } from '@/components/detail/LinkedEntityList'
import { SupportBadges } from '@/components/detail/SupportBadges'
import { TimestampList } from '@/components/detail/TimestampList'
import { PageContainer } from '@/components/layout/PageContainer'
import { Skeleton } from '@/components/ui/skeleton'
import type { EventDetailResponse } from '@/lib/api/types'

export function EventDetailPage({ data, loading = false }: { data?: EventDetailResponse; loading?: boolean }) {
  if (loading || !data) {
    return (
      <PageContainer>
        <div className="space-y-4">
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-40 w-full" />
        </div>
      </PageContainer>
    )
  }

  return (
    <PageContainer>
      <div className="space-y-6">
        <div data-testid="event-doc-id" className="text-xs text-slate-500">
          Event <code className="rounded bg-slate-100 px-1">{data.doc_id}</code>
        </div>
        <EntityHeader
          title={data.title}
          unitType="knowledge_event"
          lessonId={data.lesson_id}
          conceptIds={data.canonical_concept_ids}
        />
        <SupportBadges supportBasis={data.support_basis} confidenceScore={data.confidence_score} />
        {data.event_type ? (
          <p className="text-sm text-slate-600">
            <span className="font-medium">Event type:</span> {data.event_type}
          </p>
        ) : null}
        <section className="rounded-xl border border-slate-200 bg-white p-5">
          <h2 className="text-lg font-semibold text-slate-900">Summary</h2>
          <p className="mt-2 text-sm text-slate-700 whitespace-pre-wrap">{data.snippet || '—'}</p>
        </section>
        <section className="rounded-xl border border-slate-200 bg-white p-5">
          <h2 className="text-lg font-semibold text-slate-900">Timestamps</h2>
          <div className="mt-3">
            <TimestampList timestamps={data.timestamps} />
          </div>
        </section>
        <LinkedEntityList title="Linked evidence" cards={data.linked_evidence} emptyLabel="No linked evidence." />
        <LinkedEntityList title="Linked rules" cards={data.linked_rules} emptyLabel="No linked rules." />
        <LinkedEntityList title="Related events" cards={data.linked_events} emptyLabel="No related events." />
        <ProvenanceSection provenance={data.provenance} />
      </div>
    </PageContainer>
  )
}
