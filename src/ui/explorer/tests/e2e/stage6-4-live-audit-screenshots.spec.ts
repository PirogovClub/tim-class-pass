/* eslint-disable playwright/no-skipped-test, playwright/no-conditional-in-test -- env-gated live corpus audit */
/* eslint-disable simple-import-sort/imports -- @typescript-eslint inline type-import autofix breaks `test` token */
/**
 * Live Stage 6.4 audit screenshots — real `/browser/*` via Vite preview proxy (no route mocks).
 *
 * Requires:
 * - Same RAG corpus the bundle uses (`output_rag` built; API initialized with that data).
 * - Browser API reachable at VITE_BROWSER_API_BASE (default http://127.0.0.1:8000).
 *
 * Run: STAGE64_LIVE_E2E=1 npm run audit:screenshots:6.4:live
 * Outputs: ui/explorer/stage6-4-screenshots-live-out/*.png
 */
import { existsSync, writeFileSync } from 'node:fs'

import { expect, test, type Page } from '@playwright/test'

import {
  firstCardOfType,
  flattenSearchCards,
  pickConceptId,
  pickEventId,
  pickEvidenceId,
  type RuleDetailJson,
} from './support/stage64-live-discovery'
import { shotPath, stage64LiveScreenshotDir } from './support/stage64-screenshot-dirs'

const live = process.env.STAGE64_LIVE_E2E === '1'

const SEARCH_TRIES = ['stop', 'торговля', 'урок', 'price', 'level', 'risk']

const shotDir = stage64LiveScreenshotDir()

async function saveFullPage(page: Page, filename: string) {
  const buf = await page.screenshot({ fullPage: true })
  if (buf.length === 0) {
    throw new Error(`Empty screenshot for ${filename}`)
  }
  const target = shotPath(shotDir, filename)
  writeFileSync(target, buf)
  if (!existsSync(target)) {
    throw new Error(`Screenshot not written: ${target}`)
  }
}

test.describe.serial('stage 6.4 LIVE audit screenshots', () => {
  test.skip(!live, 'Set STAGE64_LIVE_E2E=1 and start the browser API (see RUN_STAGE6_4_AUDIT.md).')

  test('capture analyst UI against live API', async ({ page }) => {
    let flatCards: ReturnType<typeof flattenSearchCards> = []
    let ruleId = ''

    for (const q of SEARCH_TRIES) {
      const trimmed = q.trim()
      if (!trimmed) {
        continue
      }
      const respPromise = page.waitForResponse(
        (r) =>
          r.url().includes('/browser/search') &&
          r.request().method() === 'POST' &&
          r.status() === 200,
      )
      await page.goto(`/search?q=${encodeURIComponent(trimmed)}`)
      const resp = await respPromise
      const body = (await resp.json()) as Record<string, unknown>
      const cards = flattenSearchCards(body)
      const rule = firstCardOfType(cards, 'rule_card')
      if (!rule) {
        continue
      }
      flatCards = cards
      ruleId = rule.doc_id
      break
    }

    expect(ruleId, 'live search must return at least one rule_card').toBeTruthy()

    await expect(page.getByRole('region', { name: /search results/i })).toBeVisible()
    await saveFullPage(page, 'live-01-search.png')

    const ruleRespPromise = page.waitForResponse(
      (r) => r.url().includes('/browser/rule/') && r.request().method() === 'GET' && r.status() === 200,
    )
    await page.goto(`/rule/${encodeURIComponent(ruleId)}`)
    const ruleHttp = await ruleRespPromise
    const ruleJson = (await ruleHttp.json()) as RuleDetailJson
    expect(ruleJson.lesson_id, 'rule detail should include lesson_id').toBeTruthy()

    await expect(page.getByTestId('rule-doc-id')).toBeVisible()
    await saveFullPage(page, 'live-02-rule-detail.png')

    const evidenceId = pickEvidenceId(ruleJson, flatCards)
    const eventFromRule = pickEventId(ruleJson, flatCards)
    const eventFromSearch = firstCardOfType(flatCards, 'knowledge_event')?.doc_id
    const eventId = eventFromRule ?? eventFromSearch ?? null
    const conceptId = pickConceptId(ruleJson, flatCards)
    const lessonId = ruleJson.lesson_id!

    expect(evidenceId, 'need evidence id for live evidence screenshot').toBeTruthy()
    expect(conceptId, 'need concept id for live concept screenshot').toBeTruthy()
    expect(eventId, 'need a knowledge_event for live event screenshot').toBeTruthy()

    await page.goto(`/evidence/${encodeURIComponent(evidenceId!)}`)
    await expect(page.getByTestId('evidence-doc-id')).toBeVisible()
    await saveFullPage(page, 'live-03-evidence-detail.png')

    await page.goto(`/event/${encodeURIComponent(eventId!)}`)
    await expect(page.getByTestId('event-doc-id')).toBeVisible()
    await saveFullPage(page, 'live-04-event-detail.png')

    await page.goto(`/concept/${encodeURIComponent(conceptId!)}`)
    await expect(page.getByTestId('concept-id')).toBeVisible()
    await saveFullPage(page, 'live-05-concept-detail.png')

    await page.goto(`/lesson/${encodeURIComponent(lessonId)}`)
    await expect(page.getByTestId('lesson-id')).toBeVisible()
    await saveFullPage(page, 'live-06-lesson-detail.png')

    const compareA = { unit_type: 'rule_card' as const, doc_id: ruleId }
    const compareB = { unit_type: 'knowledge_event' as const, doc_id: eventId! }

    await page.addInitScript((stored) => {
      sessionStorage.setItem('explorer.compare.units', JSON.stringify(stored))
    }, [compareA, compareB])
    await page.goto('/compare/units')
    await expect(page.getByTestId('compare-units-grid')).toBeVisible()
    await saveFullPage(page, 'live-07-compare-units.png')

    expect(existsSync(shotPath(shotDir, 'live-07-compare-units.png'))).toBe(true)
  })
})
