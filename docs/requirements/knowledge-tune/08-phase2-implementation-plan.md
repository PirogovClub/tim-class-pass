# Phase 2B: Tighten anchor confidence and add span provenance ([08-phase2.md](08-phase2.md))

Implement [08-phase2.md](08-phase2.md): stop over-claiming line-level provenance by introducing **span** confidence, anchor diagnostics, and honest classification so broad/sparse anchors become `chunk` or `span` instead of `line`. Use the brief's code snippets; adapt only where the codebase differs (e.g. `AdaptedChunk` has no `candidate_visual_frame_keys` in constructor for tests).

**Goal:** `line` = tight local anchor; `span` = several nearby lines (better than chunk, not line-precise); `chunk` = no trustworthy local anchor.

---

## 1. [pipeline/schemas.py](h:\GITS\tim-class-pass\pipeline\schemas.py)

### 1.1 Extend TimestampConfidence (brief lines 48–57)

**Find:**
```python
TimestampConfidence = Literal["chunk", "line"]
```
**Replace with:**
```python
TimestampConfidence = Literal["chunk", "span", "line"]
```

### 1.2 Add Phase 2B diagnostic fields to KnowledgeEvent (brief lines 59–104)

Insert **after** `timestamp_confidence`, **before** `metadata`:

```python
    # Phase 2B anchor diagnostics (QA/debug)
    anchor_match_source: Optional[AnchorMatchSource] = None
    anchor_line_count: Optional[int] = None
    anchor_span_width: Optional[int] = None
    anchor_density: Optional[float] = None
```

(Use `AnchorMatchSource` from existing schemas, not `Optional[str]`.)

### 1.3 Tighten validate_knowledge_event (brief lines 106–141)

**Replace** the existing Phase 2A block and keep prior checks (event_id, lesson_id, event_type, placeholder_text, confidence_score). Use the brief's full validator:

- For `timestamp_confidence in {"line", "span"}`: require `source_line_start`, `source_line_end`, and non-empty `transcript_anchors`; use parameterized error message with `event.timestamp_confidence`.
- For `timestamp_confidence == "line"` only: if `anchor_span_width is not None and > 6`, append error `"timestamp_confidence='line' cannot have anchor_span_width > 6"`; if `anchor_density is not None and < 0.75`, append `"timestamp_confidence='line' requires anchor_density >= 0.75"`.
- Do **not** reject `chunk` fallback.

---

## 2. [pipeline/component2/knowledge_builder.py](h:\GITS\tim-class-pass\pipeline\component2\knowledge_builder.py)

### 2.1 Add thresholds (brief lines 152–161)

Near the top of the file (after imports / constants), add:

```python
MAX_LINE_CONFIDENCE_WIDTH = 4
MAX_SPAN_CONFIDENCE_WIDTH = 10
MIN_LINE_DENSITY = 0.75
MIN_SPAN_DENSITY = 0.50
```

### 2.2 Add contiguity/density helpers (brief lines 174–198)

Add **before** `resolve_statement_anchors`:

```python
def compute_anchor_span_width(line_indices: list[int]) -> int:
    if not line_indices:
        return 0
    return (max(line_indices) - min(line_indices)) + 1


def compute_anchor_density(line_indices: list[int]) -> float:
    if not line_indices:
        return 0.0
    width = compute_anchor_span_width(line_indices)
    if width <= 0:
        return 0.0
    return len(set(line_indices)) / float(width)


def is_near_contiguous(line_indices: list[int], *, max_gap: int = 1) -> bool:
    if len(line_indices) <= 1:
        return True
    ordered = sorted(set(line_indices))
    for prev_i, next_i in zip(ordered, ordered[1:]):
        if (next_i - prev_i) > (max_gap + 1):
            return False
    return True
```

### 2.3 Add classify_timestamp_confidence (brief lines 202–236)

