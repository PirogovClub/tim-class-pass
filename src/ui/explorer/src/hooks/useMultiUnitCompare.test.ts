import { describe, expect, it } from 'vitest'

import { parseCompareUnitsParam, serializeCompareUnitsParam } from './useMultiUnitCompare'

describe('compare units URL param', () => {
  it('round-trips two refs', () => {
    const refs = [
      { unit_type: 'rule_card' as const, doc_id: 'rule:lesson_alpha:rule_stop_loss_1' },
      { unit_type: 'knowledge_event' as const, doc_id: 'event:lesson_alpha:ke_stop_loss_1' },
    ]
    const raw = serializeCompareUnitsParam(refs)
    expect(parseCompareUnitsParam(raw)).toEqual(refs)
  })

  it('rejects fewer than two items', () => {
    expect(parseCompareUnitsParam('[{"unit_type":"rule_card","doc_id":"a"}]')).toBeNull()
  })

  it('rejects invalid unit_type', () => {
    expect(
      parseCompareUnitsParam(
        '[{"unit_type":"not_a_type","doc_id":"a"},{"unit_type":"rule_card","doc_id":"b"}]',
      ),
    ).toBeNull()
  })
})
