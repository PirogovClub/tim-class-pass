import {
  DecisionSubmissionResponseSchema,
  QueueListResponseSchema,
  QueueNextResponseSchema,
  ReviewBundleResponseSchema,
  type QualityTier,
  type QueueListResponse,
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

export type ReviewBackendQueue =
  | 'unresolved'
  | 'high_confidence_duplicates'
  | 'merge_candidates'
  | 'canonical_family_candidates'

export type ProposalQueueQueryOptions = {
  limit?: number
  offset?: number
  targetType?: ReviewTargetType
  qualityTier?: QualityTier
}

export function getProposalQueue(
  queue: Exclude<ReviewBackendQueue, 'unresolved'>,
  options: ProposalQueueQueryOptions = {},
): Promise<QueueListResponse> {
  const { limit = 500, offset = 0, targetType, qualityTier } = options
  const parts = [`queue=${enc(queue)}`, `limit=${limit}`, `offset=${offset}`]
  if (targetType) {
    parts.push(`target_type=${enc(targetType)}`)
  }
  if (qualityTier) {
    parts.push(`quality_tier=${enc(qualityTier)}`)
  }
  return apiGet(`/adjudication/queues/proposals?${parts.join('&')}`, QueueListResponseSchema)
}

export type NextQueueItemOptions = {
  qualityTier?: QualityTier
}

export function getNextQueueItem(
  filter: QueueFilter,
  reviewQueue: ReviewBackendQueue = 'unresolved',
  options?: NextQueueItemOptions,
): Promise<ReturnType<typeof QueueNextResponseSchema.parse>> {
  const q = `queue=${enc(reviewQueue)}`
  const tt = filter !== 'all' ? `&target_type=${enc(filter)}` : ''
  const qt =
    options?.qualityTier != null ? `&quality_tier=${enc(options.qualityTier)}` : ''
  return apiGet(`/adjudication/queues/next?${q}${tt}${qt}`, QueueNextResponseSchema)
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
  proposal_id?: string | null
}

export function postDecision(body: DecisionSubmissionBody) {
  return apiPost('/adjudication/decision', body, DecisionSubmissionResponseSchema)
}
