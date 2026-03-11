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
python scripts/benchmark_models.py --models gemini-2.5-flash-lite
```

Other common modes:

```bash
python scripts/benchmark_models.py --ps
python scripts/benchmark_models.py --ps --gemini
python scripts/benchmark_models.py --models "gemini-2.5-flash-lite,gpt-4o-mini"
python scripts/benchmark_models.py --models "gemini-2.5-flash-lite,openai:gpt-4o-mini"
```

Provider notes:

- Gemini models use their raw API ids such as `gemini-2.5-flash-lite`.
- OpenAI models can be passed as raw ids like `gpt-4o-mini` or with an explicit `openai:` prefix such as `openai:gpt-4o-mini`.
- `--gemini` appends all current Gemini multimodal models from the live API to whatever is already in `--models`.
- MLX models still use the `mlx-*` task names exposed by the local service.

## Outputs

Reports are written to `benchmark-reports/benchmark_<timestamp>.json` (or `--output PATH`). Each entry includes:

- prompt used
- normalized model output
- elapsed time
- token counts
- estimated costs for Gemini and supported OpenAI models

## Current model focus

For routine checks, use `gemini-2.5-flash-lite` as the default benchmark model.
