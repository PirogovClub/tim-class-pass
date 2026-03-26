import { z } from 'zod'

export const ReviewTargetTypeSchema = z.enum([
  'rule_card',
  'evidence_link',
  'concept_link',
  'related_rule_relation',
  'canonical_rule_family',
])

export const DecisionHistoryEntrySchema = z.object({
  decision_id: z.string(),
  target_type: z.string(),
  target_id: z.string(),
  decision_type: z.string(),
  reviewer_id: z.string(),
  created_at: z.string(),
  note: z.string().nullable().optional(),
  reason_code: z.string().nullable().optional(),
  related_target_id: z.string().nullable().optional(),
  artifact_version: z.string().nullable().optional(),
  proposal_id: z.string().nullable().optional(),
})

export const ReviewItemResponseSchema = z.object({
  target_type: ReviewTargetTypeSchema,
  target_id: z.string(),
  current_status: z.string().nullable().optional(),
  latest_decision_type: z.string().nullable().optional(),
  last_reviewed_at: z.string().nullable().optional(),
  last_reviewer_id: z.string().nullable().optional(),
  canonical_family_id: z.string().nullable().optional(),
  summary: z.string().nullable().optional(),
  is_duplicate: z.boolean().nullable().optional(),
  duplicate_of_rule_id: z.string().nullable().optional(),
  is_ambiguous: z.boolean().nullable().optional(),
  is_deferred: z.boolean().nullable().optional(),
  is_unsupported: z.boolean().nullable().optional(),
  support_status: z.string().nullable().optional(),
  link_status: z.string().nullable().optional(),
  relation_status: z.string().nullable().optional(),
})

export const FamilySummarySchema = z.object({
  family_id: z.string(),
  canonical_title: z.string(),
  status: z.string(),
  member_count: z.number().nullable().optional(),
})

export const QualityTierSchema = z.enum(['gold', 'silver', 'bronze', 'unresolved'])

export const TierStateSchema = z.object({
  target_type: ReviewTargetTypeSchema,
  target_id: z.string(),
  tier: QualityTierSchema,
  tier_reasons: z.array(z.string()).default([]),
  blocker_codes: z.array(z.string()).default([]),
  is_eligible_for_downstream_use: z.boolean(),
  is_promotable_to_gold: z.boolean(),
  resolved_at: z.string(),
  policy_version: z.string(),
})

export const ProposalBundleEntrySchema = z.object({
  proposal_id: z.string(),
  proposal_type: z.string(),
  source_target_type: z.string(),
  source_target_id: z.string(),
  queue_name_hint: z.string().nullable().optional(),
  score: z.number(),
  queue_priority: z.number(),
  rationale_summary: z.string(),
  related_target_type: z.string().nullable().optional(),
  related_target_id: z.string().nullable().optional(),
})

export const ReviewBundleResponseSchema = z.object({
  target_type: ReviewTargetTypeSchema,
  target_id: z.string(),
  target_summary: z.string().nullable().optional(),
  reviewed_state: ReviewItemResponseSchema,
  history: z.array(DecisionHistoryEntrySchema),
  family: FamilySummarySchema.nullable().optional(),
  family_members_preview: z.array(z.record(z.string(), z.unknown())).default([]),
  optional_context: z.record(z.string(), z.unknown()).default({}),
  quality_tier: TierStateSchema.nullable().optional(),
  open_proposals: z.array(ProposalBundleEntrySchema).default([]),
})

export const DecisionSubmissionResponseSchema = z.object({
  success: z.boolean().optional(),
  decision_id: z.string(),
  target_type: ReviewTargetTypeSchema,
  target_id: z.string(),
  updated_state: ReviewItemResponseSchema,
  family_linkage_summary: z.record(z.string(), z.unknown()).nullable().optional(),
})

export const QueueItemResponseSchema = z.object({
  target_type: ReviewTargetTypeSchema,
  target_id: z.string(),
  current_status: z.string().nullable().optional(),
  latest_decision_type: z.string().nullable().optional(),
  last_reviewed_at: z.string().nullable().optional(),
  canonical_family_id: z.string().nullable().optional(),
  queue_reason: z.string().nullable().optional(),
  summary: z.string().nullable().optional(),
  quality_tier: QualityTierSchema.nullable().optional(),
  proposal_id: z.string().nullable().optional(),
  proposal_type: z.string().nullable().optional(),
  related_target_type: z.string().nullable().optional(),
  related_target_id: z.string().nullable().optional(),
  proposal_score: z.number().nullable().optional(),
  proposal_queue_priority: z.number().nullable().optional(),
  proposal_rationale_summary: z.string().nullable().optional(),
  proposal_updated_at: z.string().nullable().optional(),
})

export const QueueListResponseSchema = z.object({
  queue: z.string(),
  items: z.array(QueueItemResponseSchema),
  total: z.number(),
})

export const QueueNextResponseSchema = QueueItemResponseSchema.nullable()

/** Stage 5.7 review metrics (read-only API). */
export const MetricsSummaryResponseSchema = z.object({
  computed_at: z.string(),
  total_supported_review_targets: z.number(),
  unresolved_count: z.number(),
  gold_count: z.number(),
  silver_count: z.number(),
  bronze_count: z.number(),
  tier_unresolved_count: z.number(),
  rejected_count: z.number(),
  unsupported_count: z.number(),
  canonical_family_count: z.number(),
  merge_decision_count: z.number(),
})

