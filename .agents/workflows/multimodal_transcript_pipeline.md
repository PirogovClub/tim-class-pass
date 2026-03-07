---
description: How to run the Multimodal YouTube Video Transcript Enrichment Pipeline
---

// turbo-all

# Multimodal Transcript Enrichment Workflow (Dense Mode)

The pipeline captures **1 frame per second** for the entire video, has the agent analyze each frame with a full description + delta, then produces a polished enriched VTT and a `video_commentary.md` screenplay.

## Project Structure
```text
data/<video_id>/
├── <video_id>.mp4                   # Video file
├── *.vtt                            # Original transcript (yt-dlp or Whisper)
├── frames_dense/                    # 1fps extracted frames (frame_000001.jpg ...)
├── dense_index.json                 # Second → frame path mapping
├── dense_batch_prompt_<N>-<M>.txt   # Batch prompt for agent (frames N–M)
├── dense_batch_response_<N>-<M>.json # Agent's analysis for that batch
├── dense_analysis.json              # Full merged analysis (description + delta per second)
├── dedup_prompt.txt                 # Scene grouping prompt for agent
├── dedup_response.json              # Agent's polished scene descriptions
├── *_enriched.vtt                   # Final VTT with [Visual: ...] blocks
└── video_commentary.md              # Non-timed full visual screenplay
```

## Running the Pipeline

### Option A: From URL
```
uv run main.py --url <youtube_url> --provider antigravity --batch-size 10
```

### Option B: Existing video folder (Whisper VTT + video already present)
```
uv run main.py --video_id <video_id> --provider antigravity --batch-size 10
```

## Agent Steps (Antigravity Mode)

The pipeline exits with **code 10** whenever agent analysis is needed. Re-run after completing each step.

---

### Step 2: Dense Frame Analysis (repeats per batch)

When the pipeline writes `dense_batch_prompt_<N>-<M>.txt` and exits:

1. Read the batch prompt file to get the list of frame paths and the previous description context.
2. For each frame in the batch (in order):
   - Use `view_file` on the absolute `.jpg` path to see the frame.
   - Write a **full description** of what is on screen (software visible, chart type, price levels, annotations, what instructor is drawing).
   - Compare description text (not images) to the **previous frame's description** and write a **delta**:
     - `"No change"` — screen is essentially identical
     - `"Added: <element>"` — minor addition (new line drawn, new label, cursor moved to point)
     - `"Scene change: <brief description>"` — completely different screen or significant rearrangement
3. Save your response JSON to `dense_batch_response_<N>-<M>.json`:
```json
{
  "000001": { "description": "...", "delta": "Scene start" },
  "000002": { "description": "...", "delta": "No change" },
  ...
}
```
4. Re-run the pipeline. It will merge this batch and start the next one.

> **Batch size guidance:** Default is 10. If coherence drifts, reduce to 5. Don't exceed 20.

---

### Step 3: Deduplication

When the pipeline writes `dedup_prompt.txt` and exits:

1. Read `dedup_prompt.txt` — it contains scenes grouped by visual change with their deltas.
2. For each scene (timestamp range), write a single polished paragraph:
   - Merge all deltas into a flowing narrative (no mechanical bullet lists).
   - For static scenes (no change): one sentence describing what is shown.
   - For scenes with many deltas: describe the progression naturally.
3. Save your response to `dedup_response.json`:
```json
{
  "00:00:53": "The instructor opens a EUR/USD daily bar chart in MetaTrader...",
  "00:01:17": "The instructor switches to MS Paint and begins drawing a diagram...",
  ...
}
```
4. Re-run the pipeline. It will produce `*_enriched.vtt` and `video_commentary.md`.

---

## Verification

After completion, the agent should:
1. Confirm `frames_dense/` has ~1 frame per second of video duration
2. Confirm `dense_analysis.json` has an entry per second with both `description` and `delta`
3. Read `video_commentary.md` — it should read as a coherent standalone visual narrative
4. Spot-check `*_enriched.vtt` — `[Visual: ...]` blocks should appear only at scene-change timestamps, not every second
