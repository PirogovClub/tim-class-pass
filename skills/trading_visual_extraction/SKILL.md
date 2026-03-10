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
    "level_identification", "level_explanation", "setup_annotation", "pattern_highlight",
    "entry_discussion", "stop_discussion", "stop_loss_placement", "target_discussion",
    "risk_reward_discussion", "atr_discussion",
    "zoom_for_context", "zoom_for_detail",
    "rule_slide", "whiteboard_logic",
    "concept_introduction", "chart_introduction", "pattern_explanation", "trade_management",
    "none"
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
        "type": "horizontal_level|trendline|arrow|text_label|rectangle|circle|highlight_zone|dashed_line|other",
        "value_or_location": "string|null",
        "label": "string|null"
      }
    ],
    "visible_annotations": [
      {
        "text": "string",
        "location": "string|null",
        "language": "string|null"
      }
    ],
    "cursor_or_highlight": {
      "present": true,
      "location": "string|null",
      "target": "string|null"
    },
    "visual_facts": ["string"],
    "structural_pattern_visible": [
      "breakout", "retest", "false_breakout", "pullback",
      "trend_continuation", "range", "reversal",
      "price_action_around_level", "stop_hunt", "liquidity_grab", "level_test"
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
    "level_values": ["string OR {type, label, value_description}"],
    "risk_reward_values": ["string"],
    "atr_values": ["string"],
    "entry_values": ["string"],
    "stop_values": ["string OR {type, label, value_description}"],
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
| `drawn_objects` | Capture all objects relevant to trading logic (levels, arrows, zones, labels). Use structured `{type, value_or_location, label}` form. |
| `visible_annotations` | Prefer structured `{text, location, language}` form. Copy readable labels exactly. |
| `visual_facts` | Only directly visible facts. No inferred claims. **For abstract teaching frames: write 4-6 full sentences** describing bars, levels, labels, and relative positions. |
| `structural_pattern_visible` | Use generic structure names. For frames showing bars interacting with a level, use `price_action_around_level`. |
| `trading_relevant_interpretation` | Low-inference only. **For abstract teaching frames: write 2-3 short bullet-style items** covering what the diagram illustrates. |
| `extracted_entities.level_values` | Use `{type, label, value_description}` objects when no numeric values exist but labels are visible. |
| `extracted_entities.stop_values` | Use `{type: "conceptual", label, value_description}` when stop zones are labeled without exact values. |
| `extracted_entities` | Only values or terms actually visible on screen. Never return "N/A" — omit the field or return empty list instead. |
| `notes` | Optional concise note, or `null`. |

---

## Visual Representation Types

| Type | When to use |
|------|------------|
| `live_chart` | Platform-based chart with market data, likely interactive |
| `static_chart_screenshot` | Captured chart image, not clearly live |
| `abstract_bar_diagram` | Generic bar-style drawing where bars represent schematic price vs a level. **Use when bars interact with a level, stop zone, or liquidity area without real ticker/date data.** |
| `candlestick_sketch` | Simplified candlestick illustration focusing on candle anatomy or pattern formation, not level interaction |
| `hand_drawn_pattern` | Freehand drawing showing structure, levels, arrows |
| `whiteboard_explanation` | Board-based explanation with logic or steps |
| `text_slide` | Slide with text/bullets, limited chart content |
| `mixed_visual` | Combination of chart, notes, annotations, diagrams |
| `unknown` | Cannot be reliably classified |

### Disambiguation: `abstract_bar_diagram` vs `candlestick_sketch`

- If the drawing shows **bars/candles interacting with a level, stop area, or liquidity zone** → use `abstract_bar_diagram`
- If the drawing focuses on **candlestick anatomy, formation, or pattern shapes** (e.g. explaining what a pinbar looks like) → use `candlestick_sketch`

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

## Visual Representation Type — disambiguation

Use abstract_bar_diagram when bars/candles show schematic price movement vs a level, stop zone, or liquidity area.
Use candlestick_sketch only when teaching candlestick anatomy or pattern formation (not level interaction).

## Output density requirements

For ABSTRACT TEACHING FRAMES (abstract_bar_diagram, hand_drawn_pattern, candlestick_sketch, whiteboard_explanation):
- visual_facts: write 4-6 FULL SENTENCES about visible elements (position, color, label, level interaction).
  Good: "A horizontal white line runs across the center labeled 'Уровень лимитного игрока'."
  Bad: "Horizontal line."
- trading_relevant_interpretation: write 2-3 SHORT BULLET ITEMS with low-inference trading insight.

## Conceptual entities

When labels identify zones without numbers:
- level_values: { "type": "horizontal", "label": "<label>", "value_description": "conceptual price level" }
- stop_values: { "type": "conceptual", "label": "<label>", "value_description": "area below/above level" }
- Never return "N/A". Use [] if nothing visible.

## Structural patterns for abstract diagrams

Use price_action_around_level when bars interact with a level.
Other patterns: stop_hunt, liquidity_grab, level_test, breakout, retest, false_breakout, pullback, reversal.

If there is no material change, return:
{ "frame_timestamp": "<timestamp if available, else null>", "material_change": false }

If there is a material change, return the full structured JSON as defined in the schema.

Rules:
- Separate direct visual facts from interpretation.
- If the visual is abstract, do not force exact prices, dates, symbols, or timeframes.
- If the visual is hand-drawn, focus on structure, arrows, levels, and labels.
- drawn_objects: use structured { type, value_or_location, label } objects.
- visible_annotations: use structured { text, location, language } objects; copy ALL labels exactly.
- Return JSON only.
```
