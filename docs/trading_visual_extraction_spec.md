# Trading Visual Extraction Spec

Version: 1.0  
Purpose: Define a robust, representation-agnostic schema and production prompt for AI image recognition on trading education videos, so extracted visuals can feed a structured trading knowledge base and later support strategy formalization and programmatic pattern detection.

---

## 1. Why this design is needed

A simple "describe what changed on screen" approach is not sufficient for trading-course extraction.

In trading videos, knowledge is often conveyed through multiple visual forms:

- live trading charts
- static chart screenshots
- abstract bar diagrams
- candlestick sketches
- hand-drawn patterns
- whiteboard explanations
- text slides
- mixed screens with charts and annotations

Because of that, the extractor must be **representation-agnostic**.

It must capture not only:

- what changed between frames

but also:

- what trading-relevant state is currently visible
- what kind of visual representation is being used
- whether the frame is a real market example or an abstract teaching diagram
- what exact labels, levels, numbers, and structures are visible
- what is visually factual versus what is low-inference interpretation

This design supports downstream use cases such as:

- course note generation
- setup taxonomy building
- contradiction tracking across lessons
- evidence-backed knowledge extraction
- future programmatic strategy design
- scanner and pattern-engine specification

---

## 2. Design principles

1. **Representation-agnostic**  
   The system must work for real charts, abstract diagrams, and hand drawings.

2. **Structured first, narrative second**  
   The output must prioritize machine-usable structure over prose.

3. **Separate fact from interpretation**  
   Directly visible elements must not be mixed with inferred trading meaning.

4. **Do not force false precision**  
   If a frame is abstract or unreadable, the model must not invent exact values.

5. **Capture full current state, not only delta**  
   When a material change occurs, the extractor must output both:
   - what changed
   - what is now visible

6. **Support knowledge-base confidence**  
   The output must include readability and confidence indicators.

7. **Store educational significance**  
   The output should mark whether a frame introduces a new example, highlights a pattern, shows a rule, switches timeframe, etc.

---

## 3. Recommended extraction workflow

For each screenshot taken from the video stream:

1. Compare current screenshot with previous screenshot.
2. Determine whether there is a **material change**.
3. If no material change, return a minimal record.
4. If there is a material change:
   - identify visual representation type
   - identify example type
   - identify extraction mode
   - extract full current structured state
   - extract educational event type
   - extract visible entities and annotations
   - separate visual facts from interpretation
   - attach confidence/readability estimates

---

## 4. Definition of material change

A frame should be marked as `material_change = true` if any of the following occur:

- symbol changed
- timeframe changed
- chart or visual example changed
- zoom level changed meaningfully
- panning changed the relevant visible area
- a new drawing, level, annotation, arrow, or label appeared or disappeared
- the instructor switched from one concept/example to another
- a previously unreadable label became readable
- emphasis shifted to a different important chart region
- the visual context changed enough to alter trading interpretation

A frame should **not** be marked as material change for:

- tiny cursor movement with no new significance
- negligible rendering differences
- minor anti-aliasing or UI jitter
- repeated static display with no meaningful new content

---

## 5. Visual representation types

Use one of the following values:

- `live_chart`
- `static_chart_screenshot`
- `abstract_bar_diagram`
- `candlestick_sketch`
- `hand_drawn_pattern`
- `whiteboard_explanation`
- `text_slide`
- `mixed_visual`
- `unknown`

### Meaning of each

#### `live_chart`
A platform-based chart with market data, likely interactive.

#### `static_chart_screenshot`
A captured chart image, not clearly live.

#### `abstract_bar_diagram`
A generic bar-style market structure drawing used for explanation.

#### `candlestick_sketch`
A simplified candlestick illustration rather than a real market chart.

#### `hand_drawn_pattern`
A freehand drawing showing structure, levels, arrows, or a setup.

#### `whiteboard_explanation`
A board-based explanation with logic, steps, or conceptual structure.

#### `text_slide`
A slide with text or bullet points and limited chart content.

#### `mixed_visual`
A combination of chart, notes, annotations, and/or diagrams.

#### `unknown`
Cannot be reliably classified.

---

## 6. Example type

Use one of the following:

- `real_market_example`
- `abstract_teaching_example`
- `mixed`
- `unknown`

### Interpretation

#### `real_market_example`
The frame shows an actual instrument or chart example from market data.

#### `abstract_teaching_example`
The frame teaches a concept using a generic drawing or non-literal structure.

#### `mixed`
The frame combines real chart content with abstract teaching overlays.

#### `unknown`
Cannot be reliably determined.

---

## 7. Extraction mode

Use one of the following:

- `market_specific`
- `structural_only`
- `conceptual_only`

### Meaning

#### `market_specific`
Used when exact chart details such as symbol, timeframe, prices, or visible levels are extractable.

#### `structural_only`
Used when the frame conveys chart structure or setup logic but not exact market metadata.