export const MetricsProposalQueueSizeSchema = z.object({
  queue_name: z.string(),
  open_count: z.number(),
})

export const MetricsQueueHealthResponseSchema = z.object({
  computed_at: z.string(),
  unresolved_queue_size: z.number(),
  deferred_rule_cards: z.number(),
  proposal_queue_open_counts: z.array(MetricsProposalQueueSizeSchema),
  unresolved_by_target_type: z.record(z.string(), z.number()),
  unresolved_backlog_by_tier: z.record(z.string(), z.number()),
  oldest_unresolved_last_reviewed_at: z.string().nullable().optional(),
  oldest_unresolved_age_seconds: z.number().nullable().optional(),
})

export const MetricsProposalTypeRowSchema = z.object({
  proposal_type: z.string(),
  total: z.number(),
  open: z.number(),
  accepted: z.number(),
  dismissed: z.number(),
  stale: z.number(),
  superseded: z.number(),
  terminal: z.number(),
  acceptance_rate_closed: z.number().nullable().optional(),
  acceptance_rate_all: z.number().nullable().optional(),
})

export const MetricsProposalUsefulnessSchema = z.object({
  computed_at: z.string(),
  total_proposals: z.number(),
  open_proposals: z.number(),
  accepted_proposals: z.number(),
  dismissed_proposals: z.number(),
  stale_proposals: z.number(),
  superseded_proposals: z.number(),
  stale_total: z.number(),
  terminal_proposals: z.number(),
  acceptance_rate_closed: z.number().nullable().optional(),
  acceptance_rate_all: z.number().nullable().optional(),
  median_seconds_to_disposition: z.number().nullable().optional(),
  by_proposal_type: z.array(MetricsProposalTypeRowSchema),
})

export const MetricsThroughputBreakdownSchema = z.object({
  decision_type: z.string(),
  count: z.number(),
})

export const MetricsReviewerThroughputSchema = z.object({
  reviewer_id: z.string(),
  count: z.number(),
})

export const MetricsThroughputResponseSchema = z.object({
  computed_at: z.string(),
  window: z.string(),
  window_start_utc: z.string(),
  decision_count: z.number(),
  by_decision_type: z.array(MetricsThroughputBreakdownSchema),
  by_reviewer_id: z.array(MetricsReviewerThroughputSchema),
})

export const MetricsCoverageBucketSchema = z.object({
  bucket_id: z.string(),
  total_targets: z.number(),
  reviewed_not_unresolved: z.number(),
  coverage_ratio: z.number().nullable().optional(),
})

export const MetricsCoverageLessonsSchema = z.object({
  computed_at: z.string(),
  explorer_available: z.boolean(),
  note: z.string().nullable().optional(),
  buckets: z.array(MetricsCoverageBucketSchema),
})

/** Same payload shape as lessons coverage; distinct route on the API. */
export const MetricsCoverageConceptsSchema = MetricsCoverageLessonsSchema

export const MetricsFlagsSummarySchema = z.object({
  ambiguity_rule_cards: z.number(),
  conflict_rule_split_required: z.number(),
  conflict_concept_invalid: z.number(),
  conflict_relation_invalid: z.number(),
})

export const MetricsFlagDistributionRowSchema = z.object({
  bucket_id: z.string(),
  ambiguity_rule_cards: z.number(),
  conflict_rule_split_required: z.number(),
})

export const MetricsFlagsResponseSchema = z.object({
  computed_at: z.string(),
  explorer_available: z.boolean(),
  note: z.string().nullable().optional(),
  summary: MetricsFlagsSummarySchema,
  by_lesson: z.array(MetricsFlagDistributionRowSchema),
  by_concept: z.array(MetricsFlagDistributionRowSchema),
})

export type MetricsSummaryResponse = z.infer<typeof MetricsSummaryResponseSchema>
export type MetricsQueueHealthResponse = z.infer<typeof MetricsQueueHealthResponseSchema>
export type MetricsProposalUsefulnessResponse = z.infer<typeof MetricsProposalUsefulnessSchema>
export type MetricsThroughputResponse = z.infer<typeof MetricsThroughputResponseSchema>
export type MetricsCoverageLessonsResponse = z.infer<typeof MetricsCoverageLessonsSchema>
export type MetricsCoverageConceptsResponse = z.infer<typeof MetricsCoverageConceptsSchema>
export type MetricsFlagsResponse = z.infer<typeof MetricsFlagsResponseSchema>

export type ReviewTargetType = z.infer<typeof ReviewTargetTypeSchema>
export type ReviewBundleResponse = z.infer<typeof ReviewBundleResponseSchema>
export type QueueListResponse = z.infer<typeof QueueListResponseSchema>
export type QueueItemResponse = z.infer<typeof QueueItemResponseSchema>
export type DecisionSubmissionResponse = z.infer<typeof DecisionSubmissionResponseSchema>
export type ReviewItemResponse = z.infer<typeof ReviewItemResponseSchema>
export type DecisionHistoryEntry = z.infer<typeof DecisionHistoryEntrySchema>
export type TierState = z.infer<typeof TierStateSchema>
export type QualityTier = z.infer<typeof QualityTierSchema>
export type ProposalBundleEntry = z.infer<typeof ProposalBundleEntrySchema>
