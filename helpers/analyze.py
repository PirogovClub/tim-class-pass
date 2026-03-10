from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any

from helpers import config as pipeline_config
from helpers.utils.frame_schema import ensure_material_change, key_to_timestamp, minimal_relevance_skip_frame

EXTRACTION_PROMPT = """You are analyzing sequential screenshots from a trading education video for building a structured trading knowledge base.

Important:
The screen may show any of: live trading charts, static chart screenshots, abstract bar diagrams,
candlestick sketches, hand-drawn pattern illustrations, whiteboard explanations, text slides, mixed visuals.
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
- Use candlestick_sketch when the drawing teaches candlestick anatomy, pattern formation shape, or candle
  structure (e.g. explaining what a pinbar or engulfing looks like). Not about level interaction.
- Example: bars interacting with a horizontal level + stop labels → abstract_bar_diagram
- Example: instructor draws a doji/pinbar shape to explain the candle → candlestick_sketch

## Your task

1. Determine whether the current screenshot is materially different from the previous screenshot.
2. Identify the visual representation type using the rules above.
3. Identify whether the frame is a real market example or an abstract teaching example.
4. Choose extraction mode: market_specific, structural_only, or conceptual_only.
5. If there is a material change, extract the current trading-relevant visual state in structured JSON.
6. Separate direct visual facts (visual_facts) from low-inference interpretation (trading_relevant_interpretation).
7. Do not invent exact numeric values, symbols, dates, or timeframes if they are abstract, unreadable, or unclear.
8. Copy visible labels exactly when readable. When labels are in non-Latin scripts (e.g., Russian/Cyrillic), copy them exactly.
9. Read titles/headers/annotation boxes/numeric markers before interpreting structure.

## Definition of material change

Mark material_change true if: symbol/timeframe/chart/example changed; zoom/pan changed relevant area;
new level, annotation, label, drawing, arrow, or highlight appeared/disappeared; instructor switched concept/example;
previously unreadable label became readable; emphasis moved; visual context changed enough to affect trading interpretation.

Mark material_change false for: tiny cursor movement with no new significance; negligible rendering differences;
repeated static frames with no meaningful new information.

If there is no material change, return only:
{ "frame_timestamp": "<timestamp>", "material_change": false }

## Output density requirements

For ABSTRACT TEACHING FRAMES (abstract_bar_diagram, hand_drawn_pattern, candlestick_sketch, whiteboard_explanation):
- visual_facts: write 4-6 FULL SENTENCES, each describing one clearly visible element
  (e.g. position, color, label, interaction with level). Do NOT use short labels like "Green candlesticks."
  Good example: "A horizontal white line runs across the center of the diagram, labeled 'Уровень лимитного игрока'."
  Bad example: "Horizontal line."
- trading_relevant_interpretation: write 2-3 SHORT BULLET ITEMS, each expressing one low-inference
  trading insight about what the diagram is teaching. Keep inference minimal.
  Good example: "The diagram illustrates price interaction with a limit player's level."
  Bad example: "This is a bullish setup."

For REAL CHART FRAMES (live_chart, static_chart_screenshot):
- visual_facts: 3-6 facts about what is visible (levels, price, structure).
- trading_relevant_interpretation: 1-3 low-inference observations.

## Structural pattern visible

Use generic pattern names. For abstract diagrams where bars interact with a level, use:
- price_action_around_level — when bars/candles interact with a horizontal level
- stop_hunt — when the diagram shows price exceeding a level to trigger stops
- liquidity_grab — when the diagram shows price sweeping above/below a zone
- level_test — when bars approach but do not break a level
Classic patterns: breakout, retest, false_breakout, pullback, trend_continuation, range, reversal

## Conceptual entities — no numbers required

When labels identify conceptual zones without numeric values, still fill extracted_entities:
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

If there is a material change, return the full structured JSON with: frame_timestamp, material_change (true),
change_summary (array of strings), visual_representation_type, example_type, extraction_mode, screen_type,
educational_event_type (array), current_state (symbol, timeframe, platform, chart_type, visible_date_range,
visible_price_range, chart_layout, drawn_objects, visible_annotations, cursor_or_highlight, visual_facts,
structural_pattern_visible, trading_relevant_interpretation, readability), extracted_entities (setup_names,
level_values, risk_reward_values, atr_values, entry_values, stop_values, target_values, pattern_terms), notes.

Rules:
- visual_facts: only directly visible facts; no inferred claims.
- trading_relevant_interpretation: low-inference only.
- Prefer visible labels over inferred meaning.
- Avoid calling a level support/resistance unless the image text says so.
- Avoid directional claims unless explicitly drawn (e.g., arrows) or labeled.
- If the visual is abstract, do not force exact prices, dates, symbols, or timeframes.
- drawn_objects: use structured { type, value_or_location, label } objects; list ALL visible drawings.
- visible_annotations: use structured { text, location, language } objects; copy ALL readable labels exactly.
- Return JSON only.
"""

