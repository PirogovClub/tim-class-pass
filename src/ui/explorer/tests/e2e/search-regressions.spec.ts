import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { expect, type Page,test } from '@playwright/test'

import { Actor } from './screenplay/actor'
import { SearchResults } from './screenplay/questions/search-results'
import { NavigateTo } from './screenplay/tasks/navigate-to'
import { SearchFor } from './screenplay/tasks/search-for'

type SearchFixture = {
  facets: Record<string, Record<string, number>>
}

function loadFixture(name: string) {
  return JSON.parse(
    readFileSync(fileURLToPath(new URL(`../../src/test/fixtures/${name}`, import.meta.url)), 'utf-8'),
  ) as SearchFixture
}

async function mockSearch(page: Page, fixtureName: string) {
  const fixture = loadFixture(fixtureName)

  await page.route('**/browser/search', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(fixture),
    })
  })

  await page.route('**/browser/facets**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(fixture.facets),
    })
  })
}

test.describe('Search behavior regressions', () => {
  test('search "Пример постановки стоп-лосса" stays evidence-first in browser flow', async ({ page }) => {
    await mockSearch(page, 'search-stop-loss.json')

    const analyst = new Actor('Analyst', page)
    await analyst.attemptsTo(NavigateTo('/search'), SearchFor('Пример постановки стоп-лосса'))

    await expect(page.getByText(/\d+ hits?/)).toBeVisible()
    expect(await analyst.asks(SearchResults.firstCardUnitType)).toBe('Evidence')
  })

  test('search "Правила торговли на разных таймфреймах" stays rule-first in browser flow', async ({ page }) => {
    await mockSearch(page, 'search-timeframe.json')

    const analyst = new Actor('Analyst', page)
    await analyst.attemptsTo(NavigateTo('/search'), SearchFor('Правила торговли на разных таймфреймах'))

    await expect(page.getByText(/\d+ hits?/)).toBeVisible()
    expect(await analyst.asks(SearchResults.firstCardUnitType)).toBe('Rule')
  })

  test('search "Как определить дневной уровень?" stays actionable-first in browser flow', async ({ page }) => {
    await mockSearch(page, 'search-daily-level.json')

    const analyst = new Actor('Analyst', page)
    await analyst.attemptsTo(NavigateTo('/search'), SearchFor('Как определить дневной уровень?'))

    await expect(page.getByText(/\d+ hits?/)).toBeVisible()
    expect(await analyst.asks(SearchResults.firstCardUnitType)).toBe('Rule')
  })
})
