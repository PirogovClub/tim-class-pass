# Rerun Stage 6.1 checks

## Assumptions

- Python 3.12+
- Repo root: `tim-class-pass`
- Dependencies installed (`pip install -e .` or equivalent with dev extras for pytest)

## Tests

```powershell
Set-Location h:\GITS\tim-class-pass
$env:PYTHONPATH = "h:\GITS\tim-class-pass"
python -m pytest tests/contracts -q
```

## Build `lesson_registry.json`

From a corpus root whose children are lesson folders containing `output_intermediate/`:

```powershell
Set-Location h:\GITS\tim-class-pass
$env:PYTHONPATH = "h:\GITS\tim-class-pass"
python -m pipeline.contracts.cli registry path\to\corpus_root -o path\to\lesson_registry.json
```

Flags: `--no-validate` skips per-lesson validation; `--lenient` uses lenient validator mode.

## Run corpus validator

```powershell
python -m pipeline.contracts.cli validate path\to\corpus_root -r validator_report.json
```

Optional: `--registry lesson_registry.json` to cross-check paths, hashes, and counts.

Console entry point (if installed): `lesson-contract registry …` / `lesson-contract validate …`
