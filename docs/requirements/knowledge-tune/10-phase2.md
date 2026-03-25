Yes. Give the agent this exact brief.

---

# Agent task: Phase 2A is serializing, but the confidence policy is not applied

## Current state

The latest rerun shows that Phase 2A fields now **do reach** final `knowledge_events.json`, which is good.

But the confidence logic is still not functioning:

* all events are `timestamp_confidence = "line"`
* `anchor_match_source` is always `null`
* `anchor_line_count` is always `null`
* `anchor_span_width` is always `null`
* `anchor_density` is always `null`

This means the code is **writing the fields**, but it is **not computing or assigning the diagnostics / downgrade logic**.

## Goal

Implement actual anchor-quality classification so final `KnowledgeEvent` uses:

* `line` for compact, dense, explicit anchors
* `span` for broader but still local anchors
* `chunk` for sparse / weak / broad anchors

And populate:

* `anchor_match_source`
* `anchor_line_count`
* `anchor_span_width`
* `anchor_density`

---

# Scope

Edit only these files unless you truly need one more helper:

1. `pipeline/schemas.py`
2. `pipeline/component2/knowledge_builder.py`
3. `tests/test_knowledge_builder.py`
4. `tests/test_schemas.py`
5. one pipeline smoke test file if you already have one

Do **not** touch:

* `evidence_linker.py`
* `ml_prep.py`
* rule export gating

That part is currently back in a good conservative state.

---

# 1) `pipeline/schemas.py`

## Ensure the enum is correct

Find:

```python
TimestampConfidence = Literal["chunk", "line"]
```

Replace with:

```python
TimestampConfidence = Literal["chunk", "span", "line"]
```

## Ensure `KnowledgeEvent` includes these fields

If not already present, add:

```python
anchor_match_source: Optional[AnchorMatchSource] = None
anchor_line_count: Optional[int] = None
anchor_span_width: Optional[int] = None
anchor_density: Optional[float] = None
```

## Tighten validation so fake `line` is rejected

Update `validate_knowledge_event(...)` to include:

```python
def validate_knowledge_event(event: KnowledgeEvent) -> List[str]:
    errors: List[str] = []
    if not (event.event_id or "").strip():
        errors.append("event_id must not be empty")
    if not (event.lesson_id or "").strip():
        errors.append("lesson_id must not be empty")
    if not event.event_type:
        errors.append("event_type must be set")
    if is_placeholder_text(event.normalized_text):
        errors.append("normalized_text is placeholder or empty")
    if is_placeholder_text(event.raw_text):
        errors.append("raw_text is placeholder or empty")

    if event.timestamp_confidence in {"line", "span"}:
        if event.source_line_start is None or event.source_line_end is None:
            errors.append(
                f"timestamp_confidence='{event.timestamp_confidence}' requires source_line_start/source_line_end"
            )
        if not event.transcript_anchors:
            errors.append(
                f"timestamp_confidence='{event.timestamp_confidence}' requires transcript_anchors"
            )

    if event.timestamp_confidence == "line":
        if event.anchor_match_source is None:
            errors.append("timestamp_confidence='line' requires anchor_match_source")
        if event.anchor_line_count is None:
            errors.append("timestamp_confidence='line' requires anchor_line_count")
        if event.anchor_span_width is None:
            errors.append("timestamp_confidence='line' requires anchor_span_width")
        if event.anchor_density is None:
            errors.append("timestamp_confidence='line' requires anchor_density")
        if event.anchor_span_width is not None and event.anchor_span_width > 4:
            errors.append("timestamp_confidence='line' cannot have anchor_span_width > 4")
        if event.anchor_density is not None and event.anchor_density < 0.75:
            errors.append("timestamp_confidence='line' requires anchor_density >= 0.75")

    return errors
```

This is important because it forces the diagnostics to be populated whenever the code claims `line`.

---

# 2) `pipeline/component2/knowledge_builder.py`

This is the main fix.

## Add explicit thresholds near the top

```python
MAX_LINE_CONFIDENCE_WIDTH = 4
MAX_SPAN_CONFIDENCE_WIDTH = 10
MIN_LINE_DENSITY = 0.75
MIN_SPAN_DENSITY = 0.50
```

## Add helpers

### A. span width and density

```python
def compute_anchor_span_width(line_indices: list[int]) -> int:
    if not line_indices:
        return 0
    ordered = sorted(set(line_indices))
    return (ordered[-1] - ordered[0]) + 1


def compute_anchor_density(line_indices: list[int]) -> float:
    if not line_indices:
        return 0.0
    width = compute_anchor_span_width(line_indices)
    if width <= 0:
        return 0.0
    return len(set(line_indices)) / float(width)


def is_near_contiguous(line_indices: list[int], *, max_gap: int = 1) -> bool:
    ordered = sorted(set(line_indices))
    if len(ordered) <= 1:
        return True
    for left, right in zip(ordered, ordered[1:]):
        if right - left > (max_gap + 1):
            return False
    return True
```

