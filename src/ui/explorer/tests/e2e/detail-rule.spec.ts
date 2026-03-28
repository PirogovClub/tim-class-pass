import { expect, test } from '@playwright/test'

import type { RuleDetailResponse } from '@/lib/api/types'

import { Actor } from './screenplay/actor'
import { RuleDetailPage } from './screenplay/questions/rule-detail-page'
import { NavigateTo } from './screenplay/tasks/navigate-to'
import { loadFixture, mockJsonRoute } from './support/browser-fixtures'

const ruleDetail = loadFixture<RuleDetailResponse>('rule-detail.json')
const ruleId = ruleDetail.doc_id

test('open rule detail directly', async ({ page }) => {
  await mockJsonRoute(page, '**/browser/rule/**', ruleDetail)

  const analyst = new Actor('Analyst', page)
  await analyst.attemptsTo(NavigateTo(`/rule/${encodeURIComponent(ruleId)}`))
  expect(await analyst.asks(RuleDetailPage.heading)).not.toEqual('')
  expect(await analyst.asks(RuleDetailPage.hasBackToSearch)).toBe(true)
  expect(await analyst.asks(RuleDetailPage.hasCopyLink)).toBe(true)
  expect(await analyst.asks(RuleDetailPage.hasTimestamps)).toBe(true)
  expect(await analyst.asks(RuleDetailPage.hasLinkedEvidence)).toBe(true)
  expect(await analyst.asks(RuleDetailPage.hasRelatedRules)).toBe(true)
  await expect(page.getByRole('heading', { name: /Timestamps/i })).toBeVisible()
})
