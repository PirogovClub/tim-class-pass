PNG files are produced by Playwright:

- Spec: `ui/explorer/tests/e2e/stage5-5-audit-screenshots.spec.ts`
- Command (from `ui/explorer`): `npm run build && npx playwright test stage5-5-audit-screenshots.spec.ts`
- Or: `npm run audit:screenshots:5.5` (runs build via Playwright `webServer` config)

Files:

1. `01-queue-high-confidence-duplicates.png` — proposal queue with `total` &gt; page size in footer.
2. `02-queue-merge-candidates-rule-card.png` — `merge_candidates` with `targetType=rule_card`.
3. `03-queue-canonical-family-candidates.png` — `canonical_family_candidates`.
4. `04-review-item-proposal-panel.png` — review item with proposal panel visible.
5. `05-back-to-queue-preserved-context.png` — queue after “Back to queue” (same `reviewQueue` / filters).
6. `06-compare-from-proposal-context.png` — compare view with both bundles loaded.

API responses in the spec are mocked in-browser (no backend required for capture).
