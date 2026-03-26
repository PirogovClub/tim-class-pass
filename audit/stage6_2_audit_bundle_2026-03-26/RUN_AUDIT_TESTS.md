# Run Stage 6.2 checks

## Environment

- Python 3.12+
- Repo root: `h:\GITS\tim-class-pass`
- `PYTHONPATH` set to repo root or editable install

## Tests

```powershell
Set-Location h:\GITS\tim-class-pass
$env:PYTHONPATH = "h:\GITS\tim-class-pass"
python -m pytest tests/corpus tests/contracts -q
```

## Build lesson registry from example corpus input

```powershell
python -m pipeline.contracts.cli registry audit/stage6_2_audit_bundle_2026-03-26/examples/corpus_input -o audit/stage6_2_audit_bundle_2026-03-26/examples/lesson_registry.json
```

## Build corpus outputs

```powershell
python -m pipeline.corpus.cli build --lesson-registry audit/stage6_2_audit_bundle_2026-03-26/examples/lesson_registry.json --input-root audit/stage6_2_audit_bundle_2026-03-26/examples/corpus_input --output-root audit/stage6_2_audit_bundle_2026-03-26/examples/corpus_output
```

## Validate corpus outputs

```powershell
python -m pipeline.corpus.cli validate --output-root audit/stage6_2_audit_bundle_2026-03-26/examples/corpus_output --lesson-registry audit/stage6_2_audit_bundle_2026-03-26/examples/lesson_registry.json --report audit/stage6_2_audit_bundle_2026-03-26/examples/corpus_validation_report.json
```

CLI entrypoint (if installed): `corpus-cli build ...` / `corpus-cli validate ...`
