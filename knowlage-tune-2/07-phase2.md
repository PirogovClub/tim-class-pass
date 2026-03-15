Yes. Here is a **very detailed Phase 2A implementation brief** for the agent, matched to your current codebase.

---

# Agent task: Phase 2A — add transcript-anchor provenance and tighter timestamps to `KnowledgeEvent`

## Goal

Improve `knowledge_events.json` from **chunk-level provenance** to **line-anchored provenance**.

Right now:

* `KnowledgeEvent` timestamps are derived from full chunk bounds
* extracted statements do not carry transcript anchors
* `KnowledgeEvent.source_event_ids` is intentionally optional and should stay that way

Phase 2A should add:

* transcript line anchors per extracted statement
* tighter event timestamps when line anchors are available
* honest fallback to chunk bounds when anchors are missing
* structured anchor metadata that downstream code can trust later

This is a provenance-quality task, not an ML task.

---

# Non-goals

Do **not** do any of the following in this task:

* no rule canonicalization
* no evidence scoring redesign
* no concept graph changes
* no fake lineage IDs in `source_event_ids`
* no broad prompt rewrite beyond what is needed for line anchors
* no breaking changes to final export gating for rules/evidence

---

# Current code facts the patch must respect

Your current code path is:

* `pipeline/component2/main.py`

  * calls `process_chunks_knowledge_extract(...)`
  * then `build_knowledge_events_from_extraction_results(...)`

* `pipeline/component2/llm_processor.py`

  * builds the actual extraction prompt used in production
  * `build_knowledge_extract_prompt(...)`
  * `KNOWLEDGE_EXTRACT_SYSTEM_PROMPT`
  * returns `ChunkExtractionResult`

* `pipeline/component2/knowledge_builder.py`

  * owns `ExtractedStatement`
  * owns `ChunkExtractionResult`
  * maps extraction output into `KnowledgeEvent`
  * currently uses chunk time bounds via `get_transcript_time_bounds(...)`

* `pipeline/schemas.py`

  * defines `KnowledgeEvent`
  * already treats `source_event_ids` as optional at the event layer

So the anchor implementation must primarily touch:

1. `pipeline/schemas.py`
2. `pipeline/component2/knowledge_builder.py`
3. `pipeline/component2/llm_processor.py`
4. tests

---

# Design choice

Use **chunk-local zero-based transcript line indices**.

That means:

* if a chunk has transcript lines `[0, 1, 2, 3]`
* and the LLM says `source_line_indices: [1, 2]`
* that refers to the 2nd and 3rd transcript lines **inside that chunk**

This is simpler and more robust than global line numbering.

Also allow:

* `source_quote` as a fallback signal
* no anchors at all when the model cannot identify them

---

# Implementation details by file

---

## 1) `pipeline/schemas.py`

## Objective

Extend `KnowledgeEvent` so it can carry anchor-level provenance explicitly.

## Add a new type

Add this near the schema definitions, above `KnowledgeEvent`:

```python
from typing import Any, Dict, List, Literal, Optional

AnchorMatchSource = Literal[
    "llm_line_indices",
    "llm_source_quote",
    "heuristic_quote_match",
    "chunk_fallback",
]

TimestampConfidence = Literal["chunk", "line"]


class TranscriptAnchor(SchemaBase):
    line_index: int = Field(ge=0)
    text: Optional[str] = None
    timestamp_start: Optional[str] = None
    timestamp_end: Optional[str] = None
    match_source: AnchorMatchSource = "chunk_fallback"
```

## Extend `KnowledgeEvent`

Add these fields to `KnowledgeEvent`:

```python
class KnowledgeEvent(ProvenanceMixin, TimeRangeMixin):
    event_id: str
    event_type: EventType
    raw_text: str
    normalized_text: str
    concept: Optional[str] = None
    subconcept: Optional[str] = None
    evidence_refs: List[str] = Field(default_factory=list)
    confidence: ConfidenceLabel = "medium"
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    ambiguity_notes: List[str] = Field(default_factory=list)

    # --- Phase 2A provenance fields ---
    source_chunk_index: Optional[int] = None
    source_line_start: Optional[int] = None
    source_line_end: Optional[int] = None
    source_quote: Optional[str] = None
    transcript_anchors: List[TranscriptAnchor] = Field(default_factory=list)
    timestamp_confidence: TimestampConfidence = "chunk"

    metadata: Dict[str, Any] = Field(default_factory=dict)
```

