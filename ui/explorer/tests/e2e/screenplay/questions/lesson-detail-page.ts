import type { Page } from '@playwright/test'

export const LessonDetailPage = {
  lessonHeading: async (page: Page) => (await page.locator('main h1').first().textContent()) ?? '',
  hasCopyLink: async (page: Page) => page.getByRole('button', { name: 'Copy link' }).isVisible(),
  hasSupportBasisDistribution: async (page: Page) =>
    page.getByRole('heading', { name: 'Support Basis Distribution' }).isVisible(),
  hasTopConcepts: async (page: Page) => page.getByTestId('top-concepts').isVisible(),
  topRuleCount: async (page: Page) => page.locator('article').count(),
}
