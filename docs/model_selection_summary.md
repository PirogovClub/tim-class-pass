# Model Selection Summary

## Decision

Use `gemini-2.5-flash-lite` as the default model across the repo for image recognition and related Gemini-powered stages.

## Why

Benchmarks run on `frame_000474_diff_0.0908.jpg` showed that `gemini-2.5-flash-lite` had the best overall tradeoff between quality, latency, token usage, and cost.

Head-to-head result against `gpt-4.1-mini`:

| Model | Prompt tokens | Output tokens | Elapsed | Notes |
|------|---------------|---------------|---------|-------|
| `gemini-2.5-flash-lite` | 832 | 334 | 4.11s | Richer `visual_facts`, lower token usage, much faster |
| `gpt-4.1-mini` | 2012 | 322 | 12.64s | Acceptable quality, but slower and more expensive in practice |

Earlier cross-provider checks on the same benchmark image also showed:

- `gpt-4o-mini` used far more prompt tokens in this flow and is not a good default choice.
- `gemini-2.5-flash-lite-preview-09-2025` was fast, but `gemini-2.5-flash-lite` was the preferred stable default.

## Benchmark Artifacts

- `benchmark-reports/benchmark_2026-03-11T11-50-45.json`
- `benchmark-reports/benchmark_2026-03-11T12-38-07.json`
- `benchmark-reports/benchmark_2026-03-11T12-40-16.json`

## Important Caveat

The benchmark scorer is still tuned to an older acceptance pattern that expects `price_action_around_level` and non-empty `stop_values`. For the `000474` reference frame, that means `passes: false` should not be treated as the primary decision signal. The model choice above is based on the actual output quality, token counts, runtime, and cost behavior from the saved reports.

## Defaulting Policy

Unless a stage has a deliberate reason to use something else, default to:

`gemini-2.5-flash-lite`

This now applies to:

- built-in Gemini client defaults
- default stage provider resolution for `images`, `gaps`, `vlm`, and analysis stages
- project example configs and environment template
- the current lesson pipeline config