### B. real confidence classification

Add:

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

    # Best case: explicit line indices + compact + dense
    if (
        match_source == "llm_line_indices"
        and near_contiguous
        and span_width <= MAX_LINE_CONFIDENCE_WIDTH
        and density >= MIN_LINE_DENSITY
    ):
        return ("line", source_line_start, source_line_end, span_width, density)

    # Still useful local anchor, but broader or quote-derived
    if (
        near_contiguous
        and span_width <= MAX_SPAN_CONFIDENCE_WIDTH
        and density >= MIN_SPAN_DENSITY
    ):
        return ("span", source_line_start, source_line_end, span_width, density)

    # Too broad / sparse to claim local precision
    return ("chunk", None, None, span_width, density)
```

---

## Fix `resolve_statement_anchors(...)`

The current behavior is likely returning line indices and anchors, but not assigning diagnostics or downgrade logic.

Replace it with this shape:

```python
def resolve_statement_anchors(
    statement: ExtractedStatement,
    chunk: AdaptedChunk,
) -> tuple[
    list[int],            # resolved_line_indices
    list[TranscriptAnchor],
    str | None,           # source_quote
    str,                  # anchor_match_source
    str,                  # timestamp_confidence
    int | None,           # source_line_start
    int | None,           # source_line_end
    str,                  # timestamp_start
    str,                  # timestamp_end
    int,                  # anchor_span_width
    float,                # anchor_density
]:
    transcript_lines = chunk.transcript_lines or []

    resolved_line_indices = clamp_line_indices(
        statement.source_line_indices or [],
        transcript_lines,
    )
    anchor_match_source = "llm_line_indices"

    if not resolved_line_indices and statement.source_quote:
        resolved_line_indices = find_line_indices_by_quote(
            statement.source_quote,
            transcript_lines,
        )
        if resolved_line_indices:
            anchor_match_source = "llm_source_quote"

    (
        timestamp_confidence,
        source_line_start,
        source_line_end,
        anchor_span_width,
        anchor_density,
    ) = classify_timestamp_confidence(
        resolved_line_indices=resolved_line_indices,
        match_source=anchor_match_source,
    )

    if timestamp_confidence in {"line", "span"} and source_line_start is not None and source_line_end is not None:
        start_seconds = float(
            transcript_lines[source_line_start].get("start_seconds", chunk.start_time_seconds)
        )
        end_seconds = float(
            transcript_lines[source_line_end].get("end_seconds", chunk.end_time_seconds)
        )
        timestamp_start = seconds_to_mmss(start_seconds)
        timestamp_end = seconds_to_mmss(end_seconds)
        transcript_anchors = build_transcript_anchors(
            resolved_line_indices,
            transcript_lines,
            match_source=anchor_match_source,
        )
    else:
        timestamp_start = seconds_to_mmss(chunk.start_time_seconds)
        timestamp_end = seconds_to_mmss(chunk.end_time_seconds)
        transcript_anchors = []
        anchor_match_source = "chunk_fallback"

    return (
        resolved_line_indices,
        transcript_anchors,
        statement.source_quote,
        anchor_match_source,
        timestamp_confidence,
        source_line_start,
        source_line_end,
        timestamp_start,
        timestamp_end,
        anchor_span_width,
        anchor_density,
    )