## Validation behavior

Do **not** make these new fields hard-required for export yet.

Update `validate_knowledge_event(...)` only with light checks:

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
    if event.confidence_score is not None and not (0.0 <= event.confidence_score <= 1.0):
        errors.append("confidence_score must be in [0, 1]")

    # Phase 2A: light consistency checks only
    if event.timestamp_confidence == "line":
        if event.source_line_start is None or event.source_line_end is None:
            errors.append("timestamp_confidence='line' requires source_line_start/source_line_end")
        if not event.transcript_anchors:
            errors.append("timestamp_confidence='line' requires transcript_anchors")

    return errors
```

## Important

Do **not** add:

* requirement that every event must have anchors
* requirement that `source_event_ids` be populated

Chunk fallback must remain valid.

---

## 2) `pipeline/component2/knowledge_builder.py`

This is the core file for Phase 2A.

---

### 2.1 Extend `ExtractedStatement`

Current model:

```python
class ExtractedStatement(BaseModel):
    text: str
    concept: Optional[str] = None
    subconcept: Optional[str] = None
    source_type: SourceType = "explicit"
    ambiguity_notes: list[str] = Field(default_factory=list)
```

Replace with:

```python
from pydantic import BaseModel, Field, field_validator

class ExtractedStatement(BaseModel):
    text: str
    concept: Optional[str] = None
    subconcept: Optional[str] = None
    source_type: SourceType = "explicit"
    ambiguity_notes: list[str] = Field(default_factory=list)

    # Phase 2A anchor hints returned by LLM
    source_line_indices: list[int] = Field(default_factory=list)
    source_quote: Optional[str] = None

    @field_validator("source_line_indices")
    @classmethod
    def normalize_source_line_indices(cls, value: list[int]) -> list[int]:
        cleaned = []
        seen = set()
        for item in value or []:
            if isinstance(item, int) and item >= 0 and item not in seen:
                seen.add(item)
                cleaned.append(item)
        return sorted(cleaned)
```

## Keep `ChunkExtractionResult` shape the same

No need to change bucket names.

---

### 2.2 Add line-render helper for prompting

Add a helper near `build_transcript_text(...)`:

```python
def build_numbered_transcript_text(transcript_lines: list[dict]) -> str:
    """
    Render transcript lines with chunk-local zero-based indices and mm:ss spans.
    Example:
    [L0 00:01-00:04] Price reacts from the level.
    [L1 00:04-00:07] A false breakout returns under the level.
    """
    rendered: list[str] = []
    for idx, line in enumerate(transcript_lines or []):
        text = normalize_statement_text((line.get("text") or "").strip())
        if not text:
            continue
        start = seconds_to_mmss(float(line.get("start_seconds", 0.0)))
        end = seconds_to_mmss(float(line.get("end_seconds", 0.0)))
        rendered.append(f"[L{idx} {start}-{end}] {text}")
    return "\n".join(rendered)
```

This will let the LLM point to exact line indices.

---

### 2.3 Add anchor-resolution helpers

Add these helpers before `extraction_result_to_knowledge_events(...)`.

#### Helper 1: resolve indices that are in range

```python
def clamp_line_indices(indices: list[int], transcript_lines: list[dict]) -> list[int]:
    if not transcript_lines:
        return []
    max_idx = len(transcript_lines) - 1
    valid = [i for i in indices if 0 <= i <= max_idx]
    return sorted(dict.fromkeys(valid))
```

#### Helper 2: quote fallback matcher

Keep this conservative. No fuzzy library needed.

```python
def find_line_indices_by_quote(source_quote: str | None, transcript_lines: list[dict]) -> list[int]:
    quote = normalize_statement_text(source_quote or "").lower()
    if not quote or not transcript_lines:
        return []

    matches: list[int] = []
    for idx, line in enumerate(transcript_lines):
        text = normalize_statement_text((line.get("text") or "")).lower()
        if not text:
            continue
        if quote in text or text in quote:
            matches.append(idx)

    return matches
```

#### Helper 3: build anchors from resolved line indices

```python
from pipeline.schemas import TranscriptAnchor

