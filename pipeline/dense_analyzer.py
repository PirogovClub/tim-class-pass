import os
import sys
import json
import re
import argparse
import base64
import time
from dotenv import load_dotenv

from helpers.utils.compare import compare_images
from helpers.utils.frame_schema import ensure_material_change, key_to_timestamp, minimal_no_change_frame

load_dotenv()

AGENT_NEEDS_ANALYSIS = 10


def _normalize_agent(agent: str) -> str:
    """Accept 'antigravity' as alias for 'ide'."""
    if agent == "antigravity":
        return "ide"
    return agent


def _parse_json_from_response(text: str) -> dict:
    """Extract JSON from API response, handling markdown code blocks."""
    text = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        text = match.group(1).strip()
    return json.loads(text)


def _encode_image(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _single_frame_prompt(frame_key: str, frame_path: str, previous_state: str) -> str:
    """Build prompt text for analyzing one frame (for API call)."""
    return (
        f"{PRODUCTION_PROMPT}\n\n"
        f"Previous frame state: {previous_state or 'None (this is the first frame)'}\n\n"
        f"Analyze this single frame. Frame key: {frame_key}. Image path: {os.path.abspath(frame_path)}\n\n"
        "Return only valid JSON, no markdown or explanation."
    )


def _analyze_frame_openai(
    frame_path: str,
    prompt_text: str,
    video_id: str | None = None,
    *,
    on_event=None,
    frame_key: str | None = None,
) -> dict:
    from helpers.clients import openai_client
    text = openai_client.chat_completion_with_image(
        prompt_text,
        frame_path,
        step="images",
        video_id=video_id,
        max_tokens=2000,
        on_event=on_event,
        stage="openai_images",
        frame_key=frame_key,
    )
    return _parse_json_from_response(text)


def _analyze_frame_gemini(
    frame_path: str,
    prompt_text: str,
    video_id: str | None = None,
    *,
    on_event=None,
    frame_key: str | None = None,
) -> dict:
    from helpers.clients import gemini_client
    from google.genai import types
    with open(frame_path, "rb") as f:
        image_bytes = f.read()
    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_text(text=prompt_text),
                types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
            ],
        )
    ]
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        temperature=0.3,
    )
    text = gemini_client.generate_with_retry_stream(
        model=gemini_client.get_model_for_step("images", video_id),
        contents=contents,
        config=config,
        on_event=on_event,
        stage="gemini_images",
        frame_key=frame_key,
    ).strip()
    if not text:
        raise ValueError("Gemini returned empty response for frame analysis")
    return _parse_json_from_response(text)

