import { Link, useLocation } from 'react-router-dom'
import type { BrowserResultCard } from '@/lib/api/types'
import { Badge } from '@/components/ui/badge'
import { CardContent, CardHeader } from '@/components/ui/card'
import { supportBasisLabel, unitTypeBadgeColor, unitTypeLabel } from '@/lib/utils/badges'
import { entityRoute } from '@/lib/utils/entity'
import { formatConfidence, formatTimestampLabel, truncateText } from '@/lib/utils/format'

export function ResultCard({ card }: { card: BrowserResultCard }) {
  const location = useLocation()
  const route = entityRoute(card)
  const confidence = formatConfidence(card.confidence_score)
  return <article className="rounded-xl border border-slate-200 bg-white shadow-sm"><CardHeader className="space-y-3"><div className="flex flex-wrap items-start justify-between gap-3"><div className="space-y-2"><Link to={route} state={{ fromSearch: `${location.pathname}${location.search}` }} className="text-lg font-semibold text-slate-900 hover:text-teal-700 hover:underline">{card.title}</Link><div className="flex flex-wrap gap-2"><Badge data-testid="unit-type-badge" className={unitTypeBadgeColor(card.unit_type)}>{unitTypeLabel(card.unit_type)}</Badge>{card.lesson_id ? <Badge className="border-slate-200 bg-slate-50 text-slate-600">{card.lesson_id}</Badge> : null}{confidence ? <Badge className="border-slate-200 bg-slate-50 text-slate-600">{confidence}</Badge> : null}</div></div>{card.subtitle ? <p className="text-sm text-slate-500">{card.subtitle}</p> : null}</div></CardHeader><CardContent className="space-y-3 text-sm text-slate-600"><p className="line-clamp-3">{truncateText(card.snippet || '')}</p><div className="flex flex-wrap gap-2">{supportBasisLabel(card.support_basis) ? <Badge className="border-slate-200 bg-white text-slate-600">{supportBasisLabel(card.support_basis)}</Badge> : null}{card.evidence_requirement ? <Badge className="border-slate-200 bg-white text-slate-600">Evidence: {card.evidence_requirement}</Badge> : null}{card.teaching_mode ? <Badge className="border-slate-200 bg-white text-slate-600">Mode: {card.teaching_mode}</Badge> : null}</div>{card.timestamps.length ? <div className="flex flex-wrap gap-2 text-xs text-slate-500">{card.timestamps.map((timestamp, index) => <span key={`${timestamp.start}-${timestamp.end}-${index}`} className="rounded-full bg-slate-100 px-2 py-1">{formatTimestampLabel(timestamp)}</span>)}</div> : null}<div className="flex flex-wrap gap-2 text-xs text-slate-500"><span className="rounded-full bg-slate-100 px-2 py-1">Evidence {card.evidence_count}</span><span className="rounded-full bg-slate-100 px-2 py-1">Rules {card.related_rule_count}</span><span className="rounded-full bg-slate-100 px-2 py-1">Events {card.related_event_count}</span></div></CardContent></article>
}
