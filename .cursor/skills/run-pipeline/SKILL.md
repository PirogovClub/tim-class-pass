---
name: run-pipeline
description: Runs the multimodal transcript enrichment pipeline end-to-end without skipping steps. Use when the user asks to run the pipeline, process a video, analyze frames, or generate enriched VTT/commentary. Monitors progress, provides updates, and continues through agent-required steps until outputs exist.
---

# Run Pipeline

## Quick Start
- Use `uv run pipeline/main.py --url ...` or `uv run pipeline/main.py --video_id ...`.
- Do not skip any steps. Follow the pipeline order as implemented by `pipeline/main.py`.

## Run-to-Completion Workflow
1. Start the pipeline with the requested URL or video_id.
2. If the run exits with code 10 (agent input required):
   - Read `data/<video_id>/batches/last_agent_task.json`.
   - Complete the task (batch or dedup), write the response file.
   - Re-run the same `uv run pipeline/main.py ...` command.
3. Repeat until `*_enriched.vtt` and `video_commentary.md` are produced.

## Monitoring and Updates
- Provide progress updates after each batch merge and after dedup completes.
- If the run is long, emit periodic status notes (e.g., frames processed / remaining).
- Never abandon a run mid-way. Continue until completion unless the user explicitly asks to stop.

## Do Not Skip Steps
- Always run the full sequence: download (if URL) → frame capture → structural compare → LLM queue → prompt build → analysis → dedup.
- Step 2 requires `llm_queue/manifest.json`; if missing, run Steps 1.5–1.7 first.

## Output Checklist
- `data/<video_id>/*_enriched.vtt`
- `data/<video_id>/video_commentary.md`