```

---

## Fix `extraction_result_to_knowledge_events(...)`

Where you call `resolve_statement_anchors(...)`, unpack the full result:

```python
(
    resolved_line_indices,
    transcript_anchors,
    source_quote,
    anchor_match_source,
    timestamp_confidence,
    source_line_start,
    source_line_end,
    ts_start,
    ts_end,
    anchor_span_width,
    anchor_density,
) = resolve_statement_anchors(st, chunk)
```

Then populate the fields on `KnowledgeEvent(...)`:

```python
ke = KnowledgeEvent(
    event_id=event_id,
    lesson_id=chunk.lesson_id,
    lesson_title=chunk.lesson_title,
    section=chunk.section,
    subsection=chunk.subsection,
    timestamp_start=ts_start,
    timestamp_end=ts_end,
    event_type=event_type,
    raw_text=raw,
    normalized_text=norm,
    concept=concept,
    subconcept=subconcept,
    source_event_ids=[],
    evidence_refs=[],
    confidence=label,
    confidence_score=conf_score,
    ambiguity_notes=st.ambiguity_notes or [],
    source_chunk_index=chunk.chunk_index,
    source_line_start=source_line_start,
    source_line_end=source_line_end,
    source_quote=source_quote,
    transcript_anchors=transcript_anchors,
    timestamp_confidence=timestamp_confidence,
    anchor_match_source=anchor_match_source,
    anchor_line_count=len(resolved_line_indices),
    anchor_span_width=anchor_span_width,
    anchor_density=anchor_density,
    metadata=strip_raw_visual_blobs_from_metadata(metadata),
)
```

## Also improve debug rows

When you add rejected/debug rows, include:

```python
"source_line_indices": st.source_line_indices or [],
"resolved_line_indices": resolved_line_indices,
"source_quote": st.source_quote,
"anchor_match_source": anchor_match_source,
"timestamp_confidence": timestamp_confidence,
"anchor_line_count": len(resolved_line_indices),
"anchor_span_width": anchor_span_width,
"anchor_density": anchor_density,
```

---

# 3) Tests to add

## `tests/test_knowledge_builder.py`

### Test: compact explicit anchors become `line`

```python
def test_compact_explicit_anchor_gets_line_confidence() -> None:
    chunk = AdaptedChunk(
        lesson_id="L2",
        lesson_title=None,
        chunk_index=0,
        start_time_seconds=1.0,
        end_time_seconds=20.0,
        transcript_lines=[
            {"start_seconds": 1.0, "end_seconds": 3.0, "text": "Intro."},
            {"start_seconds": 3.0, "end_seconds": 5.0, "text": "A level forms after repeated reactions."},
            {"start_seconds": 5.0, "end_seconds": 7.0, "text": "That level becomes important for entries."},
        ],
        transcript_text="Intro.\nA level forms after repeated reactions.\nThat level becomes important for entries.",
        visual_events=[],
        section=None,
        subsection=None,
        candidate_visual_frame_keys=[],
        candidate_visual_types=[],
        candidate_example_types=[],
    )

    extraction = ChunkExtractionResult(
        definitions=[
            ExtractedStatement(
                text="A level forms after repeated reactions.",
                source_line_indices=[1, 2],
                source_quote="repeated reactions",
            )
        ]
    )

    events, rejected = extraction_result_to_knowledge_events(extraction, chunk)
    assert rejected == []
    ev = events[0]
    assert ev.timestamp_confidence == "line"
    assert ev.anchor_match_source == "llm_line_indices"
    assert ev.anchor_line_count == 2
    assert ev.anchor_span_width == 2
    assert ev.anchor_density == 1.0
```

### Test: broader local anchors become `span`

```python
def test_broader_local_anchor_gets_span_confidence() -> None:
    chunk = AdaptedChunk(
        lesson_id="L2",
        lesson_title=None,
        chunk_index=0,
        start_time_seconds=0.0,
        end_time_seconds=30.0,
        transcript_lines=[
            {"start_seconds": 0.0, "end_seconds": 2.0, "text": "L0"},
            {"start_seconds": 2.0, "end_seconds": 4.0, "text": "L1"},
            {"start_seconds": 4.0, "end_seconds": 6.0, "text": "L2"},
            {"start_seconds": 6.0, "end_seconds": 8.0, "text": "L3"},
            {"start_seconds": 8.0, "end_seconds": 10.0, "text": "L4"},
            {"start_seconds": 10.0, "end_seconds": 12.0, "text": "L5"},
        ],
        transcript_text="...",
        visual_events=[],
        section=None,
        subsection=None,
        candidate_visual_frame_keys=[],
        candidate_visual_types=[],
        candidate_example_types=[],
    )

    extraction = ChunkExtractionResult(
        process_steps=[
            ExtractedStatement(
                text="A process spans multiple nearby lines.",
                source_line_indices=[0, 1, 2, 3, 4, 5],
                source_quote="multiple nearby lines",
            )
        ]
    )

    events, rejected = extraction_result_to_knowledge_events(extraction, chunk)
    assert rejected == []
    ev = events[0]
    assert ev.timestamp_confidence == "span"
    assert ev.anchor_match_source == "llm_line_indices"
    assert ev.anchor_line_count == 6
    assert ev.anchor_span_width == 6
