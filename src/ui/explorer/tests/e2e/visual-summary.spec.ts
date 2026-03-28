import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { expect, test } from '@playwright/test'

import { gotoWithRetry } from './screenplay/tasks/navigate-to'

const evidenceDetail = JSON.parse(
  readFileSync(fileURLToPath(new URL('../../src/test/fixtures/evidence-detail.json', import.meta.url)), 'utf-8'),
) as {
  doc_id: string
  title: string
}

const pngBody = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9sX6n9kAAAAASUVORK5CYII=',
  'base64',
)

test('evidence detail opens clickable visual screenshots', async ({ page }) => {
  await page.route('**/browser/evidence/**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(evidenceDetail),
    })
  })
  await page.route('**/browser/frame/**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'image/png',
      body: pngBody,
    })
  })

  await gotoWithRetry(page, `/evidence/${encodeURIComponent(evidenceDetail.doc_id)}`)
  await expect(page.getByText(evidenceDetail.title)).toBeVisible()
  await page.getByRole('button', { name: /view 2 screenshots/i }).click()

  await expect(page.getByRole('dialog')).toBeVisible()
  await expect(page.getByAltText('Screenshot for Frame 000036')).toBeVisible()
  await page.getByRole('button', { name: 'Next screenshot' }).click()
  await expect(page.getByText('2 of 2')).toBeVisible()
})
