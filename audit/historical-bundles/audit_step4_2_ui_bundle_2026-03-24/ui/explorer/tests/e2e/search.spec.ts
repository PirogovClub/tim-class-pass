import { expect, test } from '@playwright/test'
import { Actor } from './screenplay/actor'
import { SearchResults } from './screenplay/questions/search-results'
import { NavigateTo } from './screenplay/tasks/navigate-to'
import { OpenResultByIndex } from './screenplay/tasks/open-result'
import { SearchFor } from './screenplay/tasks/search-for'
import type { BrowserSearchResponse, RuleDetailResponse } from '@/lib/api/types'
import { loadFixture, mockJsonRoute, mockSearchRoutes } from './support/browser-fixtures'

const timeframeSearch = loadFixture<BrowserSearchResponse>('search-timeframe.json')
const ruleDetail = loadFixture<RuleDetailResponse>('rule-detail.json')

test.describe('Search page', () => {
  test('query returns cards', async ({ page }) => {
    await mockSearchRoutes(page, 'search-stop-loss.json')

    const analyst = new Actor('Analyst', page)
    await analyst.attemptsTo(NavigateTo('/search'), SearchFor('stop loss'))
    await expect(page.getByText(/\d+ hits?/)).toBeVisible()
    expect(await analyst.asks(SearchResults.count)).toBeGreaterThan(0)
  })

  test('search result opens a rule detail page', async ({ page }) => {
    await mockSearchRoutes(page, 'search-timeframe.json')
    await mockJsonRoute(page, '**/browser/rule/**', {
      ...ruleDetail,
      doc_id: timeframeSearch.cards[0]?.doc_id ?? ruleDetail.doc_id,
      title: timeframeSearch.cards[0]?.title ?? ruleDetail.title,
    })

    const analyst = new Actor('Analyst', page)
    await analyst.attemptsTo(NavigateTo('/search'), SearchFor(timeframeSearch.query))
    await expect(page.getByText(/\d+ hits?/)).toBeVisible()
    await analyst.attemptsTo(OpenResultByIndex(0))
    await expect(page).toHaveURL(/\/rule\//)
    await expect(page.locator('main h1').first()).toBeVisible()
  })
})
