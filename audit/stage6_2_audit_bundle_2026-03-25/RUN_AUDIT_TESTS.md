# Run audit tests — Stage 6.2 gap closure (2026-03-25)

## Environment

- Python 3.12+ recommended
- From repository root: `h:\GITS\tim-class-pass` (or your clone), with project dependencies installed (`pip install -e .` or equivalent)

## Pytest (corpus + legacy corpus tests + lesson registry)

```bash
python -m pytest tests/corpus tests/test_corpus.py tests/contracts/test_lesson_registry.py -q
```

## Build corpus (CLI)

Paths below are relative to the repo root.

```bash
python -m pipeline.corpus.cli build ^
  --corpus-root audit/stage6_2_audit_bundle_2026-03-25/examples/corpus_input ^
  --lesson-registry audit/stage6_2_audit_bundle_2026-03-25/examples/lesson_registry.json ^
  --output-root audit/stage6_2_audit_bundle_2026-03-25/examples/corpus_output
```

(Use `\` line continuation on Unix instead of `^`.)

## Validate corpus outputs

```bash
python -m pipeline.corpus.cli validate ^
  --output-root audit/stage6_2_audit_bundle_2026-03-25/examples/corpus_output ^
  --lesson-registry audit/stage6_2_audit_bundle_2026-03-25/examples/lesson_registry.json ^
  --report audit/stage6_2_audit_bundle_2026-03-25/examples/corpus_validation_report.json
```

## Outputs

- Built corpus files: `audit/stage6_2_audit_bundle_2026-03-25/examples/corpus_output/`
- Validation JSON: `audit/stage6_2_audit_bundle_2026-03-25/examples/corpus_validation_report.json`
