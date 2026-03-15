Below is an **agent-ready implementation brief** for the next pass.

---

# Agent task: finish Phase 1 export integrity for `knowledge_events.json` and `evidence_index.json`

## Goal

The final rule export gate is already much better.
The remaining Phase 1 blocker is that:

* `knowledge_events.json` is saved before evidence linkage is reflected
* `evidence_index.json` is saved before rule linkage is reflected
* weak evidence rows are still allowed into final export

You need to make final `knowledge_events.json` and final `evidence_index.json` as strict as final `rule_cards.json`.

## Target outcome

After this change, a rerun of **Lesson 2. Levels part 1** must satisfy:

* `rule_cards.json` remains clean
* `knowledge_events.json` has populated `evidence_refs` where evidence was linked
* `evidence_index.json` has populated `linked_rule_ids`
* weak evidence rows do **not** appear in final `evidence_index.json`
* weak evidence rows go only to `evidence_debug.json`

Do **not** broaden scope into timestamp precision or canonicalization. This task is only about final export integrity and backlink propagation.

---

# Files to edit

## 1) `pipeline/schemas.py`

Add strict export validators for:

* `KnowledgeEvent`
* `KnowledgeEventCollection`
* `EvidenceRef`
* `EvidenceIndex`

You already have:

* `validate_rule_card_for_export()`
* `validate_rule_card_collection_for_export()`

Follow the same pattern.

## Required additions

### A. `validate_knowledge_event_for_export(event: KnowledgeEvent) -> list[str]`

Strict export validation for final `knowledge_events.json`.

Reject when:

* `event_id` empty
* `lesson_id` empty
* `normalized_text` placeholder / empty
* `raw_text` placeholder / empty
* `metadata.chunk_index` missing

Do **not** require `source_event_ids` here.
For knowledge events, that field is not the right Phase 1 blocker.

### B. `validate_knowledge_event_collection_for_export(collection: KnowledgeEventCollection) -> tuple[KnowledgeEventCollection, list[dict]]`

Filter invalid events from final export and return debug rows.

### C. `validate_evidence_ref_for_export(evidence: EvidenceRef) -> list[str]`

Strict final validation for `evidence_index.json`.

Reject when:

* `lesson_id` empty
* both `frame_ids` and `raw_visual_event_ids` empty
* `source_event_ids` empty
* `linked_rule_ids` empty
* `compact_visual_summary` exceeds max policy

### D. `validate_evidence_index_for_export(index: EvidenceIndex) -> tuple[EvidenceIndex, list[dict]]`

Filter weak evidence rows from final export and return debug rows.

## Suggested code

```python
# pipeline/schemas.py

def validate_knowledge_event_for_export(event: KnowledgeEvent) -> List[str]:
    errors = list(validate_knowledge_event(event))

    metadata = getattr(event, "metadata", {}) or {}
    if metadata.get("chunk_index") is None:
        errors.append("metadata.chunk_index must not be empty for final export")

    return dedupe_preserve_order(errors)


def validate_knowledge_event_collection_for_export(
    collection: KnowledgeEventCollection,
) -> tuple[KnowledgeEventCollection, List[dict]]:
    valid_events: List[KnowledgeEvent] = []
    debug_rows: List[dict] = []

    for event in collection.events:
        errors = validate_knowledge_event_for_export(event)
        if errors:
            debug_rows.append({
                "stage": "export_validation",
                "entity_type": "knowledge_event",
                "entity_id": event.event_id,
                "event_id": event.event_id,
                "reason_rejected": errors,
                "source_event_ids": list(event.source_event_ids or []),
                "concept": event.concept,
                "subconcept": event.subconcept,
            })
            continue
        valid_events.append(event)

    return (
        KnowledgeEventCollection(
            schema_version=collection.schema_version,
            lesson_id=collection.lesson_id,
            lesson_title=collection.lesson_title,
            events=valid_events,
        ),
        debug_rows,
    )


def validate_evidence_ref_for_export(evidence: EvidenceRef) -> List[str]:
    errors = list(validate_evidence_ref(evidence, allow_unlinked_rules=False))

    if not (evidence.source_event_ids or []):
        errors.append("source_event_ids empty (not allowed in final artifact)")

    return dedupe_preserve_order(errors)


def validate_evidence_index_for_export(
    index: EvidenceIndex,
) -> tuple[EvidenceIndex, List[dict]]:
    valid_refs: List[EvidenceRef] = []
    debug_rows: List[dict] = []

    for ref in index.evidence_refs:
        errors = validate_evidence_ref_for_export(ref)
        if errors:
            debug_rows.append({
                "stage": "export_validation",
                "entity_type": "evidence_ref",
                "entity_id": ref.evidence_id,
                "evidence_id": ref.evidence_id,
                "reason_rejected": errors,
                "source_event_ids": list(ref.source_event_ids or []),
                "linked_rule_ids": list(ref.linked_rule_ids or []),
                "frame_ids": list(ref.frame_ids or []),
                "raw_visual_event_ids": list(ref.raw_visual_event_ids or []),
            })
            continue
        valid_refs.append(ref)

    return (
        EvidenceIndex(
            schema_version=index.schema_version,
            lesson_id=index.lesson_id,
            lesson_title=index.lesson_title,
            evidence_refs=valid_refs,
            metadata=index.metadata,
        ),
        debug_rows,
    )
```

