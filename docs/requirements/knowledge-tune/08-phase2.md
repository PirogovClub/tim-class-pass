Yes. Here is an **explicit agent brief with code snippets** for the next patch.

This patch is about one thing:

> **Stop over-claiming line-level provenance.**

Right now the Phase 2A plumbing exists, but the pipeline marks almost everything as `timestamp_confidence="line"`, even when the anchor spans are broad. That is too optimistic.

---

# Agent task: tighten anchor confidence and add `span` provenance

## Goal

Make `KnowledgeEvent` provenance more honest by distinguishing:

* `line` = tight local anchor
* `span` = several nearby lines, better than chunk but not truly line-precise
* `chunk` = no trustworthy local anchor

## Current problem

The current run shows:

* almost all events get `timestamp_confidence="line"`
* some events span very broad line ranges
* quote fallback and broad multi-line matches are still being treated as line-level precision

That should be corrected.

---

# Required changes

## Files to edit

1. `pipeline/schemas.py`
2. `pipeline/component2/knowledge_builder.py`
3. `pipeline/component2/llm_processor.py`
4. tests

---

# 1) `pipeline/schemas.py`

## Change the confidence enum

Find:

```python
TimestampConfidence = Literal["chunk", "line"]
```

Replace with:

```python
TimestampConfidence = Literal["chunk", "span", "line"]
```

## Add optional anchor diagnostics to `KnowledgeEvent`

Add these fields to `KnowledgeEvent` if they are not already there:

```python
anchor_match_source: Optional[str] = None
anchor_line_count: Optional[int] = None
anchor_span_width: Optional[int] = None
anchor_density: Optional[float] = None
```

These are for QA and debugging. They make it easy to inspect whether the confidence label is justified.

### Example patch

```python
# pipeline/schemas.py

AnchorMatchSource = Literal[
    "llm_line_indices",
    "llm_source_quote",
    "heuristic_quote_match",
    "chunk_fallback",
]

TimestampConfidence = Literal["chunk", "span", "line"]


class KnowledgeEvent(ProvenanceMixin, TimeRangeMixin):
    ...
    source_chunk_index: Optional[int] = None
    source_line_start: Optional[int] = None
    source_line_end: Optional[int] = None
    source_quote: Optional[str] = None
    transcript_anchors: List[TranscriptAnchor] = Field(default_factory=list)
    timestamp_confidence: TimestampConfidence = "chunk"

    # Phase 2A diagnostics
    anchor_match_source: Optional[AnchorMatchSource] = None
    anchor_line_count: Optional[int] = None
    anchor_span_width: Optional[int] = None
    anchor_density: Optional[float] = None

    metadata: Dict[str, Any] = Field(default_factory=dict)
```

## Tighten validation

Update `validate_knowledge_event(...)` so the new states are validated consistently:

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
        if event.anchor_span_width is not None and event.anchor_span_width > 6:
            errors.append("timestamp_confidence='line' cannot have anchor_span_width > 6")
        if event.anchor_density is not None and event.anchor_density < 0.75:
            errors.append("timestamp_confidence='line' requires anchor_density >= 0.75")

    return errors
```

Do **not** reject `chunk` fallback.

---

# 2) `pipeline/component2/knowledge_builder.py`

This is the main patch.

## Add explicit thresholds near the top of the file

```python
# pipeline/component2/knowledge_builder.py

MAX_LINE_CONFIDENCE_WIDTH = 4
MAX_SPAN_CONFIDENCE_WIDTH = 10
MIN_LINE_DENSITY = 0.75
MIN_SPAN_DENSITY = 0.50
```

These are sensible starting thresholds:

* `line`: compact and dense
* `span`: still local, but broader
* anything looser: `chunk`

---

## Add helper functions

### A. contiguity / density helpers

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

### B. classify confidence honestly

Add this helper:

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

    # Most trustworthy case: explicit line indices, compact, dense, local
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

    # Otherwise the anchor is too broad / sparse to claim local precision
    return ("chunk", None, None, span_width, density)
```