```

### Test: sparse anchors downgrade to `chunk`

```python
def test_sparse_anchor_downgrades_to_chunk() -> None:
    chunk = AdaptedChunk(
        lesson_id="L2",
        lesson_title=None,
        chunk_index=0,
        start_time_seconds=0.0,
        end_time_seconds=30.0,
        transcript_lines=[
            {"start_seconds": 0.0, "end_seconds": 2.0, "text": "L0"},
            {"start_seconds": 2.0, "end_seconds": 4.0, "text": "L1"},
            {"start_seconds": 4.0, "end_seconds": 6.0, "text": "L2"},
            {"start_seconds": 6.0, "end_seconds": 8.0, "text": "L3"},
            {"start_seconds": 8.0, "end_seconds": 10.0, "text": "L4"},
            {"start_seconds": 10.0, "end_seconds": 12.0, "text": "L5"},
            {"start_seconds": 12.0, "end_seconds": 14.0, "text": "L6"},
        ],
        transcript_text="...",
        visual_events=[],
        section=None,
        subsection=None,
        candidate_visual_frame_keys=[],
        candidate_visual_types=[],
        candidate_example_types=[],
    )

    extraction = ChunkExtractionResult(
        warnings=[
            ExtractedStatement(
                text="This warning is only loosely supported across the chunk.",
                source_line_indices=[0, 3, 6],
                source_quote="loosely supported",
            )
        ]
    )

    events, rejected = extraction_result_to_knowledge_events(extraction, chunk)
    assert rejected == []
    ev = events[0]
    assert ev.timestamp_confidence == "chunk"
    assert ev.anchor_match_source == "chunk_fallback"
    assert ev.source_line_start is None
    assert ev.source_line_end is None
    assert ev.transcript_anchors == []
    assert ev.anchor_line_count == 3
```

---

## `tests/test_schemas.py`

Add:

```python
def test_line_confidence_requires_anchor_diagnostics() -> None:
    event = KnowledgeEvent(
        event_id="ke1",
        lesson_id="L2",
        event_type="definition",
        raw_text="A level is a repeated reaction area.",
        normalized_text="A level is a repeated reaction area.",
        timestamp_confidence="line",
        source_line_start=0,
        source_line_end=1,
        transcript_anchors=[
            TranscriptAnchor(
                line_index=0,
                text="A level is a repeated reaction area.",
                match_source="llm_line_indices",
            )
        ],
        anchor_match_source=None,
        anchor_line_count=None,
        anchor_span_width=None,
        anchor_density=None,
        metadata={"chunk_index": 0},
    )

    errors = validate_knowledge_event(event)
    assert any("anchor_match_source" in e for e in errors)
    assert any("anchor_line_count" in e for e in errors)
    assert any("anchor_span_width" in e for e in errors)
    assert any("anchor_density" in e for e in errors)
```

---

## Pipeline smoke test

If you already have a pipeline integration test, add this invariant after writing `knowledge_events.json`:

```python
def test_pipeline_outputs_not_all_events_are_line_confidence(lesson_minimal_root: Path) -> None:
    root = _load_lesson_minimal_root(lesson_minimal_root)
    collection = KnowledgeEventCollection.model_validate_json(
        (root / "knowledge_events.json").read_text(encoding="utf-8")
    )

    confidences = [ev.timestamp_confidence for ev in collection.events]
    assert "line" in confidences
    assert any(c in {"span", "chunk"} for c in confidences)
```

This specifically guards against the current regression.

---

# 4) Temporary debug probe

Add this right before saving `knowledge_events.json` in `main.py`:

```python
if knowledge_collection.events:
    sample = knowledge_collection.events[0]
    print(
        "ANCHOR_STATS_SAMPLE",
        {
            "timestamp_confidence": sample.timestamp_confidence,
            "anchor_match_source": sample.anchor_match_source,
            "anchor_line_count": sample.anchor_line_count,
            "anchor_span_width": sample.anchor_span_width,
            "anchor_density": sample.anchor_density,
        },
    )

    counts = {"line": 0, "span": 0, "chunk": 0}
    for ev in knowledge_collection.events:
        counts[ev.timestamp_confidence] = counts.get(ev.timestamp_confidence, 0) + 1
    print("TIMESTAMP_CONFIDENCE_COUNTS", counts)
```

Remove this after verifying one good rerun.

---

# Definition of done

This patch is complete only if a rerun shows all of the following:

* `knowledge_events.json` still contains the Phase 2A fields
* `anchor_match_source` is populated for anchored events
* `anchor_line_count` is populated
* `anchor_span_width` is populated
* `anchor_density` is populated
* output contains a believable mix of:

  * `line`
  * `span`
  * `chunk`
* not all events are `line`

---

# Suggested commit message

`Apply real anchor confidence classification and populate KnowledgeEvent diagnostics`

Confidence: High. The remaining problem is very narrow now: the fields are serializing, but the downgrade logic and diagnostics are not actually being assigned.
