import { describe, expect, it } from 'vitest'

import type { ReviewBundleResponse } from '@/lib/api/adjudication-schemas'
import {
  canCompareAdjudicateRulePair,
  prefillCompareRelatedTarget,
} from '@/lib/review/compareDecisionPrefill'

function ruleBundle(id: string, familyId?: string | null): ReviewBundleResponse {
  return {
    target_type: 'rule_card',
    target_id: id,
    target_summary: null,
    reviewed_state: {
      target_type: 'rule_card',
      target_id: id,
      canonical_family_id: familyId ?? null,
    },
    history: [],
    family: familyId ? { family_id: familyId, canonical_title: 't', status: 'active' } : null,
    family_members_preview: [],
    optional_context: {},
  }
}

describe('prefillCompareRelatedTarget', () => {
  const left = ruleBundle('rule_a', 'fam_left')
  const right = ruleBundle('rule_b', 'fam_right')

  it('duplicate: primary left → other rule id is right', () => {
    expect(
      prefillCompareRelatedTarget({
        decisionType: 'duplicate_of',
        primary: 'left',
        left,
        right,
      }),
    ).toBe('rule_b')
  })

  it('duplicate: primary right → other rule id is left', () => {
    expect(
      prefillCompareRelatedTarget({
        decisionType: 'duplicate_of',
        primary: 'right',
        left,
        right,
      }),
    ).toBe('rule_a')
  })

  it('merge: primary left → family from right bundle', () => {
    expect(
      prefillCompareRelatedTarget({
        decisionType: 'merge_into',
        primary: 'left',
        left,
        right,
      }),
    ).toBe('fam_right')
  })

  it('merge: uses reviewed_state.canonical_family_id when family missing', () => {
    const r = ruleBundle('rule_b', null)
    const patched: ReviewBundleResponse = {
      ...r,
      family: null,
      reviewed_state: { ...r.reviewed_state, canonical_family_id: 'fam_state' },
    }
    expect(
      prefillCompareRelatedTarget({
        decisionType: 'merge_into',
        primary: 'left',
        left,
        right: patched,
      }),
    ).toBe('fam_state')
  })
})

describe('canCompareAdjudicateRulePair', () => {
  it('is true for two rule_card bundles', () => {
    expect(
      canCompareAdjudicateRulePair(ruleBundle('a'), ruleBundle('b')),
    ).toBe(true)
  })

  it('is false when either side null', () => {
    expect(canCompareAdjudicateRulePair(ruleBundle('a'), null)).toBe(false)
    expect(canCompareAdjudicateRulePair(null, ruleBundle('b'))).toBe(false)
  })

  it('is false for mixed target types', () => {
    const evidence = {
      target_type: 'evidence_link' as const,
      target_id: 'ev_1',
      target_summary: null,
      reviewed_state: {
        target_type: 'evidence_link' as const,
        target_id: 'ev_1',
      },
      history: [],
      family: null,
      family_members_preview: [],
      optional_context: {},
    } satisfies ReviewBundleResponse
    expect(canCompareAdjudicateRulePair(ruleBundle('a'), evidence)).toBe(false)
  })
})
