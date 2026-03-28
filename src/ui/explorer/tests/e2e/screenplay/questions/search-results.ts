import type { Page } from '@playwright/test'
export const SearchResults = {
  count: async (page: Page) => page.locator('article').count(),
  firstCardUnitType: async (page: Page) => (await page.getByTestId('unit-type-badge').first().textContent()) ?? '',
}
