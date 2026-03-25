import type { Page } from '@playwright/test'
import { gotoWithRetry } from './navigate-to'

export function OpenConceptDetail(conceptId: string) {
  return async (page: Page) => {
    await gotoWithRetry(page, `/concept/${encodeURIComponent(conceptId)}`)
  }
}