def build_transcript_anchors(
    line_indices: list[int],
    transcript_lines: list[dict],
    *,
    match_source: str,
) -> list[TranscriptAnchor]:
    anchors: list[TranscriptAnchor] = []
    for idx in line_indices:
        line = transcript_lines[idx]
        anchors.append(
            TranscriptAnchor(
                line_index=idx,
                text=normalize_statement_text(line.get("text") or ""),
                timestamp_start=seconds_to_mmss(float(line.get("start_seconds", 0.0))),
                timestamp_end=seconds_to_mmss(float(line.get("end_seconds", 0.0))),
                match_source=match_source,
            )
        )
    return anchors
```

#### Helper 4: derive timestamps from anchors

```python
def derive_event_timestamps_from_line_indices(
    line_indices: list[int],
    transcript_lines: list[dict],
    *,
    fallback_start_seconds: float,
    fallback_end_seconds: float,
) -> tuple[str, str, str, int | None, int | None]:
    """
    Returns:
      timestamp_start, timestamp_end, timestamp_confidence, source_line_start, source_line_end
    """
    resolved = clamp_line_indices(line_indices, transcript_lines)
    if not resolved:
        return (
            seconds_to_mmss(fallback_start_seconds),
            seconds_to_mmss(fallback_end_seconds),
            "chunk",
            None,
            None,
        )

    start_seconds = float(transcript_lines[resolved[0]].get("start_seconds", fallback_start_seconds))
    end_seconds = float(transcript_lines[resolved[-1]].get("end_seconds", fallback_end_seconds))

    return (
        seconds_to_mmss(start_seconds),
        seconds_to_mmss(end_seconds),
        "line",
        resolved[0],
        resolved[-1],
    )
```

#### Helper 5: unify statement anchor resolution

```python
def resolve_statement_anchors(
    statement: ExtractedStatement,
    chunk: AdaptedChunk,
) -> tuple[list[int], list[TranscriptAnchor], str | None, str, int | None, int | None, str, str]:
    """
    Returns:
      resolved_line_indices,
      transcript_anchors,
      source_quote,
      timestamp_confidence,
      source_line_start,
      source_line_end,
      timestamp_start,
      timestamp_end
    """
    transcript_lines = chunk.transcript_lines or []

    # 1. Prefer explicit LLM line indices
    line_indices = clamp_line_indices(statement.source_line_indices or [], transcript_lines)
    match_source = "llm_line_indices"

    # 2. Fall back to source_quote if needed
    if not line_indices and statement.source_quote:
        line_indices = find_line_indices_by_quote(statement.source_quote, transcript_lines)
        if line_indices:
            match_source = "llm_source_quote"

    # 3. Derive timestamps
    ts_start, ts_end, ts_conf, src_line_start, src_line_end = derive_event_timestamps_from_line_indices(
        line_indices,
        transcript_lines,
        fallback_start_seconds=chunk.start_time_seconds,
        fallback_end_seconds=chunk.end_time_seconds,
    )

    anchors: list[TranscriptAnchor] = []
    if line_indices:
        anchors = build_transcript_anchors(line_indices, transcript_lines, match_source=match_source)

    return (
        line_indices,
        anchors,
        statement.source_quote,
        ts_conf,
        src_line_start,
        src_line_end,
        ts_start,
        ts_end,
    )
```

---

### 2.4 Use anchor resolution inside `extraction_result_to_knowledge_events(...)`

Current code derives one `ts_start` and `ts_end` from the whole chunk before looping through statements.

Change that.

#### Keep chunk fallback values

You still need:

```python
chunk_t_start, chunk_t_end = get_transcript_time_bounds(
    chunk.transcript_lines,
    chunk.start_time_seconds,
    chunk.end_time_seconds,
)
chunk_ts_start = seconds_to_mmss(chunk_t_start)
chunk_ts_end = seconds_to_mmss(chunk_t_end)
```

Use those only for rejects and fallback.

#### Inside the per-statement loop

Right after you validate `raw` and `norm`, add:

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

Then in `KnowledgeEvent(...)`, replace the old timestamp/source fields with:

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

    # Phase 2A fields
    source_chunk_index=chunk.chunk_index,
    source_line_start=source_line_start,
    source_line_end=source_line_end,
    source_quote=source_quote,
    transcript_anchors=transcript_anchors,
    timestamp_confidence=timestamp_confidence,

    metadata=strip_raw_visual_blobs_from_metadata(metadata),
)
```

