import {
  DecisionSubmissionResponseSchema,
  QueueListResponseSchema,
  QueueNextResponseSchema,
  ReviewBundleResponseSchema,
  type ReviewTargetType,
} from '@/lib/api/adjudication-schemas'
import { apiGet, apiPost } from '@/lib/api/client'

function enc(s: string): string {
  return encodeURIComponent(s)
}

export function getUnresolvedQueue(): Promise<ReturnType<typeof QueueListResponseSchema.parse>> {
  return apiGet('/adjudication/queues/unresolved', QueueListResponseSchema)
}

export function getQueueByTarget(targetType: ReviewTargetType) {
  return apiGet(
    `/adjudication/queues/by-target?target_type=${enc(targetType)}`,
    QueueListResponseSchema,
  )
}

export type QueueFilter = ReviewTargetType | 'all'

export function getNextQueueItem(filter: QueueFilter) {
  const q = 'queue=unresolved'
  const tt = filter !== 'all' ? `&target_type=${enc(filter)}` : ''
  return apiGet(`/adjudication/queues/next?${q}${tt}`, QueueNextResponseSchema)
}

export function getReviewBundle(targetType: ReviewTargetType, targetId: string) {
  return apiGet(
    `/adjudication/review-bundle?target_type=${enc(targetType)}&target_id=${enc(targetId)}`,
    ReviewBundleResponseSchema,
  )
}

export type DecisionSubmissionBody = {
  target_type: ReviewTargetType
  target_id: string
  decision_type: string
  reviewer_id: string
  note?: string | null
  reason_code?: string | null
  related_target_id?: string | null
}

export function postDecision(body: DecisionSubmissionBody) {
  return apiPost('/adjudication/decision', body, DecisionSubmissionResponseSchema)
}
