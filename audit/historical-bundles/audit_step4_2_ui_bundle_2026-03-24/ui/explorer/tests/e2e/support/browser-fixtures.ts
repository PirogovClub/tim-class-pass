import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import type { Page } from '@playwright/test'

type SearchFixture = {
  facets: Record<string, Record<string, number>>
}

export function loadFixture<T>(name: string): T {
  return JSON.parse(
    readFileSync(fileURLToPath(new URL(`../../../src/test/fixtures/${name}`, import.meta.url)), 'utf-8'),
  ) as T
}

export async function mockJsonRoute(page: Page, pattern: string, body: unknown) {
  await page.route(pattern, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(body),
    })
  })
}

export async function mockSearchRoutes(page: Page, fixtureName: string) {
  const fixture = loadFixture<SearchFixture>(fixtureName)

  await mockJsonRoute(page, '**/browser/search', fixture)
  await mockJsonRoute(page, '**/browser/facets**', fixture.facets)

  return fixture
}
