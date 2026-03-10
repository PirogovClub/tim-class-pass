# Frame 591 Semantics Validation Report

**Reference:** Gemini batch `dense_batch_response_000591-000600.json` (frame `000591`).  
**Internal:** Qwen+Llama pipeline output from smoke run `data/smoke_590_591/dense_analysis.json` (frame `000591`).  
**Date:** Validation run per plan `validate_frame591_semantics_824d0548`.

---

## 1. Gemini Reference Payload (000591) — Summary

- **Top-level:** `material_change: true`, `change_summary: ["Initial frame, new abstract diagram presented."]`, `visual_representation_type: "abstract_bar_diagram"`, `example_type: "abstract_teaching_example"`, `extraction_mode: "structural_only"`, `screen_type: "chart_with_instructor"`, `educational_event_type: ["concept_introduction", "level_explanation", "stop_loss_placement"]`.
- **visual_facts (rich):** Six full sentences describing the diagram: horizontal white line as key level, green/red bars interacting with the level, green bars below/briefly piercing, two red bars piercing and closing below, dashed line КОРОТКИЙ СТОП below level (tight stop area), red box СТОПЫ above level with dashed line (stop area for short positions / stop hunting).
- **trading_relevant_interpretation (low-inference):** Three bullets: diagram illustrates price interaction with limit player’s level; potential areas for short stops below and stops above (stop hunting / liquidity); red bars as failed break attempts or price hitting stops.
- **current_state:** `chart_type: "bar_diagram"`, `chart_layout: "single_pane"`, structured `drawn_objects` (horizontal_lines, shapes, other_drawings with labels/positions), `visible_annotations` as list of objects with text/location/language, `structural_pattern_visible: "price_action_around_level"`, `readability: "high"`.
- **extracted_entities:** `level_values` and `stop_values` as lists of objects with type/label/value_description; `pattern_terms: ["price_action_around_level"]`; `notes` as a single descriptive string.

---

## 2. Internal Pipeline Payload (000591) — Summary

- **Top-level:** `material_change: true`, `change_summary: ["New chart type displayed"]`, `visual_representation_type: "candlestick sketches"`, `example_type: "abstract teaching example"`, `extraction_mode: "structural_only"`, `screen_type: "whiteboard explanations"`, `educational_event_type: "chart analysis`.
- **visual_facts (sparse):** Three short items: "Green candlesticks", "Red candlestick", "Horizontal line with annotations".
- **trading_relevant_interpretation:** Single string: "Illustration of short-term stop levels" (not a list; less nuance than Gemini).
- **current_state:** `chart_type: "candlestick"`, `chart_layout: "horizontal"`, `drawn_objects` as list of strings `["candlesticks", "horizontal lines"]`, `visible_annotations` as flat list of two strings, `structural_pattern_visible: false`, `readability: "High"`.
- **extracted_entities:** Many fields string `"N/A"` (level_values, risk_reward_values, etc.); `pattern_terms: ["short-term stop"]`; `notes` as one short sentence.

---

## 3. Field-by-Field Comparison

| Field | Gemini (reference) | Internal (Qwen+Llama) | Match? |
|-------|---------------------|------------------------|--------|
| material_change | true | true | Yes |
| change_summary | ["Initial frame, new abstract diagram presented."] | ["New chart type displayed"] | Different wording |
| visual_representation_type | abstract_bar_diagram | candlestick_sketches | Different |
| example_type | abstract_teaching_example | abstract teaching example (normalized same) | Yes |
| extraction_mode | structural_only | structural_only | Yes |
| screen_type | chart_with_instructor | whiteboard explanations | Different |
| educational_event_type | concept_introduction, level_explanation, stop_loss_placement | chart analysis | Different |
| current_state.visual_facts | 6 rich sentences | 3 short labels | Much sparser |
| current_state.trading_relevant_interpretation | 3 bullets (list) | 1 string | Much sparser, shape differs |
| current_state.chart_type | bar_diagram | candlestick | Different |
| current_state.drawn_objects | Structured (horizontal_lines, shapes, other_drawings) | List of strings | Different shape |
| current_state.visible_annotations | List of {text, location, language} | List of 2 strings | Different shape |
| current_state.structural_pattern_visible | "price_action_around_level" | false | Different |
| extracted_entities.level_values | List of objects | "N/A" | Missing |
| extracted_entities.stop_values | List of objects | "N/A" | Missing |
| extracted_entities.pattern_terms | ["price_action_around_level"] | ["short-term stop"] | Different |
| notes | One rich sentence | One short sentence | Different density |

---

## 4. Likely Cause (Attribution)

