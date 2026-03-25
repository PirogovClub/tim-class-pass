import { expect, test } from '@playwright/test'

import type {
  BrowserResultCard,
  BrowserSearchResponse,
  ConceptDetailResponse,
  ConceptNeighbor,
  ConceptRuleListResponse,
  LessonCompareResponse,
  RelatedRulesResponse,
  RuleCompareResponse,
  RuleDetailResponse,
} from '@/lib/api/types'

import { loadFixture, mockJsonRoute } from './support/browser-fixtures'

const compareRules = loadFixture<RuleCompareResponse>('compare-rules.json')
const compareLessons = loadFixture<LessonCompareResponse>('compare-lessons.json')
const relatedRules = loadFixture<RelatedRulesResponse>('related-rules.json')
const conceptDetail = loadFixture<ConceptDetailResponse>('concept-detail.json')
const conceptNeighbors = loadFixture<ConceptNeighbor[]>('concept-neighbors.json')
const conceptRules = loadFixture<ConceptRuleListResponse>('concept-rules.json')
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
    by_lesson: {
      lesson_alpha: 1,
      lesson_beta: 1,
    },
    by_concept: {},
    by_support_basis: { transcript_plus_visual: 2 },
    by_evidence_requirement: { optional: 1, required: 1 },
    by_teaching_mode: { example: 1, mixed: 1 },
  },
  hit_count: 2,
}

test.describe('Compare and traversal workflows', () => {
  test('select two rules from search results, open compare, and navigate back', async ({ page }) => {
    await mockJsonRoute(page, '**/browser/search', searchRulesResponse)
    await mockJsonRoute(page, '**/browser/facets**', searchRulesResponse.facets)
    await mockJsonRoute(page, '**/browser/compare/rules', compareRules)

    await page.goto('/search?q=compare%20rules')
    await expect(page.getByText(/2 hits?/)).toBeVisible()

    await page.getByRole('button', { name: /add to compare/i }).nth(0).click()
    await page.getByRole('button', { name: /add to compare/i }).nth(0).click()
    await expect(page.getByText('2 rules selected')).toBeVisible()

    await page.getByRole('button', { name: /open compare/i }).click()
    await expect(page).toHaveURL(/\/compare\/rules\?ids=/)
    await expect(page.getByTestId('rule-compare-summary')).toBeVisible()

    await page.goBack()
    await expect(page).toHaveURL(/\/search/)
  })

  test('open a rule detail and navigate to related rules', async ({ page }) => {
    const encodedRuleId = encodeURIComponent(relatedRules.source_doc_id)
    await mockJsonRoute(page, `**/browser/rule/${encodedRuleId}`, {
      ...ruleDetail,
      doc_id: relatedRules.source_doc_id,
      title: 'Accumulation near levels',
      visual_summary: null,
      frame_ids: [],
    })
    await mockJsonRoute(page, `**/browser/rule/${encodedRuleId}/related`, relatedRules)

    await page.goto(`/rule/${encodeURIComponent(relatedRules.source_doc_id)}`)
    await page.getByRole('link', { name: /related rules/i }).click()

    await expect(page).toHaveURL(/\/related$/)
    await expect(page.getByTestId('related-group-same_lesson')).toBeVisible()
  })

  test('open concept detail and navigate to concept rules', async ({ page }) => {
    await mockJsonRoute(page, `**/browser/concept/${encodeURIComponent(conceptDetail.concept_id)}`, conceptDetail)
    await mockJsonRoute(page, `**/browser/concept/${encodeURIComponent(conceptDetail.concept_id)}/neighbors`, conceptNeighbors)
    await mockJsonRoute(page, `**/browser/concept/${encodeURIComponent(conceptDetail.concept_id)}/rules`, conceptRules)

    await page.goto(`/concept/${encodeURIComponent(conceptDetail.concept_id)}`)
    await page.getByRole('link', { name: /all rules/i }).click()

    await expect(page).toHaveURL(/\/rules$/)
    await expect(page.getByTestId('concept-rules-list')).toBeVisible()
  })

  test('compare two lessons and show shared concept section', async ({ page }) => {
    await mockJsonRoute(page, '**/browser/compare/lessons', compareLessons)

    await page.goto('/compare/lessons?ids=lesson_alpha,lesson_beta')

    await expect(page.getByTestId('lesson-overlap-panel')).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Shared concepts' })).toBeVisible()
    await expect(page.getByText('node:breakout').first()).toBeVisible()
  })

  test('deep-link directly to rule compare URL', async ({ page }) => {
    await mockJsonRoute(page, '**/browser/compare/rules', compareRules)

    const ids = compareRules.rules.map((rule) => rule.doc_id).join(',')
    await page.goto(`/compare/rules?ids=${encodeURIComponent(ids)}`)

    await expect(page.getByTestId('rule-compare-table')).toBeVisible()
    await expect(page.getByText(compareRules.rules[0]?.title ?? '')).toBeVisible()
  })
})
