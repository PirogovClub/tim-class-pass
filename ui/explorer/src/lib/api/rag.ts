import { z } from 'zod'

import { apiPost } from '@/lib/api/client'

/** Loose schema: RAG search responses evolve with Stage 6.3; keep passthrough for forward compatibility. */
export const RagSearchHitSchema = z.record(z.string(), z.unknown())

export const RagSearchResponseSchema = z
  .object({
    query: z.string(),
    hit_count: z.number().optional(),
    top_hits: z.array(RagSearchHitSchema),
    query_analysis: z.record(z.string(), z.unknown()).optional(),
    grouped_results: z.record(z.string(), z.unknown()).optional(),
    summary: z.record(z.string(), z.unknown()).optional(),
    facets: z.record(z.string(), z.unknown()).optional(),
  })
  .passthrough()

export type RagSearchResponse = z.infer<typeof RagSearchResponseSchema>

export async function postRagSearch(payload: {
  query: string
  top_k?: number
  unit_types?: string[]
  require_evidence?: boolean
  return_summary?: boolean
}): Promise<RagSearchResponse> {
  return apiPost(
    '/rag/search',
    {
      query: payload.query,
      top_k: payload.top_k ?? 8,
      unit_types: payload.unit_types ?? [],
      filters: { lesson_ids: [], concept_ids: [], min_confidence_score: null },
      return_summary: payload.return_summary ?? true,
      require_evidence: payload.require_evidence ?? false,
    },
    RagSearchResponseSchema,
  )
}