PRODUCTION_PROMPT = """You are analyzing sequential screenshots from a trading education video for building a structured trading knowledge base.

Important:
The screen may show any of the following:
- live trading charts
- static chart screenshots
- abstract bar diagrams
- candlestick sketches
- hand-drawn pattern illustrations
- whiteboard explanations
- text slides
- mixed visuals

Do NOT assume every frame is a real market chart.
If a person/instructor is visible, ignore them unless they cover or point at the diagram.
Focus only on the chart/diagram/drawing and its text annotations.
If only the coach/person is visible (optionally with a laptop) and no diagram/text is present, return:
{ "frame_timestamp": "<timestamp>", "material_change": false, "change_summary": ["only coach is visible"] }

## Visual Representation Type — disambiguation rules

Choose EXACTLY ONE from: live_chart, static_chart_screenshot, abstract_bar_diagram, candlestick_sketch,
hand_drawn_pattern, whiteboard_explanation, text_slide, mixed_visual, unknown.

Key rule — abstract_bar_diagram vs candlestick_sketch:
- Use abstract_bar_diagram when bars/candles represent schematic price movement relative to a level, stop zone,
  or liquidity area (even if they look like candles). No real ticker or date data present.
- Use candlestick_sketch when the drawing teaches candlestick anatomy, pattern formation, or candle structure.
- Example: bars interacting with a horizontal level + stop labels → abstract_bar_diagram
- Example: instructor draws a doji/pinbar shape → candlestick_sketch

## Your task

1. Determine whether the current screenshot is materially different from the previous screenshot.
2. Identify the visual representation type.
3. Identify whether the frame is a real market example or an abstract teaching example.
4. Choose the correct extraction mode: market_specific, structural_only, or conceptual_only.
5. If there is a material change, extract the current trading-relevant visual state in structured JSON.
6. Separate direct visual facts from low-inference interpretation.
7. Do not invent exact numeric values, symbols, dates, or timeframes if they are abstract, unreadable, or unclear.
8. Copy visible labels exactly when readable. When labels are in non-Latin scripts (e.g., Russian/Cyrillic), copy them exactly.
9. Read titles/headers/annotation boxes/numeric markers before interpreting structure.

## Definition of material change

A frame is materially changed if any of the following occur:
- symbol changed
- timeframe changed
- chart or visual example changed
- zoom level changed meaningfully
- chart or diagram panned to a different relevant area
- a new level, annotation, label, drawing, arrow, or highlighted area appeared or disappeared
- the instructor switched to another concept or example
- a previously unreadable label became readable
- emphasis moved to a different important region
- the visual context changed enough to affect trading interpretation

Do NOT mark material change for:
- tiny cursor movement with no new significance
- negligible rendering differences
- repeated static frames with no meaningful new information

## Output density requirements

For ABSTRACT TEACHING FRAMES (abstract_bar_diagram, hand_drawn_pattern, candlestick_sketch, whiteboard_explanation):
- visual_facts: write 4-6 FULL SENTENCES. Each sentence describes one visible element (position, color, label,
  interaction with level). Do NOT use short labels like "Green candlesticks." Write complete sentences.
  Good: "A horizontal white line runs across the center labeled 'Уровень лимитного игрока'."
  Bad: "Horizontal line."
- trading_relevant_interpretation: write 2-3 SHORT BULLET ITEMS expressing low-inference trading insight.

For REAL CHART FRAMES (live_chart, static_chart_screenshot):
- visual_facts: 3-6 facts about visible levels, price, structure.
- trading_relevant_interpretation: 1-3 low-inference observations.

## Structural pattern visible

For abstract diagrams where bars interact with a level:
- price_action_around_level — bars interact with a horizontal level
- stop_hunt — price moves beyond a level to trigger stops
- liquidity_grab — price sweeps above/below a zone
- level_test — bars approach but do not break a level
Classic patterns: breakout, retest, false_breakout, pullback, trend_continuation, range, reversal

## Conceptual entities — no numbers required

When labels identify conceptual zones without numeric values:
- level_values: use { "type": "horizontal", "label": "<visible label>", "value_description": "conceptual price level" }
- stop_values: use { "type": "conceptual", "label": "<visible label>", "value_description": "area below/above level" }
- Do NOT return "N/A". Return [] if nothing is visible.

## screen_type values

chart, chart_with_instructor, chart_with_annotation, platform, browser, slides, mixed, unknown

## educational_event_type values (array, pick all that apply)

new_example_chart, timeframe_switch, symbol_switch, level_identification, level_explanation,
setup_annotation, pattern_highlight, entry_discussion, stop_discussion, stop_loss_placement,
target_discussion, risk_reward_discussion, atr_discussion, zoom_for_context, zoom_for_detail,
rule_slide, whiteboard_logic, concept_introduction, chart_introduction, pattern_explanation,
trade_management, none

If there is no material change, return:
{ "frame_timestamp": "<timestamp>", "material_change": false }

If there is a material change, return the full structured JSON with these fields:
frame_timestamp, material_change (true), change_summary (array of strings),
visual_representation_type, example_type, extraction_mode, screen_type,
educational_event_type (array), current_state (with symbol, timeframe, platform,
chart_type, visible_date_range, visible_price_range, chart_layout, drawn_objects,
visible_annotations, cursor_or_highlight, visual_facts, structural_pattern_visible,
trading_relevant_interpretation, readability), extracted_entities (setup_names,
level_values, risk_reward_values, atr_values, entry_values, stop_values,
target_values, pattern_terms), notes.

See skills/trading_visual_extraction/SKILL.md for the complete schema and field guidance.

Rules:
- Separate direct visual facts from interpretation.
- If the visual is abstract, do not force exact prices, dates, symbols, or timeframes.
- If the visual is hand-drawn, focus on structure, arrows, levels, and labels.
- If the visual is a real chart, capture exact values when clearly readable.
- Prefer visible labels over inferred meaning.
- Avoid calling a level support/resistance unless the image text says so.
- Avoid directional claims unless explicitly drawn (e.g., arrows) or labeled.
- drawn_objects: use structured { type, value_or_location, label } objects; list ALL visible drawings.
- visible_annotations: use structured { text, location, language } objects; copy ALL readable labels exactly.
- Return JSON only.
"""