```python
def classify_timestamp_confidence(
    *,
    resolved_line_indices: list[int],
    match_source: str,
) -> tuple[str, int | None, int | None, int, float]:
    """
    Returns:
      timestamp_confidence, source_line_start, source_line_end, span_width, density
    """
    if not resolved_line_indices:
        return ("chunk", None, None, 0, 0.0)

    ordered = sorted(set(resolved_line_indices))
    source_line_start = ordered[0]
    source_line_end = ordered[-1]
    span_width = compute_anchor_span_width(ordered)
    density = compute_anchor_density(ordered)
    near_contiguous = is_near_contiguous(ordered, max_gap=1)

    if (
        match_source == "llm_line_indices"
        and near_contiguous
        and span_width <= MAX_LINE_CONFIDENCE_WIDTH
        and density >= MIN_LINE_DENSITY
    ):
        return ("line", source_line_start, source_line_end, span_width, density)

    if (
        near_contiguous
        and span_width <= MAX_SPAN_CONFIDENCE_WIDTH
        and density >= MIN_SPAN_DENSITY
    ):
        return ("span", source_line_start, source_line_end, span_width, density)

    return ("chunk", None, None, span_width, density)
```

### 2.4 Replace resolve_statement_anchors (brief lines 256–318)

**Replace** the current `resolve_statement_anchors` with the brief's version that:

- Returns 11 values: `(resolved_line_indices, transcript_anchors, source_quote, match_source, timestamp_confidence, source_line_start, source_line_end, timestamp_start, timestamp_end, span_width, density)`.
- Calls `classify_timestamp_confidence(resolved_line_indices=line_indices, match_source=match_source)` instead of `derive_event_timestamps_from_line_indices`.
- When `timestamp_confidence in {"line", "span"}` and bounds are set: compute `timestamp_start`/`timestamp_end` from transcript lines and build anchors; else use chunk fallback, empty anchors, `match_source="chunk_fallback"`.
- Use `chunk.start_time_seconds` / `chunk.end_time_seconds` and `transcript_lines[i].get("start_seconds", ...)` (dict shape).

### 2.5 Update extraction_result_to_knowledge_events (brief lines 322–302)

- **Unpack** 11 values from `resolve_statement_anchors(st, chunk)` including `anchor_match_source`, `anchor_span_width`, `anchor_density`.
- **Build** `KnowledgeEvent` with: existing fields plus `anchor_match_source=anchor_match_source`, `anchor_line_count=len(resolved_line_indices)`, `anchor_span_width=anchor_span_width`, `anchor_density=anchor_density`.
- **Rejected/debug rows**: add to each rejected dict and to debug metadata where applicable: `"resolved_line_indices"`, `"anchor_match_source"`, `"timestamp_confidence"`, `"anchor_span_width"`, `"anchor_density"` (brief lines 291–301).

---

## 3. [pipeline/component2/llm_processor.py](h:\GITS\tim-class-pass\pipeline\component2\llm_processor.py)

### 3.1 Update ANCHOR RULES in KNOWLEDGE_EXTRACT_SYSTEM_PROMPT (brief lines 312–325)

**Replace** the current ANCHOR RULES section with:

```text
ANCHOR RULES

- source_line_indices must use chunk-local zero-based transcript line indices.
- Return the smallest set of transcript lines that directly supports the statement.
- Prefer 1-3 lines when possible.
- Do not include broad surrounding context if the statement is supported by a smaller local span.
- If the statement is only loosely supported across many lines, return an empty array and use source_quote when possible.
- If you are not confident about exact line indices, use [] rather than guessing.
- source_quote should be a short anchor phrase from the transcript, not a long paraphrase.
```

Keep the numbered transcript format from Phase 2A; no change to `build_knowledge_extract_prompt` signature.

---

## 4. [pipeline/component2/main.py](h:\GITS\tim-class-pass\pipeline\component2\main.py)

### 4.1 Optional: summary stats in Step 3.2b message (brief lines 416–428)

After saving knowledge events, optionally replace or extend the completion message:

```python
line_count = sum(1 for ev in knowledge_collection.events if ev.timestamp_confidence == "line")
span_count = sum(1 for ev in knowledge_collection.events if ev.timestamp_confidence == "span")
chunk_count = sum(1 for ev in knowledge_collection.events if ev.timestamp_confidence == "chunk")

_emit(
    f"Step 3.2b complete: wrote {len(knowledge_collection.events)} events "
    f"(line={line_count}, span={span_count}, chunk={chunk_count}) to "
    f"{paths.knowledge_events_path(lesson_name).name}."
)
```

---

## 5. Tests

### 5.1 [tests/test_knowledge_builder.py](h:\GITS\tim-class-pass\tests\test_knowledge_builder.py)

Add four tests from the brief (lines 334–458). Use `AdaptedChunk(...)` **without** `candidate_visual_frame_keys`, `candidate_visual_types`, `candidate_example_types` (they are properties on the dataclass, not constructor args).

