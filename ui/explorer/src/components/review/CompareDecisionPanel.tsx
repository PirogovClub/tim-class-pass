import { useEffect, useState } from 'react'

import { postDecision } from '@/lib/api/adjudication'
import type { ReviewBundleResponse } from '@/lib/api/adjudication-schemas'
import { isApiError } from '@/lib/api/errors'
import type { ComparePrimarySide } from '@/lib/review/compareDecisionPrefill'
import { prefillCompareRelatedTarget } from '@/lib/review/compareDecisionPrefill'
import {
  decisionRequiresRelatedTarget,
  getStoredReviewerId,
  setStoredReviewerId,
} from '@/lib/review/decisions'

const COMPARE_DECISIONS = ['duplicate_of', 'merge_into'] as const
type CompareDecisionType = (typeof COMPARE_DECISIONS)[number]

export type { ComparePrimarySide }

type Props = {
  left: ReviewBundleResponse
  right: ReviewBundleResponse
  onRefetch: () => Promise<void>
}

/**
 * Minimal adjudication from compare: duplicate_of / merge_into for two rule_card bundles.
 * Primary side = target of POST /adjudication/decision; related id is prefilled from the opposite side.
 */
export function CompareDecisionPanel({ left, right, onRefetch }: Props) {
  const [primary, setPrimary] = useState<ComparePrimarySide>('left')
  const [decisionType, setDecisionType] = useState<CompareDecisionType>('duplicate_of')
  const [relatedTargetId, setRelatedTargetId] = useState('')
  const [note, setNote] = useState('')
  const [reasonCode, setReasonCode] = useState('')
  const [reviewerId, setReviewerId] = useState(getStoredReviewerId)
  const [submitting, setSubmitting] = useState(false)
  const [message, setMessage] = useState<{ kind: 'ok' | 'err'; text: string } | null>(null)

  const source = primary === 'left' ? left : right

  useEffect(() => {
    setRelatedTargetId(
      prefillCompareRelatedTarget({ decisionType, primary, left, right }),
    )
  }, [decisionType, primary, left, right])

  const needRelated = decisionRequiresRelatedTarget(decisionType)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setMessage(null)
    setSubmitting(true)
    setStoredReviewerId(reviewerId)
    try {
      await postDecision({
        target_type: 'rule_card',
        target_id: source.target_id,
        decision_type: decisionType,
        reviewer_id: reviewerId.trim(),
        note: note.trim() || null,
        reason_code: reasonCode.trim() || null,
        related_target_id: needRelated ? relatedTargetId.trim() || null : null,
      })
      setMessage({ kind: 'ok', text: 'Decision recorded. Refreshing bundles…' })
      await onRefetch()
      setMessage({ kind: 'ok', text: 'Decision recorded. Bundles updated below.' })
    } catch (err) {
      const text = isApiError(err) ? err.message : 'Submit failed'
      setMessage({ kind: 'err', text })
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <section
      data-testid="compare-decision-panel"
      className="mt-8 rounded-lg border border-amber-200 bg-amber-50/40 p-4 shadow-sm"
    >
      <h2 className="text-sm font-semibold text-slate-900">Decide from compare</h2>
      <p className="mt-1 text-xs text-slate-600">
        Submit <code className="rounded bg-amber-100/80 px-1">duplicate_of</code> or{' '}
        <code className="rounded bg-amber-100/80 px-1">merge_into</code> for one rule without leaving
        this page. <strong>Primary</strong> is the rule card that receives the decision; the related id
        is prefilled from the other column (rule id for duplicate, family id for merge when known).
      </p>
      <form className="mt-4 space-y-3" onSubmit={(e) => void handleSubmit(e)}>
        <fieldset className="space-y-2">
          <legend className="text-xs font-medium text-slate-600">Primary (decision target)</legend>
          <div className="flex flex-wrap gap-4 text-sm">
            <label className="flex cursor-pointer items-center gap-2">
              <input
                type="radio"
                name="compare-primary"
                checked={primary === 'left'}
                onChange={() => setPrimary('left')}
              />
              <span>
                Left (A){' '}
                <span className="font-mono text-xs text-slate-500">{left.target_id}</span>
              </span>
            </label>
            <label className="flex cursor-pointer items-center gap-2">
              <input
                type="radio"
                name="compare-primary"
                checked={primary === 'right'}
                onChange={() => setPrimary('right')}
              />
              <span>
                Right (B){' '}
                <span className="font-mono text-xs text-slate-500">{right.target_id}</span>
              </span>
            </label>
          </div>
        </fieldset>
        <label className="block text-xs font-medium text-slate-600">
          Reviewer id
          <input
            className="mt-1 w-full rounded border border-slate-300 bg-white px-2 py-1.5 text-sm"
            value={reviewerId}
            onChange={(e) => setReviewerId(e.target.value)}
            required
            autoComplete="off"
          />
        </label>
        <label className="block text-xs font-medium text-slate-600">
          Decision
          <select
            data-testid="compare-decision-type"
            className="mt-1 w-full rounded border border-slate-300 bg-white px-2 py-1.5 text-sm"
            value={decisionType}
            onChange={(e) => setDecisionType(e.target.value as CompareDecisionType)}
          >
            {COMPARE_DECISIONS.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
        </label>
        {needRelated ? (
          <label className="block text-xs font-medium text-slate-600">
            Related target id
            <input
              data-testid="compare-related-target-id"
              className="mt-1 w-full rounded border border-slate-300 bg-white px-2 py-1.5 font-mono text-sm"
              value={relatedTargetId}
              onChange={(e) => setRelatedTargetId(e.target.value)}
              placeholder={
                decisionType === 'merge_into'
                  ? 'family_id (prefilled when available)'
                  : 'other rule_card id'
              }
            />
          </label>
        ) : null}
        <label className="block text-xs font-medium text-slate-600">
          Note (optional)
          <textarea
            className="mt-1 w-full rounded border border-slate-300 bg-white px-2 py-1.5 text-sm"
            rows={2}
            value={note}
            onChange={(e) => setNote(e.target.value)}
          />
        </label>
        <label className="block text-xs font-medium text-slate-600">
          Reason code (optional)
          <input
            className="mt-1 w-full rounded border border-slate-300 bg-white px-2 py-1.5 text-sm"
            value={reasonCode}
            onChange={(e) => setReasonCode(e.target.value)}
          />
        </label>
        <button
          type="submit"
          data-testid="compare-submit-decision"
          disabled={submitting || (needRelated && !relatedTargetId.trim())}
          className="rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          {submitting ? 'Submitting…' : 'Submit decision from compare'}
        </button>
      </form>
      {message ? (
        <p
          className={`mt-3 text-sm ${message.kind === 'ok' ? 'text-emerald-700' : 'text-red-700'}`}
          role="status"
        >
          {message.text}
        </p>
      ) : null}
    </section>
  )
}
