import type { SearchUrlState } from '@/lib/url/search-params'
import {
  defaultSearchUrlState,
  parseSearchUrlParams,
  searchStateToRequest,
  serializeSearchUrlParams,
} from '@/lib/url/search-params'

describe('search url params', () => {
  it('encodes and decodes round trip', () => {
    const state: SearchUrlState = {
      q: 'stop loss',
      topK: 12,
      returnGroups: false,
      filters: {
        lesson_ids: ['lesson-a'],
        concept_ids: ['concept:x'],
        unit_types: ['rule_card'],
        support_basis: ['transcript_plus_visual'],
        evidence_requirement: ['required'],
        teaching_mode: ['example'],
        min_confidence_score: 0.8,
      },
    }
    const params = serializeSearchUrlParams(state)
    expect(parseSearchUrlParams(params)).toEqual(state)
  })

  it('uses defaults for empty params', () => {
    expect(parseSearchUrlParams(new URLSearchParams())).toEqual(defaultSearchUrlState())
  })

  it('converts state to API request', () => {
    const request = searchStateToRequest(defaultSearchUrlState())
    expect(request.top_k).toBe(20)
    expect(request.return_groups).toBe(true)
  })
})
