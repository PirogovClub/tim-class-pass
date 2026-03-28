import type { z } from 'zod'

import {
  type BrowserResultCardSchema,
  type BrowserSearchFiltersSchema,
  type BrowserSearchRequestSchema,
  type BrowserSearchResponseSchema,
  type ComparisonDifferenceSchema,
  type ComparisonSummarySchema,
  type ConceptDetailResponseSchema,
  type ConceptLessonListResponseSchema,
  type ConceptNeighborSchema,
  type ConceptRuleListResponseSchema,
  type EvidenceDetailResponseSchema,
  type EventDetailResponseSchema,
  type FacetResponseSchema,
  type HealthResponseSchema,
  type LessonCompareItemSchema,
  type LessonCompareRequestSchema,
  type LessonCompareResponseSchema,
  type LessonDetailResponseSchema,
  type RelatedRuleItemSchema,
  type RelatedRulesResponseSchema,
  type RelationReasonSchema,
  type RuleCompareItemSchema,
  type RuleCompareRequestSchema,
  type RuleCompareResponseSchema,
  type RuleDetailResponseSchema,
  type UnitCompareRequestSchema,
  type UnitCompareResponseSchema,
  type UnitCompareRowSchema,
  type UnitTypeSchema,
} from '@/lib/api/schemas'

export type UnitType = z.infer<typeof UnitTypeSchema>
export type BrowserSearchFilters = z.infer<typeof BrowserSearchFiltersSchema>
export type BrowserSearchRequest = z.infer<typeof BrowserSearchRequestSchema>
export type BrowserResultCard = z.infer<typeof BrowserResultCardSchema>
export type BrowserSearchResponse = z.infer<typeof BrowserSearchResponseSchema>
export type RuleDetailResponse = z.infer<typeof RuleDetailResponseSchema>
export type ComparisonDifference = z.infer<typeof ComparisonDifferenceSchema>
export type ComparisonSummary = z.infer<typeof ComparisonSummarySchema>
export type RuleCompareRequest = z.infer<typeof RuleCompareRequestSchema>
export type RuleCompareItem = z.infer<typeof RuleCompareItemSchema>
export type RuleCompareResponse = z.infer<typeof RuleCompareResponseSchema>
export type EvidenceDetailResponse = z.infer<typeof EvidenceDetailResponseSchema>
export type EventDetailResponse = z.infer<typeof EventDetailResponseSchema>
export type ConceptNeighbor = z.infer<typeof ConceptNeighborSchema>
export type ConceptDetailResponse = z.infer<typeof ConceptDetailResponseSchema>
export type LessonDetailResponse = z.infer<typeof LessonDetailResponseSchema>
export type LessonCompareRequest = z.infer<typeof LessonCompareRequestSchema>
export type LessonCompareItem = z.infer<typeof LessonCompareItemSchema>
export type LessonCompareResponse = z.infer<typeof LessonCompareResponseSchema>
export type RelationReason = z.infer<typeof RelationReasonSchema>
export type RelatedRuleItem = z.infer<typeof RelatedRuleItemSchema>
export type RelatedRulesResponse = z.infer<typeof RelatedRulesResponseSchema>
export type ConceptRuleListResponse = z.infer<typeof ConceptRuleListResponseSchema>
export type ConceptLessonListResponse = z.infer<typeof ConceptLessonListResponseSchema>
export type HealthResponse = z.infer<typeof HealthResponseSchema>
export type FacetResponse = z.infer<typeof FacetResponseSchema>
export type UnitCompareRequest = z.infer<typeof UnitCompareRequestSchema>
export type UnitCompareResponse = z.infer<typeof UnitCompareResponseSchema>
export type UnitCompareRow = z.infer<typeof UnitCompareRowSchema>
