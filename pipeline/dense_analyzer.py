import os
import sys
import json
import re
import threading
import click
import base64
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
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
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try stripping trailing truncation (unclosed string/object)
        for suffix in (r',\s*$', r'"[^"]*$', r'[,\]}\s]*$'):
            trimmed = re.sub(suffix, "", text)
            if trimmed != text:
                try:
                    return json.loads(trimmed)
                except json.JSONDecodeError:
                    pass
        raise


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


def _analyze_frame_provider(
    provider_name: str,
    frame_path: str,
    prompt_text: str,
    video_id: str | None = None,
    *,
    on_event=None,
    frame_key: str | None = None,
) -> dict:
    from helpers.clients.providers import get_provider, resolve_model_for_stage

    provider = get_provider(provider_name)
    result = provider.generate_text_with_image(
        model=resolve_model_for_stage("images", video_id=video_id),
        prompt=prompt_text,
        image_path=frame_path,
        max_tokens=2000,
        temperature=0.3,
        response_mime_type="application/json",
        on_event=on_event,
        stage=f"{provider_name}_images",
        frame_key=frame_key,
    )
    if not result.text:
        raise ValueError(f"{provider_name} returned empty response for frame analysis")
    try:
        return _parse_json_from_response(result.text)
    except json.JSONDecodeError as e:
        if frame_key is None:
            raise
        # One retry on parse failure (model may return truncated JSON)
        result2 = provider.generate_text_with_image(
            model=resolve_model_for_stage("images", video_id=video_id),
            prompt=prompt_text,
            image_path=frame_path,
            max_tokens=2000,
            temperature=0.3,
            response_mime_type="application/json",
            on_event=on_event,
            stage=f"{provider_name}_images",
            frame_key=frame_key,
        )
        if result2.text:
            try:
                return _parse_json_from_response(result2.text)
            except json.JSONDecodeError:
                pass
        # Fallback so pipeline can complete
        return minimal_no_change_frame(frame_key, skip_reason="json_parse_failed")


def _analyze_frame_openai(
    frame_path: str,
    prompt_text: str,
    video_id: str | None = None,
    *,
    on_event=None,
    frame_key: str | None = None,
) -> dict:
    return _analyze_frame_provider(
        "openai",
        frame_path,
        prompt_text,
        video_id=video_id,
        on_event=on_event,
        frame_key=frame_key,
    )


def _analyze_frame_gemini(
    frame_path: str,
    prompt_text: str,
    video_id: str | None = None,
    *,
    on_event=None,
    frame_key: str | None = None,
) -> dict:
    return _analyze_frame_provider(
        "gemini",
        frame_path,
        prompt_text,
        video_id=video_id,
        on_event=on_event,
        frame_key=frame_key,
    )


def _analyze_frame_mlx(
    frame_path: str,
    prompt_text: str,
    video_id: str | None = None,
    *,
    on_event=None,
    frame_key: str | None = None,
) -> dict:
    return _analyze_frame_provider(
        "mlx",
        frame_path,
        prompt_text,
        video_id=video_id,
        on_event=on_event,
        frame_key=frame_key,
    )


def _analyze_frame_setra(
    frame_path: str,
    prompt_text: str,
    video_id: str | None = None,
    *,
    on_event=None,
    frame_key: str | None = None,
) -> dict:
    return _analyze_frame_provider(
        "setra",
        frame_path,
        prompt_text,
        video_id=video_id,
        on_event=on_event,
        frame_key=frame_key,
    )

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


def _chunk_label(chunk_keys: list[str]) -> str:
    return f"{chunk_keys[0]}-{chunk_keys[-1]}"


def partition_queue_keys(queue_keys: list[str], chunk_size: int) -> list[list[str]]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    return [queue_keys[i : i + chunk_size] for i in range(0, len(queue_keys), chunk_size)]


def _resolve_step2_chunk_workers(requested_workers: int | None) -> int:
    default_workers = max((os.cpu_count() or 1) - 2, 1)
    if requested_workers is None:
        return default_workers
    try:
        requested = int(requested_workers)
    except (TypeError, ValueError):
        return default_workers
    # Respect explicit config; cap at 8 to avoid thundering herd on API
    return min(max(requested, 1), 8)


