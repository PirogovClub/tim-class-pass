---
name: Trading Visual Extraction
description: Structured JSON schema and production prompt for analyzing trading education video frames.
---

# Trading Visual Extraction

This skill defines the **authoritative schema** for frame-by-frame visual analysis of trading education videos. All frame analysis in this project MUST use this schema instead of free-text descriptions.

> **Canonical spec:** [`docs/trading_visual_extraction_spec.md`](file:///h:/GITS/tim-class-pass/docs/trading_visual_extraction_spec.md)

---

## Why This Schema (Not Free-Text)

1. **Representation-agnostic** — trading videos mix live charts, hand-drawn sketches, abstract diagrams, whiteboard logic, and slides. The schema forces the agent to classify the visual type, preventing misinterpretation downstream.
2. **Fact vs. interpretation separation** — `visual_facts` captures what is literally visible; `trading_relevant_interpretation` captures low-inference meaning. This prevents the knowledge base from treating guesses as evidence.
3. **Structured entities** — price levels, setup names, ATR values, entry/stop/target values are extracted into dedicated fields, not buried in prose.
4. **Material change as boolean** — replaces fragile string matching (`"No change"`, `"Added: ..."`) with a clean `material_change: true/false` flag.
5. **Confidence signals** — `readability.text_confidence`, `numeric_confidence`, and `structure_confidence` tell downstream systems how much to trust the extraction.
6. **Downstream-ready** — enables setup taxonomy building, contradiction tracking, rule extraction, and programmatic pattern detection from structured data.

---

## Material Change Definition

Mark `material_change: true` if ANY of these occur:
- Symbol, timeframe, chart, or visual example changed
- Zoom or pan changed the relevant visible area
- A new drawing, level, annotation, arrow, or label appeared/disappeared
- Instructor switched concept/example
- A previously unreadable label became readable
- Visual context changed enough to alter trading interpretation

Mark `material_change: false` for:
- Tiny cursor movement with no new significance
- Negligible rendering differences or UI jitter
- Repeated static display with no new content

---

## Output Format

### When there is NO material change

```json
{
  "frame_timestamp": "00:12:32",
  "material_change": false
}
```

### When there IS a material change

```json
{
  "frame_timestamp": "string|null",
  "material_change": true,
  "change_summary": ["string"],
  "visual_representation_type": "live_chart|static_chart_screenshot|abstract_bar_diagram|candlestick_sketch|hand_drawn_pattern|whiteboard_explanation|text_slide|mixed_visual|unknown",
  "example_type": "real_market_example|abstract_teaching_example|mixed|unknown",
  "extraction_mode": "market_specific|structural_only|conceptual_only",
  "screen_type": "chart|platform|browser|slides|mixed|unknown",
  "educational_event_type": [
    "new_example_chart", "timeframe_switch", "symbol_switch",
    "level_identification", "setup_annotation", "pattern_highlight",
    "entry_discussion", "stop_discussion", "target_discussion",
    "risk_reward_discussion", "atr_discussion",
    "zoom_for_context", "zoom_for_detail",
    "rule_slide", "whiteboard_logic", "none"
  ],
  "current_state": {
    "symbol": "string|null",
    "timeframe": "string|null",
    "platform": "string|null",
    "chart_type": "candlestick|bar|line|sketch|unknown",
    "visible_date_range": "string|null",
    "visible_price_range": "string|null",
    "chart_layout": {
      "main_chart_present": true,
      "indicator_panels_present": false,
      "watchlist_present": false,
      "order_panel_present": false
    },
    "drawn_objects": [
      {
        "type": "horizontal_level|trendline|arrow|text_label|rectangle|circle|highlight_zone|other",
        "value_or_location": "string|null",
        "label": "string|null"
      }
    ],
    "visible_annotations": ["string"],
    "cursor_or_highlight": {
      "present": true,
      "location": "string|null",
      "target": "string|null"
    },
    "visual_facts": ["string"],
    "structural_pattern_visible": [
      "breakout", "retest", "false_breakout", "pullback",
      "trend_continuation", "range", "reversal"
    ],
    "trading_relevant_interpretation": ["string"],
    "readability": {
      "text_confidence": "high|medium|low",
      "numeric_confidence": "high|medium|low",
      "structure_confidence": "high|medium|low"
    }
  },
  "extracted_entities": {
    "setup_names": ["string"],
    "level_values": ["string"],
    "risk_reward_values": ["string"],
    "atr_values": ["string"],
    "entry_values": ["string"],
    "stop_values": ["string"],
    "target_values": ["string"],
    "pattern_terms": ["string"]
  },
  "notes": "string|null"
}
```

---

## Field Guidance

| Field | Rule |
|-------|------|
| `symbol`, `timeframe` | Only fill if clearly visible. Otherwise `null`. |
| `visible_date_range`, `visible_price_range` | Best-effort text summary. Exactness is optional. |
| `drawn_objects` | Capture all objects relevant to trading logic (levels, arrows, zones, labels). |
| `visible_annotations` | Copy readable labels exactly (e.g., `"LP Long"`, `"False breakout"`). |
| `visual_facts` | Only directly visible facts. No inferred claims. |
| `structural_pattern_visible` | Use generic structure names, not strong claims. |
| `trading_relevant_interpretation` | Low-inference only (e.g., `"Possible near retest example"`). |
| `extracted_entities` | Only values actually visible on screen. |
| `notes` | Optional concise note, or `null`. |

---

## Visual Representation Types

| Type | When to use |
|------|------------|
| `live_chart` | Platform-based chart with market data, likely interactive |
| `static_chart_screenshot` | Captured chart image, not clearly live |
| `abstract_bar_diagram` | Generic bar-style market structure drawing |
| `candlestick_sketch` | Simplified candlestick illustration |
| `hand_drawn_pattern` | Freehand drawing showing structure, levels, arrows |
| `whiteboard_explanation` | Board-based explanation with logic or steps |
| `text_slide` | Slide with text/bullets, limited chart content |
| `mixed_visual` | Combination of chart, notes, annotations, diagrams |
| `unknown` | Cannot be reliably classified |

---

## Production Prompt

When analyzing frames, use this system prompt:

```
You are analyzing sequential screenshots from a trading education video for building a structured trading knowledge base.

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

You will receive:
1. the current screenshot
2. the previous extracted state (optional)
3. the frame timestamp if available

Your task:
1. Determine whether the current screenshot is materially different from the previous screenshot.
2. Identify the visual representation type.
3. Identify whether the frame is a real market example or an abstract teaching example.
4. Choose the correct extraction mode: market_specific, structural_only, or conceptual_only.
5. If there is a material change, extract the current trading-relevant visual state in structured JSON.
6. Separate direct visual facts from low-inference interpretation.
7. Do not invent exact numeric values, symbols, dates, or timeframes if they are abstract, unreadable, or unclear.
8. Copy visible labels exactly when readable.
9. Be concise, conservative, and factual.

If there is no material change, return:
{ "frame_timestamp": "<timestamp if available, else null>", "material_change": false }

If there is a material change, return the full structured JSON as defined in the schema.

Rules:
- Separate direct visual facts from interpretation.
- If the visual is abstract, do not force exact prices, dates, symbols, or timeframes.
- If the visual is hand-drawn, focus on structure, arrows, levels, and labels.
- If the visual is a real chart, capture exact values when clearly readable.
- If text is unclear, say null or mark confidence low.
- If only approximate reading is possible, explicitly say approx.
- Keep wording concise and structured.
- Return JSON only.
```
