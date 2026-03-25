import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'

import { ErrorPanel } from '@/components/common/ErrorPanel'
import { PageContainer } from '@/components/layout/PageContainer'
import type { QueueFilter } from '@/lib/api/adjudication'
import { getNextQueueItem, getQueueByTarget, getUnresolvedQueue } from '@/lib/api/adjudication'
import type { QualityTier, QueueItemResponse } from '@/lib/api/adjudication-schemas'
import { QualityTierSchema, ReviewTargetTypeSchema } from '@/lib/api/adjudication-schemas'
import { toApiError } from '@/lib/api/errors'

const FILTER_OPTIONS: { value: QueueFilter; label: string }[] = [
  { value: 'all', label: 'All types' },
  { value: 'rule_card', label: 'Rule cards' },
  { value: 'evidence_link', label: 'Evidence links' },
  { value: 'concept_link', label: 'Concept links' },
  { value: 'related_rule_relation', label: 'Related rule relations' },
  { value: 'canonical_rule_family', label: 'Canonical families' },
]

function parseFilter(raw: string | null): QueueFilter {
  if (!raw) {
    return 'all'
  }
  const parsed = ReviewTargetTypeSchema.safeParse(raw)
  return parsed.success ? parsed.data : 'all'
}

type TierQueueFilter = 'all' | QualityTier

function parseTierFilter(raw: string | null): TierQueueFilter {
  if (!raw || raw === 'all') {
    return 'all'
  }
  const p = QualityTierSchema.safeParse(raw)
  return p.success ? p.data : 'all'
}