def _write_analysis_outputs(
    analysis: dict[str, dict],
    analysis_file: str,
    frames_dir: str,
) -> None:
    sorted_analysis = dict(sorted(analysis.items(), key=lambda item: item[0]))
    with open(analysis_file, "w", encoding="utf-8") as f:
        json.dump(sorted_analysis, f, indent=2, ensure_ascii=False)
    for key, entry in sorted_analysis.items():
        json_path = os.path.join(frames_dir, f"frame_{key}.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(entry, f, indent=2, ensure_ascii=False)


def _entries_meaningfully_different(left: dict, right: dict) -> bool:
    return json.dumps(left, sort_keys=True, ensure_ascii=False) != json.dumps(
        right,
        sort_keys=True,
        ensure_ascii=False,
    )


def _process_chunk_sequential(
    *,
    chunk_index: int,
    total_chunks: int,
    batch_entries: list[tuple[str, str]],
    initial_previous_state: str,
    video_id: str,
    agent: str,
    structural_index: dict[str, dict],
    analysis_snapshot: dict[str, dict],
    total_frames: int,
    telemetry_enabled: bool,
    video_dir: str,
    status_lock: object | None = None,
    phase_label: str = "provisional",
) -> dict[str, dict]:
    batch_label = _chunk_label([key for key, _ in batch_entries])
    chunk_prefix = f"[chunk {chunk_index + 1}/{total_chunks} {batch_label} | {phase_label}]"
    print(f"{chunk_prefix} start ({len(batch_entries)} frames)", flush=True)

    def _write_status(partial_analysis: dict[str, dict], in_flight: dict | None = None) -> None:
        if not telemetry_enabled:
            return
        if status_lock is not None:
            with status_lock:
                _write_processing_status(video_dir, partial_analysis, total_frames, in_flight=in_flight)
            return
        _write_processing_status(video_dir, partial_analysis, total_frames, in_flight=in_flight)

    batch_result: dict[str, dict] = {}
    prev_state = initial_previous_state

    for idx, (key, path) in enumerate(batch_entries):
        if not os.path.exists(path):
            print(f"{chunk_prefix} warning: frame {path} not found, skipping", flush=True)
            continue
        print(f"{chunk_prefix} frame {idx + 1}/{len(batch_entries)} -> {key}", flush=True)
        prompt = _single_frame_prompt(key, path, prev_state)
        in_flight: dict[str, object] = {}
        request_usage_records: list[dict] = []

        def on_event(ev):
            kind = ev.get("kind")
            stage = ev.get("stage", "")
            provider = ev.get("provider", "")
            fk = ev.get("frame_key")
            if kind == "start":
                in_flight["current_frame"] = fk
                in_flight["current_stage"] = stage
                in_flight["current_provider"] = provider
                in_flight["last_progress_at"] = round(time.time(), 2)
                print(f"{chunk_prefix}   [{fk}] {stage}...", flush=True)
            elif kind == "chunk":
                in_flight["last_progress_at"] = round(time.time(), 2)
                in_flight["stream_chars"] = in_flight.get("stream_chars", 0) + len(ev.get("text_delta") or "")
            elif kind == "end":
                in_flight.pop("current_frame", None)
                in_flight.pop("current_stage", None)
                in_flight.pop("current_provider", None)
                in_flight.pop("stream_chars", None)
                in_flight["last_progress_at"] = round(time.time(), 2)
                meta = ev.get("meta") or {}
                usage_records = meta.get("usage_records")
                usage = meta.get("usage")
                if isinstance(usage_records, list):
                    request_usage_records[:] = usage_records
                elif isinstance(usage, dict):
                    request_usage_records[:] = [usage]
                print(f"{chunk_prefix}   [{fk}] {stage} done", flush=True)
            elif kind == "retry":
                print(f"{chunk_prefix}   [{fk}] {stage} retry {ev.get('attempt', 1)}", flush=True)
            if in_flight:
                partial = dict(analysis_snapshot)
                partial.update(batch_result)
                _write_status(partial, in_flight=in_flight)

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
        elif agent == "mlx":
            entry = _analyze_frame_mlx(path, prompt, video_id, on_event=on_event, frame_key=key)
        elif agent == "setra":
            entry = _analyze_frame_setra(path, prompt, video_id, on_event=on_event, frame_key=key)
        else:
            entry = _analyze_frame_gemini(path, prompt, video_id, on_event=on_event, frame_key=key)
        if is_significant:
            if structural_score is not None:
                entry["structural_score"] = structural_score
            if compare_seconds is not None:
                entry["timings"] = {"compare_seconds": compare_seconds}
            if request_usage_records:
                entry["request_usage"] = request_usage_records

        entry = ensure_material_change(entry)
        batch_result[key] = entry
        prev_state = json.dumps(entry, ensure_ascii=False)
        partial_analysis = dict(analysis_snapshot)
        partial_analysis.update(batch_result)
        _write_status(partial_analysis)

    print(f"{chunk_prefix} complete", flush=True)
    return batch_result


def _reprocess_chunk_boundary(
    *,
    chunk_index: int,
    total_chunks: int,
    batch_entries: list[tuple[str, str]],
    previous_chunk_state: str,
    video_id: str,
    agent: str,
    structural_index: dict[str, dict],
    analysis_snapshot: dict[str, dict],
    total_frames: int,
    telemetry_enabled: bool,
    video_dir: str,
    status_lock: object | None = None,
) -> tuple[dict[str, dict], bool]:
    boundary_key = batch_entries[0][0]
    corrected_boundary = _process_chunk_sequential(
        chunk_index=chunk_index,
        total_chunks=total_chunks,
        batch_entries=batch_entries[:1],
        initial_previous_state=previous_chunk_state,
        video_id=video_id,
        agent=agent,
        structural_index=structural_index,
        analysis_snapshot=analysis_snapshot,
        total_frames=total_frames,
        telemetry_enabled=telemetry_enabled,
        video_dir=video_dir,
        status_lock=status_lock,
        phase_label="boundary-reprocess",
    )
    return corrected_boundary, boundary_key in corrected_boundary


def _merge_chunk_results(
    analysis: dict[str, dict],
    chunk_result: dict[str, dict],
) -> dict[str, dict]:
    merged = dict(analysis)
    merged.update(chunk_result)
    return dict(sorted(merged.items(), key=lambda item: item[0]))


def run_analysis(
    video_id: str,
    batch_size: int = 10,
    agent: str = "ide",
    parallel_batches: bool = False,
    merge_only: bool = False,
    max_batches: int | None = None,
    step2_parallel_chunks: bool | None = None,
    step2_reprocess_boundaries: bool | None = None,
    step2_chunk_size: int | None = None,
    step2_chunk_workers: int | None = None,
):
    agent = _normalize_agent(agent)
    from helpers import config as pipeline_config
    from helpers.usage_report import write_video_usage_summary

    cfg = pipeline_config.get_config_for_video(video_id)
    ssim_threshold = float(cfg.get("ssim_threshold", 0.95))
    telemetry_enabled = bool(cfg.get("telemetry_enabled", True))
    step2_parallel_chunks = bool(
        cfg.get("step2_parallel_chunks", False) if step2_parallel_chunks is None else step2_parallel_chunks
    )
    step2_reprocess_boundaries = bool(
        cfg.get("step2_reprocess_boundaries", True)
        if step2_reprocess_boundaries is None
        else step2_reprocess_boundaries
    )
    step2_chunk_size = (
        cfg.get("step2_chunk_size")
        if step2_chunk_size is None
        else step2_chunk_size
    )
    step2_chunk_workers = (
        cfg.get("step2_chunk_workers")
        if step2_chunk_workers is None
        else step2_chunk_workers
    )
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
        write_video_usage_summary(video_dir)
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

    # Prefill minimal entries for every frame not in queue, so downstream filtering/synthesis has a complete timeline.
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

    chunk_size = int(step2_chunk_size or batch_size or 1)
    use_chunk_mode = (
        agent in {"openai", "gemini", "mlx", "setra"}
        and step2_parallel_chunks
        and chunk_size > 0
        and len(remaining_keys) > 1
    )

    if use_chunk_mode:
        chunk_groups = partition_queue_keys(remaining_keys, chunk_size)
        if max_batches is not None:
            chunk_groups = chunk_groups[:max_batches]
        resolved_chunk_workers = min(_resolve_step2_chunk_workers(step2_chunk_workers), max(len(chunk_groups), 1))
        status_lock = threading.Lock()
        frames_dir = os.path.join(video_dir, "frames_dense")
        print(
            "Step 2 chunk mode enabled: "
            f"{len(chunk_groups)} chunks, chunk_size={chunk_size}, workers={resolved_chunk_workers}, "
            f"boundary_reprocess={step2_reprocess_boundaries}",
            flush=True,
        )

        chunk_metadata: dict[int, dict] = {}
        with ThreadPoolExecutor(max_workers=resolved_chunk_workers) as executor:
            future_map = {}
            for chunk_index, chunk_keys in enumerate(chunk_groups):
                batch_entries = [(key, queue_index[key]) for key in chunk_keys]
                batch_label = _chunk_label(chunk_keys)
                prompt_file = os.path.join(batches_dir, f"dense_batch_prompt_{batch_label}.txt")
                response_file = os.path.join(batches_dir, f"dense_batch_response_{batch_label}.json")
                seeded_previous_state = previous_state if chunk_index == 0 else ""
                prompt_text = get_batch_prompt(batch_entries, video_dir, seeded_previous_state)
                with open(prompt_file, "w", encoding="utf-8") as f:
                    f.write(prompt_text)
                future = executor.submit(
                    _process_chunk_sequential,
                    chunk_index=chunk_index,
                    total_chunks=len(chunk_groups),
                    batch_entries=batch_entries,
                    initial_previous_state=seeded_previous_state,
                    video_id=video_id,
                    agent=agent,
                    structural_index=structural_index,
                    analysis_snapshot=analysis,
                    total_frames=len(all_keys),
                    telemetry_enabled=telemetry_enabled,
                    video_dir=video_dir,
                    status_lock=status_lock,
                )
                future_map[future] = {
                    "chunk_index": chunk_index,
                    "chunk_keys": chunk_keys,
                    "batch_entries": batch_entries,
                    "batch_label": batch_label,
                    "response_file": response_file,
                }

            for future in as_completed(future_map):
                meta = future_map[future]
                provisional_result = future.result()
                meta["provisional_result"] = provisional_result
                chunk_metadata[meta["chunk_index"]] = meta
                print(
                    f"[chunk {meta['chunk_index'] + 1}/{len(chunk_groups)} {meta['batch_label']}] provisional result ready",
                    flush=True,
                )

        final_previous_state = previous_state
        for chunk_index in range(len(chunk_groups)):
            meta = chunk_metadata[chunk_index]
            provisional_result = meta["provisional_result"]
            final_chunk_result = dict(provisional_result)
            replayed = False

            if chunk_index > 0 and step2_reprocess_boundaries:
                print(
                    f"[chunk {chunk_index + 1}/{len(chunk_groups)} {meta['batch_label']}] boundary reprocessing start",
                    flush=True,
                )
                corrected_boundary, has_boundary = _reprocess_chunk_boundary(
                    chunk_index=chunk_index,
                    total_chunks=len(chunk_groups),
                    batch_entries=meta["batch_entries"],
                    previous_chunk_state=final_previous_state,
                    video_id=video_id,
                    agent=agent,
                    structural_index=structural_index,
                    analysis_snapshot=analysis,
                    total_frames=len(all_keys),
                    telemetry_enabled=telemetry_enabled,
                    video_dir=video_dir,
                    status_lock=status_lock,
                )
                if has_boundary:
                    boundary_key = meta["chunk_keys"][0]
                    corrected_entry = corrected_boundary[boundary_key]
                    if _entries_meaningfully_different(corrected_entry, provisional_result.get(boundary_key, {})):
                        print(
                            f"[chunk {chunk_index + 1}/{len(chunk_groups)} {meta['batch_label']}] "
                            "boundary changed, replaying chunk sequentially",
                            flush=True,
                        )
                        final_chunk_result = _process_chunk_sequential(
                            chunk_index=chunk_index,
                            total_chunks=len(chunk_groups),
                            batch_entries=meta["batch_entries"],
                            initial_previous_state=final_previous_state,
                            video_id=video_id,
                            agent=agent,
                            structural_index=structural_index,
                            analysis_snapshot=analysis,
                            total_frames=len(all_keys),
                            telemetry_enabled=telemetry_enabled,
                            video_dir=video_dir,
                            status_lock=status_lock,
                            phase_label="boundary-replay",
                        )
                        replayed = True
                    else:
                        final_chunk_result[boundary_key] = corrected_entry
                        print(
                            f"[chunk {chunk_index + 1}/{len(chunk_groups)} {meta['batch_label']}] "
                            "boundary matched provisional output",
                            flush=True,
                        )

            analysis = _merge_chunk_results(analysis, final_chunk_result)
            _write_analysis_outputs(analysis, analysis_file, frames_dir)
            write_video_usage_summary(video_dir)
            if telemetry_enabled:
                _write_processing_status(video_dir, analysis, len(all_keys))
            with open(meta["response_file"], "w", encoding="utf-8") as f:
                json.dump(final_chunk_result, f, indent=2, ensure_ascii=False)
            final_previous_state = json.dumps(
                final_chunk_result[meta["chunk_keys"][-1]],
                ensure_ascii=False,
            )
            print(
                f"[chunk {chunk_index + 1}/{len(chunk_groups)} {meta['batch_label']}] "
                f"merged ({len(final_chunk_result)} frames, replayed={replayed})",
                flush=True,
            )

        remaining_keys = [k for k in queue_keys if k not in analysis]
        done_queue = len(queue_keys) - len(remaining_keys)
        previous_state = final_previous_state
        last_relevant_key = _last_relevant_key(analysis)
        if remaining_keys:
            still_remaining = len(all_keys) - len(analysis)
            print(f"{still_remaining} frames remaining. Re-run to process next chunk set.")
            sys.exit(AGENT_NEEDS_ANALYSIS)
        print(f"Analysis complete. Saved to {analysis_file}")
        return

    batches_done = 0
    while remaining_keys and (max_batches is None or batches_done < max_batches):
        batch_keys = remaining_keys[:batch_size]
        batch_entries = [(k, queue_index[k]) for k in batch_keys]

        batch_start = batch_keys[0]
        batch_end = batch_keys[-1]
        batch_label = f"{batch_start}-{batch_end}"

        prompt_file = os.path.join(batches_dir, f"dense_batch_prompt_{batch_label}.txt")
        response_file = os.path.join(batches_dir, f"dense_batch_response_{batch_label}.json")

        prompt_text = get_batch_prompt(batch_entries, video_dir, previous_state)
        with open(prompt_file, "w", encoding="utf-8") as f:
            f.write(prompt_text)

        print(f"Batch {batch_label}: {len(batch_keys)} frames (agent: {agent})")

        if not os.path.exists(response_file):
            if agent == "ide":
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
                request_usage_records: list[dict] = []

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
                            meta = ev.get("meta") or {}
                            usage_records = meta.get("usage_records")
                            usage = meta.get("usage")
                            if isinstance(usage_records, list):
                                request_usage_records[:] = usage_records
                            elif isinstance(usage, dict):
                                request_usage_records[:] = [usage]
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
                    elif agent == "mlx":
                        entry = _analyze_frame_mlx(path, prompt, video_id, on_event=on_event, frame_key=key)
                    elif agent == "setra":
                        entry = _analyze_frame_setra(path, prompt, video_id, on_event=on_event, frame_key=key)
                    else:
                        entry = _analyze_frame_gemini(path, prompt, video_id, on_event=on_event, frame_key=key)
                    if is_significant:
                        if structural_score is not None:
                            entry["structural_score"] = structural_score
                        if compare_seconds is not None:
                            entry["timings"] = {"compare_seconds": compare_seconds}
                        if request_usage_records:
                            entry["request_usage"] = request_usage_records
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
        write_video_usage_summary(video_dir)
        if telemetry_enabled:
            _write_processing_status(video_dir, analysis, len(all_keys))

        newly_done = len(analysis)
        still_remaining = len(all_keys) - newly_done

        print(f"Merged batch. Written {len(batch_result)} txt files. Total analyzed: {newly_done}/{len(all_keys)}")

        # Update for next iteration (or exit)
        remaining_keys = [k for k in queue_keys if k not in analysis]
        done_queue = len(queue_keys) - len(remaining_keys)
        if analysis:
            last_key = sorted(analysis.keys())[-1]
            previous_state = json.dumps(analysis[last_key], ensure_ascii=False)
        last_relevant_key = _last_relevant_key(analysis)
        batches_done += 1
        if agent == "ide":
            break  # IDE: one batch per run (human writes response, then re-run)

    # After loop: report and optionally exit
    if remaining_keys:
        still_remaining = len(all_keys) - len(analysis)
        print(f"{still_remaining} frames remaining. Re-run to process next batch.")
        sys.exit(AGENT_NEEDS_ANALYSIS)

    print(f"Analysis complete. Saved to {analysis_file}")

@click.command()
@click.argument("video_id")
@click.option("--batch-size", type=int, default=10, help="Frames per agent batch (default: 10)")
@click.option(
    "--agent",
    default=os.getenv("AGENT_IMAGES", os.getenv("AGENT", "ide")),
    type=click.Choice(["openai", "gemini", "mlx", "setra", "ide", "antigravity"]),
    help="Agent: ide (IDE as AI agent), openai, gemini, mlx, setra (default: ide)",
)
@click.option("--parallel", is_flag=True, help="Option B: generate all batch task files + manifest, exit 10")
@click.option("--merge-only", is_flag=True, help="Merge all dense_batch_response_*.json into dense_analysis.json and exit")
@click.option("--max-batches", type=int, default=None, help="Stop after this many batches (default: none = run all)")
def cli(video_id, batch_size, agent, parallel, merge_only, max_batches):
    """Analyze dense frames with full description + delta."""
    run_analysis(
        video_id,
        batch_size,
        agent=agent,
        parallel_batches=parallel,
        merge_only=merge_only,
        max_batches=max_batches,
    )


if __name__ == "__main__":
    cli()
