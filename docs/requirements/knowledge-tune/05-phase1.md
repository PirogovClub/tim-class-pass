Yes. Here is a **concrete agent brief** you can paste as-is.

---

# Agent task: finalize Phase 1 by locking the `KnowledgeEvent.source_event_ids` contract

## Goal

The export-gating and evidence/ML semantics are now in good shape.
The remaining ambiguity is **contract-level**, not pipeline-logic-level:

* `KnowledgeEvent` is the **primary extracted object**
* it is currently created with `source_event_ids=[]` in `pipeline/component2/knowledge_builder.py`
* `validate_knowledge_event_for_export()` in `pipeline/schemas.py` already **does not require** non-empty `source_event_ids`
* evidence and rules already use `KnowledgeEvent.event_id` as their provenance anchor

So the next step is:

> **Make the contract explicit that `KnowledgeEvent.source_event_ids` is optional in Phase 1 and must not be treated as a failure condition.**

Do **not** add fake/self lineage just to satisfy a gate.

---

# What to change

## 1) `pipeline/schemas.py`

Make the optional contract explicit in the model and in the validator.

### Why

Right now the behavior is already correct, but it is implicit.
We need the code to say clearly:

* `KnowledgeEvent.source_event_ids` is optional
* event-level provenance for Phase 1 is:

  * `event_id`
  * `lesson_id`
  * `metadata.chunk_index`
  * timestamps
  * `evidence_refs`
* upstream lineage IDs for events are a **Phase 2** problem, not a Phase 1 export requirement

### Implementation

Find the `KnowledgeEvent` model and update the field declaration / comment.

Use something like this:

```python
# pipeline/schemas.py

class KnowledgeEvent(BaseModel):
    # ...
    source_event_ids: List[str] = Field(
        default_factory=list,
        description=(
            "Optional upstream lineage for this event. "
            "For Phase 1, KnowledgeEvent is the primary extracted unit, so this "
            "field may be empty. Final export must not reject a KnowledgeEvent "
            "solely because source_event_ids is empty."
        ),
    )
```

Now make the export validator explicitly preserve that contract.

Update `validate_knowledge_event_for_export()` to add a clarifying comment and keep the field optional:

```python
# pipeline/schemas.py

def validate_knowledge_event_for_export(event: KnowledgeEvent) -> List[str]:
    errors = list(validate_knowledge_event(event))

    metadata = getattr(event, "metadata", {}) or {}
    if metadata.get("chunk_index") is None:
        errors.append("metadata.chunk_index must not be empty for final export")

    # IMPORTANT:
    # KnowledgeEvent is the primary extracted object in Phase 1.
    # source_event_ids is optional here and should not be used as a hard export gate.
    # Stronger upstream lineage belongs to Phase 2 (e.g. transcript anchors / span ids).

    return dedupe_preserve_order(errors)
```

Do **not** add:

* `if not event.source_event_ids: ...`
* fake IDs
* self-references

---

## 2) `pipeline/component2/knowledge_builder.py`

Document the intentional behavior at the creation point.

### Why

Right now events are created with `source_event_ids=[]`.
That is fine, but it should be obvious to future readers that this is intentional.

### Implementation

Find the place where `KnowledgeEvent(...)` is instantiated with:

```python
source_event_ids=[]
```

Add an inline comment like this:

```python
# pipeline/component2/knowledge_builder.py

source_event_ids=[],  # Phase 1: KnowledgeEvent is the primary extracted unit; no upstream lineage ids yet.
```

If you want a slightly clearer version:

```python
source_event_ids=[],  # Intentionally empty in Phase 1. Use event_id + chunk_index + timestamps + evidence_refs as event provenance.
```

Do not change runtime behavior here.

---

## 3) `tests/test_phase1_export_validation.py`

Add a test that locks the intended contract.

### Why

You already have a test that placeholder knowledge events are rejected.
Add the mirror test:

> a valid knowledge event with empty `source_event_ids` is still allowed.

### Add this test

```python
# tests/test_phase1_export_validation.py

def test_final_knowledge_export_allows_empty_source_event_ids_when_event_is_otherwise_valid() -> None:
    event = KnowledgeEvent(
        lesson_id="lesson1",
        event_id="ke1",
        event_type="rule_statement",
        raw_text="A valid rule statement.",
        normalized_text="A valid rule statement.",
        source_event_ids=[],
        metadata={"chunk_index": 0},
        timestamp_start="00:01",
        timestamp_end="00:10",
    )

    collection = KnowledgeEventCollection(
        lesson_id="lesson1",
        events=[event],
    )

    valid_collection, debug_rows = validate_knowledge_event_collection_for_export(collection)

    assert len(valid_collection.events) == 1
    assert valid_collection.events[0].event_id == "ke1"
    assert debug_rows == []
```

---

## 4) `tests/test_pipeline_invariants.py`

Add an invariant for **real** knowledge-event provenance instead of event-level `source_event_ids`.

### Why

The meaningful provenance for Phase 1 knowledge events is not `source_event_ids`.
It is:

* `event_id`
* `lesson_id`
* `metadata.chunk_index`
* timestamps
* text integrity

Add a focused invariant test to make that explicit.

### Add this test

