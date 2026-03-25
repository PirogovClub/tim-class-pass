# Step 4.2 UI Re-Audit Handoff

## Scope

This bundle is the Step 4.2 explorer UI resubmission after the partial-pass audit that called out under-delivered detail pages and missing browser-level regression proof.

The rework keeps the existing search/browse architecture and focuses on the four blockers from `rag creation/05-audit result.md`:

1. rule detail completeness
2. evidence detail completeness
3. lesson detail structured intelligence
4. UI-level proof for the accepted search behaviors

## What Changed In This Rework

- route pages now render the rich composite detail pages instead of thin card wrappers:
  - `src/pages/RulePage.tsx`
  - `src/pages/EvidencePage.tsx`
  - `src/pages/LessonPage.tsx`
  - `src/pages/ConceptPage.tsx`
- shared detail header now carries the per-page copy-link affordance:
  - `src/components/detail/EntityHeader.tsx`
- the redundant top-bar copy-link was removed to avoid duplicate detail-page controls:
  - `src/components/layout/TopBar.tsx`
- route-level unit coverage was expanded for the richer detail sections:
  - `src/pages/RulePage.test.tsx`
  - `src/pages/EvidencePage.test.tsx`
  - `src/pages/LessonPage.test.tsx`
  - `src/pages/ConceptPage.test.tsx`
- Playwright Screenplay questions/specs were updated to assert the richer detail surfaces:
  - `tests/e2e/detail-rule.spec.ts`
  - `tests/e2e/detail-evidence.spec.ts`
  - `tests/e2e/lesson.spec.ts`
  - `tests/e2e/concept.spec.ts`
  - `tests/e2e/screenplay/questions/*`
- dedicated browser regression coverage was added for the three accepted search behaviors:
  - `tests/e2e/search-regressions.spec.ts`

## Blocker Mapping

### Blocker 1: rule detail must be analyst-useful

Now surfaced through the routed UI:

- support/provenance badges
- timestamps
- linked evidence
- source events
- related rules
- invalidation / exceptions / comparisons
- copy-link and back-to-search navigation

Primary files:

- `src/components/rule/RuleDetailPage.tsx`
- `src/pages/RulePage.tsx`
- `tests/e2e/detail-rule.spec.ts`

### Blocker 2: evidence detail must be analyst-useful

Now surfaced through the routed UI:

- support basis
- timestamps
- evidence strength / role
- linked rules
- linked events
- snippet / context
- copy-link and back-to-search navigation

Primary files:

- `src/components/evidence/EvidenceDetailPage.tsx`
- `src/pages/EvidencePage.tsx`
- `tests/e2e/detail-evidence.spec.ts`

### Blocker 3: lesson detail must render structured intelligence

Now surfaced through the routed UI:

- counts by unit type
- counts by support basis
- top concepts
- top rules
- top evidence

Primary files:

- `src/components/lesson/LessonDetailPage.tsx`
- `src/pages/LessonPage.tsx`
- `tests/e2e/lesson.spec.ts`

### Blocker 4: accepted search behaviors need browser proof

Added browser-level regression coverage for:

- `Пример постановки стоп-лосса` -> evidence-first
- `Правила торговли на разных таймфреймах` -> rule-first
- `Как определить дневной уровень?` -> actionable-first

Primary files:

- `tests/e2e/search-regressions.spec.ts`
- `tests/e2e/search.spec.ts`

## Validation Run

Executed from `ui/explorer/`:

```powershell
npm run typecheck
npx vitest run --reporter=verbose
npm run build
npm run test:e2e
```

Results included in this bundle:

- `typecheck_output.txt` -> pass
- `vitest_output.txt` -> pass (`20` files, `27` tests)
- `build_output.txt` -> pass
- `playwright_output_latest.txt` -> pass (`11` tests)

Additional note:

- `lint_output.txt` is included for transparency, but the reported `ScreenshotModal.tsx` `react-hooks/set-state-in-effect` findings predate this audit rework and were not introduced by the detail-page/regression-test changes in this bundle.

## Screenshots Included

See `audit_screenshots/`:

- `audit-search-results.png`
- `audit-rule-detail.png`
- `audit-evidence-detail.png`
- `audit-concept-detail.png`
- `audit-lesson-detail.png`
- `audit-back-to-search.png`

These were captured against a local preview server with deterministic `/browser/*` fixture responses so the browser screenshots match the shipped UI exactly without depending on backend timing.

## Backend Files Included For Contract Reference

The UI rework does not change explorer contracts, but these backend files are included for audit traceability:

- `backend_changed_files/pipeline/explorer/api.py`
- `backend_changed_files/pipeline/explorer/contracts.py`
- `backend_changed_files/pipeline/explorer/views.py`
- `backend_changed_files/pipeline/rag/cli.py`

## Runtime Notes

- the shipped UI still consumes `/browser/*` at runtime
- the browser tests in this bundle are deterministic and fixture-backed for audit stability
- browser API samples and the documented backend launch command remain included at bundle root
