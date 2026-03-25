import { expect, test } from '@playwright/test'
import { Actor } from './screenplay/actor'
import { EvidenceDetailPage } from './screenplay/questions/evidence-detail-page'
import { NavigateTo } from './screenplay/tasks/navigate-to'
import type { EvidenceDetailResponse } from '@/lib/api/types'
import { loadFixture, mockJsonRoute } from './support/browser-fixtures'

const evidenceDetail = loadFixture<EvidenceDetailResponse>('evidence-detail.json')
const evidenceId = evidenceDetail.doc_id

test('open evidence detail directly', async ({ page }) => {
  await mockJsonRoute(page, '**/browser/evidence/**', evidenceDetail)

  const analyst = new Actor('Analyst', page)
  await analyst.attemptsTo(NavigateTo(`/evidence/${encodeURIComponent(evidenceId)}`))
  expect(await analyst.asks(EvidenceDetailPage.heading)).toContain('Evidence:')
  expect(await analyst.asks(EvidenceDetailPage.hasBackToSearch)).toBe(true)
  expect(await analyst.asks(EvidenceDetailPage.hasCopyLink)).toBe(true)
  expect(await analyst.asks(EvidenceDetailPage.hasSnippet)).toBe(true)
  expect(await analyst.asks(EvidenceDetailPage.hasTimestamps)).toBe(true)
  expect(await analyst.asks(EvidenceDetailPage.hasSourceRules)).toBe(true)
})