RELEVANCE_PROMPT = """You are deciding whether a visual change in a trading lesson matters to the lesson itself.

Return only valid JSON with these fields:
- lesson_relevant: boolean
- scene_boundary: boolean
- change_summary: array of short strings
- explanation_summary: string or null
- skip_reason: string or null

Rules:
- Ignore visual changes that do not matter to the lesson.
- Ignore UI jitter, cursor movement, or decorative changes.
- If relevant, explain what changed and why it matters to the lesson.
- If not relevant, set explanation_summary to null and provide a concise skip_reason.
"""


def _parse_json_from_response(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        text = match.group(1).strip()
    return json.loads(text)


def _fallback_relevance_decision(extracted: dict[str, Any]) -> dict[str, Any]:
    current_state = extracted.get("current_state") or {}
    visual_facts = current_state.get("visual_facts") if isinstance(current_state, dict) else []
    change_summary = extracted.get("change_summary")
    summary_items = [str(item) for item in _as_list(change_summary) if item]
    lesson_relevant = bool(summary_items or visual_facts or extracted.get("material_change"))
    explanation = None
    if lesson_relevant:
        explanation = "; ".join(summary_items[:2] or [str(item) for item in visual_facts[:2]])
    return {
        "lesson_relevant": lesson_relevant,
        "scene_boundary": lesson_relevant,
        "change_summary": summary_items or [str(item) for item in visual_facts[:2]] or ["Visual content changed"],
        "explanation_summary": explanation,
        "skip_reason": None if lesson_relevant else "relevance_parse_failed",
    }


def _stringify_visible_facts(raw: dict[str, Any]) -> list[str]:
    facts: list[str] = []
    content = raw.get("content")
    if isinstance(content, dict):
        text = content.get("text")
        if isinstance(text, dict):
            for key, value in text.items():
                if value:
                    facts.append(f"{key}: {value}")
        chart = content.get("chart")
        if isinstance(chart, dict):
            chart_type = chart.get("type")
            if chart_type:
                facts.append(f"chart_type: {chart_type}")
            stop = chart.get("stop")
            if isinstance(stop, dict):
                for key, value in stop.items():
                    if value:
                        facts.append(f"stop_{key}: {value}")
    current_state = raw.get("current_state")
    if isinstance(current_state, dict):
        visual_facts = current_state.get("visual_facts")
        if isinstance(visual_facts, list):
            facts.extend(str(item) for item in visual_facts if item)
        chart = current_state.get("chart")
        if isinstance(chart, dict):
            for label_key in ("title", "subtitle", "type"):
                if chart.get(label_key):
                    facts.append(f"{label_key}: {chart[label_key]}")
    return facts


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _canonical_visual_type(value: Any, has_chart: bool, has_text: bool) -> str:
    raw = str(value or "").strip().lower()
    # Normalize space variants
    if raw in {"candlestick sketch", "candlestick sketches"}:
        return "candlestick_sketch"
    if raw in {"whiteboard explanation", "whiteboard explanations"}:
        return "whiteboard_explanation"
    if raw in {"text slide", "text slides"}:
        return "text_slide"
    if raw in {"abstract bar diagram", "abstract_bar_diagram", "bar diagram"}:
        return "abstract_bar_diagram"
    if raw in {"hand drawn pattern", "hand_drawn_pattern", "hand drawn"}:
        return "hand_drawn_pattern"
    if raw in {"mixed visual", "mixed_visual"}:
        return "mixed_visual"
    if raw in {"live chart", "live_chart"}:
        return "live_chart"
    if raw in {"static chart screenshot", "static_chart_screenshot", "static chart", "chart screenshot"}:
        return "static_chart_screenshot"
    if raw in {
        "live_chart",
        "static_chart_screenshot",
        "abstract_bar_diagram",
        "candlestick_sketch",
        "hand_drawn_pattern",
        "whiteboard_explanation",
        "text_slide",
        "mixed_visual",
        "unknown",
    }:
        return raw
    if "abstract" in raw and "bar" in raw:
        return "abstract_bar_diagram"
    if "candlestick" in raw or "candle" in raw:
        return "candlestick_sketch"
    if "hand" in raw and "draw" in raw:
        return "hand_drawn_pattern"
    if "whiteboard" in raw or "board" in raw:
        return "whiteboard_explanation"
    if "chart" in raw and has_text:
        return "mixed_visual"
    if "chart" in raw:
        return "static_chart_screenshot"
    if "slide" in raw or "educational" in raw:
        return "text_slide"
    return "mixed_visual" if has_chart or has_text else "unknown"


def _canonical_extraction_mode(value: Any, has_chart: bool) -> str:
    raw = str(value or "").strip().lower()
    mapping = {
        "market_specific": "market_specific",
        "structural_only": "structural_only",
        "conceptual_only": "conceptual_only",
        "structural": "structural_only",
        "conceptual": "conceptual_only",
    }
    if raw in mapping:
        return mapping[raw]
    return "structural_only" if has_chart else "conceptual_only"


def _canonical_screen_type(value: Any, has_chart: bool, has_text: bool) -> str:
    raw = str(value or "").strip().lower()
    if raw in {"chart", "platform", "browser", "slides", "mixed", "unknown", "chart_with_instructor", "chart_with_annotation"}:
        return raw
    if has_chart and has_text:
        return "mixed"
    if has_text:
        return "slides"
    if has_chart:
        return "chart"
    return "unknown"


def _looks_canonical(raw: dict[str, Any]) -> bool:
    current_state = raw.get("current_state")
    extracted_entities = raw.get("extracted_entities")
    return (
        isinstance(raw.get("change_summary"), list)
        and isinstance(current_state, dict)
        and isinstance(current_state.get("visual_facts"), list)
        and isinstance(extracted_entities, dict)
    )


def _raw_indicates_no_change(raw: dict[str, Any]) -> bool:
    """True if the model output clearly indicates no material change."""
    if raw.get("material_change") is False:
        return True
    change_summary = _as_list(raw.get("change_summary"))
    if change_summary and all(
        "no change" in str(item).lower() or "unchanged" in str(item).lower()
        for item in change_summary
    ):
        return True
    return False


def _normalize_entity_list(value: Any) -> list:
    """
    Preserve rich structured entity items (objects with type/label/value_description)
    from Gemini-style payloads. Falls back to string coercion for plain strings.
    Filters out N/A strings and None values.
    """
    result = []
    for item in _as_list(value):
        if isinstance(item, dict):
            # Preserve structured objects (e.g. {type, label, value_description})
            # but only if they carry meaningful content
            label = item.get("label") or item.get("text") or item.get("name") or item.get("value")
            if label or item.get("value_description") or item.get("type"):
                result.append(item)
        elif item is None:
            continue
        else:
            text = str(item).strip()
            if text and text.upper() != "N/A":
                result.append(text)
    return result


def _normalize_string_list(value: Any) -> list[str]:
    items: list[str] = []
    for item in _as_list(value):
        if isinstance(item, dict):
            text = item.get("text") or item.get("label") or item.get("value") or item.get("name")
            if text:
                items.append(str(text))
            continue
        if item is None:
            continue
        text = str(item).strip()
        if text and text.upper() != "N/A":
            items.append(text)
    return items


def _canonical_example_type(value: Any) -> str:
    raw = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    if raw in {"real_market_example", "abstract_teaching_example", "mixed", "unknown"}:
        return raw
    if "abstract" in raw or "teaching" in raw:
        return "abstract_teaching_example"
    if "real" in raw or "market" in raw:
        return "real_market_example"
    return "unknown"


def _normalize_readability(value: Any) -> dict[str, str]:
    if isinstance(value, dict):
        return {
            "text_confidence": str(value.get("text_confidence") or "medium"),
            "numeric_confidence": str(value.get("numeric_confidence") or "low"),
            "structure_confidence": str(value.get("structure_confidence") or "medium"),
        }
    raw = str(value or "").strip().lower()
    confidence = "medium"
    if raw in {"high", "clear"}:
        confidence = "high"
    elif raw in {"low", "unclear"}:
        confidence = "low"
    return {
        "text_confidence": confidence,
        "numeric_confidence": "medium" if confidence == "high" else "low",
        "structure_confidence": confidence,
    }


def _normalize_annotations(value: Any) -> list:
    """
    Preserve structured annotation objects ({text, location, language}) from Gemini-style payloads.
    Falls back to plain string extraction for flat string lists.
    """
    result = []
    for item in _as_list(value):
        if isinstance(item, dict):
            # Preserve structured annotation objects if they have a text field
            if item.get("text"):
                result.append(item)
        elif item is not None:
            text = str(item).strip()
            if text:
                result.append(text)
    return result


def _normalize_drawn_objects(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)] or [
            {"type": "other", "value_or_location": str(item), "label": None}
            for item in value
            if item is not None
        ]
    if isinstance(value, dict):
        items: list[dict[str, Any]] = []
        for raw_type, raw_objects in value.items():
            for obj in _as_list(raw_objects):
                if isinstance(obj, dict):
                    items.append(
                        {
                            "type": str(obj.get("type") or raw_type).strip() or "other",
                            "value_or_location": obj.get("position_description") or obj.get("value_description"),
                            "label": obj.get("label"),
                        }
                    )
                elif obj is not None:
                    items.append(
                        {
                            "type": str(raw_type).strip() or "other",
                            "value_or_location": str(obj),
                            "label": None,
                        }
                    )
        return items
    return []