#### Also enrich rejected debug rows

For rows appended to `rejected`, add:

```python
"source_line_indices": st.source_line_indices or [],
"source_quote": st.source_quote,
```

That helps QA when anchor extraction fails.

---

## 3) `pipeline/component2/llm_processor.py`

This is the production prompt path. This file must be updated.

---

### 3.1 Update the system prompt

Modify `KNOWLEDGE_EXTRACT_SYSTEM_PROMPT`.

Current item format is:

```json
{
  "text": "string",
  "concept": "string or null",
  "subconcept": "string or null",
  "source_type": "explicit | inferred | mixed",
  "ambiguity_notes": ["string", "..."]
}
```

Replace with:

```text
For every bucket except "global_notes", each item must be an object with exactly these fields:
{
  "text": "string",
  "concept": "string or null",
  "subconcept": "string or null",
  "source_type": "explicit | inferred | mixed",
  "ambiguity_notes": ["string", "..."],
  "source_line_indices": [0, 1],
  "source_quote": "string or null"
}
```

Add these rules below the item format section:

```text
ANCHOR RULES

- source_line_indices must use chunk-local zero-based transcript line indices.
- If the statement is supported by one line, return a one-element array.
- If it spans multiple adjacent transcript lines, return all relevant indices.
- If the exact line indices are unclear, return an empty array and use source_quote when possible.
- source_quote should be a short verbatim or near-verbatim anchor from the transcript, not a paraphrase.
- If neither line indices nor a short quote can be identified confidently, use [] and null.
```

### 3.2 Update the user prompt builder

Current `build_knowledge_extract_prompt(...)` takes `transcript_text`.

Extend the signature:

```python
def build_knowledge_extract_prompt(
    *,
    lesson_id: str,
    chunk_index: int,
    section: str | None = None,
    transcript_text: str,
    transcript_lines: list | None = None,
    visual_summaries: list[str],
    concept_context: str | None = None,
    start_time_seconds: float | None = None,
    end_time_seconds: float | None = None,
) -> str:
```

Then change transcript rendering:

```python
if transcript_lines:
    rendered_lines = []
    for idx, line in enumerate(transcript_lines):
        start = seconds_to_mmss(line.start_seconds)
        end = seconds_to_mmss(line.end_seconds)
        text = (line.text or "").strip()
        if not text:
            continue
        rendered_lines.append(f"[L{idx} {start}-{end}] {text}")
    transcript_block = "\n".join(rendered_lines) if rendered_lines else "(empty)"
else:
    transcript_block = transcript_text or "(empty)"
```

Then use `transcript_block` in the `<transcript>` section.

### 3.3 Update the call site

In `process_chunk_knowledge_extract(...)`, change:

```python
prompt = build_knowledge_extract_prompt(
    lesson_id=chunk.lesson_id,
    chunk_index=chunk.chunk_index,
    section=getattr(chunk, "section", None),
    transcript_text=chunk.transcript_text or "",
    visual_summaries=visual_summaries,
    concept_context=getattr(chunk, "concept_context", None),
    start_time_seconds=chunk.start_time_seconds,
    end_time_seconds=chunk.end_time_seconds,
)
```

to:

```python
prompt = build_knowledge_extract_prompt(
    lesson_id=chunk.lesson_id,
    chunk_index=chunk.chunk_index,
    section=getattr(chunk, "section", None),
    transcript_text=chunk.transcript_text or "",
    transcript_lines=getattr(chunk, "transcript_lines", None),
    visual_summaries=visual_summaries,
    concept_context=getattr(chunk, "concept_context", None),
    start_time_seconds=chunk.start_time_seconds,
    end_time_seconds=chunk.end_time_seconds,
)
```

This is critical. Otherwise the model cannot reliably emit line anchors.

---

## 4) `pipeline/component2/main.py`

No major flow rewrite is needed.

But make sure the output path preserves the richer `KnowledgeEvent` model automatically, which it should since it dumps the model.

Optional small improvement:
after `save_knowledge_events(...)`, update the completion message to include how many events got line-level timestamps.

Example:

