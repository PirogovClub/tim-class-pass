import { describe, expect, it } from 'vitest'

import { decisionRequiresRelatedTarget, decisionsForTarget } from '@/lib/review/decisions'

describe('decisionsForTarget', () => {
  it('returns rule_card policy set', () => {
    expect(decisionsForTarget('rule_card')).toContain('approve')
    expect(decisionsForTarget('rule_card')).toContain('duplicate_of')
  })

  it('returns evidence_link set', () => {
    expect(decisionsForTarget('evidence_link')).toContain('evidence_strong')
  })
})

describe('decisionRequiresRelatedTarget', () => {
  it('is true for duplicate and merge', () => {
    expect(decisionRequiresRelatedTarget('duplicate_of')).toBe(true)
    expect(decisionRequiresRelatedTarget('merge_into')).toBe(true)
    expect(decisionRequiresRelatedTarget('approve')).toBe(false)
  })
})
