# Running Stage 5.7 audit checks

## Environment

- **Python 3.12+** with dev deps from repo `pyproject.toml`.
- **Node 20+** for `ui/explorer` (Vitest / Playwright).
- Repository root: set `PYTHONPATH` (Windows `set PYTHONPATH=.`, PowerShell `$env:PYTHONPATH=(Get-Location)`) so `import pipeline` works.

## Backend tests

```text
cd <repo-root>
set PYTHONPATH=.
python -m pytest tests/adjudication_api/test_metrics_stage57.py -v
python -m pytest tests/adjudication_api/ -q
```

## Regenerate example JSON

Writes to **`audit/stage5_7_audit_bundle_2026-03-26/examples/`**:

```text
set PYTHONPATH=.
python scripts/generate_stage57_audit_examples.py
```

## Call metrics HTTP API

With adjudication API running (same app that mounts `adjudication_router`), e.g.:

```text
curl -s http://127.0.0.1:8000/adjudication/metrics/summary
curl -s "http://127.0.0.1:8000/adjudication/metrics/throughput?window=7d"
```

(Replace host/port with your server.)

## Frontend unit tests

```text
cd ui/explorer
npm run test -- --run src/pages/ReviewMetricsPage.test.tsx
```

## Screenshot (Playwright)

Builds `dist/`, starts preview on port **5199**, mocks metrics fetches, saves PNG under **`audit/stage5_7_audit_bundle_2026-03-26/screenshots/`**:

```text
cd ui/explorer
npm run audit:screenshots:5.7
```