---

## 2) `pipeline/component2/evidence_linker.py`

Add two missing backlink propagation helpers.

Right now:

* `KnowledgeEvent.evidence_refs` never gets backfilled
* `EvidenceRef.linked_rule_ids` never gets backfilled

That is the main structural gap.

## Required additions

### A. `backfill_knowledge_event_evidence_refs(...)`

Build:

* `event_id -> [evidence_id]`

from:

* `EvidenceRef.source_event_ids`

Then rewrite `knowledge_collection.events[*].evidence_refs`.

### B. `backfill_evidence_linked_rule_ids(...)`

Build:

* `evidence_id -> [rule_id]`

from:

* `RuleCard.evidence_refs`

Then rewrite `evidence_index.evidence_refs[*].linked_rule_ids`.

### C. tighten `infer_example_role(...)`

Current behavior:

```python
if not linked_events or all(t == "example" for t in event_types):
    return "ambiguous_example"
```

That is still too loose for generic intro/setup visuals.

Change it so that:

* generic / unlinked visuals default to `illustration`
* only truly mixed/unclear cases become `ambiguous_example`

## Suggested code

```python
# pipeline/component2/evidence_linker.py

from pipeline.schemas import (
    EvidenceIndex,
    KnowledgeEventCollection,
    validate_evidence_ref,
)
# also import RuleCardCollection if needed only for typing


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def backfill_knowledge_event_evidence_refs(
    knowledge_collection: KnowledgeEventCollection,
    evidence_index: EvidenceIndex,
) -> KnowledgeEventCollection:
    event_to_evidence: dict[str, list[str]] = {}

    for ref in evidence_index.evidence_refs:
        for event_id in ref.source_event_ids or []:
            event_to_evidence.setdefault(event_id, []).append(ref.evidence_id)

    updated_events: list[KnowledgeEvent] = []
    for event in knowledge_collection.events:
        existing = list(event.evidence_refs or [])
        incoming = event_to_evidence.get(event.event_id, [])
        updated_events.append(
            event.model_copy(
                update={
                    "evidence_refs": _dedupe_preserve_order(existing + incoming),
                }
            )
        )

    return knowledge_collection.model_copy(update={"events": updated_events})


def backfill_evidence_linked_rule_ids(
    evidence_index: EvidenceIndex,
    rule_cards,
) -> EvidenceIndex:
    evidence_to_rules: dict[str, list[str]] = {}

    for rule in rule_cards.rules:
        for evidence_id in rule.evidence_refs or []:
            evidence_to_rules.setdefault(evidence_id, []).append(rule.rule_id)

    updated_refs: list[EvidenceRef] = []
    for ref in evidence_index.evidence_refs:
        existing = list(ref.linked_rule_ids or [])
        incoming = evidence_to_rules.get(ref.evidence_id, [])
        updated_refs.append(
            ref.model_copy(
                update={
                    "linked_rule_ids": _dedupe_preserve_order(existing + incoming),
                }
            )
        )

    return evidence_index.model_copy(update={"evidence_refs": updated_refs})
```

## Exact `infer_example_role()` change

Replace the bottom of the function with this logic:

```python
def infer_example_role(
    candidate: VisualEvidenceCandidate,
    linked_events: list[KnowledgeEvent],
) -> str:
    content_lower = (
        (
            (candidate.compact_visual_summary or "")
            + " "
            + " ".join(candidate.concept_hints)
            + " "
            + " ".join(e.change_summary or "" for e in candidate.visual_events)
        )
        .lower()
        .strip()
    )

    event_types = [e.event_type for e in linked_events]

    if any(t in event_types for t in ("invalidation", "exception", "warning")):
        return "counterexample"

    if any(x in content_lower for x in ["failure", "trap", "mistake", "invalid", "counterexample"]):
        return "counterexample"

    if any(t in event_types for t in ("rule_statement", "condition")):
        return "positive_example"

    if any(t in event_types for t in ("definition", "comparison")):
        return "illustration"

    # More conservative fallback:
    if not linked_events:
        return "illustration"

    if all(t == "example" for t in event_types):
        return "ambiguous_example"

    return "illustration"
```

