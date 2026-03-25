import type { Page } from '@playwright/test'

export async function gotoWithRetry(page: Page, path: string, attempts = 3) {
  let lastError: unknown

  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    try {
      await page.goto(path, { waitUntil: 'domcontentloaded' })
      return
    } catch (error) {
      lastError = error
      if (attempt === attempts) {
        throw error
      }
    }
  }

  throw lastError
}

export function NavigateTo(path: string) {
  return async (page: Page) => {
    await gotoWithRetry(page, path)
  }
}
