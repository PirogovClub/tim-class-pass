# Local MLX Benchmark Guide

## Goal

Identify the fastest local MLX vision task that passes the Gemini 2.5 parity acceptance bar for dense frame extraction, with 32GB RAM as the hard constraint.

Note: The benchmark runner is optional and lives in `helpers/benchmarking/benchmark_models.py`, with the usual CLI kept as a thin wrapper at `scripts/benchmark_models.py`.

## Acceptance Bar (from gemini_parity_plan)

For frame `000591` (and the gold evaluation set):

| Field | Required |
|-------|---------|
| `visual_representation_type` | `abstract_bar_diagram` (not `candlestick_sketch`) |
| `visual_facts` | >= 4 full sentences |
| `trading_relevant_interpretation` | list with >= 2 items |
| `structural_pattern_visible` | includes `price_action_around_level` |
| `extracted_entities.level_values` | non-empty (conceptual object) |
| `extracted_entities.stop_values` | non-empty (conceptual objects) |

## Candidate Tasks for 32GB RAM

| Task | Notes |
|------|-------|
| `mlx-vision_ocr` | Local MLX vision task (OCR-focused) |
| `mlx-vision_strategy` | Local MLX vision task (strategy-focused) |

> Note: MLX tasks are provided by your local MLX service; the task list is determined by the server configuration.

## Running the Benchmark

Ensure the MLX service is running, then:

```bash
# Run benchmark against current default + candidates:
cd H:\GITS\tim-class-pass
python scripts/benchmark_models.py --models "mlx-vision_ocr,mlx-vision_strategy"
```

Or run all candidates defined in the script:

```bash
python scripts/benchmark_models.py
```

## Cross-Provider Comparison

To compare the current Gemini default against GPT-4o mini on the same frame and scorer:

```bash
cd H:\GITS\tim-class-pass
python scripts/benchmark_models.py --models "gemini-2.5-flash-lite,gpt-4o-mini"
```

You can also use an explicit provider prefix for OpenAI:

```bash
python scripts/benchmark_models.py --models "gemini-2.5-flash-lite,openai:gpt-4o-mini"
```

Requirements:

- `GEMINI_API_KEY` must be set when any `gemini-*` model is included.
- `OPENAI_API_KEY` must be set when any OpenAI model such as `gpt-4o-mini` is included.
- The report will score both providers against the same gold file and include elapsed time, token counts, and comparable cost estimates when pricing is known.

## Switching the Default Model

If a better model is found, update `pipeline.yml` or the per-video pipeline config to set `model_images`:

```yaml
# pipeline.yml
model_images: gemini-2.5-flash-lite
```

Or override via env:

```
MODEL_IMAGES=gemini-2.5-flash-lite
```

## What Changed in Phases 1-5

Before attempting model upgrades, the following improvements were made to the pipeline (Phases 1-5):

1. **Gold eval set**: `tests/gold/frame_000591_gemini.json` + acceptance tests in `tests/test_analyze.py`
2. **Within-batch context carry-forward**: fixed in `pipeline/dense_analyzer.py` so later frames get context from earlier in-progress frames
3. **Step 3 architecture reset**: the old deduplicator-based Step 3 has been removed; the current pipeline uses the invalidation-filter + markdown-synthesis flow instead
4. **Schema expansion**: `docs/trading_visual_extraction_spec.md` + `skills/trading_visual_extraction/SKILL.md` now include:
   - `abstract_bar_diagram` vs `candlestick_sketch` disambiguation rules
   - Structured `visible_annotations` ({text, location, language})
   - Conceptual `level_values` / `stop_values` ({type, label, value_description})
   - Expanded `structural_pattern_visible` (price_action_around_level, stop_hunt, etc.)
   - Expanded `educational_event_type` vocabulary (concept_introduction, level_explanation, etc.)
   - Expanded `screen_type` (chart_with_instructor)
5. **Prompt rewrite**: Both `EXTRACTION_PROMPT` (`helpers/analyze.py`) and `PRODUCTION_PROMPT` (`pipeline/dense_analyzer.py`) now require:
   - 4-6 sentence `visual_facts` for abstract frames
   - 2-3 item `trading_relevant_interpretation` list
   - Conceptual entities instead of N/A
   - Explicit pattern terms for level-interaction diagrams
6. **Normalization upgrades**: `analyze.py` now:
   - Preserves structured entity objects (level/stop values with type/label/value_description)
   - Preserves structured annotation objects ({text, location, language})
   - Accepts expanded enum vocabulary
   - Better handles `abstract_bar_diagram` phrasing variants

## Expected Impact

With only prompt/schema changes (Phases 1-5) and a local MLX task:
- Better `visual_representation_type` classification (abstract_bar_diagram)
- Denser `visual_facts` (sentences vs. labels)
- Richer `trading_relevant_interpretation` (list vs. single string)
- Some improvement in `structural_pattern_visible` and entity extraction

Upgrading to a stronger local MLX task should additionally close:
- More reliable structured entity extraction
- Better Russian label handling (conceptual annotations)
- Stronger instruction-following for density requirements

Run `python scripts/benchmark_models.py` after prompt improvements to measure the gap.
