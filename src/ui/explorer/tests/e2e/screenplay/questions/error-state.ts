import type { Page } from '@playwright/test'
export const ErrorState = { hasRuleNotFound: async (page: Page) => page.getByText('Rule not found').isVisible() }