| Mismatch | Likely cause |
|----------|----------------|
| visual_representation_type (candlestick_sketches vs abstract_bar_diagram) | **Model + prompt:** Qwen describes the scene as candlestick sketches; Gemini as abstract bar diagram. Prompt could stress “abstract bar diagram when bars represent price vs level” and give examples. |
| visual_facts sparse vs rich | **Model capability + prompt:** Qwen returns short labels; Gemini returns full sentences. Prompt already asks for “direct visual facts” and “richer”; may need explicit examples or a few-shot sentence style. |
| trading_relevant_interpretation (one string vs list of bullets) | **Normalization + model:** Internal has one string; schema expects list. Normalization already supports string→list; model often gives one sentence. Pushing for “2–3 low-inference bullets” in the prompt could help. |
| drawn_objects / visible_annotations shape | **Normalization:** We preserve list-of-strings or structured form; Gemini uses structured objects. Normalization can coerce where needed; model may still not emit structured drawn_objects without prompt examples. |
| level_values, stop_values "N/A" | **Model + prompt:** Qwen often returns "N/A" for entity slots; Gemini fills conceptual level/stop objects. Prompt could require “conceptual” level/stop when no exact numbers, with schema snippet. |
| structural_pattern_visible (false vs "price_action_around_level") | **Model:** Qwen set false or omitted; Gemini set pattern name. Prompt already lists pattern terms; could add “e.g. price_action_around_level when bars interact with a level”. |
| change_summary / educational_event_type / screen_type | **Prompt + canonical enums:** Wording and enum choices differ; prompt and normalization already steer these—tuning for “abstract diagram” and “chart_with_instructor” would align. |

**Summary of causes:** Mix of **prompt** (examples, required shapes, terminology), **normalization** (list vs string for trading_relevant_interpretation, optional structured drawn_objects), and **model** (Qwen vs Gemini verbosity and classification). No remaining **architectural** issue identified (staged flow, material_change vs lesson_relevant, no-change handling are aligned).

---

## 5. Validation Summary

### Matched

- `material_change`, `example_type`, `extraction_mode`.
- Pipeline semantics: material_change and lesson_relevant are separate; no-change behavior and normalization preserve intent.

### Still Different

- **Richness:** visual_facts and trading_relevant_interpretation are much sparser and less structured.
- **Representation type:** candlestick_sketches vs abstract_bar_diagram for the same scene.
- **Structure:** drawn_objects, visible_annotations, level_values, stop_values (flat/N/A vs structured).
- **Pattern:** structural_pattern_visible false vs "price_action_around_level".

### Likely Cause (aggregate)

- **Prompt:** Need stronger guidance and examples for “abstract bar diagram”, full-sentence visual_facts, 2–3 interpretation bullets, and conceptual level/stop entities.
- **Normalization:** Already preserves lists and coerces string→list for interpretation; can add light coercion for drawn_objects/visible_annotations when model returns flat lists.
- **Model:** Qwen is more terse and often uses “N/A”; prompt and examples can narrow the gap.

### Recommended Next Fix

1. **Prompt (analyze.py EXTRACTION_PROMPT):**  
   - Add one concrete example for “abstract bar diagram” (bars + level, no real ticker).  
   - Require “2–5 full-sentence visual_facts” and “2–3 short bullets for trading_relevant_interpretation”.  
   - For structural_only, add: “Set structural_pattern_visible to e.g. price_action_around_level when bars interact with a level.”  
   - For level/stop when no exact numbers: “Use extracted_entities.level_values / stop_values with type: conceptual and value_description when labels (e.g. КОРОТКИЙ СТОП, СТОПЫ) are visible.”

2. **Normalization (analyze.py):**  
   - Ensure single-string `trading_relevant_interpretation` is always normalized to a one-element list so downstream gets a list.  
   - Optionally, when `drawn_objects` is a list of strings, map to minimal structured form (e.g. type "other", label from string) for compatibility.

3. **Re-run smoke 590–591** after prompt/normalization changes and regenerate this comparison to confirm improvement.

---

**Output format (per plan):**

- **Matched:** material_change, example_type, extraction_mode; pipeline semantics.  
- **Still Different:** visual_facts/interpretation richness, visual_representation_type, screen_type, educational_event_type, drawn_objects/visible_annotations/level_values/stop_values shape, structural_pattern_visible.  
- **Likely Cause:** Prompt (examples, required richness, terminology), normalization (list vs string, optional structures), model (Qwen terse vs Gemini rich).  
- **Recommended Next Fix:** Strengthen EXTRACTION_PROMPT with examples and explicit requirements; normalize trading_relevant_interpretation string→list and optional drawn_objects; re-validate with smoke 590–591.
