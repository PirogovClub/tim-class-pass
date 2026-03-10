---
description: How to run the Multimodal YouTube Video Transcript Enrichment Pipeline
---

// turbo-all

# Multimodal Transcript Enrichment Workflow (Dense Mode)

Analyzes every second of a video, generates per-frame visual descriptions, groups them into scenes, and produces an enriched `.vtt` transcript + `video_commentary.md` screenplay.

---

## Critical: Do not stop until the pipeline is complete

When you run this workflow, **you must not stop** after the first pipeline run (exit code 10). The pipeline exits with code 10 when it needs agent input; that is your signal to **continue**, not to report and wait.

**Your obligation:** After each exit 10, immediately (in the same session):
1. Read the prompt file that was written (batch or dedup).
2. Perform the required agent step (view frames and write response JSON, or write dedup_response.json).
3. Re-run the pipeline with the same `--video_id` (or `--url`).
4. Repeat until the pipeline run **completes without exit 10** and produces `*_enriched.vtt` and `video_commentary.md`.

Do **not** report "Pipeline paused — agent analysis required" and then stop. Do **not** ask the user to fill the response files or re-run. You must do the analysis and re-run yourself, in a loop, until the workflow is finished.

---

## Quick Start

### From a YouTube URL:
```bash
uv run pipeline/main.py --url "https://www.youtube.com/watch?v=VIDEO_ID" --batch-size 10
```

### From an existing video folder (video + VTT already present):
```bash
uv run pipeline/main.py --video_id VIDEO_ID --batch-size 10
```

**Agents:** Step 2 (frame analysis) and Step 3 (dedup) can use different agents. Set per-video in `pipeline.yml`, or override with `--agent-images` / `--agent-dedup` / `--agent`. Choices: `ide` (IDE as AI agent — pipeline writes prompts, you fill responses, re-run), `openai`, `gemini`. With `openai` or `gemini` for both steps the pipeline runs to completion without exit 10.

**When using gemini:** Set `GEMINI_API_KEY` in `.env`. Model is chosen from `pipeline.yml` (optional `model_name`, `model_images`, `model_dedup`) or env (`MODEL_NAME`, `MODEL_IMAGES`, etc.). See README “Gemini usage” and `skills/gemini_usage/SKILL.md`.

When using **ide** for either step, the pipeline exits with **code 10** each time agent input is required. Re-run the command after completing each agent step.

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

> [!IMPORTANT]
> Use the **structured JSON schema** from `skills/trading_visual_extraction/SKILL.md` for all frame analysis. Do NOT use free-text description+delta format.

**Your job:**
1. Read the batch prompt file to understand which frames to analyze and what the previous frame state looked like.
2. For each frame in the batch, `view_file` the `.jpg` path.
3. Write a JSON response file `dense_batch_response_NNN-MMM.json`:

```json
{
  "000001": {
    "frame_timestamp": "00:00:01",
    "material_change": true,
    "change_summary": ["Scene start — MetaTrader 4 opens with EUR/USD Daily chart"],
    "visual_representation_type": "live_chart",
    "example_type": "real_market_example",
    "extraction_mode": "market_specific",
    "screen_type": "platform",
    "educational_event_type": ["new_example_chart"],
    "current_state": {
      "symbol": "EUR/USD",
      "timeframe": "Daily",
      "platform": "MetaTrader 4",
      "chart_type": "candlestick",
      "visible_date_range": null,
      "visible_price_range": "1.1580 – 1.2370",
      "chart_layout": { "main_chart_present": true, "indicator_panels_present": false, "watchlist_present": false, "order_panel_present": false },
      "drawn_objects": [],
      "visible_annotations": [],
      "cursor_or_highlight": { "present": false, "location": null, "target": null },
      "visual_facts": ["Downtrend visible from approx 1.2370 to 1.1580"],
      "structural_pattern_visible": [],
      "trading_relevant_interpretation": [],
      "readability": { "text_confidence": "high", "numeric_confidence": "medium", "structure_confidence": "high" }
    },
    "extracted_entities": { "setup_names": [], "level_values": [], "risk_reward_values": [], "atr_values": [], "entry_values": [], "stop_values": [], "target_values": [], "pattern_terms": [] },
    "notes": null
  },
  "000002": {
    "frame_timestamp": "00:00:02",
    "material_change": false
  }
}
```

**Rules:**
- `material_change: false` → minimal record (just timestamp + false). Use ONLY after viewing the frame and confirming no change.
- `material_change: true` → full structured JSON as shown above. See `skills/trading_visual_extraction/SKILL.md` for complete field guidance.
- Separate **visual facts** from **interpretation**. Do not mix.
- Do not invent values for abstract/unreadable visuals. Use `null` and mark confidence `"low"`.

4. Re-run the pipeline. It will merge the batch and write the next prompt.

**DO NOT STOP.** After re-running, if the pipeline exits with code 10 again, immediately handle the next batch (read new prompt, view frames, write response, re-run). Continue until all batches are done and the pipeline moves to Step 3.

**DO THIS AUTONOMOUSLY IN A LOOP** — you MUST `view_file` every single frame in the batch before writing any response. Writing `material_change: false` without first viewing the frame is strictly forbidden. Scene changes can occur at any frame without warning.

---

### STEP 3: Deduplication (runs once after all frames analyzed)

The pipeline writes `batches/dedup_prompt.txt` and exits.

**Your job:**
1. Read `batches/dedup_prompt.txt` — it lists ~50–80 scenes grouped by visual change.
2. For each scene, write a single polished paragraph:
   - Merge all deltas into a natural flowing narrative
   - Static scenes: one sentence suffices
   - Active scenes (drawing, annotation): describe the progression clearly
3. Save response to `batches/dedup_response.json`:

```json
{
  "00:00:11": "The instructor draws the first red horizontal resistance line on the EUR/USD Daily chart at approximately 1.1862, then adds two more lines at 1.2270 and 1.1960, building a complete support/resistance map across the downtrend.",
  "00:00:55": "The MetaTrader window is minimized, leaving a blank screen — a brief transition before the next scene.",
  "00:00:56": "MS Paint opens and the instructor begins drawing an ATR calculation diagram..."
}
```

4. Re-run the pipeline one final time to produce outputs.

**DO NOT STOP** after writing `dedup_response.json`. Re-run the pipeline in the same session so that it produces the final `*_enriched.vtt` and `video_commentary.md`. Only then is the workflow complete.

---

## Verification

After the final run confirm:
```bash
# All frame json files created
(Get-ChildItem "data\<VIDEO_ID>\frames_dense" -Filter "*.json").Count

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
| `frames_dense/frame_NNNNNN.json` | Per-frame structured extraction |
| `dense_analysis.json` | Full merged frame-by-frame analysis |
| `batches/dense_batch_prompt_NNN-MMM.txt` | Batch prompt for agent |
| `batches/dense_batch_response_NNN-MMM.json` | Batch response from agent |
| `batches/dedup_prompt.txt` | Scene grouping prompt |
| `batches/dedup_response.json` | Polished scene descriptions |
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
