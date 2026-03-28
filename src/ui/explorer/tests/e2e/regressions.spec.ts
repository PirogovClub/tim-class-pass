import { expect, test } from '@playwright/test'

import { Actor } from './screenplay/actor'
import { NavigateTo } from './screenplay/tasks/navigate-to'

test('invalid frontend route shows not found state', async ({ page }) => {
  const analyst = new Actor('Analyst', page)
  await analyst.attemptsTo(NavigateTo('/definitely-missing-route'))
  await expect(page.getByRole('heading', { name: 'Not Found' })).toBeVisible()
})
