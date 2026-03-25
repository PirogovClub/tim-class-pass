# Running tests for this audit bundle

Repository root is the `tim-class-pass` checkout (or use the mirrored paths under `source/` only for inspection).

## Python — proposal queue totals, proposal routes, adjudication API

From repo root, with dev dependencies installed (`pip install -e ".[dev]"` or your project’s equivalent):

```powershell
cd H:\GITS\tim-class-pass
python -m pytest tests/adjudication_api/test_proposal_routes.py -v --tb=short
python -m pytest tests/adjudication_api/ -q
```

**Assumptions:** Python 3.12+, dependencies from `pyproject.toml`, no live adjudication server required (tests use `TestClient` and temp SQLite files).

Focused cases for this delta:

- `test_queues_proposals_total_and_pagination` — `total` is full count, `items` length respects `limit`
- `test_queues_proposals_total_respects_queue_type` — totals differ by `queue` query param
- `test_queues_proposals_quality_tier_filter_counts` — `quality_tier` filter applies to count and list

## Explorer UI — Vitest (back link + unit tests)

From `ui/explorer`:

```powershell
cd H:\GITS\tim-class-pass\ui\explorer
npm ci
npm run test -- --run
```

**Assumptions:** Node 20+ recommended, npm 10+.

Focused files for this delta:

- `src/lib/reviewQueueBackHref.test.ts`
- `src/pages/ReviewItemPage.test.tsx`

## Playwright — regenerate screenshots (optional)

Builds production assets and serves `dist/` on port 5199 (see `playwright.config.ts`).

```powershell
cd H:\GITS\tim-class-pass\ui\explorer
npm ci
npm run build
npx playwright test stage5-5-audit-screenshots.spec.ts
```

PNG output directory: `audit/stage5_5_bundle/screenshots/`.

**Assumptions:** Chromium installed via `npx playwright install chromium` if not already present.
