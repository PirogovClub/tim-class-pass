import { Link, useLocation } from 'react-router-dom'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { CardContent, CardHeader } from '@/components/ui/card'
import { useCompareSelection } from '@/hooks/useCompareSelection'
import { useMultiUnitCompare } from '@/hooks/useMultiUnitCompare'
import type { BrowserResultCard, UnitType } from '@/lib/api/types'
import { supportBasisLabel, unitTypeBadgeColor, unitTypeLabel } from '@/lib/utils/badges'
import { entityRoute } from '@/lib/utils/entity'
import { formatConfidence, formatTimestampLabel, truncateText } from '@/lib/utils/format'

const MULTI_COMPARE_TYPES: readonly UnitType[] = [
  'rule_card',
  'knowledge_event',
  'evidence_ref',
  'concept_node',
  'concept_relation',
]

export function ResultCard({ card }: { card: BrowserResultCard }) {
  const location = useLocation()
  const compareSelection = useCompareSelection('rules')
  const multiCompare = useMultiUnitCompare()
  const route = entityRoute(card)
  const confidence = formatConfidence(card.confidence_score)
  const supportBasis = supportBasisLabel(card.support_basis)
  const canCompare = card.unit_type === 'rule_card'
  const isSelected = canCompare ? compareSelection.has(card.doc_id) : false
  const canMultiCompare = MULTI_COMPARE_TYPES.includes(card.unit_type)
  const isMultiSelected = canMultiCompare ? multiCompare.has(card.unit_type, card.doc_id) : false

  return (
    <article className="rounded-xl border border-slate-200 bg-white shadow-sm">
      <CardHeader className="space-y-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="space-y-2">
            <Link
              to={route}
              state={{ fromSearch: `${location.pathname}${location.search}` }}
              className="text-lg font-semibold text-slate-900 hover:text-teal-700 hover:underline"
            >
              {card.title}
            </Link>
            <div className="flex flex-wrap gap-2">
              <Badge data-testid="unit-type-badge" className={unitTypeBadgeColor(card.unit_type)}>
                {unitTypeLabel(card.unit_type)}
              </Badge>
              {card.lesson_id ? (
                <Badge className="border-slate-200 bg-slate-50 text-slate-600">{card.lesson_id}</Badge>
              ) : null}
              {confidence ? <Badge className="border-slate-200 bg-slate-50 text-slate-600">{confidence}</Badge> : null}
            </div>
          </div>
          {card.subtitle ? <p className="text-sm text-slate-500">{card.subtitle}</p> : null}
        </div>
      </CardHeader>

      <CardContent className="space-y-3 text-sm text-slate-600">
        <p className="line-clamp-3">{truncateText(card.snippet || '')}</p>
        <div className="flex flex-wrap gap-2">
          {supportBasis ? <Badge className="border-slate-200 bg-white text-slate-600">{supportBasis}</Badge> : null}
          {card.evidence_requirement ? (
            <Badge className="border-slate-200 bg-white text-slate-600">Evidence: {card.evidence_requirement}</Badge>
          ) : null}
          {card.teaching_mode ? (
            <Badge className="border-slate-200 bg-white text-slate-600">Mode: {card.teaching_mode}</Badge>
          ) : null}
        </div>
        {card.timestamps.length ? (
          <div className="flex flex-wrap gap-2 text-xs text-slate-500">
            {card.timestamps.map((timestamp, index) => {
              const label = formatTimestampLabel(timestamp)
              return (
                <span key={`${label}-${index}`} className="rounded-full bg-slate-100 px-2 py-1">
                  {label}
                </span>
              )
            })}
          </div>
        ) : null}
        <div className="flex flex-wrap gap-2 text-xs text-slate-500">
          {card.score != null ? (
            <span className="rounded-full bg-teal-50 px-2 py-1 font-medium text-teal-900" data-testid="hit-score">
              Score {typeof card.score === 'number' ? card.score.toFixed(4) : card.score}
            </span>
          ) : null}
          <span className="rounded-full bg-slate-100 px-2 py-1">Evidence {card.evidence_count}</span>
          <span className="rounded-full bg-slate-100 px-2 py-1">Rules {card.related_rule_count}</span>
          <span className="rounded-full bg-slate-100 px-2 py-1">Events {card.related_event_count}</span>
        </div>
        {card.why_retrieved.length ? (
          <details className="text-xs text-slate-600">
            <summary className="cursor-pointer font-medium text-slate-700">Why retrieved</summary>
            <ul className="mt-1 list-inside list-disc">
              {card.why_retrieved.map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
          </details>
        ) : null}
        {canCompare ? (
          <div>
            <Button
              type="button"
              size="sm"
              variant={isSelected ? 'secondary' : 'outline'}
              onClick={() => compareSelection.toggle(card.doc_id)}
              disabled={!isSelected && compareSelection.isFull}
            >
              {isSelected ? 'Remove from rule compare' : 'Add to rule compare'}
            </Button>
          </div>
        ) : null}
        {canMultiCompare ? (
          <div>
            <Button
              type="button"
              size="sm"
              variant={isMultiSelected ? 'secondary' : 'outline'}
              onClick={() => multiCompare.toggle(card.unit_type, card.doc_id)}
              disabled={!isMultiSelected && multiCompare.isFull}
              data-testid="multi-compare-toggle"
            >
              {isMultiSelected ? 'Remove from unit compare' : 'Add to unit compare'}
            </Button>
          </div>
        ) : null}
      </CardContent>
    </article>
  )
}
