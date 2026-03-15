---
name: run-pipeline
description: Runs the multimodal transcript enrichment pipeline end-to-end without skipping steps. Use when the user asks to run the main pipeline, process a video, analyze frames, or generate markdown/structured outputs from a transcript plus dense frame-analysis JSON.
---

# Run Pipeline

## Entry points and CLI

- **Dense pipeline:** `uv run tim-class-pass --url "..."` or `uv run tim-class-pass --video_id "<Folder Name>"` (same via `uv run python -m pipeline.main`).
- **Component 2 (markdown/structured):** `uv run python -m pipeline.component2.main --vtt "..." --visuals-json "..." [--output-root "..."] [--video-id "..."] [flags]`
- **Required (dense):** Exactly one of `--url` or `--video_id`.

### Dense pipeline flags

- `--workers N` — Max workers for Step 1 and 1.5 (cap 8). Speeds up long videos.
- `--batch-size N` — Frames per batch in Step 2 (default from config or 10).
- `--recapture` — Force re-extraction (Step 1) and re-run 1.5–1.7.
- `--recompare` — Force re-run structural compare (Step 1.5).
- `--agent-images`, `--agent` — Step 2 agent: `ide`, `openai`, `gemini`, `mlx`, `setra`.
- `--parallel` — Step 2: write all batch task files + manifest, exit 10; after subagents finish, re-run with `--merge-only`.
- `--merge-only` — Step 2: merge all `dense_batch_response_*.json` into `dense_analysis.json`, then continue to Step 3.
- `--stop-after N` — Stop after step 1, 2, or 3 (default: run all).
- `--max-batches N` — Step 2: stop after this many batches.

Config: `data/<video_id>/pipeline.yml` (`default`) for `workers`, `video_file`, `vtt_file`, `agent_images`, `batch_size`, `capture_fps`, `llm_queue_diff_threshold`, `model_component2`, `model_component2_reducer`, etc.; CLI overrides.

## Step order (do not skip)

1. **Step 0** — Download (only if `--url`).
2. **Step 1** — Dense frame capture → `frames_dense/`, `dense_index.json`. Uses `--workers`.
3. **Step 1.5** — Structural compare → `structural_index.json`, preprocessed frames. Uses `--workers`.
4. **Step 1.6** — LLM queue selection → `llm_queue/`, `manifest.json`.
5. **Step 1.7** — Build LLM prompts → `llm_queue/*_prompt.txt`.
6. **Step 2** — Dense analysis (batched); may exit 10 for agent input.
7. **Step 3** — Component 2: filter → chunks → (optional knowledge/evidence/rules/concept-graph/ML prep/exporters) → legacy markdown.

Step 2 requires `llm_queue/manifest.json`; if missing, run Steps 1.5–1.7 first.

## Exit code 10 (agent required)

1. Read `data/<video_id>/batches/last_agent_task.json` for `prompt_file`, `response_file`, `type`, `frame_paths`, `prompt_content`.
2. Complete the batch (review images, write per-frame JSON to `response_file`). See `skills/trading_visual_extraction/SKILL.md` for schema.
3. Re-run the same command. Repeat until no exit 10.

Option B: run with `--parallel`, spawn subagents per task in `batches/manifest.json`, then re-run with `--merge-only`.

## Component 2 (markdown pipeline)

Use when the user wants RAG-ready markdown, structured JSON, or transcript+visual synthesis from existing VTT + `dense_analysis.json`.

**Requirements:** Valid Gemini (or configured provider) API key for knowledge extraction and legacy pass-1 markdown. Set via `.env` or environment (e.g. `GEMINI_API_KEY`). Without it, Steps 3.2b (knowledge extraction) and 3.3 (legacy markdown) fail; filter and chunks still run.

### Minimal run (filter + chunks + legacy markdown)

```bash
uv run python -m pipeline.component2.main --vtt "data/<video_id>/<lesson>.vtt" --visuals-json "data/<video_id>/dense_analysis.json" --output-root "data/<video_id>" --video-id "<video_id>"
```

### Full structured run (all flags)

Enables knowledge events, evidence linking, rule cards, concept graph, ML prep, new markdown render, and exporters. Requires API key.

```bash
uv run python -m pipeline.component2.main --vtt "data/<video_id>/<lesson>.vtt" --visuals-json "data/<video_id>/dense_analysis.json" --output-root "data/<video_id>" --video-id "<video_id>" --enable-knowledge-events --enable-evidence-linking --enable-rule-cards --enable-concept-graph --enable-ml-prep --enable-new-markdown-render --enable-exporters
```

Optional: `--no-preserve-legacy-markdown` skips pass-1 literal-scribe and reducer (fewer API calls). `--use-llm-review-render` / `--use-llm-rag-render` use LLM for exporter markdown when `--enable-exporters` is set.

### Component 2 outputs

- Always (when run): `filtered_visual_events.json`, `filtered_visual_events.debug.json`, `output_intermediate/<lesson>.chunks.json`, `pipeline_inspection.json`.
- With legacy markdown: `output_intermediate/<lesson>.md`, `*.llm_debug.json`, `*.reducer_usage.json`, `output_rag_ready/<lesson>.md`.
- With `--enable-knowledge-events`: `*.knowledge_events.json`, `*.knowledge_debug.json`.
- With `--enable-evidence-linking`: `*.evidence_index.json`, `*.evidence_debug.json`.
- With `--enable-rule-cards`: `*.rule_cards.json`, `*.rule_debug.json`.
- With `--enable-concept-graph`: `*.concept_graph.json`, `*.concept_graph_debug.json`.
- With `--enable-ml-prep`: `*.ml_manifest.json`, `*.labeling_manifest.json`.
- With `--enable-exporters`: `output_review/<lesson>.review_markdown.md`, `output_rag_ready/<lesson>.rag_ready.md` (from rule_cards + evidence).

## Monitoring and completion

- Progress after each batch; long runs: `data/<video_id>/processing_status.json` for ETA.
- Do not stop at exit 10: do the agent step (or subagents) and re-run until done.
- **Complete when:** `filtered_visual_events.json` exists and at least one of `output_intermediate/*.md` or `output_rag_ready/*.md` (or structured outputs if using full Component 2 flags).

## Output checklist

- `data/<video_id>/filtered_visual_events.json`
- `data/<video_id>/output_intermediate/*.md` (and/or `*.chunks.json`, `*.knowledge_events.json`, etc. per flags)
- `data/<video_id>/output_rag_ready/*.md`

