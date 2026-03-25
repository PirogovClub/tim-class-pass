# Step 4.3 — explicit changed-file list (compare & traversal)

Scope: Step 4.3 only (explorer `/browser/*` compare + traversal + UI). Use this list to spot scope creep; the **authoritative source** is still `git status` / diff on your branch.

## Backend — `pipeline/explorer/`

- `pipeline/explorer/contracts.py`
- `pipeline/explorer/loader.py`
- `pipeline/explorer/views.py`
- `pipeline/explorer/service.py`
- `pipeline/explorer/api.py`

## Backend tests — `tests/explorer/`

- `tests/explorer/conftest.py`
- `tests/explorer/test_api.py`
- `tests/explorer/test_service.py`
- `tests/explorer/test_views.py`

## Frontend — API types & client — `ui/explorer/src/lib/`

- `ui/explorer/src/lib/api/schemas.ts`
- `ui/explorer/src/lib/api/types.ts`
- `ui/explorer/src/lib/api/browser.ts`
- `ui/explorer/src/lib/url/compare-params.ts`
- `ui/explorer/src/lib/url/compare-params.test.ts`

## Frontend — hooks — `ui/explorer/src/hooks/`

- `ui/explorer/src/hooks/useCompareSelection.ts`
- `ui/explorer/src/hooks/useCompareRules.ts`
- `ui/explorer/src/hooks/useCompareLessons.ts`
- `ui/explorer/src/hooks/useRelatedRules.ts`
- `ui/explorer/src/hooks/useConceptRules.ts`
- `ui/explorer/src/hooks/useConceptLessons.ts`

## Frontend — components (new or materially updated)

- `ui/explorer/src/components/compare/CompareLaunchBar.tsx`
- `ui/explorer/src/components/compare/LessonCompareGrid.tsx`
- `ui/explorer/src/components/compare/LessonComparePage.tsx`
- `ui/explorer/src/components/compare/LessonOverlapPanel.tsx`
- `ui/explorer/src/components/compare/RuleComparePage.tsx`
- `ui/explorer/src/components/compare/RuleCompareSummary.tsx`
- `ui/explorer/src/components/compare/RuleCompareTable.tsx`
- `ui/explorer/src/components/related/RelatedRuleGroup.tsx`
- `ui/explorer/src/components/related/RelatedRulesPage.tsx`
- `ui/explorer/src/components/related/RelationReasonBadge.tsx`
- `ui/explorer/src/components/concept/ConceptRulesPage.tsx`
- `ui/explorer/src/components/concept/ConceptLessonsPage.tsx`
- `ui/explorer/src/components/layout/AppShell.tsx`
- `ui/explorer/src/components/search/ResultCard.tsx`
- `ui/explorer/src/components/search/ResultCard.test.tsx`
- `ui/explorer/src/components/rule/RuleDetailPage.tsx`
- `ui/explorer/src/components/rule/RelatedRules.tsx`
- `ui/explorer/src/components/lesson/LessonDetailPage.tsx`
- `ui/explorer/src/components/concept/ConceptDetailPage.tsx`
- `ui/explorer/src/components/common/ScreenshotModal.tsx` (lint-safe modal state; hooks hygiene)

## Frontend — pages & routing

- `ui/explorer/src/pages/CompareRulesPage.tsx`
- `ui/explorer/src/pages/CompareLessonsPage.tsx`
- `ui/explorer/src/pages/RelatedRulesPage.tsx`
- `ui/explorer/src/pages/ConceptRulesPage.tsx`
- `ui/explorer/src/pages/ConceptLessonsPage.tsx`
- `ui/explorer/src/pages/CompareRulesPage.test.tsx`
- `ui/explorer/src/pages/CompareLessonsPage.test.tsx`
- `ui/explorer/src/pages/RelatedRulesPage.test.tsx`
- `ui/explorer/src/pages/ConceptRulesPage.test.tsx`
- `ui/explorer/src/pages/ConceptLessonsPage.test.tsx`
- `ui/explorer/src/app/router.tsx`

## Frontend — test infrastructure & fixtures

- `ui/explorer/src/test/mock-fetch.ts` (longest-prefix fetch mock matching for `/related` vs base rule URL)
- `ui/explorer/src/test/fixtures/compare-rules.json`
- `ui/explorer/src/test/fixtures/compare-lessons.json`
- `ui/explorer/src/test/fixtures/related-rules.json`
- `ui/explorer/src/test/fixtures/concept-rules.json`
- `ui/explorer/src/test/fixtures/concept-lessons.json`

## Frontend — e2e

- `ui/explorer/tests/e2e/compare-traversal.spec.ts`
- `ui/explorer/tests/e2e/audit-screenshots.spec.ts` (captures audit PNGs; run via `npm run audit:screenshots`)
- `ui/explorer/tests/e2e/detail-rule.spec.ts` (if updated for related-rules link)
- `ui/explorer/tests/e2e/screenplay/questions/rule-detail-page.ts` (if updated)

## Docs & audit artifacts (this step)

- `docs/step4_explorer_contracts.md`
- `docs/step4_explorer_notes.md`
- **`audit/step4-3-explorer/`** (this folder): `AUDIT_HANDOFF.md`, `AUDIT_FILE_LIST_STEP43.md` (this file), `AUDIT_VALIDATION_OUTPUT.txt`, `AUDIT_SCREENSHOT_CHECKLIST.md`, `UI_AUDIT_HANDOFF.md`, `README.md`, `package_bundle.ps1`
- `audit/step4-3-explorer/audit_step4_3_2026-03-24.zip` (optional; build via `audit/step4-3-explorer/package_bundle.ps1` or `scripts/package_audit_step43.ps1`)
- Index: `audit/README.md` → links into this folder

## Sample JSON — `browser_api_samples/` (Step 4.3 additions)

- `browser_api_samples/compare_rules.json`
- `browser_api_samples/compare_lessons.json`
- `browser_api_samples/related_rules_rule_2025_09_29_sviatoslav_chornyi_rule_2025_09_29_sviatoslav_chornyi_trade_management_stop_loss_3.json`
- `browser_api_samples/concept_rules_node_stop_loss.json`
- `browser_api_samples/concept_lessons_node_stop_loss.json`

## Screenshots (expected paths; binary files may be gitignored)

All under **`audit/step4-3-explorer/screenshots/`** (including Step 4.2 reference PNGs `01-*.png` … `11-*.png` if present):

- `audit/step4-3-explorer/screenshots/rule-compare.png`
- `audit/step4-3-explorer/screenshots/lesson-compare.png`
- `audit/step4-3-explorer/screenshots/related-rules.png`
- `audit/step4-3-explorer/screenshots/concept-rules.png`
- `audit/step4-3-explorer/screenshots/concept-lessons.png`

See `AUDIT_SCREENSHOT_CHECKLIST.md` in this folder for the full evidence matrix (including empty / error / loading / mobile) and how to capture.

---

## Files that may appear in `git status` but are not Step 4.3 explorer scope

Confirm with `git diff` before including in an audit zip (they may be local hygiene or other work):

- `pipeline/rag/cli.py` (e.g. `if __name__ == "__main__": main()`)
- `tests/rag/conftest.py` (e.g. `rag_config` / `asset_root` fixture changes)
