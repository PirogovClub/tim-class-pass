# Step 4.2 Re-Audit Checklist

## Audit Blockers -> Proof

- Rule detail is now routed through the rich analyst view:
  - code: `src/pages/RulePage.tsx`, `src/components/rule/RuleDetailPage.tsx`
  - unit proof: `src/pages/RulePage.test.tsx`
  - browser proof: `tests/e2e/detail-rule.spec.ts`
  - screenshot: `audit_screenshots/audit-rule-detail.png`

- Evidence detail is now routed through the rich analyst view:
  - code: `src/pages/EvidencePage.tsx`, `src/components/evidence/EvidenceDetailPage.tsx`
  - unit proof: `src/pages/EvidencePage.test.tsx`
  - browser proof: `tests/e2e/detail-evidence.spec.ts`
  - screenshot: `audit_screenshots/audit-evidence-detail.png`

- Lesson detail now renders structured lesson intelligence:
  - code: `src/pages/LessonPage.tsx`, `src/components/lesson/LessonDetailPage.tsx`
  - unit proof: `src/pages/LessonPage.test.tsx`
  - browser proof: `tests/e2e/lesson.spec.ts`
  - screenshot: `audit_screenshots/audit-lesson-detail.png`

- Concept detail now routes through the rich concept composite:
  - code: `src/pages/ConceptPage.tsx`, `src/components/concept/ConceptDetailPage.tsx`
  - unit proof: `src/pages/ConceptPage.test.tsx`
  - browser proof: `tests/e2e/concept.spec.ts`
  - screenshot: `audit_screenshots/audit-concept-detail.png`

- Back-to-search continuity is visible on detail pages:
  - code: `src/components/detail/EntityHeader.tsx`
  - browser proof: `tests/e2e/detail-rule.spec.ts`, `tests/e2e/detail-evidence.spec.ts`, `tests/e2e/lesson.spec.ts`, `tests/e2e/concept.spec.ts`
  - screenshot: `audit_screenshots/audit-back-to-search.png`

- Accepted search behavior is proved at the browser layer:
  - code: `tests/e2e/search-regressions.spec.ts`
  - stop-loss example evidence-first
  - timeframe query rule-first
  - daily-level query actionable-first
  - screenshot: `audit_screenshots/audit-search-results.png`

## Validation Outputs

- Typecheck pass: `typecheck_output.txt`
- Vitest pass: `vitest_output.txt`
- Build pass: `build_output.txt`
- Playwright pass: `playwright_output_latest.txt`

## Supporting Coverage

- Search page flow and result navigation: `tests/e2e/search.spec.ts`
- Not-found route regression: `tests/e2e/regressions.spec.ts`
- Visual screenshot affordance: `tests/e2e/visual-summary.spec.ts`
- Browser question/task helpers updated for the rich detail structure:
  - `tests/e2e/screenplay/questions/rule-detail-page.ts`
  - `tests/e2e/screenplay/questions/evidence-detail-page.ts`
  - `tests/e2e/screenplay/questions/lesson-detail-page.ts`
  - `tests/e2e/screenplay/questions/concept-detail-page.ts`
  - `tests/e2e/screenplay/tasks/navigate-to.ts`
  - `tests/e2e/screenplay/tasks/search-for.ts`

## Bundle Support Files

- Browser API samples: `../browser_api_samples/`
- Backend contract/reference files:
  - `../backend_changed_files/pipeline/explorer/api.py`
  - `../backend_changed_files/pipeline/explorer/contracts.py`
  - `../backend_changed_files/pipeline/explorer/views.py`
  - `../backend_changed_files/pipeline/rag/cli.py`
- Backend run command: `../RUN_BROWSER_API.md`

## Transparency Note

- `lint_output.txt` is included but is not part of the acceptance gate for this re-audit. The reported `ScreenshotModal.tsx` hook-rule findings pre-existed this detail-page rework.
