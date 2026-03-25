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
