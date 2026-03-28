import { Badge } from '@/components/ui/badge'
import type { RelationReason } from '@/lib/api/types'

const labels: Record<RelationReason, string> = {
  same_concept: 'Same concept',
  same_family: 'Same family',
  same_lesson: 'Same lesson',
  linked_by_evidence: 'Linked by evidence',
  cross_lesson_overlap: 'Cross-lesson overlap',
}

export function RelationReasonBadge({ reason }: { reason: RelationReason }) {
  return <Badge className="border-slate-200 bg-slate-50 text-slate-700">{labels[reason]}</Badge>
}