1. **test_compact_explicit_anchor_gets_line_confidence** — Chunk with 3 lines; definition with `source_line_indices=[1, 2]`; assert `timestamp_confidence == "line"`, `source_line_start == 1`, `source_line_end == 2`.
2. **test_broader_local_anchor_gets_span_confidence** — Chunk with 6 lines; process_steps with `source_line_indices=[0,1,2,3,4,5]`; assert `timestamp_confidence == "span"`, `source_line_start == 0`, `source_line_end == 5`.
3. **test_sparse_anchor_downgrades_to_chunk** — Chunk with 7 lines; warnings with `source_line_indices=[0, 3, 6]`; assert `timestamp_confidence == "chunk"`, `source_line_start`/`source_line_end` None, `transcript_anchors == []`.
4. **test_quote_fallback_defaults_to_span_when_local_match_found** — Invalidations with empty `source_line_indices` and `source_quote="returns below the level"`; assert `timestamp_confidence in {"span", "line"}`, `anchor_match_source == "llm_source_quote"`.

### 5.2 [tests/test_schemas.py](h:\GITS\tim-class-pass\tests\test_schemas.py)

Add **test_line_confidence_rejects_broad_anchor_width** (brief 464–488): `KnowledgeEvent` with `timestamp_confidence="line"`, `source_line_start=0`, `source_line_end=10`, 11 `TranscriptAnchor`s, `anchor_span_width=11`, `anchor_density=1.0`. Assert `validate_knowledge_event(event)` contains an error with `"anchor_span_width > 6"`. Import `TranscriptAnchor` from `pipeline.schemas`.

### 5.3 [tests/test_component2_pipeline.py](h:\GITS\tim-class-pass\tests\test_component2_pipeline.py)

Add **test_pipeline_outputs_mixed_timestamp_confidence_not_all_line** (brief 494–508): Load `knowledge_events.json` from a known output path (e.g. `data/Lesson 2. Levels part 1/output_intermediate/Lesson 2. Levels part 1.knowledge_events.json` or a fixture path). Parse as `KnowledgeEventCollection`. Assert `"line" in confidences` and `any(c in {"span", "chunk"} for c in confidences)`. If the test runs only after a full pipeline run, use a path under `data/Lesson 2. Levels part 1` or skip when file missing. Adapt `lesson_minimal_root` / `_load_lesson_minimal_root` if those exist in the test module; otherwise use a concrete path or pytest fixture that points to the lesson output directory.

---

## 6. Rerun Component 2 to the end

- Run for **Lesson 2. Levels part 1** with:
  - `--vtt "data/Lesson 2. Levels part 1/Lesson 2. Levels part 1.vtt"`
  - `--visuals-json "data/Lesson 2. Levels part 1/dense_analysis.json"`
  - `--output-root "data/Lesson 2. Levels part 1"`
  - `--video-id "Lesson 2. Levels part 1"`
  - `--enable-knowledge-events --enable-evidence-linking --enable-rule-cards --enable-ml-prep --enable-exporters --no-preserve-legacy-markdown`
- **Success:** Run completes; `knowledge_events.json` has a **mix** of `timestamp_confidence` values (`line`, `span`, `chunk`); not all events are `line`; Phase 2B diagnostic fields populated where applicable.

---

## 7. Implementation order

1. **schemas.py** — Extend `TimestampConfidence`; add diagnostic fields to `KnowledgeEvent`; update `validate_knowledge_event`.
2. **knowledge_builder.py** — Add thresholds; add contiguity/density helpers and `classify_timestamp_confidence`; replace `resolve_statement_anchors`; update `extraction_result_to_knowledge_events` unpack and event construction; enrich rejected/debug with new fields.
3. **llm_processor.py** — Replace ANCHOR RULES in system prompt.
4. **main.py** — Optional Step 3.2b message with line/span/chunk counts.
5. **Tests** — test_knowledge_builder (4), test_schemas (1), test_component2_pipeline (1).
6. **Rerun** — Component 2 full run with exporters for Lesson 2.

---

## 8. Rules (from brief)

- Add `span`; downgrade broad or sparse anchors to `chunk` or `span`.
- Keep chunk fallback honest; reserve `line` for compact, dense, explicit matches.
- Do not keep everything as `line`; do not invent anchors; do not fake precision from `source_quote` alone.
- Do not change rule/evidence export gates in this patch.
