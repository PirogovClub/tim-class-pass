import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'

import { ErrorPanel } from '@/components/common/ErrorPanel'
import { PageContainer } from '@/components/layout/PageContainer'
import { DecisionPanel } from '@/components/review/DecisionPanel'
import { FamilyPanel } from '@/components/review/FamilyPanel'
import { HistoryPanel } from '@/components/review/HistoryPanel'
import { OptionalContextPanel } from '@/components/review/OptionalContextPanel'
import type { QueueFilter } from '@/lib/api/adjudication'
import { getNextQueueItem, getReviewBundle } from '@/lib/api/adjudication'
import type { ReviewBundleResponse } from '@/lib/api/adjudication-schemas'
import { ReviewTargetTypeSchema } from '@/lib/api/adjudication-schemas'
function parseQueueFilter(raw: string | null): QueueFilter {
  if (!raw || raw === 'all') {
    return 'all'
  }
  const p = ReviewTargetTypeSchema.safeParse(raw)
  return p.success ? p.data : 'all'
}

export function ReviewItemPage() {
  const { targetType: targetTypeParam, targetId: targetIdParam } = useParams()
  const [searchParams] = useSearchParams()
  const queueReason = searchParams.get('queueReason') ?? ''
  const navigate = useNavigate()
  const queueFilter = parseQueueFilter(searchParams.get('queueFilter'))

  const targetTypeRaw = targetTypeParam ? decodeURIComponent(targetTypeParam) : ''
  const targetId = targetIdParam ? decodeURIComponent(targetIdParam) : ''
  const typeParsed = ReviewTargetTypeSchema.safeParse(targetTypeRaw)
  const targetType = typeParsed.success ? typeParsed.data : null

  const [bundle, setBundle] = useState<ReviewBundleResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<unknown>(null)

  const load = useCallback(async () => {
    if (!targetType) {
      return
    }
    setLoading(true)
    setError(null)
    try {
      const b = await getReviewBundle(targetType, targetId)
      setBundle(b)
    } catch (e) {
      setError(e)
      setBundle(null)
    } finally {
      setLoading(false)
    }
  }, [targetType, targetId])

  useEffect(() => {
    if (!targetType) {
      setLoading(false)
      setError(new Error('Invalid target type in URL'))
      return
    }
    void load()
  }, [load, targetId, targetType])

  async function handleNext() {
    try {
      const next = await getNextQueueItem(queueFilter)
      if (!next) {
        setError(new Error('No next item in queue.'))
        return
      }
      void navigate(
        `/review/item/${encodeURIComponent(next.target_type)}/${encodeURIComponent(next.target_id)}?queueFilter=${encodeURIComponent(queueFilter)}&queueReason=${encodeURIComponent(next.queue_reason ?? '')}`,
        { replace: true },
      )
    } catch (e) {
      setError(e)
    }
  }

  const [compareOtherId, setCompareOtherId] = useState('')

  function goCompare() {
    if (!targetType || !compareOtherId.trim()) {
      return
    }
    const bType = targetType
    const bId = compareOtherId.trim()
    void navigate(
      `/review/compare?aType=${encodeURIComponent(targetType)}&aId=${encodeURIComponent(targetId)}&bType=${encodeURIComponent(bType)}&bId=${encodeURIComponent(bId)}`,
    )
  }

  if (!targetType) {
    return (
      <PageContainer>
        <ErrorPanel error={new Error('Invalid or missing target type.')} title="Bad link" />
      </PageContainer>
    )
  }

  return (
    <PageContainer>
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Review item</h1>
          <p className="mt-1 font-mono text-sm text-slate-600">
            {targetType} / {targetId}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link
            to={`/review/queue${queueFilter !== 'all' ? `?targetType=${encodeURIComponent(queueFilter)}` : ''}`}
            className="rounded border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-800 hover:bg-slate-50"
          >
            Back to queue
          </Link>
          <button
            type="button"
            className="rounded bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-800"
            onClick={() => {
              void handleNext()
            }}
          >
            Next in queue
          </button>
        </div>
      </div>

      {loading ? <p className="text-sm text-slate-600">Loading review bundle…</p> : null}
      {error && !loading ? <ErrorPanel error={error} title="Failed to load item" onRetry={() => void load()} /> : null}

      {bundle && !loading && !error ? (
        <div className="grid gap-6 lg:grid-cols-3">
          <div className="space-y-6 lg:col-span-2">
            <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
              <h2 className="text-sm font-semibold text-slate-800">Summary</h2>
              <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
                <div>
                  <dt className="text-slate-500">Title / summary</dt>
                  <dd className="text-slate-900">{bundle.target_summary ?? '—'}</dd>
                </div>
                <div>
                  <dt className="text-slate-500">Current status</dt>
                  <dd className="text-slate-900">{bundle.reviewed_state.current_status ?? '—'}</dd>
                </div>
                <div>
                  <dt className="text-slate-500">Latest decision</dt>
                  <dd className="text-slate-900">{bundle.reviewed_state.latest_decision_type ?? '—'}</dd>
                </div>
                <div>
                  <dt className="text-slate-500">Queue reason</dt>
                  <dd className="text-slate-900">{queueReason || '—'}</dd>
                </div>
              </dl>
            </section>

            <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
              <h2 className="text-sm font-semibold text-slate-800">Reviewed state</h2>
              <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
                <div>
                  <dt className="text-slate-500">Last reviewed</dt>
                  <dd className="text-slate-900">{bundle.reviewed_state.last_reviewed_at ?? '—'}</dd>
                </div>
                <div>
                  <dt className="text-slate-500">Last reviewer</dt>
                  <dd className="text-slate-900">{bundle.reviewed_state.last_reviewer_id ?? '—'}</dd>
                </div>
                <div>
                  <dt className="text-slate-500">Duplicate</dt>
                  <dd className="text-slate-900">
                    {bundle.reviewed_state.is_duplicate ? 'yes' : 'no'}
                    {bundle.reviewed_state.duplicate_of_rule_id
                      ? ` → ${bundle.reviewed_state.duplicate_of_rule_id}`
                      : ''}
                  </dd>
                </div>
                <div>
                  <dt className="text-slate-500">Family id</dt>
                  <dd className="break-all font-mono text-xs text-slate-900">
                    {bundle.reviewed_state.canonical_family_id ?? '—'}
                  </dd>
                </div>
              </dl>
            </section>

            <HistoryPanel history={bundle.history} />
            <FamilyPanel bundle={bundle} />
            <OptionalContextPanel bundle={bundle} />

            {targetType === 'rule_card' ? (
              <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
                <h2 className="text-sm font-semibold text-slate-800">Compare with another rule</h2>
                <p className="mt-1 text-xs text-slate-500">
                  Opens a side-by-side view for duplicate / merge decisions.
                </p>
                <div className="mt-3 flex flex-wrap gap-2">
                  <input
                    className="min-w-[12rem] flex-1 rounded border border-slate-300 px-2 py-1.5 font-mono text-sm"
                    placeholder="Other rule_card id"
                    value={compareOtherId}
                    onChange={(e) => setCompareOtherId(e.target.value)}
                  />
                  <button
                    type="button"
                    disabled={!compareOtherId.trim()}
                    className="rounded bg-slate-800 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
                    onClick={goCompare}
                  >
                    Open compare
                  </button>
                </div>
              </section>
            ) : null}
          </div>

          <div className="space-y-6">
            <DecisionPanel bundle={bundle} onSubmitted={load} />
          </div>
        </div>
      ) : null}
    </PageContainer>
  )
}
