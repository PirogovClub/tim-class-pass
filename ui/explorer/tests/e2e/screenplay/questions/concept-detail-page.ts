import type { Page } from '@playwright/test'

export const ConceptDetailPage = {
  hasConceptId: async (page: Page, conceptId: string) => page.getByRole('heading', { name: conceptId }).isVisible(),
  hasAliases: async (page: Page) => page.getByTestId('concept-aliases').isVisible(),
  hasLessonCoverage: async (page: Page) => page.getByRole('heading', { name: 'Lesson Coverage' }).isVisible(),
  hasCountPills: async (page: Page) => page.locator('main').getByText(/\d+ rules/).first().isVisible(),
  neighborLinkCount: async (page: Page) => page.getByTestId('concept-neighbors').locator('a[href^="/concept/"]').count(),
}
