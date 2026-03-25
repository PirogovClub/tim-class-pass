/**
 * Stage 5.3 audit screenshots → audit/stage5_3_audit_bundle/screenshots/
 * Run from ui/explorer: npm run build && npm run audit:screenshots:5.3
 * Output: repo-root audit/stage5_3_audit_bundle/screenshots/
 */
import { mkdirSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { expect, test } from '@playwright/test'

import { loadFixture, mockJsonRoute } from './support/browser-fixtures'

// e2e -> explorer -> ui -> repo root -> audit/stage5_3_audit_bundle/screenshots
const shotDir = join(dirname(fileURLToPath(import.meta.url)), '../../../../audit/stage5_3_audit_bundle/screenshots')
mkdirSync(shotDir, { recursive: true })
const shot = (name: string) => join(shotDir, name)

const queuePopulated = loadFixture<Record<string, unknown>>('adjudication-queue-populated.json')
const queueEmpty = loadFixture<Record<string, unknown>>('adjudication-queue-empty.json')
const bundleFamily = loadFixture<Record<string, unknown>>('adjudication-bundle-with-family.json')
const bundleNoFamily = loadFixture<Record<string, unknown>>('adjudication-bundle-no-family.json')
const bundleAfterApprove = loadFixture<Record<string, unknown>>('adjudication-bundle-after-approve.json')

function enc(s: string) {
  return encodeURIComponent(s)
}

test.describe.serial('Stage 5.3 audit screenshots', () => {
  test('queue: default, filtered, empty, error, loading', async ({ page }) => {
    await mockJsonRoute(page, '**/adjudication/queues/unresolved', queuePopulated)
    await mockJsonRoute(page, '**/adjudication/queues/by-target**', queuePopulated)
    await page.goto('/review/queue')
    await expect(page.getByRole('heading', { name: 'Review queue' })).toBeVisible()
    await expect(page.getByText('2 items unresolved')).toBeVisible()
    await page.screenshot({ path: shot('01-queue-unresolved-default.png'), fullPage: true })

    const qItems = queuePopulated.items as { target_type: string }[]
    await mockJsonRoute(page, '**/adjudication/queues/by-target**', {
      ...queuePopulated,
      items: qItems.filter((row) => row.target_type === 'rule_card'),
      total: qItems.filter((row) => row.target_type === 'rule_card').length,
    })
    await page.goto('/review/queue?targetType=rule_card')
    await expect(page.getByText('low_confidence_extraction')).toBeVisible()
    await page.screenshot({ path: shot('02-queue-filtered-rule-card.png'), fullPage: true })

    await mockJsonRoute(page, '**/adjudication/queues/unresolved', queueEmpty)
    await mockJsonRoute(page, '**/adjudication/queues/by-target**', queueEmpty)
    await page.goto('/review/queue')
    await expect(page.getByText('Queue is empty for this filter.')).toBeVisible()
    await page.screenshot({ path: shot('03-queue-empty.png'), fullPage: true })

    await page.route('**/adjudication/queues/unresolved', (route) =>
      route.fulfill({
        status: 503,
        contentType: 'application/json',
        body: JSON.stringify({ message: 'Adjudication index unavailable' }),
      }),
    )
    await page.goto('/review/queue')
    await expect(page.getByRole('alert')).toBeVisible({ timeout: 15_000 })
    await page.screenshot({ path: shot('04-queue-error.png'), fullPage: true })
    await page.unroute('**/adjudication/queues/unresolved')

    let release!: () => void
    const gate = new Promise<void>((resolve) => {
      release = resolve
    })
    await mockJsonRoute(page, '**/adjudication/queues/by-target**', queuePopulated)
    await page.route('**/adjudication/queues/unresolved', async (route) => {
      await gate
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(queuePopulated),
      })
    })
    await page.goto('/review/queue')
    await expect(page.getByText('Loading queue…')).toBeVisible()
    await page.screenshot({ path: shot('05-queue-loading.png'), fullPage: true })
    release()
    await expect(page.getByText('2 items unresolved')).toBeVisible({ timeout: 15_000 })
    await page.unroute('**/adjudication/queues/unresolved')
  })

  test('review item: data, no family, loading, error', async ({ page }) => {
    await page.route('**/adjudication/review-bundle**', async (route) => {
      const url = route.request().url()
      if (url.includes(enc('rule_audit_alpha'))) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(bundleFamily),
        })
      } else {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(bundleNoFamily),
        })
      }
    })

    await page.goto('/review/item/rule_card/rule_audit_alpha?queueReason=demo')
    await expect(page.getByRole('heading', { name: 'Review item' })).toBeVisible()
    await expect(page.getByText('Structure-based stop loss')).toBeVisible()
    await page.screenshot({ path: shot('06-review-item-with-family.png'), fullPage: true })

    await page.goto('/review/item/rule_card/rule_audit_beta')
    await expect(page.getByText('No family linked for this target.')).toBeVisible()
    await page.screenshot({ path: shot('07-review-item-no-family.png'), fullPage: true })

    let releaseItem!: () => void
    const gateItem = new Promise<void>((resolve) => {
      releaseItem = resolve
    })
    await page.route('**/adjudication/review-bundle**', async (route) => {
      await gateItem
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(bundleFamily),
      })
    })
    await page.goto('/review/item/rule_card/rule_audit_alpha')
    await expect(page.getByText('Loading review bundle…')).toBeVisible()
    await page.screenshot({ path: shot('08-review-item-loading.png'), fullPage: true })
    releaseItem()
    await expect(page.getByRole('button', { name: 'Submit decision' })).toBeVisible({ timeout: 15_000 })
    await page.unroute('**/adjudication/review-bundle**')

    await page.route('**/adjudication/review-bundle**', (route) =>
      route.fulfill({
        status: 404,
        contentType: 'application/json',
        body: JSON.stringify({ message: 'Unknown target' }),
      }),
    )
    await page.goto('/review/item/rule_card/missing_rule_id')
    await expect(page.getByRole('alert')).toBeVisible({ timeout: 15_000 })
    await page.screenshot({ path: shot('09-review-item-error.png'), fullPage: true })
    await page.unroute('**/adjudication/review-bundle**')
  })

  test('decision: form, validation disabled, success + refresh, API error', async ({ page }) => {
    let alphaBundle: unknown = bundleFamily
    await page.route('**/adjudication/review-bundle**', async (route) => {
      const url = route.request().url()
      const body = url.includes('rule_audit_beta') ? bundleNoFamily : alphaBundle
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(body),
      })
    })

    await page.goto('/review/item/rule_card/rule_audit_alpha')
    await expect(page.getByRole('heading', { name: 'Submit decision' })).toBeVisible()
    await page.screenshot({ path: shot('10-decision-before-submit.png'), fullPage: true })

    await page.getByLabel(/Decision/i).selectOption('duplicate_of')
    await expect(page.getByRole('button', { name: 'Submit decision' })).toBeDisabled()
    await page.screenshot({ path: shot('11-decision-validation-related-required.png'), fullPage: true })

    await page.route('**/adjudication/decision', async (route) => {
      alphaBundle = bundleAfterApprove
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          decision_id: 'dec_new',
          target_type: 'rule_card',
          target_id: 'rule_audit_alpha',
          updated_state: (bundleAfterApprove as { reviewed_state: unknown }).reviewed_state,
        }),
      })
    })

    await page.getByLabel(/Decision/i).selectOption('approve')
    await page.getByRole('button', { name: 'Submit decision' }).click()
    // load() sets loading and unmounts DecisionPanel, so "Decision recorded." may not persist;
    // assert refreshed bundle (new history row from fixture).
    await expect(page.getByText('Looks consistent with lesson')).toBeVisible({ timeout: 15_000 })
    await page.screenshot({ path: shot('12-decision-success-refreshed.png'), fullPage: true })

    await page.unroute('**/adjudication/decision')
    await page.route('**/adjudication/decision', (route) =>
      route.fulfill({
        status: 422,
        contentType: 'application/json',
        body: JSON.stringify({ message: 'Reviewer not registered' }),
      }),
    )
    await page.goto('/review/item/rule_card/rule_audit_beta')
    await page.getByRole('button', { name: 'Submit decision' }).click()
    await expect(page.getByText('Reviewer not registered')).toBeVisible()
    await page.screenshot({ path: shot('13-decision-api-error.png'), fullPage: true })
    await page.unroute('**/adjudication/decision')
    await page.unroute('**/adjudication/review-bundle**')
  })

  test('compare: two columns, invalid params, mobile queue', async ({ page }) => {
    await page.route('**/adjudication/review-bundle**', async (route) => {
      const url = route.request().url()
      const body =
        url.includes(enc('rule_audit_alpha')) || url.includes('rule_audit_alpha')
          ? bundleFamily
          : bundleNoFamily
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(body),
      })
    })

    const q =
      `aType=${enc('rule_card')}&aId=${enc('rule_audit_alpha')}&bType=${enc('rule_card')}&bId=${enc('rule_audit_beta')}`
    await page.goto(`/review/compare?${q}`)
    await expect(page.getByText('Left (A)')).toBeVisible()
    await expect(page.getByText('Right (B)')).toBeVisible()
    await page.screenshot({ path: shot('14-compare-two-items.png'), fullPage: true })

    await page.goto('/review/compare?aType=bad&aId=x&bType=rule_card&bId=y')
    await expect(page.getByRole('heading', { name: 'Invalid compare link' })).toBeVisible()
    await page.screenshot({ path: shot('15-compare-invalid-params.png'), fullPage: true })

    await mockJsonRoute(page, '**/adjudication/queues/unresolved', queuePopulated)
    await page.setViewportSize({ width: 390, height: 844 })
    await page.goto('/review/queue')
    await expect(page.getByText('2 items unresolved')).toBeVisible()
    await page.screenshot({ path: shot('16-review-queue-mobile.png'), fullPage: true })
    await page.unroute('**/adjudication/review-bundle**')
  })

  test('workflow: next item, return to queue, compare then item link', async ({ page }) => {
    await mockJsonRoute(page, '**/adjudication/queues/unresolved', queuePopulated)
    await mockJsonRoute(page, '**/adjudication/queues/next**', {
      target_type: 'rule_card',
      target_id: 'rule_audit_beta',
      queue_reason: 'ambiguous_family',
    })
    await page.route('**/adjudication/review-bundle**', async (route) => {
      const url = route.request().url()
      const body = url.includes('rule_audit_beta') ? bundleNoFamily : bundleFamily
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(body),
      })
    })

    await page.goto('/review/queue')
    await page.getByRole('button', { name: 'Open next item' }).click()
    await expect(page).toHaveURL(/rule_audit_beta/)
    await page.screenshot({ path: shot('17-workflow-next-item.png'), fullPage: true })

    await page.getByRole('link', { name: 'Back to queue' }).click()
    await expect(page).toHaveURL(/\/review\/queue/)
    await page.screenshot({ path: shot('18-workflow-back-to-queue.png'), fullPage: true })

    await page.goto(
      `/review/compare?aType=${enc('rule_card')}&aId=${enc('rule_audit_alpha')}&bType=${enc('rule_card')}&bId=${enc('rule_audit_beta')}`,
    )
    await page.getByRole('link', { name: 'Open full review' }).first().click()
    await expect(page).toHaveURL(/rule_audit_alpha/)
    await page.screenshot({ path: shot('19-workflow-compare-to-full-review.png'), fullPage: true })
  })

  test('decision submitting pending state', async ({ page }) => {
    let finishPost!: () => void
    const postDone = new Promise<void>((r) => {
      finishPost = r
    })
    await mockJsonRoute(page, '**/adjudication/review-bundle**', bundleNoFamily)
    await page.route('**/adjudication/decision', async (route) => {
      await postDone
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          decision_id: 'x',
          target_type: 'rule_card',
          target_id: 'rule_audit_beta',
          updated_state: (bundleNoFamily as { reviewed_state: Record<string, unknown> }).reviewed_state,
        }),
      })
    })

    await page.goto('/review/item/rule_card/rule_audit_beta')
    await page.getByRole('button', { name: 'Submit decision' }).click()
    await expect(page.getByRole('button', { name: 'Submitting…' })).toBeVisible()
    await page.screenshot({ path: shot('20-decision-submitting.png'), fullPage: true })
    finishPost()
    await expect(page.getByRole('button', { name: 'Submit decision' })).toBeVisible({ timeout: 15_000 })
    await page.unroute('**/adjudication/decision')
  })
})
