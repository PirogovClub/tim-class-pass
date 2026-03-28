import type { Page } from '@playwright/test'

export function OpenResultByIndex(index: number) {
  return async (page: Page) => {
    await page.locator('article a').nth(index).click()
    await page.waitForLoadState('domcontentloaded')
  }
}
