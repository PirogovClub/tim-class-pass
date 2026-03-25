import { entityRoute } from '@/lib/utils/entity'

describe('entityRoute', () => {
  it('routes cards to detail pages', () => {
    expect(entityRoute({ doc_id: 'rule-1', unit_type: 'rule_card', lesson_id: null, title: '', subtitle: '', snippet: '', concept_ids: [], support_basis: null, evidence_requirement: null, teaching_mode: null, confidence_score: null, timestamps: [], evidence_count: 0, related_rule_count: 0, related_event_count: 0, score: null, why_retrieved: [] })).toBe('/rule/rule-1')
    expect(entityRoute({ doc_id: 'evidence-1', unit_type: 'evidence_ref', lesson_id: null, title: '', subtitle: '', snippet: '', concept_ids: [], support_basis: null, evidence_requirement: null, teaching_mode: null, confidence_score: null, timestamps: [], evidence_count: 0, related_rule_count: 0, related_event_count: 0, score: null, why_retrieved: [] })).toBe('/evidence/evidence-1')
    expect(entityRoute({ doc_id: 'x', unit_type: 'concept_node', lesson_id: null, title: '', subtitle: '', snippet: '', concept_ids: ['concept:stop_loss'], support_basis: null, evidence_requirement: null, teaching_mode: null, confidence_score: null, timestamps: [], evidence_count: 0, related_rule_count: 0, related_event_count: 0, score: null, why_retrieved: [] })).toBe('/concept/concept%3Astop_loss')
  })
})