```python
line_level_count = sum(
    1 for ev in knowledge_collection.events
    if getattr(ev, "timestamp_confidence", None) == "line"
)
_emit(
    f"Step 3.2b complete: wrote {len(knowledge_collection.events)} events "
    f"({line_level_count} line-anchored) to "
    f"{paths.knowledge_events_path(lesson_name).name}, "
    f"debug to {paths.knowledge_debug_path(lesson_name).name}."
)
```

This is optional but useful.

---

## 5) Tests to add or update

This part is important. Do not skip it.

---

### 5.1 `tests/test_llm_processor.py`

## Add: prompt contains line-numbered transcript format

```python
def test_build_knowledge_extract_prompt_renders_numbered_transcript_lines() -> None:
    chunk_lines = [
        TranscriptLine(start_seconds=1.0, end_seconds=3.0, text="Price reacts from the level."),
        TranscriptLine(start_seconds=3.0, end_seconds=5.0, text="Then it returns below the level."),
    ]

    prompt = build_knowledge_extract_prompt(
        lesson_id="L2",
        chunk_index=0,
        transcript_text="ignored when transcript_lines exist",
        transcript_lines=chunk_lines,
        visual_summaries=["Annotated chart with level"],
        start_time_seconds=1.0,
        end_time_seconds=5.0,
    )

    assert "[L0 00:01-00:03] Price reacts from the level." in prompt
    assert "[L1 00:03-00:05] Then it returns below the level." in prompt
```

## Add: parser accepts anchor fields

```python
def test_parse_knowledge_extraction_accepts_source_line_indices_and_source_quote() -> None:
    payload = """
    {
      "definitions": [
        {
          "text": "A level is a price area of repeated reaction.",
          "concept": "level",
          "subconcept": null,
          "source_type": "explicit",
          "ambiguity_notes": [],
          "source_line_indices": [0, 1],
          "source_quote": "price reacts from the same area several times"
        }
      ],
      "rule_statements": [],
      "conditions": [],
      "invalidations": [],
      "exceptions": [],
      "comparisons": [],
      "warnings": [],
      "process_steps": [],
      "algorithm_hints": [],
      "examples": [],
      "global_notes": []
    }
    """
    parsed = parse_knowledge_extraction(payload)
    assert parsed.definitions[0].source_line_indices == [0, 1]
    assert parsed.definitions[0].source_quote is not None
```

---

### 5.2 `tests/test_knowledge_builder.py`

## Add: line indices narrow timestamps

```python
def test_extraction_result_to_knowledge_events_uses_line_indices_for_tighter_timestamps() -> None:
    chunk = AdaptedChunk(
        lesson_id="L2",
        lesson_title=None,
        chunk_index=0,
        start_time_seconds=1.0,
        end_time_seconds=20.0,
        transcript_lines=[
            {"start_seconds": 1.0, "end_seconds": 4.0, "text": "Intro line."},
            {"start_seconds": 4.0, "end_seconds": 7.0, "text": "A level forms after repeated reactions."},
            {"start_seconds": 7.0, "end_seconds": 10.0, "text": "This level becomes important for entries."},
        ],
        transcript_text="Intro line.\nA level forms after repeated reactions.\nThis level becomes important for entries.",
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
                concept="level",
                source_line_indices=[1, 2],
                source_quote="repeated reactions",
            )
        ]
    )

    events, rejected = extraction_result_to_knowledge_events(extraction, chunk)
    assert rejected == []
    assert len(events) == 1

    ev = events[0]
    assert ev.timestamp_start == "00:04"
    assert ev.timestamp_end == "00:10"
    assert ev.timestamp_confidence == "line"
    assert ev.source_line_start == 1
    assert ev.source_line_end == 2
    assert len(ev.transcript_anchors) == 2
```

## Add: quote fallback works

