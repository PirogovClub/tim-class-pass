import { parseCompareIds, serializeCompareIds } from '@/lib/url/compare-params'

describe('compare params', () => {
  it('serializes and parses compare ids', () => {
    const params = serializeCompareIds(['rule_a', 'rule_b'])
    expect(params.toString()).toBe('ids=rule_a%2Crule_b')
    expect(parseCompareIds(params)).toEqual(['rule_a', 'rule_b'])
  })

  it('dedupes and trims ids', () => {
    const params = new URLSearchParams('ids=rule_a,%20rule_b,rule_a')
    expect(parseCompareIds(params)).toEqual(['rule_a', 'rule_b'])
  })
})
