import type { Page } from '@playwright/test'

export function ClickNeighbor(name: string) {
  return async (page: Page) => {
    await page.getByRole('link', { name }).first().click()
    await page.waitForLoadState('domcontentloaded')
  }
}