```python
def test_extraction_result_to_knowledge_events_falls_back_to_source_quote_match() -> None:
    chunk = AdaptedChunk(
        lesson_id="L2",
        lesson_title=None,
        chunk_index=0,
        start_time_seconds=1.0,
        end_time_seconds=20.0,
        transcript_lines=[
            {"start_seconds": 1.0, "end_seconds": 4.0, "text": "Intro line."},
            {"start_seconds": 4.0, "end_seconds": 7.0, "text": "A false breakout returns below the level."},
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
                concept="false_breakout",
                source_line_indices=[],
                source_quote="returns below the level",
            )
        ]
    )

    events, rejected = extraction_result_to_knowledge_events(extraction, chunk)
    assert rejected == []
    ev = events[0]
    assert ev.timestamp_confidence == "line"
    assert ev.source_line_start == 1
    assert ev.source_line_end == 1
    assert len(ev.transcript_anchors) == 1
```

## Add: invalid indices fall back safely

```python
def test_extraction_result_to_knowledge_events_invalid_line_indices_fall_back_to_chunk_bounds() -> None:
    chunk = AdaptedChunk(
        lesson_id="L2",
        lesson_title=None,
        chunk_index=0,
        start_time_seconds=1.0,
        end_time_seconds=20.0,
        transcript_lines=[
            {"start_seconds": 1.0, "end_seconds": 4.0, "text": "One line."},
        ],
        transcript_text="One line.",
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
                text="One line.",
                source_line_indices=[99],
                source_quote=None,
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

---

### 5.3 `tests/test_schemas.py`

Add one schema-level validation test:

```python
def test_knowledge_event_with_line_confidence_requires_anchor_fields() -> None:
    event = KnowledgeEvent(
        event_id="ke1",
        lesson_id="L2",
        event_type="definition",
        raw_text="A level is a repeated reaction area.",
        normalized_text="A level is a repeated reaction area.",
        timestamp_confidence="line",
        source_line_start=None,
        source_line_end=None,
        transcript_anchors=[],
        metadata={"chunk_index": 0},
    )

    errors = validate_knowledge_event(event)
    assert any("timestamp_confidence='line'" in e for e in errors)
```

---

### 5.4 `tests/test_component2_pipeline.py`

Add one pipeline-level smoke test so the end-to-end flow preserves anchors.

High-level pattern:

* mock `process_chunks_knowledge_extract(...)` or its provider path to return a `ChunkExtractionResult` with `source_line_indices`
* run the component2 pipeline
* read written `knowledge_events.json`
* assert at least one event has:

  * `timestamp_confidence == "line"`
  * `source_line_start` / `source_line_end`
  * non-empty `transcript_anchors`

You do not need a full live provider call.

---

# Important implementation rules

## Rule 1

Prefer explicit LLM line indices.

## Rule 2

If line indices are missing, try quote-based fallback.

## Rule 3

If both fail, keep chunk fallback and do **not** invent anchors.

## Rule 4

Never populate `source_event_ids` with fake values.

## Rule 5

Do not reject otherwise valid events just because anchors are unavailable.

That fallback is expected.

---

# Suggested debug additions

In `knowledge_debug.json`, each emitted/rejected row should include enough information to audit anchor behavior.

Add these fields where helpful:

* `source_line_indices`
* `source_quote`
* `resolved_line_indices`
* `timestamp_confidence`

This is especially useful when the model returns bad indices.

---

# Suggested prompt wording change summary

The LLM must now understand:

* transcript lines are numbered
* it can cite them with `source_line_indices`
* it should include a short `source_quote` when useful
* empty anchors are allowed if uncertain

This makes the system robust instead of brittle.

---

# Acceptance criteria

This task is complete only when all are true:

1. `KnowledgeEvent` supports transcript anchors and timestamp confidence
2. extraction prompt shows numbered transcript lines
3. extraction schema accepts `source_line_indices` and `source_quote`
4. `extraction_result_to_knowledge_events(...)` uses line anchors to tighten timestamps
5. quote fallback works when indices are missing
6. invalid/missing anchors fall back to chunk bounds safely
7. tests cover:

   * prompt format
   * parser acceptance
   * line-based timestamp narrowing
   * quote fallback
   * chunk fallback
   * pipeline preservation

---

# Suggested commit message

`Add transcript-anchor provenance and line-level timestamp narrowing for KnowledgeEvent`

---

# Optional follow-up after this patch

After Phase 2A lands, the next logical task is:

* use transcript anchors to improve rule provenance summaries and evidence specificity

But do not combine that with this patch.

**Confidence: High — this matches your current production path (`llm_processor.py` → `knowledge_builder.py` → `main.py`) and keeps the scope narrow enough to implement safely.**
