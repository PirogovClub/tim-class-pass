# Stage 5.3 audit screenshots

All captured with **Playwright** against **production build** (`npm run preview` on `127.0.0.1:4173`). Adjudication HTTP responses are **mocked** in `ui/explorer/tests/e2e/stage5-3-audit-screenshots.spec.ts`; JSON fixtures live under `ui/explorer/src/test/fixtures/adjudication-*.json`.

| File | Maps to audit request (5-3-audit-request §7) |
|------|---------------------------------------------|
| `01-queue-unresolved-default.png` | Queue — default unresolved |
| `02-queue-filtered-rule-card.png` | Queue — filtered (`targetType=rule_card`) |
| `03-queue-empty.png` | Queue — empty |
| `04-queue-error.png` | Queue — error (503 + JSON `message`) |
| `05-queue-loading.png` | Queue — loading |
| `06-review-item-with-family.png` | Review item — real data + family |
| `07-review-item-no-family.png` | Review item — no family |
| `08-review-item-loading.png` | Review item — loading |
| `09-review-item-error.png` | Review item — error (404) |
| `10-decision-before-submit.png` | Decision — panel before submit |
| `11-decision-validation-related-required.png` | Decision — validation (`duplicate_of`, submit disabled) |
| `12-decision-success-refreshed.png` | Decision — after successful submit (**bundle refetched**; success toast is cleared when `load()` unmounts the panel) |
| `13-decision-api-error.png` | Decision — API error (422 + `message`) |
| `14-compare-two-items.png` | Compare — two bundles |
| `15-compare-invalid-params.png` | Compare — invalid `aType` |
| `16-review-queue-mobile.png` | Workflow — narrow viewport queue |
| `17-workflow-next-item.png` | Next-item — landed on second row |
| `18-workflow-back-to-queue.png` | Return to queue |
| `19-workflow-compare-to-full-review.png` | Compare → “Open full review” → item page |
| `20-decision-submitting.png` | Submit pending (`Submitting…`) |

**Regenerate:** from `ui/explorer`: `npm run build && npm run audit:screenshots:5.3`.