This is the critical fix.

---

## Update anchor resolution flow

### Current issue

Your current helper likely returns line indices and directly promotes them into line-level timestamps.

### Required change

Make anchor resolution return:

* resolved indices
* anchors
* match source
* confidence
* diagnostics

## Replace `resolve_statement_anchors(...)` with something like this

```python
def resolve_statement_anchors(
    statement: ExtractedStatement,
    chunk: AdaptedChunk,
) -> tuple[
    list[int],            # resolved_line_indices
    list[TranscriptAnchor],
    str | None,           # source_quote
    str,                  # match_source
    str,                  # timestamp_confidence
    int | None,           # source_line_start
    int | None,           # source_line_end
    str,                  # timestamp_start
    str,                  # timestamp_end
    int,                  # span_width
    float,                # density
]:
    transcript_lines = chunk.transcript_lines or []

    line_indices = clamp_line_indices(statement.source_line_indices or [], transcript_lines)
    match_source = "llm_line_indices"

    if not line_indices and statement.source_quote:
        line_indices = find_line_indices_by_quote(statement.source_quote, transcript_lines)
        if line_indices:
            match_source = "llm_source_quote"

    timestamp_confidence, source_line_start, source_line_end, span_width, density = (
        classify_timestamp_confidence(
            resolved_line_indices=line_indices,
            match_source=match_source,
        )
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
        anchors = build_transcript_anchors(
            line_indices,
            transcript_lines,
            match_source=match_source,
        )
    else:
        timestamp_start = seconds_to_mmss(chunk.start_time_seconds)
        timestamp_end = seconds_to_mmss(chunk.end_time_seconds)
        anchors = []
        match_source = "chunk_fallback"

    return (
        line_indices,
        anchors,
        statement.source_quote,
        match_source,
        timestamp_confidence,
        source_line_start,
        source_line_end,
        timestamp_start,
        timestamp_end,
        span_width,
        density,
    )
```

---

## Update `extraction_result_to_knowledge_events(...)`

Where you currently do:

```python
(
    resolved_line_indices,
    transcript_anchors,
    source_quote,
    timestamp_confidence,
    source_line_start,
    source_line_end,
    ts_start,
    ts_end,
) = resolve_statement_anchors(st, chunk)
```

Replace with:

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

And then populate the event with the new fields:

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

---

## Improve debug output

When you append rejected rows or debug metadata, add:

```python
"source_line_indices": st.source_line_indices or [],
"resolved_line_indices": resolved_line_indices,
"source_quote": st.source_quote,
"anchor_match_source": anchor_match_source,
"timestamp_confidence": timestamp_confidence,
"anchor_span_width": anchor_span_width,
"anchor_density": anchor_density,
```

This will make QA much easier.

---

# 3) `pipeline/component2/llm_processor.py`

The prompt should encourage **smallest valid spans**, not broad coverage.

## Update the anchor rules in `KNOWLEDGE_EXTRACT_SYSTEM_PROMPT`

Add or replace the anchor section with this:

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

This is important. The model is currently too liberal with line anchoring.

---

## Update prompt rendering if needed

Keep the numbered transcript format from Phase 2A. No major change needed there.

---

# 4) Tests to add

Do not skip these. They are the real guardrail.

---

## `tests/test_knowledge_builder.py`

### Test 1: compact explicit anchors become `line`

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
    assert ev.source_line_start == 1
    assert ev.source_line_end == 2
```

### Test 2: broader but local anchors become `span`

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
    assert ev.source_line_start == 0
    assert ev.source_line_end == 5
```

### Test 3: sparse anchors downgrade to `chunk`

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
    assert ev.source_line_start is None
    assert ev.source_line_end is None
    assert ev.transcript_anchors == []
