import { supportBasisLabel, unitTypeBadgeColor } from '@/lib/utils/badges'

describe('badge helpers', () => {
  it('maps support basis labels', () => {
    expect(supportBasisLabel('transcript_plus_visual')).toContain('Transcript')
    expect(supportBasisLabel(null)).toBeNull()
  })

  it('returns badge class strings', () => {
    expect(unitTypeBadgeColor('rule_card')).toContain('sky')
    expect(unitTypeBadgeColor('lesson')).toContain('rose')
  })
})
