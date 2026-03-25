import { expect, test } from '@playwright/test'

import type { ReviewBundleResponse } from '@/lib/api/adjudication-schemas'

import { loadFixture } from './support/browser-fixtures'

const bundleAlpha = loadFixture<ReviewBundleResponse>('adjudication-bundle-with-family.json')
const bundleBeta = loadFixture<ReviewBundleResponse>('adjudication-bundle-no-family.json')

/** Works for absolute URLs and path-only URLs (Playwright may return either). */
function targetIdFromReviewBundleRequest(url: string): string | null {
  const q = url.includes('?') ? url.slice(url.indexOf('?') + 1) : ''
  const params = new URLSearchParams(q.split('#')[0])
  return params.get('target_id')
}

test.describe('Compare adjudication (rule_card pair)', () => {
  test('shows decision panel, prefills duplicate related id, submit refreshes state', async ({
    page,
  }) => {
    let postCount = 0
    const leftAfterDup: ReviewBundleResponse = {
      ...bundleAlpha,
      reviewed_state: {
        ...bundleAlpha.reviewed_state,
        current_status: 'duplicate',
        latest_decision_type: 'duplicate_of',
        duplicate_of_rule_id: bundleBeta.target_id,
        is_duplicate: true,
      },
    }

    await page.route('**/adjudication/review-bundle**', async (route) => {
      const tid = targetIdFromReviewBundleRequest(route.request().url())
      const body =
        tid === bundleAlpha.target_id
          ? postCount > 0
            ? leftAfterDup
            : bundleAlpha
          : bundleBeta
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(body),
      })
    })

    await page.route('**/adjudication/decision', async (route) => {
      postCount += 1
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          decision_id: 'dec_compare',
          target_type: 'rule_card',
          target_id: bundleAlpha.target_id,
          updated_state: leftAfterDup.reviewed_state,
        }),
      })
    })

    const q = `aType=rule_card&aId=${encodeURIComponent(bundleAlpha.target_id)}&bType=rule_card&bId=${encodeURIComponent(bundleBeta.target_id)}`
    await page.goto(`/review/compare?${q}`)

    await expect(page.getByTestId('compare-decision-panel')).toBeVisible({ timeout: 15_000 })
    await expect(page.getByTestId('compare-related-target-id')).toHaveValue(bundleBeta.target_id)

    await page.getByTestId('compare-submit-decision').click()
    await expect(page.getByText('Bundles updated below.')).toBeVisible({ timeout: 15_000 })
    await expect(page.getByText('Latest: duplicate_of')).toBeVisible()
  })

  test('merge_into prefills family id from opposite column', async ({ page }) => {
    const betaWithFamily: ReviewBundleResponse = {
      ...bundleBeta,
      family: {
        family_id: 'fam_beta_only',
        canonical_title: 'Beta family',
        status: 'active',
        member_count: 1,
      },
      reviewed_state: {
        ...bundleBeta.reviewed_state,
        canonical_family_id: 'fam_beta_only',
      },
    }

    await page.route('**/adjudication/review-bundle**', async (route) => {
      const tid = targetIdFromReviewBundleRequest(route.request().url())
      const body = tid === bundleAlpha.target_id ? bundleAlpha : betaWithFamily
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(body),
      })
    })

    const q = `aType=rule_card&aId=${encodeURIComponent(bundleAlpha.target_id)}&bType=rule_card&bId=${encodeURIComponent(bundleBeta.target_id)}`
    await page.goto(`/review/compare?${q}`)

    await page.getByTestId('compare-decision-type').selectOption('merge_into')
    await expect(page.getByTestId('compare-related-target-id')).toHaveValue('fam_beta_only')
  })

  test('no decision panel when pair is not two rule_cards', async ({ page }) => {
    const evidence = loadFixture<ReviewBundleResponse>('adjudication-bundle-no-family.json')
    const ev: ReviewBundleResponse = {
      ...evidence,
      target_type: 'evidence_link',
      target_id: 'ev_compare_1',
      reviewed_state: {
        target_type: 'evidence_link',
        target_id: 'ev_compare_1',
      },
    }

    await page.route('**/adjudication/review-bundle**', async (route) => {
      const tid = targetIdFromReviewBundleRequest(route.request().url())
      const body = tid === ev.target_id ? ev : bundleAlpha
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(body),
      })
    })

    const q = `aType=evidence_link&aId=${encodeURIComponent(ev.target_id)}&bType=rule_card&bId=${encodeURIComponent(bundleAlpha.target_id)}`
    await page.goto(`/review/compare?${q}`)

    await expect(page.getByText('Left (A)')).toBeVisible({ timeout: 15_000 })
    await expect(page.getByTestId('compare-decision-panel')).toHaveCount(0)
  })

  test('compare invalid params still shows error, no decision panel', async ({ page }) => {
    await page.goto('/review/compare?aType=bad&aId=x&bType=rule_card&bId=y')
    await expect(page.getByRole('heading', { name: 'Invalid compare link' })).toBeVisible()
    await expect(page.getByTestId('compare-decision-panel')).toHaveCount(0)
  })
})
