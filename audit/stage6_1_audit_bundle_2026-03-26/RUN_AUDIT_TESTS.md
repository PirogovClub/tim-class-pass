# Rerun Stage 6.1 + gap checks

## Environment

- Python 3.12+
- Repo root: `tim-class-pass`
- `PYTHONPATH` = repo root (or editable install)

## Tests

```powershell
Set-Location h:\GITS\tim-class-pass
$env:PYTHONPATH = "h:\GITS\tim-class-pass"
python -m pytest tests/contracts -q
```

## Static compile (no Ruff in project)

```powershell
python -m compileall -q pipeline/contracts tests/contracts
```

## Build registry (example corpus in this bundle)

```powershell
python -m pipeline.contracts.cli registry audit/stage6_1_audit_bundle_2026-03-26/examples/corpus_example -o lesson_registry.json
```

## Validate corpus + registry cross-check

```powershell
python -m pipeline.contracts.cli validate audit/stage6_1_audit_bundle_2026-03-26/examples/corpus_example -r validator_report.json --registry lesson_registry.json
```

Entry point when installed: `lesson-contract registry …` / `lesson-contract validate …`
