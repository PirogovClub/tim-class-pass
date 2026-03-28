/**
 * Stage 5.7 audit screenshot → audit/stage5_7_audit_bundle_2026-03-26/screenshots/
 * From ui/explorer: npm run build && npm run audit:screenshots:5.7
 */
import { mkdirSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { expect, test } from '@playwright/test'

const shotDir = join(
  dirname(fileURLToPath(import.meta.url)),
  '../../../../audit/stage5_7_audit_bundle_2026-03-26/screenshots',
)
mkdirSync(shotDir, { recursive: true })
const shot = (name: string) => join(shotDir, name)

const summaryBody = {
  computed_at: '2026-03-26T12:00:00+00:00',
  total_supported_review_targets: 120,
  unresolved_count: 44,
  gold_count: 12,
  silver_count: 8,
  bronze_count: 3,
  tier_unresolved_count: 40,
  rejected_count: 1,
  unsupported_count: 2,
  canonical_family_count: 5,
  merge_decision_count: 4,
}

const queuesBody = {
  computed_at: '2026-03-26T12:00:00+00:00',
  unresolved_queue_size: 44,
  deferred_rule_cards: 2,
  proposal_queue_open_counts: [
    { queue_name: 'high_confidence_duplicates', open_count: 3 },
    { queue_name: 'merge_candidates', open_count: 5 },
    { queue_name: 'canonical_family_candidates', open_count: 1 },
  ],
  unresolved_by_target_type: { rule_card: 38, evidence_link: 4, concept_link: 1, related_rule_relation: 1 },
  unresolved_backlog_by_tier: { gold: 0, silver: 2, bronze: 1, unresolved: 30, none: 11 },
  oldest_unresolved_last_reviewed_at: '2026-03-20T10:15:00+00:00',
  oldest_unresolved_age_seconds: 518400,
}

const proposalsBody = {
  computed_at: '2026-03-26T12:00:00+00:00',
  total_proposals: 24,
  open_proposals: 6,
  accepted_proposals: 10,
  dismissed_proposals: 5,
  stale_proposals: 2,
  superseded_proposals: 1,
  stale_total: 3,
  terminal_proposals: 18,
  acceptance_rate_closed: 0.555556,
  acceptance_rate_all: 0.416667,
  median_seconds_to_disposition: 3600,
  by_proposal_type: [
    {
      proposal_type: 'duplicate_candidate',
      total: 10,
      open: 2,
      accepted: 5,
      dismissed: 2,
      stale: 1,
      superseded: 0,
      terminal: 8,
      acceptance_rate_closed: 0.625,
      acceptance_rate_all: 0.5,
    },
    {
      proposal_type: 'merge_candidate',
      total: 9,
      open: 3,
      accepted: 4,
      dismissed: 2,
      stale: 0,
      superseded: 1,
      terminal: 7,
      acceptance_rate_closed: 0.571429,
      acceptance_rate_all: 0.444444,
    },
    {
      proposal_type: 'canonical_family_candidate',
      total: 5,
      open: 1,
      accepted: 1,
      dismissed: 1,
      stale: 1,
      superseded: 0,
      terminal: 3,
      acceptance_rate_closed: 0.333333,
      acceptance_rate_all: 0.2,
    },
  ],
}

const throughputBody = {
  computed_at: '2026-03-26T12:00:00+00:00',
  window: '7d',
  window_start_utc: '2026-03-19T12:00:00+00:00',
  decision_count: 17,
  by_decision_type: [
    { decision_type: 'approve', count: 9 },
    { decision_type: 'needs_review', count: 4 },
    { decision_type: 'reject', count: 2 },
  ],
  by_reviewer_id: [
    { reviewer_id: 'human:alice', count: 11 },
    { reviewer_id: 'human:bob', count: 6 },
  ],
}

const coverageLessonsBody = {
  computed_at: '2026-03-26T12:00:00+00:00',
  explorer_available: true,
  note: null,
  buckets: [
    { bucket_id: 'lesson_risk', total_targets: 40, reviewed_not_unresolved: 22, coverage_ratio: 0.55 },
    { bucket_id: 'lesson_exec', total_targets: 25, reviewed_not_unresolved: 10, coverage_ratio: 0.4 },
  ],
}

const coverageConceptsBody = {
  ...coverageLessonsBody,
  buckets: [
    { bucket_id: 'concept:stop_loss', total_targets: 30, reviewed_not_unresolved: 18, coverage_ratio: 0.6 },
    { bucket_id: 'concept:position_sizing', total_targets: 18, reviewed_not_unresolved: 6, coverage_ratio: 0.333333 },
  ],
}

const flagsBody = {
  computed_at: '2026-03-26T12:00:00+00:00',
  explorer_available: true,
  note: null,
  summary: {
    ambiguity_rule_cards: 4,
    conflict_rule_split_required: 2,
    conflict_concept_invalid: 1,
    conflict_relation_invalid: 1,
  },
  by_lesson: [
    { bucket_id: 'lesson_risk', ambiguity_rule_cards: 2, conflict_rule_split_required: 1 },
    { bucket_id: 'lesson_exec', ambiguity_rule_cards: 1, conflict_rule_split_required: 0 },
  ],
  by_concept: [
    { bucket_id: 'concept:stop_loss', ambiguity_rule_cards: 2, conflict_rule_split_required: 1 },
  ],
}

test('Review metrics page (Stage 5.7 audit screenshot)', async ({ page }) => {
  await page.route('**/adjudication/metrics/summary**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(summaryBody),
    })
  })
  await page.route('**/adjudication/metrics/queues**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(queuesBody),
    })
  })
  await page.route('**/adjudication/metrics/proposals**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(proposalsBody),
    })
  })
  await page.route('**/adjudication/metrics/throughput**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(throughputBody),
    })
  })
  await page.route('**/adjudication/metrics/coverage/lessons**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(coverageLessonsBody),
    })
  })
  await page.route('**/adjudication/metrics/coverage/concepts**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(coverageConceptsBody),
    })
  })
  await page.route('**/adjudication/metrics/flags**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(flagsBody),
    })
  })

  await page.goto('/review/metrics')
  await expect(page.getByRole('heading', { name: 'Review metrics' })).toBeVisible()
  await expect(page.getByText('Supported targets')).toBeVisible()
  await expect(page.getByText('120')).toBeVisible()
  await expect(page.getByText('Queue health')).toBeVisible()
  await expect(page.getByText(/high_confidence_duplicates: 3 open/)).toBeVisible()
  await expect(page.getByText('lesson_risk')).toBeVisible()
  await page.screenshot({ path: shot('01-review-metrics-page.png'), fullPage: true })
})