export function ReviewQueuePage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()
  const filter = useMemo(() => parseFilter(searchParams.get('targetType')), [searchParams])
  const tierFilter = useMemo(() => parseTierFilter(searchParams.get('qualityTier')), [searchParams])

  const [items, setItems] = useState<QueueItemResponse[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res =
        filter === 'all' ? await getUnresolvedQueue() : await getQueueByTarget(filter)
      setItems(res.items)
      setTotal(res.total)
    } catch (e) {
      setError(toApiError(e))
    } finally {
      setLoading(false)
    }
  }, [filter])

  useEffect(() => {
    void load()
  }, [load])

  function setFilter(next: QueueFilter) {
    const p = new URLSearchParams(searchParams)
    if (next === 'all') {
      p.delete('targetType')
    } else {
      p.set('targetType', next)
    }
    setSearchParams(p, { replace: true })
  }

  function setTierFilter(next: TierQueueFilter) {
    const p = new URLSearchParams(searchParams)
    if (next === 'all') {
      p.delete('qualityTier')
    } else {
      p.set('qualityTier', next)
    }
    setSearchParams(p, { replace: true })
  }

  const displayedItems = useMemo(() => {
    if (tierFilter === 'all') {
      return items
    }
    return items.filter((row) => row.quality_tier === tierFilter)
  }, [items, tierFilter])

  async function handleNext() {
    try {
      const next = await getNextQueueItem(filter)
      if (!next) {
        setError(new Error('No next item in queue for this filter.'))
        return
      }
      const tierQs = tierFilter !== 'all' ? `&qualityTier=${encodeURIComponent(tierFilter)}` : ''
      void navigate(
        `/review/item/${encodeURIComponent(next.target_type)}/${encodeURIComponent(next.target_id)}?queueFilter=${encodeURIComponent(filter)}&queueReason=${encodeURIComponent(next.queue_reason ?? '')}${tierQs}`,
      )
    } catch (e) {
      setError(toApiError(e))
    }
  }

  return (
    <PageContainer>
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-slate-900">Review queue</h1>
        <p className="mt-1 text-sm text-slate-600">
          Unresolved items from the adjudication API (Stage 5.2 queue + Stage 5.4 tier column when
          materialized).
        </p>
      </div>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-2 text-sm text-slate-700">
          <span className="font-medium">Target type</span>
          <select
            className="rounded border border-slate-300 bg-white px-2 py-1.5 text-sm"
            value={filter}
            onChange={(e) => setFilter(e.target.value as QueueFilter)}
          >
            {FILTER_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          className="rounded border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-800 hover:bg-slate-50"
          onClick={() => void load()}
          disabled={loading}
        >
          Refresh
        </button>
        <button
          type="button"
          className="rounded bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-800"
          onClick={() => {
            void handleNext()
          }}
        >
          Open next item
        </button>
        <label className="flex items-center gap-2 text-sm text-slate-700">
          <span className="font-medium">Quality tier</span>
          <select
            className="rounded border border-slate-300 bg-white px-2 py-1.5 text-sm"
            value={tierFilter}
            onChange={(e) => setTierFilter(e.target.value as TierQueueFilter)}
          >
            <option value="all">All tiers</option>
            <option value="unresolved">unresolved</option>
            <option value="bronze">bronze</option>
            <option value="silver">silver</option>
            <option value="gold">gold</option>
          </select>
        </label>
      </div>

      {error ? <ErrorPanel error={error} title="Queue error" onRetry={() => void load()} /> : null}

      {loading ? <p className="text-sm text-slate-600">Loading queue…</p> : null}

      {!loading && !error && displayedItems.length === 0 && items.length > 0 && tierFilter !== 'all' ? (
        <p className="rounded border border-dashed border-amber-200 bg-amber-50/50 p-4 text-sm text-slate-700">
          No rows match tier filter <strong>{tierFilter}</strong> ({items.length} unresolved before
          filter).
        </p>
      ) : null}

      {!loading && !error && total === 0 ? (
        <p className="rounded border border-dashed border-slate-200 bg-white p-6 text-center text-sm text-slate-600">
          Queue is empty for this filter.
        </p>
      ) : null}

      {!loading && total > 0 ? (
        <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white shadow-sm">
          <table className="min-w-full text-left text-sm">
            <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-3 py-2">Type</th>
                <th className="px-3 py-2">Tier</th>
                <th className="px-3 py-2">Target id</th>
                <th className="px-3 py-2">Queue reason</th>
                <th className="px-3 py-2">Summary</th>
                <th className="px-3 py-2">Status</th>
                <th className="px-3 py-2">Latest decision</th>
                <th className="px-3 py-2">Last reviewed</th>
                <th className="px-3 py-2">Family</th>
                <th className="px-3 py-2" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {displayedItems.map((row) => (
                <tr key={`${row.target_type}:${row.target_id}`} className="hover:bg-slate-50/80">
                  <td className="px-3 py-2 font-mono text-xs">{row.target_type}</td>
                  <td className="px-3 py-2 text-xs text-slate-700">{row.quality_tier ?? '—'}</td>
                  <td className="max-w-[14rem] truncate px-3 py-2 font-mono text-xs" title={row.target_id}>
                    {row.target_id}
                  </td>
                  <td className="px-3 py-2 text-slate-700">{row.queue_reason ?? '—'}</td>
                  <td className="max-w-[12rem] truncate px-3 py-2 text-slate-600" title={row.summary ?? ''}>
                    {row.summary ?? '—'}
                  </td>
                  <td className="px-3 py-2 text-slate-600">{row.current_status ?? '—'}</td>
                  <td className="px-3 py-2 text-slate-600">{row.latest_decision_type ?? '—'}</td>
                  <td className="whitespace-nowrap px-3 py-2 text-xs text-slate-500">
                    {row.last_reviewed_at ?? '—'}
                  </td>
                  <td className="max-w-[8rem] truncate px-3 py-2 font-mono text-xs" title={row.canonical_family_id ?? ''}>
                    {row.canonical_family_id ?? '—'}
                  </td>
                  <td className="px-3 py-2">
                    <Link
                      to={`/review/item/${encodeURIComponent(row.target_type)}/${encodeURIComponent(row.target_id)}?queueFilter=${encodeURIComponent(filter)}&queueReason=${encodeURIComponent(row.queue_reason ?? '')}${tierFilter !== 'all' ? `&qualityTier=${encodeURIComponent(tierFilter)}` : ''}`}
                      className="text-sm font-medium text-blue-700 hover:underline"
                    >
                      Open
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="border-t border-slate-100 px-3 py-2 text-xs text-slate-500">
            Showing {displayedItems.length} of {total} unresolved
            {tierFilter !== 'all' ? ` (tier filter: ${tierFilter})` : ''}
          </p>
        </div>
      ) : null}
    </PageContainer>
  )
}