```

### Test 4: quote fallback should usually become `span`, not `line`

```python
def test_quote_fallback_defaults_to_span_when_local_match_found() -> None:
    chunk = AdaptedChunk(
        lesson_id="L2",
        lesson_title=None,
        chunk_index=0,
        start_time_seconds=0.0,
        end_time_seconds=20.0,
        transcript_lines=[
            {"start_seconds": 0.0, "end_seconds": 3.0, "text": "Intro line."},
            {"start_seconds": 3.0, "end_seconds": 6.0, "text": "A false breakout returns below the level."},
        ],
        transcript_text="Intro line.\nA false breakout returns below the level.",
        visual_events=[],
        section=None,
        subsection=None,
        candidate_visual_frame_keys=[],
        candidate_visual_types=[],
        candidate_example_types=[],
    )

    extraction = ChunkExtractionResult(
        invalidations=[
            ExtractedStatement(
                text="A false breakout is invalid when price returns below the level.",
                source_line_indices=[],
                source_quote="returns below the level",
            )
        ]
    )

    events, rejected = extraction_result_to_knowledge_events(extraction, chunk)
    assert rejected == []
    ev = events[0]
    assert ev.timestamp_confidence in {"span", "line"}
    assert ev.anchor_match_source == "llm_source_quote"
```

If you want stricter behavior, make this assert exactly `"span"`.

---

## `tests/test_schemas.py`

Add:

```python
def test_line_confidence_rejects_broad_anchor_width() -> None:
    event = KnowledgeEvent(
        event_id="ke1",
        lesson_id="L2",
        event_type="definition",
        raw_text="A level is a repeated reaction area.",
        normalized_text="A level is a repeated reaction area.",
        timestamp_confidence="line",
        source_line_start=0,
        source_line_end=10,
        transcript_anchors=[
            TranscriptAnchor(line_index=i, text=f"L{i}", match_source="llm_line_indices")
            for i in range(11)
        ],
        anchor_span_width=11,
        anchor_density=1.0,
        metadata={"chunk_index": 0},
    )

    errors = validate_knowledge_event(event)
    assert any("anchor_span_width > 6" in e for e in errors)
```

---

## `tests/test_component2_pipeline.py`

Add one smoke-level invariant after running the pipeline:

```python
def test_pipeline_outputs_mixed_timestamp_confidence_not_all_line(lesson_minimal_root: Path) -> None:
    root = _load_lesson_minimal_root(lesson_minimal_root)
    collection = KnowledgeEventCollection.model_validate_json(
        (root / "knowledge_events.json").read_text(encoding="utf-8")
    )

    confidences = [ev.timestamp_confidence for ev in collection.events]
    assert "line" in confidences
    assert any(c in {"span", "chunk"} for c in confidences)
```

This is a very useful regression guard. The current problem is that everything becomes `line`.

---

# 5) Optional improvement in `main.py`

After saving knowledge events, add summary stats:

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

This is optional, but it will help you see immediately whether the pipeline is overclaiming again.

---

# Behavior rules for the agent

## Must do

* add `span`
* downgrade broad or sparse anchors
* keep chunk fallback honest
* keep line-level only for compact, dense, explicit matches

## Must not do

* do not keep everything as `line`
* do not invent anchors
* do not fake precision just because a `source_quote` exists
* do not change rule/evidence export gates in this patch

---

# Definition of done

This patch is done only when:

1. `KnowledgeEvent.timestamp_confidence` supports `chunk | span | line`
2. broad anchor spans no longer get `line`
3. sparse anchors downgrade to `chunk`
4. quote fallback is not automatically treated as true line precision
5. pipeline outputs a mix of confidence states on realistic lessons
6. Phase 1 safety remains intact

---

# Suggested commit message

`Tighten KnowledgeEvent anchor confidence and add span provenance level`

**Confidence: High — this is the right narrow fix for the current Phase 2A regression, and it addresses the real issue: overconfident anchor labeling rather than missing schema or missing orchestration.**
