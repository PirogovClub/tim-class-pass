import type { Page } from '@playwright/test'

export const RuleDetailPage = {
  heading: async (page: Page) => (await page.locator('main h1').first().textContent()) ?? '',
  hasBackToSearch: async (page: Page) => page.getByRole('link', { name: 'Back to search' }).isVisible(),
  hasCopyLink: async (page: Page) => page.getByRole('button', { name: 'Copy link' }).isVisible(),
  hasTimestamps: async (page: Page) => page.getByRole('heading', { name: 'Timestamps' }).isVisible(),
  hasLinkedEvidence: async (page: Page) => page.getByTestId('linked-evidence').isVisible(),
  hasRelatedRules: async (page: Page) => page.getByRole('heading', { name: /Related Rules/i }).isVisible(),
}