That preserves the false-breakout fix while reducing junk ambiguous rows.

---

## 3) `pipeline/component2/main.py`

This is the most important orchestration edit.

Right now:

* `knowledge_events.json` is saved too early
* `evidence_index.json` is saved too early
* neither artifact gets a final strict export pass like rules do

You need to add final export validation and overwrite those artifacts after backlink propagation.

## Imports to add

At top of file:

```python
from pipeline.schemas import (
    RuleCardCollection,
    validate_rule_card_collection_for_export,
    validate_knowledge_event_collection_for_export,
    validate_evidence_index_for_export,
)

from pipeline.component2.evidence_linker import (
    build_evidence_index,
    load_knowledge_events,
    save_evidence_debug,
    save_evidence_index,
    backfill_knowledge_event_evidence_refs,
    backfill_evidence_linked_rule_ids,
)
```

## A. Keep the early knowledge save, but overwrite later

Do not spend time refactoring the whole pipeline flow.
Minimal safe patch:

* keep the existing first save after extraction
* after evidence is built, backfill and overwrite `knowledge_events.json` with final validated events

### Add after `build_evidence_index(...)` and before saving evidence

Current code:

```python
evidence_index, evidence_debug = build_evidence_index(...)
save_evidence_index(...)
save_evidence_debug(...)
```

Change to:

```python
evidence_index, evidence_debug = build_evidence_index(
    lesson_id=lesson_name,
    knowledge_events=knowledge_events_for_evidence,
    chunks=raw_chunks,
    dense_analysis=raw_analysis,
    video_root=paths.video_root,
    compaction_cfg=compaction_cfg,
)

# If knowledge_collection exists in memory, backfill event -> evidence_refs
if knowledge_collection is not None:
    knowledge_collection = backfill_knowledge_event_evidence_refs(
        knowledge_collection,
        evidence_index,
    )

    validated_knowledge_collection, knowledge_export_rejects = (
        validate_knowledge_event_collection_for_export(knowledge_collection)
    )

    existing_knowledge_debug: list[dict] = []
    if paths.knowledge_debug_path(lesson_name).exists():
        existing_knowledge_debug = json.loads(
            paths.knowledge_debug_path(lesson_name).read_text(encoding="utf-8")
        )

    combined_knowledge_debug = [*existing_knowledge_debug]
    if knowledge_export_rejects:
        combined_knowledge_debug.append({
            "stage": "export_validation",
            "entity_type": "knowledge_event_collection",
            "rejected_events": knowledge_export_rejects,
        })

    knowledge_collection = validated_knowledge_collection
    save_knowledge_events(
        knowledge_collection,
        paths.knowledge_events_path(lesson_name),
    )
    save_knowledge_debug(
        combined_knowledge_debug,
        paths.knowledge_debug_path(lesson_name),
    )

# still save preliminary evidence_debug for now; final overwrite comes later
save_evidence_index(evidence_index, paths.evidence_index_path(lesson_name))
save_evidence_debug(evidence_debug, paths.evidence_debug_path(lesson_name))
```

## B. After final rules are accepted, backfill evidence -> linked_rule_ids and re-save evidence

After the final filtered `rule_cards` are built in the `enable_rule_cards` block, and **before** the final `_emit(...)`, add:

```python
if evidence_index is not None:
    evidence_index = backfill_evidence_linked_rule_ids(evidence_index, rule_cards)

    validated_evidence_index, evidence_export_rejects = validate_evidence_index_for_export(
        evidence_index
    )

    existing_evidence_debug: list[dict] = []
    if paths.evidence_debug_path(lesson_name).exists():
        existing_evidence_debug = json.loads(
            paths.evidence_debug_path(lesson_name).read_text(encoding="utf-8")
        )

    combined_evidence_debug = [*existing_evidence_debug, *evidence_export_rejects]

    evidence_index = validated_evidence_index
    save_evidence_index(evidence_index, paths.evidence_index_path(lesson_name))
    save_evidence_debug(combined_evidence_debug, paths.evidence_debug_path(lesson_name))
```

This is the core Phase 1 fix for `evidence_index.json`.

## C. After ML enrichment rewrites final rule cards, re-backfill evidence again

This matters because `main.py` overwrites `rule_cards.json` again after ML enrichment.

Inside `enable_ml_prep`, after:

