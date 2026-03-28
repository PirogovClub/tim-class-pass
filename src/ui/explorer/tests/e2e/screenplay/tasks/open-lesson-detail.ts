import type { Page } from '@playwright/test'

import { gotoWithRetry } from './navigate-to'

export function OpenLessonDetail(lessonId: string) {
  return async (page: Page) => {
    await gotoWithRetry(page, `/lesson/${encodeURIComponent(lessonId)}`)
  }
}
