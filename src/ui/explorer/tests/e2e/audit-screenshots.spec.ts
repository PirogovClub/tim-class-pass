/**
 * Captures Step 4.3 audit screenshots into audit/step4-3-explorer/screenshots/
 * Run: npm run build && npm run audit:screenshots
 */
import { mkdirSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { expect, test } from '@playwright/test'

import type {
  BrowserResultCard,
  BrowserSearchResponse,
  ConceptDetailResponse,
  ConceptLessonListResponse,
  ConceptNeighbor,
  ConceptRuleListResponse,
  LessonCompareResponse,
  RelatedRulesResponse,
  RuleCompareResponse,
  RuleDetailResponse,
} from '@/lib/api/types'

import { loadFixture, mockJsonRoute } from './support/browser-fixtures'

// tests/e2e -> repo root is four levels up (e2e -> tests -> explorer -> ui -> root)
const shotDir = join(dirname(fileURLToPath(import.meta.url)), '../../../../audit/step4-3-explorer/screenshots')
mkdirSync(shotDir, { recursive: true })

const shot = (name: string) => join(shotDir, name)

const compareRules = loadFixture<RuleCompareResponse>('compare-rules.json')
const compareLessons = loadFixture<LessonCompareResponse>('compare-lessons.json')
const relatedRules = loadFixture<RelatedRulesResponse>('related-rules.json')
const conceptDetail = loadFixture<ConceptDetailResponse>('concept-detail.json')
const conceptNeighbors = loadFixture<ConceptNeighbor[]>('concept-neighbors.json')
const conceptRules = loadFixture<ConceptRuleListResponse>('concept-rules.json')
const conceptLessons = loadFixture<ConceptLessonListResponse>('concept-lessons.json')
const ruleDetail = loadFixture<RuleDetailResponse>('rule-detail.json')

const searchRulesResponse: BrowserSearchResponse = {
  query: 'compare rules',
  cards: compareRules.rules.map<BrowserResultCard>((rule) => ({
    doc_id: rule.doc_id,
    unit_type: 'rule_card',
    lesson_id: rule.lesson_id,
    title: rule.title,
    subtitle: rule.concept ?? '',
    snippet: rule.rule_text_ru,
    concept_ids: rule.canonical_concept_ids,
    support_basis: rule.support_basis,
    evidence_requirement: rule.evidence_requirement,
    teaching_mode: rule.teaching_mode,
    confidence_score: rule.confidence_score,
    timestamps: rule.timestamps,
    evidence_count: rule.linked_evidence_count,
    related_rule_count: rule.related_rule_count,
    related_event_count: rule.linked_source_event_count,
    score: null,
    why_retrieved: [],
  })),
  groups: {},
  facets: {
    by_unit_type: { rule_card: 2 },
    by_lesson: { lesson_alpha: 1, lesson_beta: 1 },
    by_concept: {},
    by_support_basis: { transcript_plus_visual: 2 },
    by_evidence_requirement: { optional: 1, required: 1 },
    by_teaching_mode: { example: 1, mixed: 1 },
  },
  hit_count: 2,
}

test.describe.serial('audit screenshots', () => {
  test('rule-compare, lesson-compare, related-rules, concept-rules, concept-lessons', async ({ page }) => {
    await mockJsonRoute(page, '**/browser/compare/rules', compareRules)
    await page.goto('/compare/rules?ids=' + encodeURIComponent(compareRules.rules.map((r) => r.doc_id).join(',')))
    await expect(page.getByTestId('rule-compare-table')).toBeVisible()
    await page.screenshot({ path: shot('rule-compare.png'), fullPage: true })

    await mockJsonRoute(page, '**/browser/compare/lessons', compareLessons)
    await page.goto('/compare/lessons?ids=lesson_alpha,lesson_beta')
    await expect(page.getByTestId('lesson-overlap-panel')).toBeVisible()
    await page.screenshot({ path: shot('lesson-compare.png'), fullPage: true })

    const enc = encodeURIComponent(relatedRules.source_doc_id)
    await mockJsonRoute(page, `**/browser/rule/${enc}`, {
      ...ruleDetail,
      doc_id: relatedRules.source_doc_id,
      title: 'Accumulation near levels',
      visual_summary: null,
      frame_ids: [],
    })
    await mockJsonRoute(page, `**/browser/rule/${enc}/related`, relatedRules)
    await page.goto(`/rule/${encodeURIComponent(relatedRules.source_doc_id)}/related`)
    await expect(page.getByTestId('related-group-same_lesson')).toBeVisible()
    await page.screenshot({ path: shot('related-rules.png'), fullPage: true })

    const c = encodeURIComponent(conceptDetail.concept_id)
    await mockJsonRoute(page, `**/browser/concept/${c}`, conceptDetail)
    await mockJsonRoute(page, `**/browser/concept/${c}/neighbors`, conceptNeighbors)
    await mockJsonRoute(page, `**/browser/concept/${c}/rules`, conceptRules)
    await page.goto(`/concept/${encodeURIComponent(conceptDetail.concept_id)}/rules`)
    await expect(page.getByTestId('concept-rules-list')).toBeVisible()
    await page.screenshot({ path: shot('concept-rules.png'), fullPage: true })

    await mockJsonRoute(page, `**/browser/concept/${c}/lessons`, conceptLessons)
    await page.goto(`/concept/${encodeURIComponent(conceptDetail.concept_id)}/lessons`)
    await expect(page.getByTestId('concept-lessons-list')).toBeVisible()
    await page.screenshot({ path: shot('concept-lessons.png'), fullPage: true })
  })

  test('audit-01 main search, audit-02 rule detail', async ({ page }) => {
    await mockJsonRoute(page, '**/browser/search', searchRulesResponse)
    await mockJsonRoute(page, '**/browser/facets**', searchRulesResponse.facets)
    await page.goto('/search?q=compare%20rules')
    await expect(page.getByText(/2 hits?/)).toBeVisible()
    await page.screenshot({ path: shot('audit-01-main-search.png'), fullPage: true })

    const enc = encodeURIComponent(relatedRules.source_doc_id)
    await mockJsonRoute(page, `**/browser/rule/${enc}`, {
      ...ruleDetail,
      doc_id: relatedRules.source_doc_id,
      title: 'Accumulation near levels',
      visual_summary: null,
      frame_ids: [],
    })
    await page.goto(`/rule/${encodeURIComponent(relatedRules.source_doc_id)}`)
    await expect(page.getByRole('link', { name: /related rules/i })).toBeVisible()
    await page.screenshot({ path: shot('audit-02-rule-detail.png'), fullPage: true })
  })

  test('audit-03 deep link URL note + screenshot', async ({ page }) => {
    await mockJsonRoute(page, '**/browser/compare/rules', compareRules)
    const ids = compareRules.rules.map((r) => r.doc_id).join(',')
    const path = `/compare/rules?ids=${encodeURIComponent(ids)}`
    await page.goto(path)
    await expect(page.getByTestId('rule-compare-summary')).toBeVisible()
    await page.screenshot({ path: shot('audit-03-compare-deeplink.png'), fullPage: true })
    const base = 'http://127.0.0.1:4173'
    writeFileSync(join(shotDir, 'audit-03-compare-deeplink-URL.txt'), `${base}${path}\n`, 'utf-8')
  })

  test('audit-04 empty compare (no ids)', async ({ page }) => {
    await page.goto('/compare/rules')
    await expect(page.getByRole('heading', { name: /need at least two rules/i, level: 3 })).toBeVisible()
    await page.screenshot({ path: shot('audit-04-compare-empty.png'), fullPage: true })
  })

  test('audit-05 loading skeleton', async ({ page }) => {
    const ids = compareRules.rules.map((r) => r.doc_id).join(',')
    let release!: () => void
    const gate = new Promise<void>((resolve) => {
      release = resolve
    })
    await page.route('**/browser/compare/rules', async (route) => {
      await gate
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(compareRules),
      })
    })
    await page.goto('/compare/rules?ids=' + encodeURIComponent(ids))
    await expect(page.locator('.animate-pulse').first()).toBeVisible({ timeout: 10_000 })
    await page.screenshot({ path: shot('audit-05-loading.png'), fullPage: true })
    release()
    await expect(page.getByTestId('rule-compare-table')).toBeVisible({ timeout: 15_000 })
    await page.unroute('**/browser/compare/rules')
  })

  test('audit-06 error panel', async ({ page }) => {
    const ids = compareRules.rules.map((r) => r.doc_id).join(',')
    await page.route('**/browser/compare/rules', (route) =>
      route.fulfill({ status: 500, contentType: 'application/json', body: '{"detail":"fail"}' }),
    )
    await page.goto('/compare/rules?ids=' + encodeURIComponent(ids))
    await expect(page.getByRole('alert')).toBeVisible({ timeout: 15_000 })
    await page.screenshot({ path: shot('audit-06-error.png'), fullPage: true })
    await page.unroute('**/browser/compare/rules')
  })

  test('audit-07 mobile narrow search + compare', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    await mockJsonRoute(page, '**/browser/search', searchRulesResponse)
    await mockJsonRoute(page, '**/browser/facets**', searchRulesResponse.facets)
    await page.goto('/search?q=compare%20rules')
    await expect(page.getByText(/2 hits?/)).toBeVisible()
    await page.screenshot({ path: shot('audit-07-mobile-narrow.png'), fullPage: true })

    await mockJsonRoute(page, '**/browser/compare/rules', compareRules)
    await page.goto('/compare/rules?ids=' + encodeURIComponent(compareRules.rules.map((r) => r.doc_id).join(',')))
    await expect(page.getByTestId('rule-compare-table')).toBeVisible()
    await page.screenshot({ path: shot('audit-07-mobile-compare.png'), fullPage: true })
  })
})
