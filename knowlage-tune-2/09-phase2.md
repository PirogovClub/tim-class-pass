Yes. Paste this to the agent.

---

# Agent task: Phase 2A fields are not reaching `knowledge_events.json`

## Goal

The latest run still outputs the **legacy `knowledge_events.json` shape**.
The new Phase 2A provenance fields are **missing from the final artifact**.

Before tuning any `line/span/chunk` logic, fix the serialization path so these fields actually appear in the saved JSON.

## Expected fields that must appear in final `knowledge_events.json`

Each event should be able to include these Phase 2A fields:

* `source_chunk_index`
* `source_line_start`
* `source_line_end`
* `source_quote`
* `transcript_anchors`
* `timestamp_confidence`

Optional diagnostics are also good to keep if already implemented:

* `anchor_match_source`
* `anchor_line_count`
* `anchor_span_width`
* `anchor_density`

---

# What to investigate

## 1) `pipeline/schemas.py`

Confirm that `KnowledgeEvent` really declares the new fields.

### Expected shape

```python
# pipeline/schemas.py

AnchorMatchSource = Literal[
    "llm_line_indices",
    "llm_source_quote",
    "heuristic_quote_match",
    "chunk_fallback",
]

TimestampConfidence = Literal["chunk", "span", "line"]


class TranscriptAnchor(SchemaBase):
    line_index: int = Field(ge=0)
    text: Optional[str] = None
    timestamp_start: Optional[str] = None
    timestamp_end: Optional[str] = None
    match_source: AnchorMatchSource = "chunk_fallback"


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

    # Phase 2A provenance
    source_chunk_index: Optional[int] = None
    source_line_start: Optional[int] = None
    source_line_end: Optional[int] = None
    source_quote: Optional[str] = None
    transcript_anchors: List[TranscriptAnchor] = Field(default_factory=list)
    timestamp_confidence: TimestampConfidence = "chunk"

    # Optional diagnostics
    anchor_match_source: Optional[AnchorMatchSource] = None
    anchor_line_count: Optional[int] = None
    anchor_span_width: Optional[int] = None
    anchor_density: Optional[float] = None

    metadata: Dict[str, Any] = Field(default_factory=dict)
```

### If these fields are not present

Add them first.
Do not move to later steps until `KnowledgeEvent` itself contains them.

---

## 2) `pipeline/component2/knowledge_builder.py`

Confirm that `KnowledgeEvent(...)` is actually being instantiated with the new fields.

## Add a temporary assertion / debug print

Right after constructing each `KnowledgeEvent`, add:

```python
# TEMP DEBUG
event_dump = ke.model_dump()
missing_phase2a = [
    key for key in [
        "source_chunk_index",
        "source_line_start",
        "source_line_end",
        "source_quote",
        "transcript_anchors",
        "timestamp_confidence",
    ]
    if key not in event_dump
]
if missing_phase2a:
    print("PHASE2A_MISSING_IN_MODEL", ke.event_id, missing_phase2a)
```

### Expected constructor pattern

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

    # Optional diagnostics
    anchor_match_source=anchor_match_source,
    anchor_line_count=len(resolved_line_indices),
    anchor_span_width=anchor_span_width,
    anchor_density=anchor_density,

    metadata=strip_raw_visual_blobs_from_metadata(metadata),
)
```

### If fields are missing here

That is the bug. Fix the constructor first.

---

## 3) `save_knowledge_events(...)`

This is the most likely failure point.

Find the function that writes `knowledge_events.json`. It may be in:

* `pipeline/component2/knowledge_builder.py`
* `pipeline/component2/main.py`
* a serializer helper file

## Problem to look for

You may have something like this:

```python
payload = [
    {
        "event_id": e.event_id,
        "event_type": e.event_type,
        "raw_text": e.raw_text,
        ...
    }
    for e in collection.events
]
```

If so, that is manually projecting only legacy keys and dropping the new fields.

## Replace manual projection with full model serialization

Use full `model_dump()` on the collection or event objects.

### Safe implementation

```python
# wherever save_knowledge_events lives

