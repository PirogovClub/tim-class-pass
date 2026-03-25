# Stage 5.3 — changed / relevant files (explorer UI)

Scope: **frontend only** (no Stage 5.2 backend edits in this patch). Paths from repository root.

## Routes & pages

- `ui/explorer/src/app/router.tsx` — `/review/queue`, `/review/item/:targetType/:targetId`, `/review/compare`
- `ui/explorer/src/pages/ReviewQueuePage.tsx`
- `ui/explorer/src/pages/ReviewItemPage.tsx`
- `ui/explorer/src/pages/ReviewComparePage.tsx`

## Review components

- `ui/explorer/src/components/review/DecisionPanel.tsx`
- `ui/explorer/src/components/review/HistoryPanel.tsx`
- `ui/explorer/src/components/review/FamilyPanel.tsx`
- `ui/explorer/src/components/review/OptionalContextPanel.tsx`
- `ui/explorer/src/components/review/CompareDecisionPanel.tsx` — `duplicate_of` / `merge_into` from compare (rule_card pair)

## API client & schemas

- `ui/explorer/src/lib/api/adjudication.ts`
- `ui/explorer/src/lib/api/adjudication-schemas.ts`
- `ui/explorer/src/lib/api/client.ts` — prefers top-level JSON `message` on errors

## Decision policy mirror (frontend)

- `ui/explorer/src/lib/review/decisions.ts`
- `ui/explorer/src/lib/review/decisions.test.ts`
- `ui/explorer/src/lib/review/compareDecisionPrefill.ts`
- `ui/explorer/src/lib/review/compareDecisionPrefill.test.ts`

## Chrome / dev proxy

- `ui/explorer/src/components/layout/TopBar.tsx` — Search + Review queue
- `ui/explorer/vite.config.ts` — `server.proxy['/adjudication']`

## Docs

- `notes/stage5_3_ui_contract.md`
- `ui/explorer/README.md` — Stage 5.3 subsection

## Fixtures (Playwright / Vitest)

- `ui/explorer/src/test/fixtures/adjudication-queue-populated.json`
- `ui/explorer/src/test/fixtures/adjudication-queue-empty.json`
- `ui/explorer/src/test/fixtures/adjudication-bundle-with-family.json`
- `ui/explorer/src/test/fixtures/adjudication-bundle-no-family.json`
- `ui/explorer/src/test/fixtures/adjudication-bundle-after-approve.json`

## E2E

- `ui/explorer/tests/e2e/stage5-3-audit-screenshots.spec.ts`
- `ui/explorer/tests/e2e/compare-adjudication.spec.ts`
- `ui/explorer/playwright.config.ts` — build + preview on port **5199** for deterministic e2e

## NPM scripts

- `ui/explorer/package.json` — `audit:screenshots:5.3`

## This bundle (audit deliverables)

- `audit/stage5_3_audit_bundle/AUDIT_HANDOFF.md`
- `audit/stage5_3_audit_bundle/FILE_LIST.md` (this file)
- `audit/stage5_3_audit_bundle/SCREENSHOT_INDEX.md`
- `audit/stage5_3_audit_bundle/README.md`
- `audit/stage5_3_audit_bundle/package_bundle.ps1`
- `audit/stage5_3_audit_bundle/screenshots/*.png`
- `audit/stage5_3_audit_bundle/terminal/*.txt`