def _normalize_chart_layout(value: Any, has_chart: bool) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {
        "main_chart_present": has_chart,
        "indicator_panels_present": False,
        "watchlist_present": False,
        "order_panel_present": False,
        "layout_description": str(value) if value not in (None, "", "N/A") else None,
    }


def _normalize_extraction_output(frame_key: str, raw: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize model output into the project's canonical frame schema.
    Preserves no-change intent: if raw says no change, do not refill change_summary from facts.
    Preserves richer model structures (visual_facts, trading_relevant_interpretation) when present.
    """
    no_change = _raw_indicates_no_change(raw)

    visible_facts = _stringify_visible_facts(raw)
    text_content = ((raw.get("content") or {}).get("text") or {}) if isinstance(raw.get("content"), dict) else {}
    chart_content = ((raw.get("content") or {}).get("chart") or {}) if isinstance(raw.get("content"), dict) else {}
    raw_state = raw.get("current_state") or {}
    if isinstance(raw_state, dict):
        if not text_content:
            title = ((raw_state.get("chart") or {}).get("title")) if isinstance(raw_state.get("chart"), dict) else None
            subtitle = ((raw_state.get("chart") or {}).get("subtitle")) if isinstance(raw_state.get("chart"), dict) else None
            if title:
                text_content["title"] = title
            if subtitle:
                text_content["subtitle"] = subtitle
        if not chart_content and isinstance(raw_state.get("chart"), dict):
            chart_content = raw_state.get("chart") or {}
    extracted_entities = {
        "setup_names": [],
        "level_values": [],
        "risk_reward_values": [],
        "atr_values": [],
        "entry_values": [],
        "stop_values": [],
        "target_values": [],
        "pattern_terms": [],
    }
    for key, value in text_content.items() if isinstance(text_content, dict) else []:
        if not value:
            continue
        if "level" in key.lower():
            extracted_entities["level_values"].append(str(value))
        if "stop" in key.lower():
            extracted_entities["stop_values"].append(str(value))
    if isinstance(raw.get("extracted_entities"), dict):
        for k in extracted_entities:
            if k in raw["extracted_entities"]:
                # Use entity-preserving normalization for values/stops/levels so structured
                # Gemini-style objects survive; use string normalization for name/term lists.
                if k in {"level_values", "stop_values", "entry_values", "target_values", "risk_reward_values", "atr_values"}:
                    extracted_entities[k] = _normalize_entity_list(raw["extracted_entities"][k])
                else:
                    extracted_entities[k] = _normalize_string_list(raw["extracted_entities"][k])

    visual_representation_type = _canonical_visual_type(
        raw.get("visual_representation_type"),
        has_chart=bool(chart_content),
        has_text=bool(text_content),
    )
    example_type = _canonical_example_type(raw.get("example_type"))
    if example_type == "unknown":
        example_type = "abstract_teaching_example"
    extraction_mode = _canonical_extraction_mode(raw.get("extraction_mode"), has_chart=bool(chart_content))
    screen_type = _canonical_screen_type(raw.get("screen_type"), has_chart=bool(chart_content), has_text=bool(text_content))
    change_summary = [str(item) for item in _as_list(raw.get("change_summary")) if item]
    if change_summary and all("no change" in item.lower() or "unchanged" in item.lower() for item in change_summary):
        change_summary = []
    if no_change:
        material_change = False
        change_summary = []
    else:
        material_change = bool(raw.get("material_change", True))
        if not change_summary:
            change_summary = visible_facts[:3] or ["Visual content changed"]

    # Preserve richer current_state from raw when present
    visual_facts_out = visible_facts
    trading_interp_out: list[str] = []
    if isinstance(raw_state, dict):
        vf = _normalize_string_list(raw_state.get("visual_facts"))
        if vf:
            visual_facts_out = vf
        trading_interp_out = _normalize_string_list(raw_state.get("trading_relevant_interpretation"))

    current_state_out = {
        "symbol": raw_state.get("symbol") if isinstance(raw_state, dict) else None,
        "timeframe": raw_state.get("timeframe") if isinstance(raw_state, dict) else None,
        "platform": raw_state.get("platform") if isinstance(raw_state, dict) else None,
        "chart_type": (chart_content.get("type") if isinstance(chart_content, dict) else None) or (raw_state.get("chart_type") if isinstance(raw_state, dict) else None) or "unknown",
        "visible_date_range": raw_state.get("visible_date_range") if isinstance(raw_state, dict) else None,
        "visible_price_range": raw_state.get("visible_price_range") if isinstance(raw_state, dict) else None,
        "chart_layout": _normalize_chart_layout(
            raw_state.get("chart_layout") if isinstance(raw_state, dict) else None,
            has_chart=bool(chart_content),
        ),
        "drawn_objects": _normalize_drawn_objects(
            raw_state.get("drawn_objects") if isinstance(raw_state, dict) else None
        ),
        "visible_annotations": (
            _normalize_annotations(raw_state.get("visible_annotations"))
            if isinstance(raw_state, dict)
            else [str(v) for v in (text_content.values() if isinstance(text_content, dict) else []) if v]
        ),
        "cursor_or_highlight": (
            raw_state.get("cursor_or_highlight")
            if isinstance(raw_state, dict) and isinstance(raw_state.get("cursor_or_highlight"), dict)
            else {"present": False, "location": None, "target": None}
        ),
        "visual_facts": visual_facts_out,
        "structural_pattern_visible": (
            _normalize_string_list(raw_state.get("structural_pattern_visible"))
            if isinstance(raw_state, dict)
            else []
        ),
        "trading_relevant_interpretation": trading_interp_out,
        "readability": _normalize_readability(
            raw_state.get("readability") if isinstance(raw_state, dict) else None
        ),
    }

    return {
        "frame_timestamp": raw.get("frame_timestamp") or raw.get("timestamp") or key_to_timestamp(frame_key),
        "material_change": material_change,
        "change_summary": change_summary,
        "visual_representation_type": visual_representation_type,
        "example_type": example_type,
        "extraction_mode": extraction_mode,
        "screen_type": screen_type,
        "educational_event_type": [
            str(item) for item in _as_list(raw.get("educational_event_type")) if str(item).strip().lower() in {
                # Original vocabulary
                "new_example_chart",
                "timeframe_switch",
                "symbol_switch",
                "level_identification",
                "setup_annotation",
                "pattern_highlight",
                "entry_discussion",
                "stop_discussion",
                "target_discussion",
                "risk_reward_discussion",
                "atr_discussion",
                "zoom_for_context",
                "zoom_for_detail",
                "rule_slide",
                "whiteboard_logic",
                "none",
                # Gemini-expanded vocabulary
                "concept_introduction",
                "level_explanation",
                "stop_loss_placement",
                "chart_introduction",
                "pattern_explanation",
                "trade_management",
            }
        ] or ["none"],
        "current_state": current_state_out,
        "extracted_entities": extracted_entities,
        "notes": raw.get("notes") if isinstance(raw.get("notes"), (str, type(None))) else raw,
    }


def _get_cfg(video_id: str | None) -> dict[str, Any]:
    if not video_id:
        return {}
    try:
        return pipeline_config.get_config_for_video(video_id)
    except Exception:
        return {}


def _resolve_agent(agent: str | None, video_id: str | None) -> str:
    if agent:
        return str(agent).strip().lower()
    cfg = _get_cfg(video_id)
    cfg_agent = cfg.get("agent_images") or cfg.get("agent") or cfg.get("agent_dedup")
    env_agent = os.getenv("AGENT_IMAGES") or os.getenv("AGENT")
    return str(cfg_agent or env_agent or "gemini").strip().lower()


def _call_agent(
    agent: str,
    image_path: Path | str,
    prompt: str,
    *,
    video_id: str | None = None,
    on_event: Any = None,
    stage: str,
    frame_key: str | None = None,
) -> dict[str, Any]:
    if agent == "openai":
        from helpers.clients import openai_client
        text = openai_client.chat_completion_with_image(
            prompt,
            str(image_path),
            step="images",
            video_id=video_id,
            max_tokens=2000,
            on_event=on_event,
            stage=stage,
            frame_key=frame_key,
        )
        return _parse_json_from_response(text)
    if agent == "gemini":
        from helpers.clients import gemini_client
        from google.genai import types
        with open(image_path, "rb") as f:
            image_bytes = f.read()
        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(text=prompt),
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
            stage=stage,
            frame_key=frame_key,
        ).strip()
        if not text:
            raise ValueError("Gemini returned empty response for analysis")
        return _parse_json_from_response(text)
    raise ValueError(f"Unsupported agent: {agent}. Use openai or gemini.")


def build_extraction_prompt(
    frame_key: str,
    previous_state: dict[str, Any] | None = None,
) -> str:
    previous = json.dumps(previous_state or {}, ensure_ascii=False)
    return (
        f"{EXTRACTION_PROMPT}\n\n"
        f"Frame timestamp: {key_to_timestamp(frame_key)}\n"
        f"Previous accepted visual state JSON: {previous or '{}'}\n\n"
        "Return JSON only."
    )


def build_relevance_prompt(
    frame_key: str,
    extracted: dict[str, Any],
    previous_state: dict[str, Any] | None = None,
    transcript_context: str | None = None,
) -> str:
    previous = json.dumps(previous_state or {}, ensure_ascii=False)
    extracted_json = json.dumps(extracted, ensure_ascii=False)
    transcript = transcript_context or ""
    return (
        f"{RELEVANCE_PROMPT}\n\n"
        f"Frame timestamp: {key_to_timestamp(frame_key)}\n"
        f"Transcript context: {transcript}\n"
        f"Previous accepted visual state JSON: {previous or '{}'}\n"
        f"Current extracted visual facts JSON: {extracted_json}\n\n"
        "Return JSON only."
    )


def extract_with_agent(
    image_path: Path | str,
    frame_key: str,
    *,
    agent: str,
    previous_state: dict[str, Any] | None = None,
    video_id: str | None = None,
    on_event: Any = None,
) -> dict[str, Any]:
    prompt = build_extraction_prompt(frame_key, previous_state=previous_state)
    raw = _call_agent(
        agent,
        image_path,
        prompt,
        video_id=video_id,
        on_event=on_event,
        stage="extract",
        frame_key=frame_key,
    )
    return _normalize_extraction_output(frame_key, raw)


def judge_relevance(
    image_path: Path | str,
    frame_key: str,
    extracted: dict[str, Any],
    *,
    agent: str,
    previous_state: dict[str, Any] | None = None,
    transcript_context: str | None = None,
    video_id: str | None = None,
    on_event: Any = None,
) -> dict[str, Any]:
    prompt = build_relevance_prompt(
        frame_key,
        extracted,
        previous_state=previous_state,
        transcript_context=transcript_context,
    )
    try:
        return _call_agent(
            agent,
            image_path,
            prompt,
            video_id=video_id,
            on_event=on_event,
            stage="relevance",
            frame_key=frame_key,
        )
    except (json.JSONDecodeError, TypeError, ValueError):
        return _fallback_relevance_decision(extracted)


def analyze_frame(
    image_path: Path | str,
    frame_key: str,
    *,
    structural_score: float,
    previous_state: dict[str, Any] | None = None,
    previous_relevant_frame: str | None = None,
    transcript_context: str | None = None,
    video_id: str | None = None,
    agent: str | None = None,
    on_event: Any = None,
) -> dict[str, Any]:
    timings: dict[str, float] = {}

    resolved_agent = _resolve_agent(agent, video_id)

    started = time.perf_counter()
    extracted = extract_with_agent(
        image_path,
        frame_key,
        agent=resolved_agent,
        previous_state=previous_state,
        video_id=video_id,
        on_event=on_event,
    )
    timings["extract_seconds"] = round(time.perf_counter() - started, 4)

    started = time.perf_counter()
    relevance = judge_relevance(
        image_path,
        frame_key,
        extracted,
        agent=resolved_agent,
        previous_state=previous_state,
        transcript_context=transcript_context,
        video_id=video_id,
        on_event=on_event,
    )
    timings["relevance_seconds"] = round(time.perf_counter() - started, 4)

    lesson_relevant = bool(relevance.get("lesson_relevant"))
    if not lesson_relevant:
        skipped = minimal_relevance_skip_frame(
            frame_key,
            extracted_facts=extracted,
            skip_reason=str(relevance.get("skip_reason") or "lesson_irrelevant"),
        )
        skipped.update(
            {
                "structural_score": structural_score,
                "content_changed": bool(extracted.get("material_change", True)),
                "scene_boundary": False,
                "change_summary": relevance.get("change_summary") or [],
                "previous_relevant_frame": previous_relevant_frame,
                "timings": timings,
            }
        )
        return ensure_material_change(skipped)

    merged = dict(extracted)
    merged.setdefault("frame_timestamp", key_to_timestamp(frame_key))
    merged["material_change"] = bool(extracted.get("material_change", True))
    merged["structural_change"] = True
    merged["structural_score"] = structural_score
    merged["content_changed"] = bool(extracted.get("material_change", True))
    merged["lesson_relevant"] = True
    merged["scene_boundary"] = bool(relevance.get("scene_boundary", True))
    merged["skip_reason"] = None
    merged["extracted_facts"] = extracted
    merged["explanation_summary"] = relevance.get("explanation_summary")
    merged["previous_relevant_frame"] = previous_relevant_frame
    merged["timings"] = timings
    merged["pipeline_status"] = "explained"
    if not merged.get("change_summary"):
        merged["change_summary"] = relevance.get("change_summary") or []
    return ensure_material_change(merged)
