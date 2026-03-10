# What deduplicator.py does (step by step)

The deduplicator runs **after** Step 2 (frame analysis). It turns the per-frame analysis into **scenes** and then produces the final **enriched VTT** and **video commentary**.

---

## 1. Load the analysis

- Reads `data/<video_id>/dense_analysis.json`.

**How that file is generated:** Step 2 (**pipeline/dense_analyzer.py**) produces it. The analyzer takes every frame from `dense_index.json`, auto-skips frames that are structurally unchanged (using `structural_index.json`), and for the rest runs the vision/LLM agent in batches. After each batch it merges the batch response into `dense_analysis.json` and writes per-frame `frames_dense/frame_<key>.json`. So by the time Step 3 runs, `dense_analysis.json` is the full merged result of all batches. See [pipeline.md](pipeline.md) (Step 2) for the full flow.

- The file is a dictionary: keys are frame keys (e.g. `"000014"`), values are the per-frame extraction objects (e.g. `frame_timestamp`, `material_change`, `lesson_relevant`, `scene_boundary`, `change_summary`, `current_state`, etc.).
- If the file is missing, the script exits with an error and tells you to run the dense analyzer first.

**Where `lesson_relevant` and `scene_boundary` come from (Step 2):**

| Agent | Populated? | How |
|-------|------------|-----|
| **OpenAI / Gemini** | Usually no | Step 2 uses the vision API only; the production prompt does not ask for these fields. The model returns extraction JSON (e.g. `material_change`, `change_summary`) but typically omits `lesson_relevant` and `scene_boundary`. |
| **IDE** | Optional | Whatever the agent puts in the batch response JSON. |
| **Auto-skipped frames** | Partial | `frame_schema.minimal_no_change_frame()` sets `lesson_relevant: False`; no `scene_boundary`. |

When either field is missing, the deduplicator falls back: `lesson_relevant = entry.get("material_change", True)` and `scene_boundary = bool(lesson_relevant and entry.get("material_change", True))`. So **material_change** alone drives grouping.

**How valuable they are:** When present, they separate “something changed on screen” from “this change matters for the lesson” and “this is a new teaching moment,” so you get fewer one-frame scenes and less noise (e.g. cursor jitter). When missing (typical for OpenAI/Gemini), every frame with `material_change: true` can start a new scene, so scenes are finer and noisier. Adding `lesson_relevant` and `scene_boundary` to the Step 2 prompt or schema for OpenAI/Gemini would make scene grouping more useful.

---

## 2. Group frames into scenes

- **Input:** The full `dense_analysis.json` (one entry per analyzed frame).
- **Logic:** `group_scenes(analysis)` walks frames in order and decides when to **start a new scene**:
  - For each frame it reads:
    - **lesson_relevant** — whether this frame is considered relevant for the lesson (e.g. has diagram/content). If missing, it falls back to `material_change`.
    - **scene_boundary** — whether this frame should start a new scene. If missing, it is derived from `lesson_relevant` and `material_change`.
  - **New scene** starts when `scene_boundary` is true for that frame.
  - Otherwise the frame is **appended to the current scene** (same scene continues).
- **Output:** A list of **scene** objects. Each scene has:
  - `start_key`, `end_key` — first and last frame key in the scene.
  - `frames` — list of all frame keys in the scene.
  - `change_summaries` — list of `change_summary` arrays from each frame in the scene.
  - `first_entry` — the raw analysis of the first frame in the scene.
  - `first_relevant_entry` — the first frame in the scene that is `lesson_relevant` (used for summarization; falls back to `first_entry` if none).

So “deduplication” here means: many consecutive frames that belong to the same visual/teaching moment are grouped into one **scene**, instead of one description per frame.

---

## 3. Build a text summary per scene (for the agent)

- For each scene, the script builds a short **summary** of the “anchor” frame (prefer `first_relevant_entry`, else `first_entry`) using `summarize_entry()`.
- That summary is made from: `explanation_summary`, `visual_representation_type`, `current_state` (symbol, timeframe, platform, visual_facts, trading_relevant_interpretation), and `extracted_facts` / legacy `description` if needed.
- All `change_summary` items from every frame in the scene are collected into one list (“changes within scene”).

---

## 4. Write the dedup prompt (for IDE agent)

