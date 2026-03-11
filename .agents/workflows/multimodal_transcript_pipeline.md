---
description: How to run the Multimodal YouTube Video Transcript Enrichment Pipeline
---

// turbo-all

# Multimodal Transcript Enrichment Workflow

Analyzes every second of a video, generates per-frame visual descriptions, then runs the new Step 3 markdown synthesis flow to produce lesson markdown and debug artifacts.

---

## Critical: Do not stop until the pipeline is complete

When you run this workflow, **you must not stop** after the first pipeline run (exit code 10). The pipeline exits with code 10 when it needs agent input; that is your signal to **continue**, not to report and wait.

**Your obligation:** After each exit 10, immediately (in the same session):
1. Read the prompt file that was written for the batch.
2. Perform the required batch step (view frames and write response JSON).
3. Re-run the pipeline with the same `--video_id` (or `--url`).
4. Repeat until the pipeline run **completes without exit 10** and produces markdown outputs under `output_markdown/`.

Do **not** report "Pipeline paused — agent analysis required" and then stop. Do **not** ask the user to fill the response files or re-run. You must do the analysis and re-run yourself, in a loop, until the workflow is finished.

---

## Quick Start

### From a YouTube URL:
```bash
uv run tim-class-pass --url "https://www.youtube.com/watch?v=VIDEO_ID" --batch-size 10
```

### From an existing video folder (video + VTT already present):
```bash
uv run tim-class-pass --video_id VIDEO_ID --batch-size 10
```

**Agents:** Step 2 (frame analysis) can use `ide`, `openai`, or `gemini`. Step 3 is the markdown synthesis flow and uses Gemini via the shared client. Set Step 2 per-video in `data/<video_id>/pipeline.yml`, or override with `--agent-images` / `--agent`.

**When using gemini:** Set `GEMINI_API_KEY` in `.env`. Model is chosen from `pipeline.yml` (optional `model_name`, `model_images`, `model_component2`) or env (`MODEL_NAME`, `MODEL_IMAGES`, etc.). See README “Gemini usage” and `skills/gemini_usage/SKILL.md`.

When using **ide** for Step 2, the pipeline exits with **code 10** each time batch input is required. Re-run the command after completing each batch.

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

### STEP 3: Markdown synthesis (runs automatically after all frames analyzed)

Once Step 2 is complete, the pipeline:

1. Filters `dense_analysis.json` into `filtered_visual_events.json`
2. Parses the VTT and builds lesson chunks
3. Calls Gemini structured outputs
4. Writes:
   - `filtered_visual_events.json`
   - `filtered_visual_events.debug.json`
   - `output_markdown/<lesson>.md`
   - `output_markdown/<lesson>.chunks.json`
   - `output_markdown/<lesson>.llm_debug.json`

If Gemini is configured correctly, Step 3 should not pause for manual agent input.

---

## Verification

After the final run confirm:
```bash
# All frame json files created
(Get-ChildItem "data\<VIDEO_ID>\frames_dense" -Filter "*.json").Count

# Final outputs present
Get-ChildItem "data\<VIDEO_ID>" -Filter "filtered_visual_events.json"
Get-ChildItem "data\<VIDEO_ID>\output_markdown" -Filter "*.md"
```

Read the first 40 lines of the generated markdown file to confirm the narrative reads coherently.

---

## Output Files

| File | Description |
|------|-------------|
| `frames_dense/frame_NNNNNN.jpg` | 1fps extracted frames |
| `frames_dense/frame_NNNNNN.json` | Per-frame structured extraction |
| `dense_analysis.json` | Full merged frame-by-frame analysis |
| `batches/dense_batch_prompt_NNN-MMM.txt` | Batch prompt for agent |
| `batches/dense_batch_response_NNN-MMM.json` | Batch response from agent |
| `filtered_visual_events.json` | Instructional visual events only |
| `filtered_visual_events.debug.json` | Filter report |
| `output_markdown/<lesson>.md` | **Final**: synthesized lesson markdown |
| `output_markdown/<lesson>.chunks.json` | Chunk debug output |
| `output_markdown/<lesson>.llm_debug.json` | LLM debug output |

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