#### `conceptual_only`
Used when the frame teaches rules or concepts without meaningful chart structure.

---

## 8. Educational event types

Use zero or more of the following:

- `new_example_chart`
- `timeframe_switch`
- `symbol_switch`
- `level_identification`
- `setup_annotation`
- `pattern_highlight`
- `entry_discussion`
- `stop_discussion`
- `target_discussion`
- `risk_reward_discussion`
- `atr_discussion`
- `zoom_for_context`
- `zoom_for_detail`
- `rule_slide`
- `whiteboard_logic`
- `none`

These tags help convert frame-level extraction into class-level knowledge notes.

---

## 9. Full JSON schema

```json
{
  "frame_timestamp": "string|null",
  "material_change": true,
  "change_summary": [
    "string"
  ],
  "visual_representation_type": "live_chart|static_chart_screenshot|abstract_bar_diagram|candlestick_sketch|hand_drawn_pattern|whiteboard_explanation|text_slide|mixed_visual|unknown",
  "example_type": "real_market_example|abstract_teaching_example|mixed|unknown",
  "extraction_mode": "market_specific|structural_only|conceptual_only",
  "screen_type": "chart|platform|browser|slides|mixed|unknown",
  "educational_event_type": [
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
        "type": "horizontal_level|trendline|arrow|text_label|rectangle|circle|highlight_zone|other",
        "value_or_location": "string|null",
        "label": "string|null"
      }
    ],
    "visible_annotations": [
      "string"
    ],
    "cursor_or_highlight": {
      "present": true,
      "location": "string|null",
      "target": "string|null"
    },
    "visual_facts": [
      "string"
    ],
    "structural_pattern_visible": [
      "breakout",
      "retest",
      "false_breakout",
      "pullback",
      "trend_continuation",
      "range",
      "reversal"
    ],
    "trading_relevant_interpretation": [
      "string"
    ],
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

## 10. Field guidance

### `frame_timestamp`
Timestamp of the screenshot in the video if available.

### `material_change`
Whether this frame differs meaningfully from the previous frame.

### `change_summary`
Short, factual items describing what changed.

Examples:
- `Switched from USDJPY Daily to USDJPY H1`
- `Added horizontal level near recent high`
- `Zoomed into retest area`
- `Hand-drawn false breakout diagram replaced real chart`

### `screen_type`
High-level screen category.

### `current_state.symbol`
Only fill if clearly visible. Otherwise `null`.

### `current_state.timeframe`
Only fill if clearly visible. Otherwise `null`.

### `current_state.visible_date_range`
Best-effort text summary if visible. Exactness is optional.

### `current_state.visible_price_range`
Best-effort text summary if visible. Exactness is optional.

### `drawn_objects`
Capture all visible objects that matter for trading logic.

Examples:
- horizontal levels
- arrows
- boxes
- labels
- highlight zones

### `visible_annotations`
Copy readable labels exactly when possible.

Examples:
- `LP Long`
- `Near retest`
- `False breakout`

### `visual_facts`
Only directly visible facts.

Good examples:
- `Horizontal line drawn across recent highs`
- `Three rising bars visible into resistance`
- `Small pullback shown before retest`

Bad examples:
- `This is definitely a profitable setup`
- `Institutional buyer is present`

### `structural_pattern_visible`
Use generic structure names, not strong claims.

### `trading_relevant_interpretation`
Low-inference trading meaning derived from the visual.

Good examples:
- `Possible near retest example`
- `Instructor appears to focus on breakout failure`
- `This frame likely illustrates continuation context`

### `extracted_entities`
Use only for values or terms actually visible on screen.

---

## 11. Output when there is no material change

When there is no meaningful change, allow a minimal output:

```json
{
  "frame_timestamp": "00:12:32",
  "material_change": false
}
```

---

## 12. Production prompt for image recognition

```text
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
2. the previous screenshot (optional)
3. the previous extracted state (optional)
4. the frame timestamp if available

Your task:
1. Determine whether the current screenshot is materially different from the previous screenshot.
2. Identify the visual representation type.
3. Identify whether the frame is a real market example or an abstract teaching example.
4. Choose the correct extraction mode:
   - market_specific
   - structural_only
   - conceptual_only
5. If there is a material change, extract the current trading-relevant visual state in a structured way.
6. Separate direct visual facts from low-inference interpretation.
7. Do not invent exact numeric values, symbols, dates, or timeframes if they are abstract, unreadable, or unclear.
8. Copy visible labels exactly when readable.
9. Be concise, conservative, and factual.

Definition of material change:
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

Return JSON only.

If there is no material change, return:
{
  "frame_timestamp": "<timestamp if available, else null>",
  "material_change": false
}

If there is a material change, return JSON using this schema:

