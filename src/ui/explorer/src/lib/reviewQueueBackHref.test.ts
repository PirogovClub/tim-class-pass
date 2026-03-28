import { describe, expect, it } from 'vitest'

import { buildReviewQueueBackHref } from '@/lib/reviewQueueBackHref'

function paramsFromHref(href: string): URLSearchParams {
  const u = new URL(href, 'http://local.test')
  return u.searchParams
}

describe('buildReviewQueueBackHref', () => {
  it('preserves reviewQueue for merge_candidates', () => {
    const sp = new URLSearchParams()
    sp.set('reviewQueue', 'merge_candidates')
    sp.set('queueFilter', 'rule_card')
    const href = buildReviewQueueBackHref(sp)
    const q = paramsFromHref(href)
    expect(href.startsWith('/review/queue')).toBe(true)
    expect(q.get('reviewQueue')).toBe('merge_candidates')
    expect(q.get('targetType')).toBe('rule_card')
  })

  it('preserves reviewQueue, targetType mapping from queueFilter, and qualityTier', () => {
    const sp = new URLSearchParams()
    sp.set('reviewQueue', 'canonical_family_candidates')
    sp.set('queueFilter', 'rule_card')
    sp.set('qualityTier', 'silver')
    const q = paramsFromHref(buildReviewQueueBackHref(sp))
    expect(q.get('reviewQueue')).toBe('canonical_family_candidates')
    expect(q.get('targetType')).toBe('rule_card')
    expect(q.get('qualityTier')).toBe('silver')
  })

  it('omits reviewQueue when it is unresolved (default queue)', () => {
    const sp = new URLSearchParams()
    sp.set('reviewQueue', 'unresolved')
    sp.set('queueFilter', 'rule_card')
    const q = paramsFromHref(buildReviewQueueBackHref(sp))
    expect(q.has('reviewQueue')).toBe(false)
    expect(q.get('targetType')).toBe('rule_card')
  })

  it('uses targetType when queueFilter is absent', () => {
    const sp = new URLSearchParams()
    sp.set('reviewQueue', 'merge_candidates')
    sp.set('targetType', 'rule_card')
    const q = paramsFromHref(buildReviewQueueBackHref(sp))
    expect(q.get('reviewQueue')).toBe('merge_candidates')
    expect(q.get('targetType')).toBe('rule_card')
  })
})