- Builds a single text prompt that describes **all scenes** to the agent.
- The prompt explains the task: “Write one polished paragraph per scene; merge changes into a natural narrative; for static scenes one sentence is enough.”
- For each scene it appends:
  - Time range `[HH:MM:SS --> HH:MM:SS]`.
  - “First frame:” plus the summarized anchor text.
  - “Changes within scene (N):” plus up to 20 change items (capped to avoid huge prompts).
- Saves this to `data/<video_id>/batches/dedup_prompt.txt`.
- If the agent is **ide** and `dedup_response.json` does **not** exist yet:
  - Writes `batches/last_agent_task.json` with paths and prompt content.
  - Prints that the agent must write polished scene descriptions to `dedup_response.json`.
  - Exits with code 10 (`AGENT_NEEDS_ANALYSIS`) and **stops** — no VTT or commentary yet. The human/IDE must produce `dedup_response.json` and re-run.

---

## 5. Call the API (for OpenAI/Gemini agent)

- If the agent is **openai** or **gemini** and `dedup_response.json` does not exist:
  - Sends the same prompt text to the corresponding API, with instructions to return a single JSON object: keys = scene start timestamps (`HH:MM:SS`), values = one polished description string per scene.
  - Parses the response (including markdown code blocks if present) and writes the result to `data/<video_id>/batches/dedup_response.json`.
- If `dedup_response.json` already exists (e.g. from a previous run or from the IDE agent), this step is skipped.

---

## 6. Load the scene descriptions

- Reads `data/<video_id>/batches/dedup_response.json`.
- Expected format: `{ "HH:MM:SS": "polished description paragraph", ... }` — one entry per scene start time.

---

## 7. Resolve which VTT file(s) to enrich

- If a **VTT override** is set (e.g. from pipeline config), only that file in `data/<video_id>/` is used.
- Otherwise, all `.vtt` files in `data/<video_id>/` are taken **except** ones whose name contains `_enriched` or `_final`.

---

## 8. Stitch enriched VTT

- For each chosen VTT file, `stitch_vtt(vtt_file, scene_map)`:
  - Reads the VTT line by line.
  - For each cue (line containing `-->`), it has a start and end timestamp.
  - For each scene start time in `scene_map`, it checks if that time falls **inside** this cue’s interval (`is_time_in_block`).
  - The first matching scene for that cue gets a line inserted right after the cue line: `[Visual: <description>]` where `<description>` is the polished text from `dedup_response.json`.
  - Each scene is inserted at most once.
- Result: the original spoken transcript plus visual blocks at the right timestamps.
- Saves as `data/<video_id>/<original_name>_enriched.vtt`.

---

## 9. Write video_commentary.md

- One markdown file per run: `data/<video_id>/video_commentary.md`.
- Header: title “Video Commentary: &lt;video_id&gt;” and a short note that it’s a non-timed visual description of every scene.
- For each scene in order:
  - A heading: `## [HH:MM:SS] Scene N (duration_s s)`.
  - The polished description from `scene_map` for that scene’s start time (or the raw first-frame summary if the key is missing).
- So the commentary is a **scene-by-scene narrative** of what is shown on screen, without cue timings inside the body.

---

## Summary

| Step | What happens |
|------|------------------|
| 1 | Load `dense_analysis.json` (per-frame analysis from Step 2). |
| 2 | Group frames into **scenes** using `lesson_relevant` / `scene_boundary` (or `material_change` fallback). |
| 3 | Build a text summary per scene (anchor frame + all change summaries). |
| 4 | Write `dedup_prompt.txt`; if agent=ide and no response yet, exit with code 10. |
| 5 | If agent=openai/gemini and no response yet, call API and write `dedup_response.json`. |
| 6 | Load `dedup_response.json` (scene start time → polished description). |
| 7 | Decide which VTT file(s) to enrich (override or all non-enriched). |
| 8 | For each VTT, insert `[Visual: ...]` at the first cue that contains each scene start time; save `*_enriched.vtt`. |
| 9 | Write `video_commentary.md` with one section per scene and the polished description. |

So in one sentence: **Deduplicator turns per-frame analysis into scenes, asks the agent for one polished description per scene, then injects those descriptions into the transcript (enriched VTT) and writes a standalone scene-by-scene commentary (video_commentary.md).**
