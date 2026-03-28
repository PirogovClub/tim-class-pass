/**
 * Stage 5.5 audit screenshots → audit/stage5_5_bundle/screenshots/
 * Run from ui/explorer: npm run build && npm run audit:screenshots:5.5
 */
import { mkdirSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { expect, test } from '@playwright/test'

const shotDir = join(dirname(fileURLToPath(import.meta.url)), '../../../../audit/stage5_5_bundle/screenshots')
mkdirSync(shotDir, { recursive: true })
const shot = (name: string) => join(shotDir, name)

function enc(s: string) {
  return encodeURIComponent(s)
}

const dupQueueItem = {
  target_type: 'rule_card',
  target_id: 'rule:dup:audit:a',
  current_status: 'needs_review',
  latest_decision_type: null,
  last_reviewed_at: null,
  canonical_family_id: null,
  queue_reason: 'high_confidence_duplicates',
  summary: null,
  quality_tier: 'silver',
  proposal_id: 'prop-dup-audit',
  proposal_type: 'duplicate_candidate',
  related_target_type: 'rule_card',
  related_target_id: 'rule:dup:audit:b',
  proposal_score: 0.94,
  proposal_queue_priority: 0.97,
  proposal_rationale_summary: 'Very high lexical overlap for audit screenshot',
  proposal_updated_at: '2026-03-24T12:00:00Z',
}

const mergeQueueItem = {
  target_type: 'rule_card',
  target_id: 'rule:merge:audit:a',
  current_status: 'needs_review',
  latest_decision_type: null,
  last_reviewed_at: null,
  canonical_family_id: null,
  queue_reason: 'merge_candidates',
  summary: null,
  quality_tier: 'silver',
  proposal_id: 'prop-merge-audit',
  proposal_type: 'merge_candidate',
  related_target_type: 'rule_card',
  related_target_id: 'rule:merge:audit:b',
  proposal_score: 0.78,
  proposal_queue_priority: 0.88,
  proposal_rationale_summary: 'Merge candidate for audit screenshot',
  proposal_updated_at: '2026-03-24T12:00:00Z',
}

const canonicalQueueItem = {
  ...mergeQueueItem,
  target_id: 'rule:canon:audit:a',
  related_target_id: 'rule:canon:audit:b',
  queue_reason: 'canonical_family_candidates',
  proposal_id: 'prop-canon-audit',
  proposal_type: 'canonical_family_candidate',
  proposal_rationale_summary: 'Canonical family candidate for audit',
}

function minimalBundle(targetId: string, openProposals: unknown[]) {
  return {
    target_type: 'rule_card',
    target_id: targetId,
    target_summary: `Summary for ${targetId}`,
    reviewed_state: {
      target_type: 'rule_card',
      target_id: targetId,
      current_status: 'needs_review',
    },
    history: [],
    family: null,
    family_members_preview: [],
    optional_context: {},
    quality_tier: null,
    open_proposals: openProposals,
  }
}

test.describe.serial('Stage 5.5 audit screenshots', () => {
  test('proposal queues, review item, back link, compare', async ({ page }) => {
    await page.route('**/adjudication/queues/proposals**', async (route) => {
      const url = new URL(route.request().url())
      const queue = url.searchParams.get('queue')
      if (queue === 'high_confidence_duplicates') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            queue: 'high_confidence_duplicates',
            total: 37,
            items: [dupQueueItem],
          }),
        })
        return
      }
      if (queue === 'merge_candidates') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            queue: 'merge_candidates',
            total: 12,
            items: [mergeQueueItem, { ...mergeQueueItem, target_id: 'rule:merge:audit:c', proposal_id: 'prop-2' }],
          }),
        })
        return
      }
      if (queue === 'canonical_family_candidates') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            queue: 'canonical_family_candidates',
            total: 5,
            items: [canonicalQueueItem],
          }),
        })
        return
      }
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ queue: queue ?? '', total: 0, items: [] }),
      })
    })

    await page.goto('/review/queue?reviewQueue=high_confidence_duplicates')
    await expect(page.getByRole('heading', { name: 'Review queue' })).toBeVisible()
    await expect(page.getByText(/Showing 1 of 37 proposal queue/)).toBeVisible()
    await page.screenshot({ path: shot('01-queue-high-confidence-duplicates.png'), fullPage: true })

    await page.goto('/review/queue?reviewQueue=merge_candidates&targetType=rule_card')
    await expect(page.getByText(/Showing 2 of 12 proposal queue/)).toBeVisible()
    await page.screenshot({ path: shot('02-queue-merge-candidates-rule-card.png'), fullPage: true })

    await page.goto('/review/queue?reviewQueue=canonical_family_candidates')
    await expect(page.getByText(/Showing 1 of 5 proposal queue/)).toBeVisible()
    await page.screenshot({ path: shot('03-queue-canonical-family-candidates.png'), fullPage: true })

    const openProposal = {
      proposal_id: mergeQueueItem.proposal_id,
      proposal_type: mergeQueueItem.proposal_type,
      source_target_type: 'rule_card',
      source_target_id: mergeQueueItem.target_id,
      queue_name_hint: 'merge_candidates',
      score: mergeQueueItem.proposal_score,
      queue_priority: mergeQueueItem.proposal_queue_priority,
      rationale_summary: mergeQueueItem.proposal_rationale_summary,
      related_target_type: 'rule_card',
      related_target_id: mergeQueueItem.related_target_id,
    }

    await page.route('**/adjudication/review-bundle**', async (route) => {
      const url = route.request().url()
      if (url.includes(enc('rule:merge:audit:a'))) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(minimalBundle('rule:merge:audit:a', [openProposal])),
        })
      } else if (url.includes(enc('rule:merge:audit:b'))) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(minimalBundle('rule:merge:audit:b', [])),
        })
      } else {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(minimalBundle('rule:unknown', [])),
        })
      }
    })

    await page.goto('/review/queue?reviewQueue=merge_candidates&targetType=rule_card&qualityTier=silver')
    await page.getByRole('link', { name: 'Open' }).first().click()
    await expect(page.getByRole('heading', { name: 'Review item' })).toBeVisible()
    await expect(page.getByText(/AI proposal only/)).toBeVisible()
    await page.screenshot({ path: shot('04-review-item-proposal-panel.png'), fullPage: true })

    await page.getByRole('link', { name: /back to queue/i }).click()
    await expect(page).toHaveURL(/\/review\/queue\?/)
    const u = new URL(page.url())
    expect(u.searchParams.get('reviewQueue')).toBe('merge_candidates')
    expect(u.searchParams.get('targetType')).toBe('rule_card')
    expect(u.searchParams.get('qualityTier')).toBe('silver')
    await page.screenshot({ path: shot('05-back-to-queue-preserved-context.png'), fullPage: true })

    await page.goto(
      `/review/compare?aType=${enc('rule_card')}&aId=${enc('rule:merge:audit:a')}&bType=${enc('rule_card')}&bId=${enc('rule:merge:audit:b')}`,
    )
    await expect(page.getByRole('heading', { name: 'Compare' })).toBeVisible({ timeout: 15_000 })
    await expect(page.getByText('Summary for rule:merge:audit:a')).toBeVisible({ timeout: 15_000 })
    await expect(page.getByText('Summary for rule:merge:audit:b')).toBeVisible()
    await page.screenshot({ path: shot('06-compare-from-proposal-context.png'), fullPage: true })
  })
})