```python
save_rule_cards(enriched_rule_cards, ...)
save_rule_debug(combined_rule_debug, ...)
rule_cards = enriched_rule_cards
```

add:

```python
evidence_index = backfill_evidence_linked_rule_ids(evidence_index, rule_cards)

validated_evidence_index, evidence_export_rejects = validate_evidence_index_for_export(
    evidence_index
)

existing_evidence_debug: list[dict] = []
if paths.evidence_debug_path(lesson_name).exists():
    existing_evidence_debug = json.loads(
        paths.evidence_debug_path(lesson_name).read_text(encoding="utf-8")
    )

combined_evidence_debug = [*existing_evidence_debug, *evidence_export_rejects]

evidence_index = validated_evidence_index
save_evidence_index(evidence_index, paths.evidence_index_path(lesson_name))
save_evidence_debug(combined_evidence_debug, paths.evidence_debug_path(lesson_name))
```

That ensures final evidence backlinks reflect final accepted rules, not pre-ML/pre-filter rules.

---

## 4) `pipeline/component2/provenance.py`

You do **not** need a major rewrite here.

Keep rule provenance logic as is.

Optional small addition only:
add hard final validators for evidence / knowledge if you want symmetry, but this is not necessary for this pass because strict export validators in `schemas.py` are enough.

So for this task:

* leave provenance mostly unchanged

---

## 5) `pipeline/component2/knowledge_builder.py`

Do **not** try to solve timestamp precision here.

That is not a Phase 1 task.

Only keep current behavior:

* chunk-level timestamps are acceptable for now
* final knowledge export must reject placeholder text, not broad time windows

No major changes required here.

---

## 6) Tests

Add these tests.

---

### A. `tests/test_evidence_linker.py`

Add:

```python
from pipeline.component2.evidence_linker import (
    backfill_knowledge_event_evidence_refs,
    backfill_evidence_linked_rule_ids,
)
from pipeline.schemas import (
    EvidenceIndex,
    EvidenceRef,
    KnowledgeEvent,
    KnowledgeEventCollection,
    RuleCard,
    RuleCardCollection,
)
```

### Test 1: event gets evidence backfilled

```python
def test_backfill_knowledge_event_evidence_refs_populates_events() -> None:
    event1 = KnowledgeEvent(
        lesson_id="lesson1",
        event_id="ke1",
        event_type="rule_statement",
        raw_text="A rule.",
        normalized_text="A rule.",
        metadata={"chunk_index": 0},
    )
    event2 = KnowledgeEvent(
        lesson_id="lesson1",
        event_id="ke2",
        event_type="definition",
        raw_text="A definition.",
        normalized_text="A definition.",
        metadata={"chunk_index": 0},
    )

    knowledge = KnowledgeEventCollection(
        lesson_id="lesson1",
        events=[event1, event2],
    )

    evidence = EvidenceIndex(
        lesson_id="lesson1",
        evidence_refs=[
            EvidenceRef(
                lesson_id="lesson1",
                evidence_id="ev1",
                frame_ids=["001"],
                source_event_ids=["ke1", "ke2"],
            )
        ],
    )

    result = backfill_knowledge_event_evidence_refs(knowledge, evidence)
    by_id = {e.event_id: e for e in result.events}

    assert by_id["ke1"].evidence_refs == ["ev1"]
    assert by_id["ke2"].evidence_refs == ["ev1"]
```

### Test 2: evidence gets rule backlinks backfilled

```python
def test_backfill_evidence_linked_rule_ids_populates_evidence() -> None:
    evidence = EvidenceIndex(
        lesson_id="lesson1",
        evidence_refs=[
            EvidenceRef(
                lesson_id="lesson1",
                evidence_id="ev1",
                frame_ids=["001"],
                source_event_ids=["ke1"],
            )
        ],
    )

    rules = RuleCardCollection(
        lesson_id="lesson1",
        rules=[
            RuleCard(
                lesson_id="lesson1",
                rule_id="r1",
                concept="level",
                rule_text="A valid rule.",
                source_event_ids=["ke1"],
                evidence_refs=["ev1"],
            )
        ],
    )

    result = backfill_evidence_linked_rule_ids(evidence, rules)
    assert result.evidence_refs[0].linked_rule_ids == ["r1"]
```

### Test 3: generic unlinked visual defaults to illustration

```python
def test_infer_example_role_unlinked_generic_defaults_to_illustration() -> None:
    candidate = VisualEvidenceCandidate(
        candidate_id="ev1",
        lesson_id="lesson1",
        chunk_index=0,
        timestamp_start=0.0,
        timestamp_end=10.0,
        compact_visual_summary="Intro chart with highlighted level area.",
        concept_hints=["level"],
        visual_events=[],
    )
    role = infer_example_role(candidate, [])
    assert role == "illustration"
```