```python
# tests/test_pipeline_invariants.py

def test_every_knowledge_event_has_phase1_provenance_fields(lesson_minimal_root: Path) -> None:
    """KnowledgeEvent provenance in Phase 1 is event_id + lesson_id + chunk_index + timestamps, not source_event_ids."""
    root = _load_lesson_minimal_root(lesson_minimal_root)
    path = root / "knowledge_events.json"
    collection = KnowledgeEventCollection.model_validate_json(path.read_text(encoding="utf-8"))

    for ev in collection.events:
        assert ev.event_id, f"KnowledgeEvent missing event_id: {ev}"
        assert ev.lesson_id, f"KnowledgeEvent {ev.event_id} missing lesson_id"
        assert (ev.metadata or {}).get("chunk_index") is not None, (
            f"KnowledgeEvent {ev.event_id} missing metadata.chunk_index"
        )
        assert ev.timestamp_start, f"KnowledgeEvent {ev.event_id} missing timestamp_start"
        assert ev.timestamp_end, f"KnowledgeEvent {ev.event_id} missing timestamp_end"
        assert ev.normalized_text, f"KnowledgeEvent {ev.event_id} missing normalized_text"
```

Do **not** add a test requiring `KnowledgeEvent.source_event_ids`.

---

## 5) `tests/test_pipeline_cross_artifact_refs.py`

Add a clarifying comment and optionally a focused contract test.

### Why

Cross-artifact provenance is already correct at:

* evidence → knowledge events
* rules → knowledge events

That is the important graph.

Add a short comment or test making clear that the reverse is not required.

### Optional test to add

```python
# tests/test_pipeline_cross_artifact_refs.py

def test_knowledge_event_source_event_ids_are_not_required_for_cross_artifact_integrity() -> None:
    knowledge_events = KnowledgeEventCollection(
        schema_version="1.0",
        lesson_id="test",
        events=[
            KnowledgeEvent(
                event_id="e1",
                lesson_id="test",
                event_type="rule_statement",
                raw_text="A rule.",
                normalized_text="A rule.",
                source_event_ids=[],
                metadata={"chunk_index": 0},
                timestamp_start="00:01",
                timestamp_end="00:05",
            ),
        ],
    )
    evidence_index = EvidenceIndex(
        schema_version="1.0",
        lesson_id="test",
        evidence_refs=[
            EvidenceRef(
                evidence_id="ev1",
                lesson_id="test",
                source_event_ids=["e1"],
                linked_rule_ids=["r1"],
                frame_ids=["f1"],
            ),
        ],
    )
    rule_cards = RuleCardCollection(
        schema_version="1.0",
        lesson_id="test",
        rules=[
            RuleCard(
                rule_id="r1",
                lesson_id="test",
                concept="level",
                rule_text="Valid rule.",
                source_event_ids=["e1"],
                evidence_refs=["ev1"],
            ),
        ],
    )

    errors = validate_cross_artifact_references(
        knowledge_events, evidence_index, rule_cards
    )
    assert errors == []
```

This locks the real contract:

* events can be roots
* evidence/rules point **to** them

---

## 6) `tests/fixtures/.../knowledge_events.json`

No runtime code change is needed, but ensure the fixture shape stays consistent:

* `source_event_ids: []` is fine
* events should still have:

  * `event_id`
  * `lesson_id`
  * `metadata.chunk_index`
  * timestamps
  * `normalized_text`

No fake lineage IDs.

---

## 7) Optional: `pipeline/contracts.py`

Only do this if you want the contract made visible in one central policy place.

If you already use validation policy flags, add:

```python
# pipeline/contracts.py

@dataclass(frozen=True)
class ValidationPolicy:
    require_rule_source_event_ids: bool = True
    require_knowledge_event_source_event_ids: bool = False
```

And in the strict final export policy:

```python
STRICT_FINAL_EXPORT_POLICY = ValidationPolicy(
    require_rule_source_event_ids=True,
    require_knowledge_event_source_event_ids=False,
)
```

Only do this if the file is actually used in your validation flow.
If it is still mostly dead code, skip this step.

---

# What not to do

Do **not** implement any of these:

* self-populating `source_event_ids=[event.event_id]`
* synthetic IDs like `chunk_0_line_12`
* fake “anchor ids” not actually grounded in extraction output
* making `KnowledgeEvent.source_event_ids` required
* broad provenance rewrites in `evidence_linker.py`, `ml_prep.py`, or `main.py`

Those would either be fake lineage or unnecessary scope growth.

---

# Expected result after this patch

After the patch:

* final artifacts remain unchanged in substance
* tests/documentation now align with actual pipeline semantics
* `KnowledgeEvent.source_event_ids=[]` is explicitly treated as valid Phase 1 behavior
* provenance expectations remain strict where they matter:

  * `RuleCard.source_event_ids` must be non-empty
  * `EvidenceRef.source_event_ids` must be non-empty
  * evidence/rule refs must resolve to existing knowledge-event ids

---

# Definition of done

This task is done when all are true:

1. `validate_knowledge_event_for_export()` still allows empty `source_event_ids`
2. there is a test proving valid knowledge events can export with empty `source_event_ids`
3. there is an invariant test for real Phase 1 event provenance fields
4. no test in the suite treats empty `KnowledgeEvent.source_event_ids` as a failure
5. no fake lineage ids are introduced

---

# Suggested commit message

```text
Clarify KnowledgeEvent provenance contract for Phase 1

- document KnowledgeEvent.source_event_ids as optional
- keep final event export validation focused on real Phase 1 provenance
- add tests proving valid events may export with empty source_event_ids
- lock cross-artifact integrity on evidence/rule refs to knowledge event ids
`