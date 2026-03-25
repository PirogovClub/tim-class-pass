import { expect, test } from '@playwright/test'
import { Actor } from './screenplay/actor'
import { ConceptDetailPage } from './screenplay/questions/concept-detail-page'
import { ClickNeighbor } from './screenplay/tasks/click-neighbor'
import { OpenConceptDetail } from './screenplay/tasks/open-concept-detail'
import type { ConceptDetailResponse, ConceptNeighbor } from '@/lib/api/types'
import { loadFixture, mockJsonRoute } from './support/browser-fixtures'

const conceptDetail = loadFixture<ConceptDetailResponse>('concept-detail.json')
const conceptNeighbors = loadFixture<ConceptNeighbor[]>('concept-neighbors.json')
const conceptId = conceptDetail.concept_id
const firstNeighborId = conceptNeighbors[0]?.concept_id ?? 'node:trade_management'

test('open concept detail and follow a neighbor', async ({ page }) => {
  await mockJsonRoute(page, `**/browser/concept/${encodeURIComponent(conceptId)}`, conceptDetail)
  await mockJsonRoute(page, `**/browser/concept/${encodeURIComponent(conceptId)}/neighbors`, conceptNeighbors)
  await mockJsonRoute(page, `**/browser/concept/${encodeURIComponent(firstNeighborId)}`, {
    ...conceptDetail,
    concept_id: firstNeighborId,
    aliases: [],
    neighbors: [],
  })
  await mockJsonRoute(page, `**/browser/concept/${encodeURIComponent(firstNeighborId)}/neighbors`, [])

  const analyst = new Actor('Analyst', page)
  await analyst.attemptsTo(OpenConceptDetail(conceptId))
  await expect(page.getByRole('heading', { name: conceptId })).toBeVisible()
  expect(await analyst.asks((p) => ConceptDetailPage.hasConceptId(p, conceptId))).toBe(true)
  expect(await analyst.asks(ConceptDetailPage.hasAliases)).toBe(true)
  expect(await analyst.asks(ConceptDetailPage.hasLessonCoverage)).toBe(true)
  expect(await analyst.asks(ConceptDetailPage.hasCountPills)).toBe(true)
  const count = await analyst.asks(ConceptDetailPage.neighborLinkCount)
  expect(count).toBeGreaterThan(0)
  const neighborName =
    (await page.getByTestId('concept-neighbors').locator('a[href^="/concept/"]').first().textContent()) ?? ''
  await analyst.attemptsTo(ClickNeighbor(neighborName))
  await expect(page.locator('main h1').first()).toBeVisible()
})
