---
name: Run Pipeline to Completion
description: Run the multimodal transcript enrichment pipeline from start to finish without stopping; complete every agent step and re-run until final outputs exist. Use subagents for batch and dedup steps when possible.
---

# Run Pipeline to Completion

When you run this project's pipeline (`uv run tim-class-pass --video_id ...` or `--url ...`), run it **from beginning to end**. Use `--workers N` (cap 8) to speed up Step 1 (frame extraction) and Step 1.5 (structural compare) on long videos.

## Do not stop at exit code 10

The pipeline exits with **code 10** when it needs agent input (batch response or dedup response). That is your signal to **continue**, not to stop.

## Two modes: sequential (default) vs Option B (parallel)

### Sequential mode (default)

After each exit 10:

1. Read `data/<video_id>/batches/last_agent_task.json` to get `prompt_file`, `response_file`, `type` ("batch" | "dedup"), and for batch: `frame_paths`; optionally `prompt_content` (full prompt text).
2. **Spawn a subagent** (e.g. `mcp_task`, subagent_type `generalPurpose`) with a single task:
   - **Batch:** "You are processing one batch. Use the prompt (how to review each image) provided below. View each frame image at the listed paths. Follow the schema in `skills/trading_visual_extraction/SKILL.md`. Write a single JSON object to `<response_file>`: keys = frame numbers (e.g. \"000001\"), values = per-frame extraction JSON. Do not run the pipeline." If state has `prompt_content`, embed it in the task; otherwise tell the subagent to read `prompt_file`.
   - **Dedup:** "Read the dedup prompt (or use the embedded prompt_content below). Write a JSON object to `<response_file>` mapping each scene timestamp (HH:MM:SS) to one polished paragraph. Do not run the pipeline."
3. Wait for the subagent to complete (response file exists and is valid).
4. Re-run the same command (`uv run tim-class-pass --video_id ...` or `--url ...`).
5. Repeat until the pipeline completes without exit 10 and produces `*_enriched.vtt` and `video_commentary.md`.

### Option B (parallel batches)

To run all frame-analysis batches in parallel with subagents:

1. Run once with **--parallel**: `uv run tim-class-pass --video_id <id> --parallel`. Step 1 runs (extract frames); Step 2 generates all batch task files (`batches/task_*.json`) and `batches/manifest.json`, then exits 10.
2. Read `data/<video_id>/batches/manifest.json`. It contains `task_files`: a list of `{ "task_file", "response_file" }`.
3. **Spawn one subagent per task** in parallel. Each subagent receives one task file: it contains `prompt_content` (how to review), `frame_paths`, `response_file`. The subagent views those images (or calls an external vision API with the same prompt) and writes the JSON to `response_file`. Same contract for "review images" and "call API" subagents.
4. Wait until **all** response files exist.
5. Re-run with **--merge-only**: `uv run tim-class-pass --video_id <id> --merge-only`. Step 2 merges all `dense_batch_response_*.json` into `dense_analysis.json`, then Step 3 (dedup) runs. If Step 3 uses IDE agent it may exit 10 for dedup; then use the sequential flow above for the single dedup step (read `last_agent_task.json`, spawn one subagent, write `dedup_response.json`, re-run).

## What you must not do

- Do **not** report "Pipeline paused" and wait for the user.
- Do **not** ask the user to fill the response files or re-run.
- You must perform the agent step (yourself or via subagents) and re-run in a loop until the run finishes.

Only when the pipeline run completes without exit 10 and the final outputs exist (`*_enriched.vtt`, `video_commentary.md`) is the task complete.
