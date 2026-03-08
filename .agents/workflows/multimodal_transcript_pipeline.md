---
description: How to run the Multimodal YouTube Video Transcript Enrichment Pipeline
---

// turbo-all

# Multimodal Transcript Enrichment Workflow (Dense Mode)

Analyzes every second of a video, generates per-frame visual descriptions, groups them into scenes, and produces an enriched `.vtt` transcript + `video_commentary.md` screenplay.

---

## Quick Start

### From a YouTube URL:
```bash
uv run main.py --url "https://www.youtube.com/watch?v=VIDEO_ID" --batch-size 10
```

### From an existing video folder (video + VTT already present):
```bash
uv run main.py --video_id VIDEO_ID --batch-size 10
```

The pipeline exits with **code 10** each time agent input is required. Re-run the command after completing each agent step.

---

## Step-by-Step Agent Instructions

### STEP 1: Initial Run

Run the pipeline command above. It will:
- Download the video + transcript (if `--url`)
- Extract 1 frame per second → `data/<id>/frames_dense/`
- Write the first batch prompt and exit

---

### STEP 2: Dense Frame Analysis (repeats for every batch)

The pipeline writes `dense_batch_prompt_NNN-MMM.txt` and exits.

**Your job:**
1. Read the batch prompt file to understand which frames to analyze and what the previous frame looked like.
2. For each frame in the batch, `view_file` the `.jpg` path.
3. Write a JSON response file `dense_batch_response_NNN-MMM.json`:

```json
{
  "000001": { "description": "Full description of what is on screen", "delta": "Scene start" },
  "000002": { "description": "Same as before", "delta": "No change" },
  "000003": { "description": "Same chart, new red horizontal line added at 1.1960", "delta": "Added: red horizontal line at 1.1960" }
}
```

**Description rules:**
- Describe all visible elements: application name, chart type, instrument, timeframe, price levels, annotations, instructor webcam position
- Be specific about what's drawn/written on screen

**Delta rules:**
- `"Scene start"` — first frame only
- `"No change"` — screen is essentially identical to previous frame
- `"Added: <element>"` — something new appeared (new line drawn, label added, cursor moved to point something out)
- `"Scene change: <brief description>"` — completely different application, chart, or significant layout change

4. Re-run the pipeline. It will merge the batch and write the next prompt.

**DO THIS AUTONOMOUSLY IN A LOOP** — you MUST `view_file` every single frame in the batch before writing any response. Writing "No change" without first viewing the frame is strictly forbidden. Scene changes can occur at any frame without warning.

---

### STEP 3: Deduplication (runs once after all frames analyzed)

The pipeline writes `dedup_prompt.txt` and exits.

**Your job:**
1. Read `dedup_prompt.txt` — it lists ~50–80 scenes grouped by visual change.
2. For each scene, write a single polished paragraph:
   - Merge all deltas into a natural flowing narrative
   - Static scenes: one sentence suffices
   - Active scenes (drawing, annotation): describe the progression clearly
3. Save response to `dedup_response.json`:

```json
{
  "00:00:11": "The instructor draws the first red horizontal resistance line on the EUR/USD Daily chart at approximately 1.1862, then adds two more lines at 1.2270 and 1.1960, building a complete support/resistance map across the downtrend.",
  "00:00:55": "The MetaTrader window is minimized, leaving a blank screen — a brief transition before the next scene.",
  "00:00:56": "MS Paint opens and the instructor begins drawing an ATR calculation diagram..."
}
```

4. Re-run the pipeline one final time to produce outputs.

---

## Verification

After the final run confirm:
```bash
# All frame txt files created
(Get-ChildItem "data\<VIDEO_ID>\frames_dense" -Filter "*.txt").Count

# Final outputs present
Get-ChildItem "data\<VIDEO_ID>" -Filter "*_enriched.vtt"
Get-ChildItem "data\<VIDEO_ID>" -Filter "video_commentary.md"
```

Read the first 40 lines of `video_commentary.md` to confirm the narrative reads coherently.

---

## Output Files

| File | Description |
|------|-------------|
| `frames_dense/frame_NNNNNN.jpg` | 1fps extracted frames |
| `frames_dense/frame_NNNNNN.txt` | Per-frame description + delta |
| `dense_analysis.json` | Full merged frame-by-frame analysis |
| `*_enriched.vtt` | **Final**: original spoken VTT + `[Visual: ...]` scene blocks |
| `video_commentary.md` | **Final**: polished visual-only screenplay |

---

## Rules for Analysis

> [!CAUTION]
> **You MUST view every frame before writing its description. No exceptions.**
> Skipping frames and writing "No change" without viewing is strictly forbidden.
> Scene changes (chart timeframe switch, new application, annotation added) can happen at any frame.

| Situation | Strategy |
|-----------|----------|
| Any frame | Call `view_file` on it FIRST, then write description and delta |
| Looks similar to previous | Still view it — verify before writing "No change" |
| Active drawing / annotation | View every frame; changes happen every 1–3 seconds |
| Scene transition detected | Mark delta as `"Scene change: <description>"` |

**Batch size:** Default 10 is safe.
