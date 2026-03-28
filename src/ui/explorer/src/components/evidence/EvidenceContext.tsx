import { VisualSummarySection } from '@/components/common/VisualSummarySection'

type EvidenceContextProps = {
  snippet: string
  visualSummary?: string | null
  lessonId: string
  frameIds: string[]
}

export function EvidenceContext({ snippet, visualSummary, lessonId, frameIds }: EvidenceContextProps) {
  return (
    <div className="space-y-4">
      <section>
        <h2 className="text-lg font-semibold text-slate-900">Snippet</h2>
        <p data-testid="evidence-snippet" className="mt-2 text-sm text-slate-700">
          {snippet}
        </p>
      </section>
      {visualSummary ? (
        <VisualSummarySection visualSummary={visualSummary} lessonId={lessonId} frameIds={frameIds} />
      ) : null}
    </div>
  )
}
