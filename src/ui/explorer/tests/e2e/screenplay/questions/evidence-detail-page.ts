import type { Page } from '@playwright/test'

export const EvidenceDetailPage = {
  heading: async (page: Page) => (await page.locator('main h1').first().textContent()) ?? '',
  hasBackToSearch: async (page: Page) => page.getByRole('link', { name: 'Back to search' }).isVisible(),
  hasCopyLink: async (page: Page) => page.getByRole('button', { name: 'Copy link' }).isVisible(),
  hasSnippet: async (page: Page) => page.getByTestId('evidence-snippet').isVisible(),
  hasTimestamps: async (page: Page) => page.getByRole('heading', { name: 'Timestamps' }).isVisible(),
  hasSourceRules: async (page: Page) => page.getByTestId('source-rules').isVisible(),
}