def get_batch_prompt(batch_entries: list[tuple[str, str]], video_dir: str, previous_state: str) -> str:
    """
    Returns the production prompt for the agent to analyze a batch of frames
    using the structured trading visual extraction schema.
    batch_entries: list of (frame_key, frame_path)
    previous_state: JSON string of the last analyzed frame's structured output
    """
    lines = [
        PRODUCTION_PROMPT,
        "",
        f"Previous frame state: {previous_state or 'None (this is the first frame)'}",
        "",
        "Frames to analyze:",
    ]
    for key, path in batch_entries:
        abs_path = os.path.abspath(path)
        lines.append(f"  Frame {key}: {abs_path}")
    lines += [
        "",
        "Save your response as a JSON object to the response file.",
        "Keys are the frame numbers (e.g. \"000001\").",
        "Values are the structured extraction JSON for each frame.",
        "",
        "Example:",
        '{',
        '  "000001": { "frame_timestamp": "00:00:01", "material_change": true, "change_summary": [...], ... },',
        '  "000002": { "frame_timestamp": "00:00:02", "material_change": false }',
        '}',
        "",
        "NOTE: Per-frame .json files will be automatically written to frames_dense/ alongside each .jpg.",
    ]
    return "\n".join(lines)


def get_batch_prompt_independent(batch_entries: list[tuple[str, str]], video_dir: str) -> str:
    """
    Same as get_batch_prompt but without previous_state (Option B: independent batches).
    Use for parallel batch tasks so each subagent gets the same "how to review" prompt.
    """
    lines = [
        PRODUCTION_PROMPT,
        "",
        "Frames to analyze (review each independently; no previous frame context):",
    ]
    for key, path in batch_entries:
        abs_path = os.path.abspath(path)
        lines.append(f"  Frame {key}: {abs_path}")
    lines += [
        "",
        "Save your response as a JSON object to the response file.",
        "Keys are the frame numbers (e.g. \"000001\").",
        "Values are the structured extraction JSON for each frame.",
        "",
        "Example:",
        '{',
        '  "000001": { "frame_timestamp": "00:00:01", "material_change": true, "change_summary": [...], ... },',
        '  "000002": { "frame_timestamp": "00:00:02", "material_change": false }',
        '}',
        "",
        "NOTE: Per-frame .json files will be automatically written to frames_dense/ alongside each .jpg.",
    ]
    return "\n".join(lines)


def _previous_frame_key(all_keys: list[str], current_key: str) -> str | None:
    try:
        index = all_keys.index(current_key)
    except ValueError:
        return None
    if index <= 0:
        return None
    return all_keys[index - 1]


def _last_relevant_key(analysis: dict[str, dict]) -> str | None:
    for key in sorted(analysis.keys(), reverse=True):
        entry = analysis[key]
        if entry.get("lesson_relevant") is True:
            return key
        if "lesson_relevant" not in entry and entry.get("material_change") is True:
            return key
    return None


