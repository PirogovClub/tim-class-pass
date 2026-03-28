from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

SINGLE_FRAME_PROMPT = """You are analyzing a single frame from a trading education video for building a structured trading knowledge base.

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

1. Identify the visual representation type.
2. Identify whether the frame is a real market example or an abstract teaching example.
3. Choose the correct extraction mode: market_specific, structural_only, or conceptual_only.
4. Extract the current trading-relevant visual state in structured JSON.
5. Separate direct visual facts from low-inference interpretation.
6. Do not invent exact numeric values, symbols, dates, or timeframes if they are abstract, unreadable, or unclear.
7. Copy visible labels exactly when readable. When labels are in non-Latin scripts (e.g., Russian/Cyrillic), copy them exactly.
8. Read titles/headers/annotation boxes/numeric markers before interpreting structure.

Set material_change to true. The only exception: if only the coach is visible, return the minimal JSON shown above.

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

Return the full structured JSON with these fields:
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


def _build_prompt(frame_key: str, image_path: Path) -> str:
    return (
        f"{SINGLE_FRAME_PROMPT}\n\n"
        f"Analyze this single frame. Frame key: {frame_key}. Image path: {os.path.abspath(image_path)}\n\n"
        "Return only valid JSON, no markdown or explanation."
    )


def build_llm_prompts(video_id: str) -> Path:
    video_dir = Path("data") / video_id
    queue_dir = video_dir / "llm_queue"
    manifest_path = queue_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Missing manifest: {manifest_path}")

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    items: dict[str, dict] = manifest.get("items") or {}
    written = 0

    for key, info in items.items():
        rel_path = info.get("source")
        if not rel_path:
            continue
        image_path = video_dir / rel_path
        if not image_path.exists():
            continue
        prompt_text = _build_prompt(key, image_path)
        prompt_path = queue_dir / f"{image_path.stem}_prompt.txt"
        with open(prompt_path, "w", encoding="utf-8") as f:
            f.write(prompt_text)
        written += 1

    print(f"Step 1.7: Prompt files written: {written} | folder: {queue_dir}")
    return queue_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Build per-frame prompt files for llm_queue.")
    parser.add_argument("--video_id", required=True, help="Video ID folder under data/")
    args = parser.parse_args()

    build_llm_prompts(args.video_id)


if __name__ == "__main__":
    main()
