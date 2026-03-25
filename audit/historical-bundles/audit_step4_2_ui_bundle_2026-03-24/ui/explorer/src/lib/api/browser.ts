import {
  BrowserSearchRequestSchema,
  BrowserSearchResponseSchema,
  ConceptDetailResponseSchema,
  ConceptNeighborsResponseSchema,
  EvidenceDetailResponseSchema,
  FacetResponseSchema,
  HealthResponseSchema,
  LessonDetailResponseSchema,
  RuleDetailResponseSchema,
} from '@/lib/api/schemas'
import type {
  BrowserSearchFilters,
  BrowserSearchRequest,
  BrowserSearchResponse,
  ConceptDetailResponse,
  ConceptNeighbor,
  EvidenceDetailResponse,
  FacetResponse,
  HealthResponse,
  LessonDetailResponse,
  RuleDetailResponse,
} from '@/lib/api/types'
import { apiGet, apiPost } from '@/lib/api/client'

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

export function getBrowserEvidence(docId: string): Promise<EvidenceDetailResponse> {
  return apiGet(`/browser/evidence/${encodeURIComponent(docId)}`, EvidenceDetailResponseSchema)
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

export type BrowserFacetsParams = {
  query?: string | null
  filters: BrowserSearchFilters
}

export function getBrowserFacets(params: BrowserFacetsParams): Promise<FacetResponse> {
  const qs = new URLSearchParams()
  if (params.query) qs.set('query', params.query)
  for (const id of params.filters.lesson_ids) qs.append('lesson_ids', id)
  for (const id of params.filters.concept_ids) qs.append('concept_ids', id)
  for (const u of params.filters.unit_types) qs.append('unit_types', u)
  for (const s of params.filters.support_basis) qs.append('support_basis', s)
  for (const e of params.filters.evidence_requirement) qs.append('evidence_requirement', e)
  for (const t of params.filters.teaching_mode) qs.append('teaching_mode', t)
  if (params.filters.min_confidence_score != null) {
    qs.set('min_confidence_score', String(params.filters.min_confidence_score))
  }
  const suffix = qs.toString()
  return apiGet(`/browser/facets${suffix ? `?${suffix}` : ''}`, FacetResponseSchema)
}