def save_knowledge_events(collection: KnowledgeEventCollection, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = collection.model_dump(mode="json", exclude_none=False)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
```

### If you must serialize event-by-event

Do this instead:

```python
def save_knowledge_events(collection: KnowledgeEventCollection, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": collection.schema_version,
        "lesson_id": collection.lesson_id,
        "lesson_title": collection.lesson_title,
        "events": [
            event.model_dump(mode="json", exclude_none=False)
            for event in collection.events
        ],
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
```

## Do not use

* hand-picked legacy key lists
* `exclude_unset=True` if the new fields might not count as explicitly set
* any helper that strips unknown keys

---

## 4) `pipeline/component2/main.py`

Add a runtime check before and after saving.

Right before calling `save_knowledge_events(...)`, add:

```python
if knowledge_collection.events:
    sample = knowledge_collection.events[0]
    print("KNOWLEDGE_EVENT_MODEL_KEYS", sorted(sample.model_dump().keys()))
```

Immediately after saving, read back the file and inspect the first event:

```python
saved = json.loads(paths.knowledge_events_path(lesson_name).read_text(encoding="utf-8"))
if saved.get("events"):
    print("KNOWLEDGE_EVENT_JSON_KEYS", sorted(saved["events"][0].keys()))
```

## Interpret the result

### Case A

`MODEL_KEYS` contains Phase 2A fields, but `JSON_KEYS` does not
→ serialization path is dropping them

### Case B

Neither contains the fields
→ builder / schema path is still not populating them

### Case C

Both contain the fields
→ rerun artifact was likely from old code or wrong branch

---

## 5) Check for alternate save path / overwrite

Search the repo for all writes to `knowledge_events.json`.

Use something like:

```python
save_knowledge_events(
paths.knowledge_events_path(
"knowledge_events.json"
```

You want to confirm there is only one final write path.

## Common failure pattern

The correct enriched file gets written once, then later another older function overwrites it using the legacy schema.

If you find multiple write paths, keep only the final one using full model serialization.

---

# Tests to add

## 1) Serialization test

Add a direct test that the new fields survive save/load.

```python
def test_save_knowledge_events_preserves_phase2a_fields(tmp_path: Path) -> None:
    collection = KnowledgeEventCollection(
        lesson_id="L2",
        lesson_title="Lesson 2",
        events=[
            KnowledgeEvent(
                event_id="ke1",
                lesson_id="L2",
                event_type="definition",
                raw_text="A level is a repeated reaction area.",
                normalized_text="A level is a repeated reaction area.",
                timestamp_start="00:04",
                timestamp_end="00:07",
                source_chunk_index=0,
                source_line_start=1,
                source_line_end=2,
                source_quote="repeated reaction area",
                transcript_anchors=[
                    TranscriptAnchor(
                        line_index=1,
                        text="A level is a repeated reaction area.",
                        timestamp_start="00:04",
                        timestamp_end="00:07",
                        match_source="llm_line_indices",
                    )
                ],
                timestamp_confidence="line",
                metadata={"chunk_index": 0},
            )
        ],
    )

    out = tmp_path / "knowledge_events.json"
    save_knowledge_events(collection, out)

    payload = json.loads(out.read_text(encoding="utf-8"))
    ev = payload["events"][0]

    assert ev["source_chunk_index"] == 0
    assert ev["source_line_start"] == 1
    assert ev["source_line_end"] == 2
    assert ev["source_quote"] == "repeated reaction area"
    assert ev["timestamp_confidence"] == "line"
    assert len(ev["transcript_anchors"]) == 1
```

---

## 2) Builder test

Prove the builder creates these fields before serialization.

```python
def test_extraction_result_to_knowledge_events_emits_phase2a_fields() -> None:
    chunk = AdaptedChunk(
        lesson_id="L2",
        lesson_title=None,
        chunk_index=0,
        start_time_seconds=1.0,
        end_time_seconds=10.0,
        transcript_lines=[
            {"start_seconds": 1.0, "end_seconds": 3.0, "text": "Intro."},
            {"start_seconds": 3.0, "end_seconds": 5.0, "text": "A level forms after repeated reactions."},
        ],
        transcript_text="Intro.\nA level forms after repeated reactions.",
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
                source_line_indices=[1],
                source_quote="repeated reactions",
            )
        ]
    )

    events, rejected = extraction_result_to_knowledge_events(extraction, chunk)
    assert rejected == []
    ev = events[0]

    assert hasattr(ev, "source_chunk_index")
    assert hasattr(ev, "source_line_start")
    assert hasattr(ev, "source_line_end")
    assert hasattr(ev, "source_quote")
    assert hasattr(ev, "transcript_anchors")
    assert hasattr(ev, "timestamp_confidence")
```

---

## 3) Pipeline smoke test

After pipeline execution, verify the saved artifact contains at least one Phase 2A field.

```python
def test_pipeline_written_knowledge_events_contains_phase2a_fields(lesson_minimal_root: Path) -> None:
    root = _load_lesson_minimal_root(lesson_minimal_root)
    payload = json.loads((root / "knowledge_events.json").read_text(encoding="utf-8"))
    assert payload["events"], "knowledge_events.json is empty"

    first = payload["events"][0]
    assert "timestamp_confidence" in first
    assert "transcript_anchors" in first
```

---

# Most likely fix

The highest-probability root cause is:

> `save_knowledge_events(...)` or another serializer is manually projecting legacy fields and dropping the new ones.

So the fastest path is:

1. verify `KnowledgeEvent.model_dump()` contains the new fields
2. replace manual save projection with full `model_dump(mode="json", exclude_none=False)`
3. confirm no later overwrite happens

---

# Definition of done

This task is complete only when:

1. final `knowledge_events.json` actually contains the Phase 2A fields
2. the saved JSON fields match what exists on the in-memory `KnowledgeEvent`
3. no later overwrite removes them
4. at least one test proves save/load preserves them

---

# Suggested commit message

`Fix knowledge_events serialization to preserve Phase 2A provenance fields`

**Confidence: High — the current problem is not anchor quality anymore; it is that the Phase 2A fields are missing from the final artifact, which strongly suggests a serialization or overwrite issue.**
