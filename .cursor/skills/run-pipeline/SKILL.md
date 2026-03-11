---
name: run-pipeline
description: Runs the multimodal transcript enrichment pipeline end-to-end without skipping steps. Use when the user asks to run the main pipeline, process a video, analyze frames, or generate markdown lesson output from a transcript plus dense frame-analysis JSON.
---

# Run Pipeline

## Entry points and CLI

- **Dense pipeline:** `uv run tim-class-pass --url "..."` or `uv run tim-class-pass --video_id "<Folder Name>"` (same options via `uv run python -m pipeline.main`).
- **Markdown pipeline:** `uv run python -m pipeline.component2.main --vtt "..." --visuals-json "..." [--output-root "..."] [--video-id "..."]`
- **Required:** Exactly one of `--url` or `--video_id`.
- **Useful flags:**
  - `--workers N` — Max workers for Step 1 (frame extraction) and Step 1.5 (structural compare). Cap 8; default `min(cpu_count, 8)`. Speeds up long videos.
  - `--batch-size N` — Frames per batch in Step 2 (default from config or 10).
  - `--recapture` — Force re-extraction of frames (Step 1) and re-run 1.5–1.7.
  - `--recompare` — Force re-run of structural compare (Step 1.5).
  - `--agent-images`, `--agent` — Set the Step 2 agent (ide, openai, gemini).
  - `--parallel` — Step 2: generate all batch task files + manifest, then exit 10; after subagents finish, re-run with `--merge-only`.
  - `--merge-only` — Step 2: merge all batch response files into `dense_analysis.json`, then continue to Step 3.

Main-pipeline config: `data/<video_id>/pipeline.yml` (`default` section) can set `workers`, `video_file`, `vtt_file`, `agent_images`, `batch_size`, `model_component2`, etc.; CLI overrides.

## Step order (do not skip)

1. **Step 0** — Download (only if `--url`).
2. **Step 1** — Dense frame capture (`dense_capturer`): 1 fps from video → `frames_dense/`, `dense_index.json`. Uses `--workers` (parallel segments when > 1).
3. **Step 1.5** — Structural compare (SSIM): `structural_compare` → `structural_index.json`, frame renames. Uses `--workers`.
4. **Step 1.6** — LLM queue selection → `llm_queue/`, `manifest.json`.
5. **Step 1.7** — Build LLM prompts → `llm_queue/*_prompt.txt`.
6. **Step 2** — Dense analysis (batched); may exit 10 for agent input.
7. **Step 3** — Component 2 + markdown synthesis → `filtered_visual_events.json`, `output_markdown/*.md`.

Step 2 needs `llm_queue/manifest.json`; if missing, Steps 1.5–1.7 must run first.

## When the pipeline exits with code 10 (agent required)

1. Read `data/<video_id>/batches/last_agent_task.json` for `prompt_file`, `response_file`, `type` (`"batch"`), `frame_paths`, and `prompt_content`.
2. **Batch:** Complete the batch task (review images per prompt, write per-frame JSON to `response_file`). See `skills/trading_visual_extraction/SKILL.md` for schema.
3. Re-run the same command (e.g. `uv run tim-class-pass --video_id "<id>"`).
4. Repeat until the run completes without exit 10 and produces the final outputs.

Option B (parallel batches): run once with `--parallel`, spawn one subagent per task from `batches/manifest.json`, then re-run with `--merge-only`.

## Monitoring and completion

- Emit progress after each batch. For long runs, use `data/<video_id>/processing_status.json` (if present) for ETA.
- Do not stop at exit 10: perform the agent step (or delegate to a subagent) and re-run until done.
- Task is complete only when `filtered_visual_events.json` and at least one markdown file under `data/<video_id>/output_markdown/` exist.

## Running the markdown pipeline

Use the markdown pipeline when the user wants RAG-ready lesson markdown, translation, or transcript + visual synthesis from an existing VTT plus dense JSON.

Example:

```bash
uv run python -m pipeline.component2.main --vtt "data/<video_id>/<lesson>.vtt" --visuals-json "data/<video_id>/dense_analysis.json" --output-root "data/<video_id>" --video-id "<video_id>"
```

Outputs:

- `filtered_visual_events.json`
- `filtered_visual_events.debug.json`
- `output_markdown/<lesson>.md`
- `output_markdown/<lesson>.chunks.json`
- `output_markdown/<lesson>.llm_debug.json`

## Output checklist

- `data/<video_id>/filtered_visual_events.json`
- `data/<video_id>/output_markdown/*.md`

