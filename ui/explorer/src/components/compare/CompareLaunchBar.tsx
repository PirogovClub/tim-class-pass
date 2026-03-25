import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import type { CompareKind } from '@/lib/url/compare-params'
import { serializeCompareIds } from '@/lib/url/compare-params'

function compareHref(kind: CompareKind, ids: string[]) {
  const params = serializeCompareIds(ids)
  const suffix = params.toString()
  return `/compare/${kind}${suffix ? `?${suffix}` : ''}`
}

export function CompareLaunchBar({
  kind,
  ids,
  onClear,
}: {
  kind: CompareKind
  ids: string[]
  onClear: () => void
}) {
  if (ids.length < 2) {return null}

  const label = kind === 'rules' ? 'rules' : 'lessons'

  return (
    <div className="border-b border-slate-200 bg-teal-50">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-6 lg:px-8">
        <div className="flex flex-wrap items-center gap-2 text-sm text-slate-700">
          <span className="font-medium">{ids.length} {label} selected</span>
          {ids.map((id) => (
            <span key={id} className="rounded-full bg-white px-3 py-1 text-xs text-slate-600">
              {id}
            </span>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <Button type="button" variant="ghost" size="sm" onClick={onClear}>
            Clear
          </Button>
          <Link to={compareHref(kind, ids)}>
            <Button type="button" size="sm">
              Open compare
            </Button>
          </Link>
        </div>
      </div>
    </div>
  )
}
