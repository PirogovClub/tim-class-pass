import { ArrowLeft } from 'lucide-react'
import { Link, useLocation } from 'react-router-dom'

import { CopyLinkButton } from '@/components/common/CopyLinkButton'
import type { UnitType } from '@/lib/api/types'
import { Badge } from '@/components/ui/badge'
import { unitTypeBadgeColor, unitTypeLabel } from '@/lib/utils/badges'

interface EntityHeaderProps {
  title: string
  unitType: UnitType | 'lesson'
  lessonId?: string | null
  conceptIds?: string[]
}

export function EntityHeader({ title, unitType, lessonId, conceptIds = [] }: EntityHeaderProps) {
  const location = useLocation()
  const fromSearch = (location.state as { fromSearch?: string } | null)?.fromSearch ?? '/search'

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Link
          to={fromSearch}
          className="inline-flex items-center gap-2 text-sm font-medium text-slate-600 hover:text-slate-900"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to search
        </Link>
        <CopyLinkButton />
      </div>
      <div className="space-y-3">
        <div className="flex flex-wrap gap-2">
          <Badge className={unitTypeBadgeColor(unitType)}>{unitTypeLabel(unitType)}</Badge>
          {lessonId ? (
            <Link
              to={`/lesson/${encodeURIComponent(lessonId)}`}
              className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-medium text-slate-700 hover:border-teal-300 hover:text-teal-700"
            >
              {lessonId}
            </Link>
          ) : null}
        </div>
        <h1 className="text-2xl font-semibold text-slate-900">{title}</h1>
        {conceptIds.length ? (
          <div className="flex flex-wrap gap-2">
            {conceptIds.map((conceptId) => (
              <Link
                key={conceptId}
                to={`/concept/${encodeURIComponent(conceptId)}`}
                className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-medium text-slate-700 hover:border-teal-300 hover:text-teal-700"
              >
                {conceptId}
              </Link>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  )
}