def _write_processing_status(
    video_dir: str,
    analysis: dict[str, dict],
    total_frames: int,
    in_flight: dict | None = None,
) -> None:
    status_path = os.path.join(video_dir, "processing_status.json")
    completed = len(analysis)
    remaining = max(total_frames - completed, 0)
    status_counts = {
        "structural_skips": 0,
        "relevance_skips": 0,
        "accepted_scene_changes": 0,
        "failures": 0,
    }
    total_timing = 0.0
    timed_frames = 0

    for entry in analysis.values():
        if entry.get("skip_reason") == "structural_unchanged":
            status_counts["structural_skips"] += 1
        if entry.get("pipeline_status") == "relevance_skipped":
            status_counts["relevance_skips"] += 1
        if entry.get("lesson_relevant") is True or (
            "lesson_relevant" not in entry and entry.get("material_change") is True
        ):
            status_counts["accepted_scene_changes"] += 1
        if entry.get("pipeline_status") == "failed":
            status_counts["failures"] += 1

        timings = entry.get("timings") or {}
        if isinstance(timings, dict) and timings:
            total_timing += sum(
                float(value)
                for value in timings.values()
                if isinstance(value, (int, float))
            )
            timed_frames += 1

    avg_seconds = round(total_timing / timed_frames, 4) if timed_frames else None
    eta_seconds = round(avg_seconds * remaining, 2) if avg_seconds is not None else None
    payload = {
        "total_frames": total_frames,
        "completed_frames": completed,
        "remaining_frames": remaining,
        "avg_seconds_per_timed_frame": avg_seconds,
        "eta_seconds": eta_seconds,
        "counts": status_counts,
    }
    if in_flight:
        payload.update(in_flight)
    with open(status_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def _load_structural_index(video_dir: str) -> dict[str, dict]:
    path = os.path.join(video_dir, "structural_index.json")
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def run_analysis(
    video_id: str,
    batch_size: int = 10,
    agent: str = "ide",
    parallel_batches: bool = False,
    merge_only: bool = False,
):
    agent = _normalize_agent(agent)
    from helpers import config as pipeline_config

    cfg = pipeline_config.get_config_for_video(video_id)
    ssim_threshold = float(cfg.get("ssim_threshold", 0.95))
    telemetry_enabled = bool(cfg.get("telemetry_enabled", True))
    video_dir = os.path.join("data", video_id)
    index_file = os.path.join(video_dir, "dense_index.json")
    analysis_file = os.path.join(video_dir, "dense_analysis.json")
    batches_dir = os.path.join(video_dir, "batches")
    os.makedirs(batches_dir, exist_ok=True)

    # ── Merge-only mode (Option B): merge all batch response files, then return ──
    if merge_only:
        import glob
        pattern = os.path.join(batches_dir, "dense_batch_response_*.json")
        response_files = sorted(glob.glob(pattern))
        if not response_files:
            print("Merge-only: No dense_batch_response_*.json files found.")
            return
        analysis = {}
        for path in response_files:
            with open(path, "r", encoding="utf-8") as f:
                batch_result = json.load(f)
            analysis.update(batch_result)
        # Sort and write dense_analysis.json
        analysis = dict(sorted(analysis.items(), key=lambda x: x[0]))
        with open(analysis_file, "w", encoding="utf-8") as f:
            json.dump(analysis, f, indent=2, ensure_ascii=False)
        # Write per-frame .json files
        frames_dir = os.path.join(video_dir, "frames_dense")
        for key, entry in analysis.items():
            json_path = os.path.join(frames_dir, f"frame_{key}.json")
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(entry, f, indent=2, ensure_ascii=False)
        if telemetry_enabled:
            _write_processing_status(video_dir, analysis, len(analysis))
        print(f"Merge-only: Merged {len(response_files)} batch files into {analysis_file} ({len(analysis)} frames).")
        return

    if not os.path.exists(index_file):
        print(f"Error: {index_file} not found. Run pipeline/dense_capturer.py first.")
        sys.exit(1)

    with open(index_file, "r", encoding="utf-8") as f:
        index = json.load(f)

    all_keys = sorted(index.keys())
    structural_index = _load_structural_index(video_dir)

    # ── LLM queue mode: only analyze frames in llm_queue/ (from Step 1.6) ──
    queue_index = {}  # key -> absolute path to image in llm_queue/
    manifest_path = os.path.join(video_dir, "llm_queue", "manifest.json")
    if not os.path.isfile(manifest_path):
        print("Error: llm_queue/manifest.json not found. Run Steps 1.5–1.7 (structural compare → select LLM frames → build prompts).")
        sys.exit(1)
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    items = manifest.get("items") or {}
    for key, info in items.items():
        rel = (info or {}).get("source") or ""
        if not rel:
            continue
        basename = os.path.basename(rel)
        path = os.path.join(video_dir, "llm_queue", basename)
        if os.path.isfile(path):
            queue_index[key] = path
    if not queue_index:
        print("Error: llm_queue/manifest.json has no usable items. Re-run Step 1.6 to rebuild the queue.")
        sys.exit(1)
    queue_keys = sorted(queue_index.keys())
    print(f"Step 2: Using llm_queue only ({len(queue_keys)} frames). Non-queue frames get minimal entries.")

    # ── Option B: generate all batch task files + manifest, exit 10 once ──
    if parallel_batches and agent == "ide":
        keys_for_batches = queue_keys
        path_for_key = (lambda k: queue_index[k])
        tasks = []
        for i in range(0, len(keys_for_batches), batch_size):
            batch_keys = keys_for_batches[i : i + batch_size]
            batch_entries = [(k, path_for_key(k)) for k in batch_keys]
            batch_start = batch_keys[0]
            batch_end = batch_keys[-1]
            batch_label = f"{batch_start}-{batch_end}"
            response_file = os.path.join(batches_dir, f"dense_batch_response_{batch_label}.json")
            prompt_content = get_batch_prompt_independent(batch_entries, video_dir)
            frame_paths = [os.path.abspath(p) for _, p in batch_entries]
            task_file = os.path.join(batches_dir, f"task_{batch_label}.json")
            task_data = {
                "prompt_content": prompt_content,
                "frame_paths": frame_paths,
                "response_file": os.path.abspath(response_file),
                "batch_label": batch_label,
            }
            with open(task_file, "w", encoding="utf-8") as f:
                json.dump(task_data, f, indent=2, ensure_ascii=False)
            tasks.append({"task_file": os.path.abspath(task_file), "response_file": os.path.abspath(response_file)})
        manifest = {"task_files": tasks, "merge_after": True}
        manifest_path = os.path.join(batches_dir, "manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
        print(f"Option B: Generated {len(tasks)} batch task files and {manifest_path}. Spawn subagents, then re-run with --merge-only.")
        sys.exit(AGENT_NEEDS_ANALYSIS)

    # Load existing analysis (partial progress)
    if os.path.exists(analysis_file):
        with open(analysis_file, "r", encoding="utf-8") as f:
            analysis = json.load(f)
    else:
        analysis = {}

    # Prefill minimal entries for every frame not in queue, so dedup has full key set.
    for key in all_keys:
        if key in analysis:
            continue
        if key in queue_keys:
            continue
        info = structural_index.get(key) if isinstance(structural_index, dict) else None
        entry = minimal_no_change_frame(key, skip_reason="not_in_llm_queue")
        if info and info.get("score") is not None:
            entry["structural_score"] = info["score"]
        if info and info.get("compare_seconds") is not None:
            entry.setdefault("timings", {})["compare_seconds"] = info["compare_seconds"]
        analysis[key] = entry
    with open(analysis_file, "w", encoding="utf-8") as f:
        json.dump(dict(sorted(analysis.items(), key=lambda x: x[0])), f, indent=2, ensure_ascii=False)
    remaining_keys = [k for k in queue_keys if k not in analysis]

    if not remaining_keys:
        print("All frames already analyzed.")
        if telemetry_enabled:
            _write_processing_status(video_dir, analysis, len(all_keys))
        return

    done_queue = len(queue_keys) - len(remaining_keys)
    print(f"Total frames: {len(all_keys)} | LLM queue: {len(queue_keys)} | Done: {done_queue} | Remaining: {len(remaining_keys)}")

    # Get the last analyzed frame's structured state for context
    if analysis:
        last_key = sorted(analysis.keys())[-1]
        previous_state = json.dumps(analysis[last_key], ensure_ascii=False)
    else:
        previous_state = ""
    last_relevant_key = _last_relevant_key(analysis)

    # Process next batch (llm_queue image path)
    batch_keys = remaining_keys[:batch_size]
    batch_entries = [(k, queue_index[k]) for k in batch_keys]

    batch_start = batch_keys[0]
    batch_end = batch_keys[-1]
    batch_label = f"{batch_start}-{batch_end}"

    prompt_file = os.path.join(batches_dir, f"dense_batch_prompt_{batch_label}.txt")
    response_file = os.path.join(batches_dir, f"dense_batch_response_{batch_label}.json")

    # Write the prompt (for ide and for reproducibility)
    prompt_text = get_batch_prompt(batch_entries, video_dir, previous_state)
    with open(prompt_file, "w", encoding="utf-8") as f:
        f.write(prompt_text)

    print(f"Batch {batch_label}: {len(batch_keys)} frames (agent: {agent})")

    if not os.path.exists(response_file):
        if agent == "ide":
            # State file for orchestrator/subagent: prompt and response paths, frame_paths, prompt_content
            state_file = os.path.join(batches_dir, "last_agent_task.json")
            frame_paths_abs = [os.path.abspath(path) for _, path in batch_entries]
            state = {
                "prompt_file": os.path.abspath(prompt_file),
                "response_file": os.path.abspath(response_file),
                "type": "batch",
                "frame_paths": frame_paths_abs,
                "prompt_content": prompt_text,
            }
            with open(state_file, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
            print(f"IDE: Batch prompt written to: {prompt_file}")
            print(f"IDE: Agent must write response to: {response_file}")
            print(f"IDE: State written to: {state_file}")
            sys.exit(AGENT_NEEDS_ANALYSIS)
        # OpenAI or Gemini: call vision API per frame and write response file
        done_after = done_queue + len(batch_keys)
        total_frames = len(queue_keys)
        print(f"Processing batch (frames {batch_start}-{batch_end}) [{done_after}/{total_frames} queued]")
        batch_result = {}
        prev_state = previous_state
        for idx, (key, path) in enumerate(batch_entries):
            if not os.path.exists(path):
                print(f"Warning: Frame {path} not found, skipping.")
                continue
            print(f"  Analyzing frame {key} ({idx + 1}/{len(batch_entries)})...")
            prompt = _single_frame_prompt(key, path, prev_state)
            in_flight = {}

            def _make_on_event(iframe_key, ivideo_dir, ianalysis, ibatch_result, itotal_frames, itelemetry_enabled, iin_flight):
                def on_event(ev):
                    kind = ev.get("kind")
                    stage = ev.get("stage", "")
                    provider = ev.get("provider", "")
                    fk = ev.get("frame_key")
                    if kind == "start":
                        iin_flight["current_frame"] = fk
                        iin_flight["current_stage"] = stage
                        iin_flight["current_provider"] = provider
                        iin_flight["last_progress_at"] = round(time.time(), 2)
                        print(f"    [{fk}] {stage}...", flush=True)
                    elif kind == "chunk":
                        iin_flight["last_progress_at"] = round(time.time(), 2)
                        iin_flight["stream_chars"] = iin_flight.get("stream_chars", 0) + len(ev.get("text_delta") or "")
                    elif kind == "end":
                        iin_flight.pop("current_frame", None)
                        iin_flight.pop("current_stage", None)
                        iin_flight.pop("current_provider", None)
                        iin_flight.pop("stream_chars", None)
                        iin_flight["last_progress_at"] = round(time.time(), 2)
                        print(f"    [{fk}] {stage} done", flush=True)
                    elif kind == "retry":
                        print(f"    [{fk}] {stage} retry {ev.get('attempt', 1)}", flush=True)
                    if itelemetry_enabled and iin_flight:
                        partial = dict(ianalysis)
                        partial.update(ibatch_result)
                        _write_processing_status(ivideo_dir, partial, itotal_frames, in_flight=iin_flight)
                return on_event

            on_event = _make_on_event(key, video_dir, analysis, batch_result, total_frames, telemetry_enabled, in_flight)
            try:
                frame_started = time.perf_counter()
                structural_info = structural_index.get(key) if isinstance(structural_index, dict) else None
                structural_score = None
                compare_seconds = None
                is_significant = True

                if structural_info:
                    is_significant = bool(structural_info.get("is_significant", True))
                    if structural_info.get("score") is not None:
                        structural_score = float(structural_info.get("score"))
                    compare_seconds = structural_info.get("compare_seconds")

                if not is_significant:
                    entry = minimal_no_change_frame(key)
                    if structural_score is not None:
                        entry["structural_score"] = structural_score
                    entry["timings"] = {
                        "compare_seconds": compare_seconds,
                        "total_seconds": round(time.perf_counter() - frame_started, 4),
                    }
                elif agent == "openai":
                    entry = _analyze_frame_openai(path, prompt, video_id, on_event=on_event, frame_key=key)
                    if structural_score is not None:
                        entry["structural_score"] = structural_score
                    if compare_seconds is not None:
                        entry["timings"] = {"compare_seconds": compare_seconds}
                else:
                    entry = _analyze_frame_gemini(path, prompt, video_id, on_event=on_event, frame_key=key)
                    if structural_score is not None:
                        entry["structural_score"] = structural_score
                    if compare_seconds is not None:
                        entry["timings"] = {"compare_seconds": compare_seconds}
                entry = ensure_material_change(entry)
                batch_result[key] = entry
                prev_state = json.dumps(entry, ensure_ascii=False)
                if entry.get("lesson_relevant") is True or (
                    "lesson_relevant" not in entry and entry.get("material_change") is True
                ):
                    last_relevant_key = key
                if telemetry_enabled:
                    partial_analysis = dict(analysis)
                    partial_analysis.update(batch_result)
                    _write_processing_status(video_dir, partial_analysis, len(all_keys))
            except Exception as e:
                print(f"Error analyzing frame {key}: {e}")
                raise
        with open(response_file, "w", encoding="utf-8") as f:
            json.dump(batch_result, f, indent=2, ensure_ascii=False)
        print(f"API: Wrote batch response to {response_file}")

    # Read and merge batch response
    with open(response_file, "r", encoding="utf-8") as f:
        batch_result = json.load(f)

    analysis.update(batch_result)

    # Write per-frame .json files in frames_dense/ alongside the .jpg
    frames_dir = os.path.join(video_dir, "frames_dense")
    for key, entry in batch_result.items():
        json_path = os.path.join(frames_dir, f"frame_{key}.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(entry, f, indent=2, ensure_ascii=False)

    with open(analysis_file, "w", encoding="utf-8") as f:
        json.dump(analysis, f, indent=2, ensure_ascii=False)
    if telemetry_enabled:
        _write_processing_status(video_dir, analysis, len(all_keys))

    newly_done = len(analysis)
    still_remaining = len(all_keys) - newly_done

    print(f"Merged batch. Written {len(batch_result)} txt files. Total analyzed: {newly_done}/{len(all_keys)}")

    if still_remaining > 0:
        print(f"IDE: {still_remaining} frames remaining. Re-run to process next batch.")
        sys.exit(AGENT_NEEDS_ANALYSIS)

    print(f"Analysis complete. Saved to {analysis_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze dense frames with full description + delta")
    parser.add_argument("video_id", help="Video ID in data/")
    parser.add_argument("--batch-size", type=int, default=10, help="Frames per agent batch (default: 10)")
    parser.add_argument(
        "--agent",
        default=os.getenv("AGENT_IMAGES", os.getenv("AGENT", "ide")),
        choices=["openai", "gemini", "ide", "antigravity"],
        help="Agent: ide (IDE as AI agent), openai, gemini (default: ide)",
    )
    parser.add_argument("--parallel", action="store_true", help="Option B: generate all batch task files + manifest, exit 10")
    parser.add_argument("--merge-only", action="store_true", help="Merge all dense_batch_response_*.json into dense_analysis.json and exit")
    args = parser.parse_args()
    run_analysis(
        args.video_id,
        args.batch_size,
        agent=args.agent,
        parallel_batches=args.parallel,
        merge_only=args.merge_only,
    )
