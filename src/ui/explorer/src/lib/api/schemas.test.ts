import * as S from '@/lib/api/schemas'
import conceptDetail from '@/test/fixtures/concept-detail.json'
import conceptNeighbors from '@/test/fixtures/concept-neighbors.json'
import evidenceDetail from '@/test/fixtures/evidence-detail.json'
import facets from '@/test/fixtures/facets.json'
import health from '@/test/fixtures/health.json'
import lessonDetail from '@/test/fixtures/lesson-detail.json'
import ruleDetail from '@/test/fixtures/rule-detail.json'
import searchStopLoss from '@/test/fixtures/search-stop-loss.json'

describe('api schemas', () => {
  it('parses real fixture payloads', () => {
    expect(S.HealthResponseSchema.safeParse(health).success).toBe(true)
    expect(S.BrowserSearchResponseSchema.safeParse(searchStopLoss).success).toBe(true)
    expect(S.RuleDetailResponseSchema.safeParse(ruleDetail).success).toBe(true)
    expect(S.EvidenceDetailResponseSchema.safeParse(evidenceDetail).success).toBe(true)
    expect(S.ConceptDetailResponseSchema.safeParse(conceptDetail).success).toBe(true)
    expect(S.ConceptNeighborsResponseSchema.safeParse(conceptNeighbors).success).toBe(true)
    expect(S.LessonDetailResponseSchema.safeParse(lessonDetail).success).toBe(true)
    expect(S.FacetResponseSchema.safeParse(facets).success).toBe(true)
  })

  it('rejects invalid result cards', () => {
    expect(S.BrowserResultCardSchema.safeParse({ title: 'x', unit_type: 'rule_card' }).success).toBe(false)
    expect(S.BrowserResultCardSchema.safeParse({ doc_id: 'x', title: 'x', unit_type: 'bad' }).success).toBe(false)
  })
})