{
  "frame_timestamp": "<timestamp if available, else null>",
  "material_change": true,
  "change_summary": [
    "<short factual description of each meaningful change>"
  ],
  "visual_representation_type": "live_chart | static_chart_screenshot | abstract_bar_diagram | candlestick_sketch | hand_drawn_pattern | whiteboard_explanation | text_slide | mixed_visual | unknown",
  "example_type": "real_market_example | abstract_teaching_example | mixed | unknown",
  "extraction_mode": "market_specific | structural_only | conceptual_only",
  "screen_type": "chart | platform | browser | slides | mixed | unknown",
  "educational_event_type": [
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
    "none"
  ],
  "current_state": {
    "symbol": "<ticker/pair if clearly visible, else null>",
    "timeframe": "<timeframe if clearly visible, else null>",
    "platform": "<platform name if visible, else null>",
    "chart_type": "candlestick | bar | line | sketch | unknown",
    "visible_date_range": "<best effort summary or null>",
    "visible_price_range": "<best effort summary or null>",
    "chart_layout": {
      "main_chart_present": true,
      "indicator_panels_present": false,
      "watchlist_present": false,
      "order_panel_present": false
    },
    "drawn_objects": [
      {
        "type": "horizontal_level | trendline | arrow | text_label | rectangle | circle | highlight_zone | other",
        "value_or_location": "<exact if readable, otherwise descriptive>",
        "label": "<text if readable, else null>"
      }
    ],
    "visible_annotations": [
      "<copy all readable annotations exactly>"
    ],
    "cursor_or_highlight": {
      "present": true,
      "location": "<where cursor/highlight is focused>",
      "target": "<what it appears to point at>"
    },
    "visual_facts": [
      "<only direct visual facts>"
    ],
    "structural_pattern_visible": [
      "<generic pattern names such as breakout, retest, false_breakout, pullback, trend_continuation, range, reversal>"
    ],
    "trading_relevant_interpretation": [
      "<low-inference interpretation appropriate to the visual type>"
    ],
    "readability": {
      "text_confidence": "high | medium | low",
      "numeric_confidence": "high | medium | low",
      "structure_confidence": "high | medium | low"
    }
  },
  "extracted_entities": {
    "setup_names": ["<readable setup names>"],
    "level_values": ["<readable price levels>"],
    "risk_reward_values": ["<readable RR values>"],
    "atr_values": ["<readable ATR values>"],
    "entry_values": ["<readable entry values>"],
    "stop_values": ["<readable stop values>"],
    "target_values": ["<readable target values>"],
    "pattern_terms": ["<readable pattern terms>"]
  },
  "notes": "<optional concise note or null>"
}

Rules:
- Separate direct visual facts from interpretation.
- If the visual is abstract, do not force exact prices, dates, symbols, or timeframes.
- If the visual is hand-drawn, focus on structure, arrows, levels, and labels.
- If the visual is a real chart, capture exact values when clearly readable.
- If text is unclear, say null or mark confidence low.
- If only approximate reading is possible, explicitly say approx.
- Keep wording concise and structured.
- Do not output prose outside JSON.
```

---

## 13. Recommended description for your documentation

Use the following wording in your pipeline description document.

### Suggested wording

This extraction system is designed for trading education videos where knowledge may be presented through multiple visual forms, not only live market charts.

The system therefore does not operate as simple screen-diff detection. Instead, it performs two tasks whenever a material visual change occurs:

1. it records what changed relative to the previous frame
2. it captures the full current trading-relevant visual state in a structured format

This is necessary because trading knowledge is often conveyed through:

- platform charts
- saved screenshots
- abstract bar diagrams
- hand-drawn setup sketches
- whiteboard logic
- text slides with rules or labels

A change-only description is insufficient for downstream knowledge engineering, because it does not reliably preserve the visible trading state, the representation type, the educational significance of the frame, or the exact labels and numbers shown on screen.

The schema therefore separates:

- direct visual facts
- low-inference trading interpretation
- real market examples versus abstract teaching examples
- market-specific extraction versus structural-only or conceptual-only extraction

This makes the extracted visual data suitable for:

- structured class notes
- setup taxonomy growth
- rule extraction
- contradiction tracking across lessons
- evidence-backed strategy research
- future programmatic pattern detection

---

## 14. Optional future extensions

You may later add fields such as:

- `speaker_reference_linked`: whether the frame aligns with spoken transcript at the same timestamp
- `kb_candidate_claims`: possible rule statements suggested by the frame
- `contradiction_watch`: whether the frame appears to contradict an existing knowledge-base rule
- `setup_confidence_score`: frame-level confidence that a setup is being intentionally demonstrated
- `multi_timeframe_relation`: higher timeframe vs entry timeframe linkage

These are not required for v1, but they may become valuable once the course knowledge base grows.

---

## 15. Final recommendation

For your project, this schema should be treated as the **visual extraction layer**, not the final trading strategy layer.

It is designed to preserve evidence and structure from course visuals so that later steps can:

- merge frame records into class-level notes
- extract class claims and setup logic
- mark new / confirmed / contradictory knowledge
- formalize programmatic detection rules only when enough evidence exists

