import { apiGet, apiPost } from '@/lib/api/client'
import {
  BrowserSearchRequestSchema,
  BrowserSearchResponseSchema,
  ConceptDetailResponseSchema,
  ConceptLessonListResponseSchema,
  ConceptNeighborsResponseSchema,
  ConceptRuleListResponseSchema,
  EvidenceDetailResponseSchema,
  EventDetailResponseSchema,
  FacetResponseSchema,
  HealthResponseSchema,
  LessonCompareRequestSchema,
  LessonCompareResponseSchema,
  LessonDetailResponseSchema,
  RelatedRulesResponseSchema,
  RuleCompareRequestSchema,
  RuleCompareResponseSchema,
  RuleDetailResponseSchema,
  UnitCompareRequestSchema,
  UnitCompareResponseSchema,
} from '@/lib/api/schemas'
import type {
  BrowserSearchFilters,
  BrowserSearchRequest,
  BrowserSearchResponse,
  ConceptDetailResponse,
  ConceptLessonListResponse,
  ConceptNeighbor,
  ConceptRuleListResponse,
  EvidenceDetailResponse,
  EventDetailResponse,
  FacetResponse,
  HealthResponse,
  LessonCompareRequest,
  LessonCompareResponse,
  LessonDetailResponse,
  RelatedRulesResponse,
  RuleCompareRequest,
  RuleCompareResponse,
  RuleDetailResponse,
  UnitCompareRequest,
  UnitCompareResponse,
} from '@/lib/api/types'

export function getBrowserHealth(): Promise<HealthResponse> {
  return apiGet('/browser/health', HealthResponseSchema)
}

export function postBrowserSearch(req: BrowserSearchRequest): Promise<BrowserSearchResponse> {
  const validated = BrowserSearchRequestSchema.parse(req)
  return apiPost('/browser/search', validated, BrowserSearchResponseSchema)
}

export function getBrowserRule(docId: string): Promise<RuleDetailResponse> {
  return apiGet(`/browser/rule/${encodeURIComponent(docId)}`, RuleDetailResponseSchema)
}

export function postCompareRules(req: RuleCompareRequest): Promise<RuleCompareResponse> {
  const validated = RuleCompareRequestSchema.parse(req)
  return apiPost('/browser/compare/rules', validated, RuleCompareResponseSchema)
}

export function getBrowserEvidence(docId: string): Promise<EvidenceDetailResponse> {
  return apiGet(`/browser/evidence/${encodeURIComponent(docId)}`, EvidenceDetailResponseSchema)
}

export function getBrowserEvent(docId: string): Promise<EventDetailResponse> {
  return apiGet(`/browser/event/${encodeURIComponent(docId)}`, EventDetailResponseSchema)
}

export function getBrowserConcept(conceptId: string): Promise<ConceptDetailResponse> {
  return apiGet(`/browser/concept/${encodeURIComponent(conceptId)}`, ConceptDetailResponseSchema)
}

export function getBrowserConceptNeighbors(conceptId: string): Promise<ConceptNeighbor[]> {
  return apiGet(
    `/browser/concept/${encodeURIComponent(conceptId)}/neighbors`,
    ConceptNeighborsResponseSchema,
  )
}

export function getBrowserLesson(lessonId: string): Promise<LessonDetailResponse> {
  return apiGet(`/browser/lesson/${encodeURIComponent(lessonId)}`, LessonDetailResponseSchema)
}

export function postCompareLessons(req: LessonCompareRequest): Promise<LessonCompareResponse> {
  const validated = LessonCompareRequestSchema.parse(req)
  return apiPost('/browser/compare/lessons', validated, LessonCompareResponseSchema)
}

export function postCompareUnits(req: UnitCompareRequest): Promise<UnitCompareResponse> {
  const validated = UnitCompareRequestSchema.parse(req)
  return apiPost('/browser/compare/units', validated, UnitCompareResponseSchema)
}

export function getRelatedRules(docId: string): Promise<RelatedRulesResponse> {
  return apiGet(`/browser/rule/${encodeURIComponent(docId)}/related`, RelatedRulesResponseSchema)
}

export function getConceptRules(conceptId: string): Promise<ConceptRuleListResponse> {
  return apiGet(`/browser/concept/${encodeURIComponent(conceptId)}/rules`, ConceptRuleListResponseSchema)
}

export function getConceptLessons(conceptId: string): Promise<ConceptLessonListResponse> {
  return apiGet(`/browser/concept/${encodeURIComponent(conceptId)}/lessons`, ConceptLessonListResponseSchema)
}

export type BrowserFacetsParams = {
  query?: string | null
  filters: BrowserSearchFilters
}

export function getBrowserFacets(params: BrowserFacetsParams): Promise<FacetResponse> {
  const qs = new URLSearchParams()
  if (params.query) {qs.set('query', params.query)}
  for (const id of params.filters.lesson_ids) {qs.append('lesson_ids', id)}
  for (const id of params.filters.concept_ids) {qs.append('concept_ids', id)}
  for (const u of params.filters.unit_types) {qs.append('unit_types', u)}
  for (const s of params.filters.support_basis) {qs.append('support_basis', s)}
  for (const e of params.filters.evidence_requirement) {qs.append('evidence_requirement', e)}
  for (const t of params.filters.teaching_mode) {qs.append('teaching_mode', t)}
  if (params.filters.min_confidence_score != null) {
    qs.set('min_confidence_score', String(params.filters.min_confidence_score))
  }
  const suffix = qs.toString()
  return apiGet(`/browser/facets${suffix ? `?${suffix}` : ''}`, FacetResponseSchema)
}
