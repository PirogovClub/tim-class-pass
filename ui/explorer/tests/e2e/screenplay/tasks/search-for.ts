import type { Page } from '@playwright/test'

export function SearchFor(query: string) {
  return async (page: Page) => {
    const input = page.getByRole('searchbox')
    await input.fill(query)
    await page.getByRole('button', { name: 'Search', exact: true }).click()
    await page.waitForURL((url) => url.searchParams.get('q') === query)
  }
}
