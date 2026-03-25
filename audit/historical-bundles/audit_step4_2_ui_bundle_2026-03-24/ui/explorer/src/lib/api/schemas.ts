import { z } from 'zod'

/** Matches `pipeline.rag.config.UnitType`. */
export const UnitTypeSchema = z.enum([
  'rule_card',
  'knowledge_event',
  'evidence_ref',
  'concept_node',
  'concept_relation',
])

const JsonDictSchema = z.record(z.string(), z.unknown())

export const BrowserSearchFiltersSchema = z.object({
  lesson_ids: z.array(z.string()),
  concept_ids: z.array(z.string()),
  unit_types: z.array(UnitTypeSchema),
  support_basis: z.array(z.string()),
  evidence_requirement: z.array(z.string()),
  teaching_mode: z.array(z.string()),
  min_confidence_score: z.number().nullable(),
})

export const BrowserSearchRequestSchema = z.object({
  query: z.string(),
  top_k: z.number().int(),
  filters: BrowserSearchFiltersSchema,
  return_groups: z.boolean(),
})

export const BrowserResultCardSchema = z.object({
  doc_id: z.string(),
  unit_type: UnitTypeSchema,
  lesson_id: z.string().nullable(),
  title: z.string(),
  subtitle: z.string(),
  snippet: z.string(),
  concept_ids: z.array(z.string()),
  support_basis: z.string().nullable(),
  evidence_requirement: z.string().nullable(),
  teaching_mode: z.string().nullable(),
  confidence_score: z.number().nullable(),
  timestamps: z.array(JsonDictSchema),
  evidence_count: z.number().int(),
  related_rule_count: z.number().int(),
  related_event_count: z.number().int(),
  score: z.number().nullable(),
  why_retrieved: z.array(z.string()),
})

export const BrowserSearchResponseSchema = z.object({
  query: z.string(),
  cards: z.array(BrowserResultCardSchema),
  groups: z.record(z.string(), z.array(BrowserResultCardSchema)),
  facets: z.record(z.string(), z.record(z.string(), z.number().int())),
  hit_count: z.number().int(),
})

export const RuleDetailResponseSchema = z.object({
  doc_id: z.string(),
  lesson_id: z.string(),
  lesson_slug: z.string().nullable(),
  title: z.string(),
  concept: z.string().nullable(),
  subconcept: z.string().nullable(),
  canonical_concept_ids: z.array(z.string()),
  rule_text: z.string(),
  rule_text_ru: z.string(),
  conditions: z.array(z.string()),
  invalidation: z.array(z.string()),
  exceptions: z.array(z.string()),
  comparisons: z.array(z.string()),
  visual_summary: z.string().nullable(),
  frame_ids: z.array(z.string()),
  support_basis: z.string().nullable(),
  evidence_requirement: z.string().nullable(),
  teaching_mode: z.string().nullable(),
  confidence_score: z.number().nullable(),
  timestamps: z.array(JsonDictSchema),
  evidence_refs: z.array(BrowserResultCardSchema),
  source_events: z.array(BrowserResultCardSchema),
  related_rules: z.array(BrowserResultCardSchema),
})

export const EvidenceDetailResponseSchema = z.object({
  doc_id: z.string(),
  lesson_id: z.string(),
  title: z.string(),
  snippet: z.string(),
  timestamps: z.array(JsonDictSchema),
  support_basis: z.string().nullable(),
  confidence_score: z.number().nullable(),
  evidence_strength: z.string().nullable(),
  evidence_role_detail: z.string().nullable(),
  visual_summary: z.string().nullable(),
  frame_ids: z.array(z.string()),
  source_rules: z.array(BrowserResultCardSchema),
  source_events: z.array(BrowserResultCardSchema),
})

export const ConceptNeighborSchema = z.object({
  concept_id: z.string(),
  relation: z.string(),
  direction: z.string(),
  weight: z.number().nullable(),
})

export const ConceptDetailResponseSchema = z.object({
  concept_id: z.string(),
  aliases: z.array(z.string()),
  top_rules: z.array(BrowserResultCardSchema),
  top_events: z.array(BrowserResultCardSchema),
  lessons: z.array(z.string()),
  neighbors: z.array(ConceptNeighborSchema),
  rule_count: z.number().int(),
  event_count: z.number().int(),
  evidence_count: z.number().int(),
})

export const LessonDetailResponseSchema = z.object({
  lesson_id: z.string(),
  lesson_title: z.string().nullable(),
  rule_count: z.number().int(),
  event_count: z.number().int(),
  evidence_count: z.number().int(),
  concept_count: z.number().int(),
  support_basis_counts: z.record(z.string(), z.number().int()),
  top_concepts: z.array(z.string()),
  top_rules: z.array(BrowserResultCardSchema),
  top_evidence: z.array(BrowserResultCardSchema),
})

export const HealthResponseSchema = z.object({
  status: z.string(),
  rag_ready: z.boolean(),
  explorer_ready: z.boolean(),
  doc_count: z.number(),
  corpus_contract_version: z.union([z.string(), z.number()]).optional(),
})

export const FacetResponseSchema = z.record(z.string(), z.record(z.string(), z.number().int()))

export const ConceptNeighborsResponseSchema = z.array(ConceptNeighborSchema)
