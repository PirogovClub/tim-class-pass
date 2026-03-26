# Running Stage 5.7 audit checks

From the repository root (set `PYTHONPATH` so `pipeline` resolves):

```text
set PYTHONPATH=.
python -m pytest tests/adjudication_api/test_metrics_stage57.py -v
python -m pytest tests/adjudication_api/ -q
```

Regenerate example JSON:

```text
set PYTHONPATH=.
python scripts/generate_stage57_audit_examples.py
```

UI (optional):

```text
cd ui/explorer
npm run test -- --run src/pages/ReviewMetricsPage.test.tsx
```
