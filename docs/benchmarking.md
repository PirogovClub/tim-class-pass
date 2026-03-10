# Benchmarking (optional)

Benchmarking is **not** the primary workflow. The main functionality of this repo is **information extraction** from frames into structured JSON. Use benchmarks only when you want to compare models or validate prompt changes.

## Where the benchmark lives

- **Core runner:** `helpers/benchmarking/benchmark_models.py`
- **CLI wrapper:** `scripts/benchmark_models.py` (recommended entrypoint)
- **Prompt builder:** `scripts/build_benchmark_frame_prompt.py` (reused across runs)

## When to run

- After prompt changes that should improve extraction quality.
- Before switching to a new model or provider.
- When tracking cost/performance changes across model updates.

## How to run

```bash
python scripts/benchmark_models.py --models gemini-2.5-flash-lite-preview-09-2025
```

Other common modes:

```bash
python scripts/benchmark_models.py --ps
python scripts/benchmark_models.py --ps --gemini
```

## Outputs

Reports are written to `benchmark-reports/benchmark_<timestamp>.json` (or `--output PATH`). Each entry includes:

- prompt used
- normalized model output
- elapsed time
- token counts and estimated costs (Gemini only)

## Current model focus

For routine checks, use `gemini-2.5-flash-lite-preview-09-2025` as the default benchmark model.
