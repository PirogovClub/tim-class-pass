import { useState } from 'react'

import { postDecision } from '@/lib/api/adjudication'
import type { ReviewBundleResponse } from '@/lib/api/adjudication-schemas'
import { isApiError } from '@/lib/api/errors'
import {
  decisionRequiresRelatedTarget,
  decisionsForTarget,
  getStoredReviewerId,
  setStoredReviewerId,
} from '@/lib/review/decisions'

type Props = {
  bundle: ReviewBundleResponse
  onSubmitted: () => Promise<void>
  /** When set, included on decision POST for Stage 5.5 proposal linkage */
  proposalId?: string | null
}

export function DecisionPanel({ bundle, onSubmitted, proposalId = null }: Props) {
  const targetType = bundle.target_type
  const options = decisionsForTarget(targetType)
  const [decisionType, setDecisionType] = useState(options[0] ?? '')
  const [note, setNote] = useState('')
  const [reasonCode, setReasonCode] = useState('')
  const [relatedTargetId, setRelatedTargetId] = useState('')
  const [reviewerId, setReviewerId] = useState(getStoredReviewerId)
  const [submitting, setSubmitting] = useState(false)
  const [message, setMessage] = useState<{ kind: 'ok' | 'err'; text: string } | null>(null)

  const needRelated = decisionRequiresRelatedTarget(decisionType)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setMessage(null)
    setSubmitting(true)
    setStoredReviewerId(reviewerId)
    try {
      await postDecision({
        target_type: targetType,
        target_id: bundle.target_id,
        decision_type: decisionType,
        reviewer_id: reviewerId.trim(),
        note: note.trim() || null,
        reason_code: reasonCode.trim() || null,
        related_target_id: needRelated ? relatedTargetId.trim() || null : null,
        proposal_id: proposalId?.trim() ? proposalId.trim() : null,
      })
      setMessage({ kind: 'ok', text: 'Decision recorded.' })
      await onSubmitted()
    } catch (err) {
      const text = isApiError(err) ? err.message : 'Submit failed'
      setMessage({ kind: 'err', text })
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <section className="rounded-lg border border-amber-200 bg-amber-50/40 p-4 shadow-sm">
      <h2 className="text-sm font-semibold text-slate-900">Submit decision</h2>
      <form className="mt-3 space-y-3" onSubmit={handleSubmit}>
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
            className="mt-1 w-full rounded border border-slate-300 bg-white px-2 py-1.5 text-sm"
            value={decisionType}
            onChange={(e) => setDecisionType(e.target.value)}
          >
            {options.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
        </label>
        {needRelated ? (
          <label className="block text-xs font-medium text-slate-600">
            Related target id (required for duplicate / merge)
            <input
              className="mt-1 w-full rounded border border-slate-300 bg-white px-2 py-1.5 font-mono text-sm"
              value={relatedTargetId}
              onChange={(e) => setRelatedTargetId(e.target.value)}
              placeholder={
                decisionType === 'merge_into' ? 'family_id' : 'other rule_card id'
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
          disabled={submitting || (needRelated && !relatedTargetId.trim())}
          className="rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          {submitting ? 'Submitting…' : 'Submit decision'}
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