---

### B. `tests/test_phase1_export_validation.py`

Add imports:

```python
from pipeline.schemas import (
    EvidenceIndex,
    EvidenceRef,
    KnowledgeEvent,
    KnowledgeEventCollection,
    validate_knowledge_event_collection_for_export,
    validate_evidence_index_for_export,
)
```

### Test 4: final evidence export rejects empty source_event_ids

```python
def test_final_evidence_export_rejects_empty_source_event_ids() -> None:
    index = EvidenceIndex(
        lesson_id="lesson1",
        evidence_refs=[
            EvidenceRef(
                lesson_id="lesson1",
                evidence_id="ev1",
                frame_ids=["001"],
                linked_rule_ids=["r1"],
                source_event_ids=[],
            )
        ],
    )

    valid_index, debug_rows = validate_evidence_index_for_export(index)
    assert len(valid_index.evidence_refs) == 0
    assert len(debug_rows) == 1
    assert "source_event_ids" in " ".join(debug_rows[0]["reason_rejected"])
```

### Test 5: final evidence export rejects empty linked_rule_ids

```python
def test_final_evidence_export_rejects_empty_linked_rule_ids() -> None:
    index = EvidenceIndex(
        lesson_id="lesson1",
        evidence_refs=[
            EvidenceRef(
                lesson_id="lesson1",
                evidence_id="ev1",
                frame_ids=["001"],
                source_event_ids=["ke1"],
                linked_rule_ids=[],
            )
        ],
    )

    valid_index, debug_rows = validate_evidence_index_for_export(index)
    assert len(valid_index.evidence_refs) == 0
    assert len(debug_rows) == 1
    assert "linked_rule_ids" in " ".join(debug_rows[0]["reason_rejected"])
```

### Test 6: final knowledge export rejects placeholder text

```python
def test_final_knowledge_export_rejects_placeholder_event() -> None:
    bad_event = KnowledgeEvent.model_construct(
        lesson_id="lesson1",
        event_id="ke1",
        event_type="rule_statement",
        raw_text="No rule text extracted.",
        normalized_text="No rule text extracted.",
        metadata={"chunk_index": 0},
    )

    collection = KnowledgeEventCollection(
        lesson_id="lesson1",
        events=[bad_event],
    )

    valid_collection, debug_rows = validate_knowledge_event_collection_for_export(collection)
    assert len(valid_collection.events) == 0
    assert len(debug_rows) == 1
```

---

### C. `tests/test_component2_pipeline.py` or `tests/test_pipeline_integration.py`

Add one pipeline-style test for artifact rewrite order.

You do not need full live execution.
Use monkeypatches around:

* extraction result builder
* evidence builder
* rule builder

### Test 7: final saved knowledge events contain evidence_refs after evidence linking

High level:

* monkeypatch `build_knowledge_events_from_extraction_results()` to return one event with empty `evidence_refs`
* monkeypatch `build_evidence_index()` to return one evidence row pointing to that event
* run pipeline with `enable_knowledge_events=True`, `enable_evidence_linking=True`
* assert saved `knowledge_events.json` contains `evidence_refs=["ev1"]`

### Test 8: final saved evidence contains linked_rule_ids after rule build

High level:

* monkeypatch `build_rule_cards()` to return one valid rule with `evidence_refs=["ev1"]`
* run with `enable_rule_cards=True`
* assert saved `evidence_index.json` contains `linked_rule_ids=["r1"]`

Do not overcomplicate these tests; one happy-path pipeline rewrite test per artifact is enough.

---

# Notes for the agent

## Do not change

* timestamp extraction policy
* concept graph logic
* ML feature heuristics
* reducer grouping/canonicalization

## Do change

* final export validators for events/evidence
* backfill functions
* main save order / overwrite logic
* evidence debug quarantine
* 6–8 focused tests

---

# Definition of done

This task is done only if all are true on rerun:

* `rule_cards.json`: no placeholders, no empty `source_event_ids`
* `knowledge_events.json`: no placeholder text, and linked events have `evidence_refs`
* `evidence_index.json`: no rows with empty `source_event_ids` or empty `linked_rule_ids`
* weak evidence rows appear only in `evidence_debug.json`
* `ml_manifest.json` and `labeling_manifest.json` still remain clean

**Confidence: High — the remaining blocker is now clearly missing backlink propagation plus missing final export gates for knowledge/evidence.**
