import type { z } from 'zod'
import {
  BrowserResultCardSchema,
  BrowserSearchFiltersSchema,
  BrowserSearchRequestSchema,
  BrowserSearchResponseSchema,
  ConceptDetailResponseSchema,
  ConceptNeighborSchema,
  EvidenceDetailResponseSchema,
  FacetResponseSchema,
  HealthResponseSchema,
  LessonDetailResponseSchema,
  RuleDetailResponseSchema,
  UnitTypeSchema,
} from '@/lib/api/schemas'

export type UnitType = z.infer<typeof UnitTypeSchema>
export type BrowserSearchFilters = z.infer<typeof BrowserSearchFiltersSchema>
export type BrowserSearchRequest = z.infer<typeof BrowserSearchRequestSchema>
export type BrowserResultCard = z.infer<typeof BrowserResultCardSchema>
export type BrowserSearchResponse = z.infer<typeof BrowserSearchResponseSchema>
export type RuleDetailResponse = z.infer<typeof RuleDetailResponseSchema>
export type EvidenceDetailResponse = z.infer<typeof EvidenceDetailResponseSchema>
export type ConceptNeighbor = z.infer<typeof ConceptNeighborSchema>
export type ConceptDetailResponse = z.infer<typeof ConceptDetailResponseSchema>
export type LessonDetailResponse = z.infer<typeof LessonDetailResponseSchema>
export type HealthResponse = z.infer<typeof HealthResponseSchema>
export type FacetResponse = z.infer<typeof FacetResponseSchema>
