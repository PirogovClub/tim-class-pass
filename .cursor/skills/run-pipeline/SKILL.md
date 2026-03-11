---
name: run-pipeline
description: Runs the multimodal transcript enrichment pipeline end-to-end without skipping steps. Use when the user asks to run the pipeline, process a video, analyze frames, or generate enriched VTT/commentary. Monitors progress, provides updates, and continues through agent-required steps until outputs exist.
---

# Run Pipeline

## Entry point and CLI

- **Command:** `uv run tim-class-pass --url "..."` or `uv run tim-class-pass --video_id "<Folder Name>"` (same options via `uv run python -m pipeline.main`).
- **Required:** Exactly one of `--url` or `--video_id`.
- **Useful flags:**
  - `--workers N` — Max workers for Step 1 (frame extraction) and Step 1.5 (structural compare). Cap 8; default `min(cpu_count, 8)`. Speeds up long videos.
  - `--batch-size N` — Frames per batch in Step 2 (default from config or 10).
  - `--recapture` — Force re-extraction of frames (Step 1) and re-run 1.5–1.7.
  - `--recompare` — Force re-run of structural compare (Step 1.5).
  - `--agent-images`, `--agent-dedup`, `--agent` — Set agent for Step 2 (ide, openai, gemini) and/or Step 3.
  - `--parallel` — Step 2: generate all batch task files + manifest, then exit 10; after subagents finish, re-run with `--merge-only`.
  - `--merge-only` — Step 2: merge all batch response files into `dense_analysis.json`, then run Step 3 (use after parallel subagents completed).

Config: `pipeline.yml` (project or `data/<video_id>/`) can set `workers`, `video_file`, `vtt_file`, `agent_images`, `agent_dedup`, `batch_size`, etc.; CLI overrides.

## Step order (do not skip)

1. **Step 0** — Download (only if `--url`).
2. **Step 1** — Dense frame capture (`dense_capturer`): 1 fps from video → `frames_dense/`, `dense_index.json`. Uses `--workers` (parallel segments when > 1).
3. **Step 1.5** — Structural compare (SSIM): `structural_compare` → `structural_index.json`, frame renames. Uses `--workers`.
4. **Step 1.6** — LLM queue selection → `llm_queue/`, `manifest.json`.
5. **Step 1.7** — Build LLM prompts → `llm_queue/*_prompt.txt`.
6. **Step 2** — Dense analysis (batched); may exit 10 for agent input.
7. **Step 3** — Deduplication → `*_enriched.vtt`, `video_commentary.md`; may exit 10 for dedup agent.

Step 2 needs `llm_queue/manifest.json`; if missing, Steps 1.5–1.7 must run first.

## When the pipeline exits with code 10 (agent required)

1. Read `data/<video_id>/batches/last_agent_task.json` for `prompt_file`, `response_file`, `type` ("batch" | "dedup"), and for batch: `frame_paths`, `prompt_content`.
2. **Batch:** Complete the batch task (review images per prompt, write per-frame JSON to `response_file`). See `skills/trading_visual_extraction/SKILL.md` for schema.
3. **Dedup:** Write a JSON map of scene timestamps (HH:MM:SS) to polished paragraphs to `response_file`.
4. Re-run the same command (e.g. `uv run tim-class-pass --video_id "<id>"`).
5. Repeat until the run completes without exit 10 and produces the final outputs.

Option B (parallel batches): run once with `--parallel`, spawn one subagent per task from `batches/manifest.json`, then re-run with `--merge-only`.

## Monitoring and completion

- Emit progress after each batch and after dedup. For long runs, use `data/<video_id>/processing_status.json` (if present) for ETA.
- Do not stop at exit 10: perform the agent step (or delegate to a subagent) and re-run until done.
- Task is complete only when `*_enriched.vtt` and `video_commentary.md` exist under `data/<video_id>/`.

## Output checklist

- `data/<video_id>/*_enriched.vtt`
- `data/<video_id>/video_commentary.md`

