import { useQuery } from '@tanstack/react-query'
import { useMemo } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { CopyLinkButton } from '@/components/common/CopyLinkButton'
import { ErrorPanel } from '@/components/common/ErrorPanel'
import { PageContainer } from '@/components/layout/PageContainer'
import { Button } from '@/components/ui/button'
import { TimestampList } from '@/components/detail/TimestampList'
import { serializeCompareUnitsParam, useMultiUnitCompare } from '@/hooks/useMultiUnitCompare'
import { postCompareUnits } from '@/lib/api/browser'
import type { UnitCompareRow } from '@/lib/api/types'
import { unitTypeLabel } from '@/lib/utils/badges'

function CompareColumn({ row }: { row: UnitCompareRow }) {
  return (
    <div
      className="flex min-w-[220px] max-w-md flex-1 flex-col gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm"
      data-testid={`compare-column-${row.doc_id}`}
    >
      <div className="text-xs font-medium text-slate-500">{unitTypeLabel(row.unit_type)}</div>
      <div className="text-sm font-semibold text-slate-900">{row.title}</div>
      <p className="text-xs text-slate-500">
        <span className="font-medium">ID</span>{' '}
        <code className="rounded bg-slate-100 px-1 break-all">{row.doc_id}</code>
      </p>
      <p className="text-xs text-slate-600">
        <span className="font-medium">Lesson</span> {row.lesson_id || '—'}
      </p>
      <div className="text-xs text-slate-700">
        <span className="font-medium">Summary</span>
        <p className="mt-1 whitespace-pre-wrap">{row.summary || '—'}</p>
      </div>
      {row.event_type ? (
        <p className="text-xs text-slate-600">
          <span className="font-medium">Event type</span> {row.event_type}
        </p>
      ) : null}
      {row.canonical_concept_ids.length ? (
        <p className="text-xs text-slate-600">
          <span className="font-medium">Concepts</span> {row.canonical_concept_ids.join(', ')}
        </p>
      ) : null}
      {row.evidence_ids.length ? (
        <p className="text-xs text-slate-600">
          <span className="font-medium">Evidence IDs</span> {row.evidence_ids.join(', ')}
        </p>
      ) : null}
      <div>
        <h3 className="text-xs font-semibold text-slate-800">Timestamps</h3>
        <div className="mt-1">
          <TimestampList timestamps={row.timestamps} />
        </div>
      </div>
      {Object.keys(row.provenance).length ? (
        <details className="text-xs">
          <summary className="cursor-pointer font-medium text-slate-700">Provenance</summary>
          <pre className="mt-2 max-h-40 overflow-auto rounded bg-slate-50 p-2 text-[10px] whitespace-pre-wrap">
            {JSON.stringify(row.provenance, null, 2)}
          </pre>
        </details>
      ) : null}
    </div>
  )
}

export function CompareUnitsPage() {
  const [searchParams] = useSearchParams()
  const multi = useMultiUnitCompare(searchParams.get('units'))

  const shareCompareHref = useMemo(() => {
    if (multi.refs.length < 2 || typeof window === 'undefined') {
      return ''
    }
    const q = encodeURIComponent(serializeCompareUnitsParam(multi.refs))
    return `${window.location.origin}/compare/units?units=${q}`
  }, [multi.refs])

  const q = useQuery({
    queryKey: ['browser-compare-units', multi.refs] as const,
    queryFn: () => postCompareUnits({ items: multi.refs }),
    enabled: multi.refs.length >= 2,
  })

  return (
    <PageContainer>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">Compare retrieval units</h1>
          <p className="mt-1 text-sm text-slate-600">
            Stage 6.4 side-by-side view for 2–4 items (rules, events, evidence, concepts).
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link
            to="/search"
            className="inline-flex h-9 items-center justify-center rounded-md border border-slate-300 bg-white px-4 text-sm font-medium text-slate-900 hover:bg-slate-50"
          >
            Back to search
          </Link>
          {shareCompareHref ? (
            <CopyLinkButton href={shareCompareHref} label="Copy compare link" />
          ) : null}
          <Button type="button" variant="ghost" onClick={() => multi.clear()}>
            Clear selection
          </Button>
        </div>
      </div>

      {multi.refs.length < 2 ? (
        <p className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900" data-testid="compare-units-empty">
          Select at least two items from search results (or detail pages where available), open a shared{' '}
          <code className="rounded bg-amber-100 px-1">/compare/units?units=…</code> link, or return here after
          choosing items.
        </p>
      ) : null}

      {q.isLoading ? <p className="text-sm text-slate-600">Loading comparison…</p> : null}
      {q.isError ? <ErrorPanel error={q.error} onRetry={() => void q.refetch()} /> : null}
      {q.isSuccess && q.data ? (
        <div
          className="flex flex-col gap-6 lg:flex-row lg:items-start lg:overflow-x-auto"
          data-testid="compare-units-grid"
        >
          {q.data.items.map((row) => (
            <CompareColumn key={`${row.unit_type}:${row.doc_id}`} row={row} />
          ))}
        </div>
      ) : null}
    </PageContainer>
  )
}
