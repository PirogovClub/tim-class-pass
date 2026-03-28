import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { QualityTierPanel } from '@/components/review/QualityTierPanel'
import type { ReviewBundleResponse } from '@/lib/api/adjudication-schemas'

function bundleWithTier(
  partial: NonNullable<ReviewBundleResponse['quality_tier']>,
): ReviewBundleResponse {
  return {
    target_type: 'rule_card',
    target_id: 'rule:test:1',
    target_summary: null,
    reviewed_state: {
      target_type: 'rule_card',
      target_id: 'rule:test:1',
    },
    history: [],
    optional_context: {},
    family_members_preview: [],
    open_proposals: [],
    quality_tier: partial,
  }
}

describe('QualityTierPanel', () => {
  it('renders tier badge and blockers', () => {
    render(
      <QualityTierPanel
        bundle={bundleWithTier({
          target_type: 'rule_card',
          target_id: 'rule:test:1',
          tier: 'silver',
          tier_reasons: ['Valid duplicate_of — high utility, capped below Gold.'],
          blocker_codes: ['duplicate_not_gold_eligible'],
          is_eligible_for_downstream_use: true,
          is_promotable_to_gold: false,
          resolved_at: '2026-03-24T00:00:00+00:00',
          policy_version: 'tier_policy.v1',
        })}
      />,
    )
    expect(screen.getByText('silver')).toBeInTheDocument()
    expect(screen.getByText('duplicate_not_gold_eligible')).toBeInTheDocument()
    expect(screen.getByText(/duplicate_of/i)).toBeInTheDocument()
  })

  it('handles missing tier data gracefully', () => {
    const b = bundleWithTier({
      target_type: 'rule_card',
      target_id: 'x',
      tier: 'gold',
      tier_reasons: [],
      blocker_codes: [],
      is_eligible_for_downstream_use: true,
      is_promotable_to_gold: false,
      resolved_at: 't',
      policy_version: 'tier_policy.v1',
    })
    render(<QualityTierPanel bundle={{ ...b, quality_tier: undefined }} />)
    expect(screen.getByText(/No tier data/i)).toBeInTheDocument()
  })
})
