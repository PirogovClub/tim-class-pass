import { useCallback, useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { ErrorPanel } from '@/components/common/ErrorPanel'
import { PageContainer } from '@/components/layout/PageContainer'
import { CompareDecisionPanel } from '@/components/review/CompareDecisionPanel'
import { FamilyPanel } from '@/components/review/FamilyPanel'
import { HistoryPanel } from '@/components/review/HistoryPanel'
import { OptionalContextPanel } from '@/components/review/OptionalContextPanel'
import { getReviewBundle } from '@/lib/api/adjudication'
import type { ReviewBundleResponse, ReviewTargetType } from '@/lib/api/adjudication-schemas'
import { ReviewTargetTypeSchema } from '@/lib/api/adjudication-schemas'
import { canCompareAdjudicateRulePair } from '@/lib/review/compareDecisionPrefill'

function BundleColumn({
  label,
  bundle,
  error,
  loading,
}: {
  label: string
  bundle: ReviewBundleResponse | null
  error: unknown
  loading: boolean
}) {
  if (loading) {
    return (
      <div className="rounded-lg border border-slate-200 bg-white p-4">
        <p className="text-sm text-slate-600">Loading {label}…</p>
      </div>
    )
  }
  if (error) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-4">
        <ErrorPanel error={error} title={`${label} failed`} />
      </div>
    )
  }
  if (!bundle) {
    return null
  }

  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <h2 className="text-sm font-semibold text-slate-800">{label}</h2>
        <p className="mt-1 font-mono text-xs text-slate-600">
          {bundle.target_type} / {bundle.target_id}
        </p>
        <p className="mt-2 text-sm text-slate-900">{bundle.target_summary ?? '—'}</p>
        <dl className="mt-3 grid gap-1 text-xs text-slate-600">
          <div>Status: {bundle.reviewed_state.current_status ?? '—'}</div>
          <div>Latest: {bundle.reviewed_state.latest_decision_type ?? '—'}</div>
        </dl>
        <Link
          to={`/review/item/${encodeURIComponent(bundle.target_type)}/${encodeURIComponent(bundle.target_id)}`}
          className="mt-3 inline-block text-sm font-medium text-blue-700 hover:underline"
        >
          Open full review
        </Link>
      </div>
      <HistoryPanel history={bundle.history} />
      <FamilyPanel bundle={bundle} />
      <OptionalContextPanel bundle={bundle} />
    </div>
  )
}

function CompareFetch({
  aType,
  aId,
  bType,
  bId,
}: {
  aType: ReviewTargetType
  aId: string
  bType: ReviewTargetType
  bId: string
}) {
  const [left, setLeft] = useState<ReviewBundleResponse | null>(null)
  const [right, setRight] = useState<ReviewBundleResponse | null>(null)
  const [errLeft, setErrLeft] = useState<unknown>(null)
  const [errRight, setErrRight] = useState<unknown>(null)
  const [loading, setLoading] = useState(true)

  const refetchBoth = useCallback(async () => {
    const [l, r] = await Promise.all([
      getReviewBundle(aType, aId),
      getReviewBundle(bType, bId),
    ])
    setLeft(l)
    setRight(r)
    setErrLeft(null)
    setErrRight(null)
  }, [aType, aId, bType, bId])

  useEffect(() => {
    let cancelled = false

    async function run() {
      setLoading(true)
      setErrLeft(null)
      setErrRight(null)
      try {
        const l = await getReviewBundle(aType, aId)
        if (!cancelled) {
          setLeft(l)
        }
      } catch (e) {
        if (!cancelled) {
          setErrLeft(e)
          setLeft(null)
        }
      }
      try {
        const r = await getReviewBundle(bType, bId)
        if (!cancelled) {
          setRight(r)
        }
      } catch (e) {
        if (!cancelled) {
          setErrRight(e)
          setRight(null)
        }
      }
      if (!cancelled) {
        setLoading(false)
      }
    }

    void run()
    return () => {
      cancelled = true
    }
  }, [aType, aId, bType, bId])

  const showCompareDecision =
    !loading &&
    canCompareAdjudicateRulePair(left, right) &&
    !errLeft &&
    !errRight

  return (
    <div>
      <div className="grid gap-6 lg:grid-cols-2">
        <BundleColumn label="Left (A)" bundle={left} error={errLeft} loading={loading} />
        <BundleColumn label="Right (B)" bundle={right} error={errRight} loading={loading} />
      </div>
      {showCompareDecision && left && right ? (
        <CompareDecisionPanel left={left} right={right} onRefetch={refetchBoth} />
      ) : null}
    </div>
  )
}

export function ReviewComparePage() {
  const [searchParams] = useSearchParams()
  const aTypeRaw = searchParams.get('aType') ?? ''
  const aId = searchParams.get('aId') ?? ''
  const bTypeRaw = searchParams.get('bType') ?? ''
  const bId = searchParams.get('bId') ?? ''

  const pa = ReviewTargetTypeSchema.safeParse(aTypeRaw)
  const pb = ReviewTargetTypeSchema.safeParse(bTypeRaw)
  const badParams = !pa.success || !pb.success || !aId || !bId

  const compareKey = `${aTypeRaw}|${aId}|${bTypeRaw}|${bId}`

  return (
    <PageContainer>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Compare</h1>
          <p className="mt-1 text-sm text-slate-600">Side-by-side review bundles for duplicate / merge workflows.</p>
        </div>
        <Link
          to="/review/queue"
          className="rounded border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-800 hover:bg-slate-50"
        >
          Back to queue
        </Link>
      </div>

      {badParams ? (
        <ErrorPanel
          error={new Error('Need query params aType, aId, bType, bId (valid target types).')}
          title="Invalid compare link"
        />
      ) : (
        <CompareFetch key={compareKey} aType={pa.data} aId={aId} bType={pb.data} bId={bId} />
      )}
    </PageContainer>
  )
}
