import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'

import { ErrorPanel } from '@/components/common/ErrorPanel'
import { PageContainer } from '@/components/layout/PageContainer'
import type { QueueFilter, ReviewBackendQueue } from '@/lib/api/adjudication'
import {
  getNextQueueItem,
  getProposalQueue,
  getQueueByTarget,
  getUnresolvedQueue,
} from '@/lib/api/adjudication'
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

const BACKEND_QUEUE_OPTIONS: { value: ReviewBackendQueue; label: string }[] = [
  { value: 'unresolved', label: 'Unresolved (inventory)' },
  { value: 'high_confidence_duplicates', label: 'Proposals: high-confidence duplicates' },
  { value: 'merge_candidates', label: 'Proposals: merge candidates' },
  { value: 'canonical_family_candidates', label: 'Proposals: canonical family' },
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

function parseReviewBackendQueue(raw: string | null): ReviewBackendQueue {
  const allowed: ReviewBackendQueue[] = [
    'unresolved',
    'high_confidence_duplicates',
    'merge_candidates',
    'canonical_family_candidates',
  ]
  if (raw && (allowed as string[]).includes(raw)) {
    return raw as ReviewBackendQueue
  }
  return 'unresolved'
}

export function ReviewQueuePage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()
  const filter = useMemo(() => parseFilter(searchParams.get('targetType')), [searchParams])
  const tierFilter = useMemo(() => parseTierFilter(searchParams.get('qualityTier')), [searchParams])
  const reviewQueue = useMemo(
    () => parseReviewBackendQueue(searchParams.get('reviewQueue')),
    [searchParams],
  )

  const [items, setItems] = useState<QueueItemResponse[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)

  const isProposalQueue = reviewQueue !== 'unresolved'

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      if (reviewQueue === 'unresolved') {
        const res =
          filter === 'all' ? await getUnresolvedQueue() : await getQueueByTarget(filter)
        setItems(res.items)
        setTotal(res.total)
      } else {
        const res = await getProposalQueue(reviewQueue, {
          limit: 500,
          offset: 0,
          targetType: filter === 'all' ? undefined : filter,
          qualityTier: tierFilter === 'all' ? undefined : tierFilter,
        })
        setItems(res.items)
        setTotal(res.total)
      }
    } catch (e) {
      setError(toApiError(e))
    } finally {
      setLoading(false)
    }
  }, [filter, reviewQueue, tierFilter])

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

  function setReviewQueue(next: ReviewBackendQueue) {
    const p = new URLSearchParams(searchParams)
    if (next === 'unresolved') {
      p.delete('reviewQueue')
    } else {
      p.set('reviewQueue', next)
    }
    setSearchParams(p, { replace: true })
  }

  const displayedItems = useMemo(() => {
    if (isProposalQueue) {
      return items
    }
    if (tierFilter === 'all') {
      return items
    }
    return items.filter((row) => row.quality_tier === tierFilter)
  }, [items, tierFilter, isProposalQueue])

  async function handleNext() {
    try {
      const next = await getNextQueueItem(filter, reviewQueue, {
        qualityTier: tierFilter === 'all' ? undefined : tierFilter,
      })
      if (!next) {
        setError(new Error('No next item in queue for this filter.'))
        return
      }
      const tierQs = tierFilter !== 'all' ? `&qualityTier=${encodeURIComponent(tierFilter)}` : ''
      const rq =
        reviewQueue !== 'unresolved'
          ? `&reviewQueue=${encodeURIComponent(reviewQueue)}`
          : ''
      const pid = next.proposal_id ? `&proposalId=${encodeURIComponent(next.proposal_id)}` : ''
      void navigate(
        `/review/item/${encodeURIComponent(next.target_type)}/${encodeURIComponent(next.target_id)}?queueFilter=${encodeURIComponent(filter)}&queueReason=${encodeURIComponent(next.queue_reason ?? '')}${tierQs}${rq}${pid}`,
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
          {isProposalQueue
            ? 'Proposal-backed queues (Stage 5.5): deterministic suggestions only — submit normal decisions to change state.'
            : 'Unresolved items from the adjudication API (Stage 5.2 queue + Stage 5.4 tier column when materialized).'}
        </p>
      </div>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-2 text-sm text-slate-700">
          <span className="font-medium">Queue</span>
          <select
            className="rounded border border-slate-300 bg-white px-2 py-1.5 text-sm"
            value={reviewQueue}
            onChange={(e) => setReviewQueue(e.target.value as ReviewBackendQueue)}
          >
            {BACKEND_QUEUE_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </label>
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
          No rows match tier filter <strong>{tierFilter}</strong> ({items.length} before filter).
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
                {isProposalQueue ? <th className="px-3 py-2">Proposal</th> : null}
                <th className="px-3 py-2">Type</th>
                <th className="px-3 py-2">Tier</th>
                <th className="px-3 py-2">Target id</th>
                <th className="px-3 py-2">Queue reason</th>
                <th className="px-3 py-2">Summary / rationale</th>
                {isProposalQueue ? <th className="px-3 py-2">Score</th> : null}
                <th className="px-3 py-2">Status</th>
                <th className="px-3 py-2">Latest decision</th>
                <th className="px-3 py-2">Last reviewed</th>
                <th className="px-3 py-2">Family</th>
                <th className="px-3 py-2">Related</th>
                <th className="px-3 py-2" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {displayedItems.map((row) => {
                const rowKey = row.proposal_id
                  ? `p:${row.proposal_id}`
                  : `${row.target_type}:${row.target_id}`
                const rq =
                  reviewQueue !== 'unresolved'
                    ? `&reviewQueue=${encodeURIComponent(reviewQueue)}`
                    : ''
                const pid = row.proposal_id
                  ? `&proposalId=${encodeURIComponent(row.proposal_id)}`
                  : ''
                const rationale = row.proposal_rationale_summary ?? row.summary
                return (
                  <tr key={rowKey} className="hover:bg-slate-50/80">
                    {isProposalQueue ? (
                      <td className="px-3 py-2 font-mono text-xs text-slate-600">
                        {row.proposal_type ?? '—'}
                      </td>
                    ) : null}
                    <td className="px-3 py-2 font-mono text-xs">{row.target_type}</td>
                    <td className="px-3 py-2 text-xs text-slate-700">{row.quality_tier ?? '—'}</td>
                    <td
                      className="max-w-[14rem] truncate px-3 py-2 font-mono text-xs"
                      title={row.target_id}
                    >
                      {row.target_id}
                    </td>
                    <td className="px-3 py-2 text-slate-700">{row.queue_reason ?? '—'}</td>
                    <td
                      className="max-w-[14rem] truncate px-3 py-2 text-slate-600"
                      title={rationale ?? ''}
                    >
                      {rationale ?? '—'}
                    </td>
                    {isProposalQueue ? (
                      <td className="px-3 py-2 text-xs text-slate-700">
                        {row.proposal_score != null ? row.proposal_score.toFixed(3) : '—'}
                      </td>
                    ) : null}
                    <td className="px-3 py-2 text-slate-600">{row.current_status ?? '—'}</td>
                    <td className="px-3 py-2 text-slate-600">{row.latest_decision_type ?? '—'}</td>
                    <td className="whitespace-nowrap px-3 py-2 text-xs text-slate-500">
                      {row.last_reviewed_at ?? '—'}
                    </td>
                    <td
                      className="max-w-[8rem] truncate px-3 py-2 font-mono text-xs"
                      title={row.canonical_family_id ?? ''}
                    >
                      {row.canonical_family_id ?? '—'}
                    </td>
                    <td
                      className="max-w-[10rem] truncate px-3 py-2 font-mono text-xs text-slate-600"
                      title={row.related_target_id ?? ''}
                    >
                      {row.related_target_id ?? '—'}
                    </td>
                    <td className="px-3 py-2">
                      <Link
                        to={`/review/item/${encodeURIComponent(row.target_type)}/${encodeURIComponent(row.target_id)}?queueFilter=${encodeURIComponent(filter)}&queueReason=${encodeURIComponent(row.queue_reason ?? '')}${tierFilter !== 'all' ? `&qualityTier=${encodeURIComponent(tierFilter)}` : ''}${rq}${pid}`}
                        className="text-sm font-medium text-blue-700 hover:underline"
                      >
                        Open
                      </Link>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          <p className="border-t border-slate-100 px-3 py-2 text-xs text-slate-500">
            Showing {displayedItems.length} of {total} {isProposalQueue ? 'proposal queue' : 'unresolved'}{' '}
            rows
            {tierFilter !== 'all' ? ` (tier filter: ${tierFilter})` : ''}
          </p>
        </div>
      ) : null}
    </PageContainer>
  )
}
