# Step 4.3 — UI audit handoff (explorer)

The **canonical** Step 4.3 audit package is the folder **`audit/step4-3-explorer/`**:

- [`AUDIT_HANDOFF.md`](AUDIT_HANDOFF.md) — full narrative, test mapping, regressions, reproduce steps  
- [`AUDIT_FILE_LIST_STEP43.md`](AUDIT_FILE_LIST_STEP43.md) — every path in scope  
- [`AUDIT_VALIDATION_OUTPUT.txt`](AUDIT_VALIDATION_OUTPUT.txt) — lint, typecheck, build, pytest, Vitest, Playwright transcripts  
- [`README.md`](README.md) — index  

This file is a **short UI-focused index**.

## Implemented routes

- `/compare/rules?ids=...`
- `/compare/lessons?ids=...`
- `/rule/:docId/related`
- `/concept/:conceptId/rules`
- `/concept/:conceptId/lessons`

Plus: compare launch bar, add-to-compare on cards and detail pages, traversal links on rule and concept detail.

## Validation (from `AUDIT_VALIDATION_OUTPUT.txt`)

From `ui/explorer`:

- `npm run lint` — pass  
- `npm run typecheck` — pass  
- `npm run build` — pass  
- `npm run test` — 35 tests passed  
- `npm run test:e2e` — 23 tests passed (includes `audit-screenshots.spec.ts`)  

## Proof artifacts

- **Samples:** repo root `browser_api_samples/compare_*.json`, `related_rules_*.json`, `concept_*_node_stop_loss.json`  
- **Screenshots:** [`screenshots/`](screenshots/) in this folder; matrix in [`AUDIT_SCREENSHOT_CHECKLIST.md`](AUDIT_SCREENSHOT_CHECKLIST.md)  

## Out of scope (unchanged)

Write-back, graph viz, export tooling, auth/roles, retrieval tuning beyond preserving existing search regression tests.
