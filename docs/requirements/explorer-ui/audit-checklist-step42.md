# Step 4.2 Audit Checklist

Screenshot files live under **`../../../audit/step4-3-explorer/screenshots/`** (repo root).

## Acceptance Mapping

- Search page supports empty-query browse: `src/pages/SearchPage.tsx`, `src/hooks/useBrowserSearch.ts`, `tests/e2e/search.spec.ts`, `../../../audit/step4-3-explorer/screenshots/01-search-browse.png`
- Search page supports real query flow: `src/components/search/SearchBar.tsx`, `src/pages/SearchPage.tsx`, `tests/e2e/search.spec.ts`, `../../../audit/step4-3-explorer/screenshots/02-search-query.png`
- Filters are visible and usable: `src/components/filters/FiltersPanel.tsx`, `src/components/filters/FacetSection.tsx`, `src/pages/SearchPage.tsx`, `../../../audit/step4-3-explorer/screenshots/04-filters-open-mobile.png`
- Active filters produce chips and survive URL state: `src/components/filters/FilterChips.tsx`, `src/hooks/useSearchUrlState.ts`, `src/lib/url/search-params.ts`, `src/lib/url/search-params.test.ts`, `../../../audit/step4-3-explorer/screenshots/03-active-filter-chips.png`
- Result cards are typed and navigable: `src/components/search/ResultCard.tsx`, `src/lib/utils/entity.ts`, `src/components/search/ResultCard.test.tsx`
- Rule detail page renders via deep link: `src/pages/RulePage.tsx`, `src/hooks/useRuleDetail.ts`, `tests/e2e/detail-rule.spec.ts`, `../../../audit/step4-3-explorer/screenshots/05-rule-detail.png`
- Evidence detail page renders via deep link: `src/pages/EvidencePage.tsx`, `src/hooks/useEvidenceDetail.ts`, `tests/e2e/detail-evidence.spec.ts`, `../../../audit/step4-3-explorer/screenshots/06-evidence-detail.png`
- Concept detail page renders and neighbor navigation works: `src/pages/ConceptPage.tsx`, `src/hooks/useConceptDetail.ts`, `src/hooks/useConceptNeighbors.ts`, `tests/e2e/concept.spec.ts`, `../../../audit/step4-3-explorer/screenshots/07-concept-detail.png`, `../../../audit/step4-3-explorer/screenshots/08-concept-neighbor-navigation.png`
- Lesson detail page renders via deep link: `src/pages/LessonPage.tsx`, `src/hooks/useLessonDetail.ts`, `tests/e2e/lesson.spec.ts`, `../../../audit/step4-3-explorer/screenshots/09-lesson-detail.png`
- Not-found state renders for dead routes: `src/components/common/NotFound.tsx`, `src/app/router.tsx`, `tests/e2e/regressions.spec.ts`, `../../../audit/step4-3-explorer/screenshots/10-not-found.png`
- Empty state renders for no-hit search: `src/components/search/EmptyState.tsx`, `src/pages/SearchPage.tsx`, `../../../audit/step4-3-explorer/screenshots/11-empty-state.png`
- Error states are visible and not silently swallowed: `src/components/common/ErrorPanel.tsx`
- UI only calls `/browser/*`: `src/lib/api/client.ts`, `src/lib/api/browser.ts`
- Frontend response parsing is typed and validated: `src/lib/api/schemas.ts`, `src/lib/api/types.ts`, `src/lib/api/client.ts`, `src/lib/api/schemas.test.ts`
- Build passes: `build_output.txt`
- Lint passes: `lint_output.txt`
- Typecheck passes: `typecheck_output.txt`
- Vitest passes: `vitest_output.txt`
- Playwright passes: `playwright_output.txt`

## Backend Alignment Included In Bundle

- route list: `browser_routes.txt`
- contract reference: `docs/step4_explorer_contracts.md`
- API samples: `browser_api_samples/`
- live backend contract code: `pipeline/explorer/contracts.py`, `pipeline/explorer/api.py`, `pipeline/rag/api.py`
- backend change included for this UI audit: `backend_changed_files/pipeline/rag/cli.py`

## Regression Signals Preserved

- stop-loss example retrieval: `browser_api_samples/search_stop_loss_example.json`, `tests/e2e/search.spec.ts`
- timeframe rule-card preference: `browser_api_samples/search_timeframe_rules.json`
- daily-level actionable preference: `browser_api_samples/search_daily_level.json`
