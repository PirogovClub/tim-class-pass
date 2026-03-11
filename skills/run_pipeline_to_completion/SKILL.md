---
name: Run Pipeline to Completion
description: Run the multimodal transcript enrichment pipeline from start to finish without stopping; complete every batch-analysis step and re-run until the requested markdown outputs exist. Use subagents for batch steps when possible.
---

# Run Pipeline to Completion

When you run this project's dense pipeline (`uv run tim-class-pass --video_id ...` or `--url ...`), run it **from beginning to end**. Use `--workers N` (cap 8) to speed up Step 1 (frame extraction) and Step 1.5 (structural compare) on long videos. The current defaults are tuned for recall: dense capture is typically `0.5 fps`, structural compare uses grayscale+blur SSIM, and the queue threshold is lower than before.

## Do not stop at exit code 10

The pipeline exits with **code 10** when it needs Step 2 batch input. That is your signal to **continue**, not to stop.

## Two modes: sequential (default) vs Option B (parallel)

### Sequential mode (default)

After each exit 10:

1. Read `data/<video_id>/batches/last_agent_task.json` to get `prompt_file`, `response_file`, `type` (`"batch"`), and `frame_paths`; optionally `prompt_content` (full prompt text).
2. **Spawn a subagent** (e.g. `mcp_task`, subagent_type `generalPurpose`) with a single task:
   - **Batch:** "You are processing one batch. Use the prompt (how to review each image) provided below. View each frame image at the listed paths. Follow the schema in `skills/trading_visual_extraction/SKILL.md`. Write a single JSON object to `<response_file>`: keys = frame numbers (e.g. \"000001\"), values = per-frame extraction JSON. Do not run the pipeline." If state has `prompt_content`, embed it in the task; otherwise tell the subagent to read `prompt_file`.
3. Wait for the subagent to complete (response file exists and is valid).
4. Re-run the same command (`uv run tim-class-pass --video_id ...` or `--url ...`).
5. Repeat until the pipeline completes without exit 10 and produces markdown outputs.

### Option B (parallel batches)

To run all frame-analysis batches in parallel with subagents:

1. Run once with **--parallel**: `uv run tim-class-pass --video_id <id> --parallel`. Step 1 runs (extract frames); Step 2 generates all batch task files (`batches/task_*.json`) and `batches/manifest.json`, then exits 10.
2. Read `data/<video_id>/batches/manifest.json`. It contains `task_files`: a list of `{ "task_file", "response_file" }`.
3. **Spawn one subagent per task** in parallel. Each subagent receives one task file: it contains `prompt_content` (how to review), `frame_paths`, `response_file`. The subagent views those images (or calls an external vision API with the same prompt) and writes the JSON to `response_file`. Same contract for "review images" and "call API" subagents.
4. Wait until **all** response files exist.
5. Re-run with **--merge-only**: `uv run tim-class-pass --video_id <id> --merge-only`. Step 2 merges all `dense_batch_response_*.json` into `dense_analysis.json`, then Step 3 runs automatically.

## What you must not do

- Do **not** report "Pipeline paused" and wait for the user.
- Do **not** ask the user to fill the response files or re-run.
- You must perform the agent step (yourself or via subagents) and re-run in a loop until the run finishes.

Only when the pipeline run completes without exit 10 and the final outputs exist is the task complete.

Required outputs:

- `filtered_visual_events.json`
- `output_intermediate/<lesson>.md`
- `output_rag_ready/<lesson>.md`
- the final RAG-ready markdown file looks coherent on a quick read
