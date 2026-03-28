/**
 * Stage 6.4 explorer audit screenshots → audit/stage6_4_explorer_screenshots/
 * Run from ui/explorer: npm run build && npm run audit:screenshots:6.4
 */
/* eslint-disable simple-import-sort/imports -- @typescript-eslint inline type-import autofix breaks `test` token */
import { existsSync, writeFileSync } from 'node:fs'

import { expect, test, type Page } from '@playwright/test'

import { loadFixture, mockJsonRoute } from './support/browser-fixtures'
import { shotPath, stage64MockScreenshotDir } from './support/stage64-screenshot-dirs'

/** Mocked JSON — UI proof only; see `stage6-4-live-audit-screenshots.spec.ts` for live corpus shots. */
const shotDir = stage64MockScreenshotDir()
const shot = (name: string) => shotPath(shotDir, name)

async function saveFullPage(page: Page, filename: string) {
  const buf = await page.screenshot({ fullPage: true })
  if (buf.length === 0) {
    throw new Error(`Empty screenshot for ${filename}`)
  }
  const target = shot(filename)
  writeFileSync(target, buf)
  if (!existsSync(target)) {
    throw new Error(`Screenshot not written: ${target}`)
  }
}

const searchStopLoss = loadFixture<Record<string, unknown>>('search-stop-loss.json')
const ruleDetail = loadFixture<Record<string, unknown>>('rule-detail.json')
const evidenceDetail = loadFixture<Record<string, unknown>>('evidence-detail.json')
const eventDetail = loadFixture<Record<string, unknown>>('event-detail.json')
const conceptDetail = loadFixture<Record<string, unknown>>('concept-detail.json')
const conceptNeighbors = loadFixture<unknown[]>('concept-neighbors.json')
const lessonDetail = loadFixture<Record<string, unknown>>('lesson-detail.json')
const facets = loadFixture<Record<string, unknown>>('facets.json')
const unitCompare = loadFixture<Record<string, unknown>>('unit-compare.json')

const ruleId = String(ruleDetail.doc_id)
const evidenceId = String(evidenceDetail.doc_id)
const eventId = String(eventDetail.doc_id)
const conceptId = String(conceptDetail.concept_id)
const lessonId = String(lessonDetail.lesson_id)

test.describe.serial('stage 6.4 audit screenshots', () => {
  test('capture analyst browser pages', async ({ page }) => {
    await mockJsonRoute(page, '**/browser/search**', searchStopLoss)
    await mockJsonRoute(page, '**/browser/facets**', facets)
    await mockJsonRoute(page, `**/browser/rule/${encodeURIComponent(ruleId)}`, ruleDetail)
    await mockJsonRoute(page, `**/browser/evidence/${encodeURIComponent(evidenceId)}`, evidenceDetail)
    await mockJsonRoute(page, `**/browser/event/${encodeURIComponent(eventId)}`, eventDetail)
    await mockJsonRoute(page, `**/browser/concept/${encodeURIComponent(conceptId)}`, conceptDetail)
    await mockJsonRoute(
      page,
      `**/browser/concept/${encodeURIComponent(conceptId)}/neighbors`,
      conceptNeighbors,
    )
    await mockJsonRoute(page, `**/browser/lesson/${encodeURIComponent(lessonId)}`, lessonDetail)
    await mockJsonRoute(page, '**/browser/compare/units', unitCompare)
    await mockJsonRoute(page, '**/rag/search/explain', {
      search_response: { query: 'x', top_hits: [] },
      retrieval_trace: { per_hit_scores: [], note: 'fixture' },
    })

    await page.goto('/search?q=stop')
    await expect(page.getByRole('region', { name: /search results/i })).toBeVisible()
    await saveFullPage(page, '01-search.png')

    await page.goto(`/rule/${encodeURIComponent(ruleId)}`)
    await expect(page.getByTestId('rule-doc-id')).toBeVisible()
    await saveFullPage(page, '02-rule-detail.png')

    await page.goto(`/evidence/${encodeURIComponent(evidenceId)}`)
    await expect(page.getByTestId('evidence-doc-id')).toBeVisible()
    await saveFullPage(page, '03-evidence-detail.png')

    await page.goto(`/event/${encodeURIComponent(eventId)}`)
    await expect(page.getByTestId('event-doc-id')).toBeVisible()
    await saveFullPage(page, '04-event-detail.png')

    await page.goto(`/concept/${encodeURIComponent(conceptId)}`)
    await expect(page.getByTestId('concept-id')).toBeVisible()
    await saveFullPage(page, '05-concept-detail.png')

    await page.goto(`/lesson/${encodeURIComponent(lessonId)}`)
    await expect(page.getByTestId('lesson-id')).toBeVisible()
    await saveFullPage(page, '06-lesson-detail.png')

    const refs = (unitCompare.items as { unit_type: string; doc_id: string }[]).map((row) => ({
      unit_type: row.unit_type,
      doc_id: row.doc_id,
    }))
    await page.addInitScript((stored) => {
      sessionStorage.setItem('explorer.compare.units', JSON.stringify(stored))
    }, refs)
    await page.goto('/compare/units')
    await expect(page.getByTestId('compare-units-grid')).toBeVisible()
    await saveFullPage(page, '07-compare-units.png')

    expect(existsSync(shot('01-search.png'))).toBe(true)
  })
})
