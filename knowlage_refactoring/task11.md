Yes — here is the **full description for Task 11**.

I’m assuming Task 11 is the next item in the sequence we established:

**Task 11 — Preserve Provenance Everywhere**

**Confidence: High**

---

# Task 11 — Preserve Provenance Everywhere

## Goal

Make provenance a **first-class invariant** across the structured pipeline so that every important artifact can be traced back to its origin.

This task must ensure that:

* every `KnowledgeEvent` can be traced to its source lesson/chunk/time range
* every `EvidenceRef` can be traced to source frames / visual events / timestamps
* every `RuleCard` can be traced to the exact source events and evidence used to build it
* exported markdown can be audited back to structured artifacts
* provenance survives merging, splitting, normalization, and rendering

This task must **not** add noisy raw blobs everywhere.
It should preserve **compact, structured, useful provenance**.

---

# Why this task exists

By this point, the pipeline already produces multiple derived layers:

* raw visual analysis
* chunked transcript + visual sync
* `knowledge_events.json`
* `evidence_index.json`
* `rule_cards.json`
* `review_markdown.md`
* `rag_ready.md`

Without a strong provenance layer, you risk losing the ability to answer:

* Where exactly did this rule come from?
* Which lesson chunk produced it?
* Which visual evidence supports it?
* Did this rule come from explicit transcript language or from inferred examples?
* Which frames/screenshots should a human inspect to verify it?
* If the rule is wrong, what upstream extraction produced it?

For a serious trading research workflow, provenance is essential.

---

# Deliverables

Create:

* `pipeline/component2/provenance.py`
* `tests/test_provenance.py`

Update:

* `knowledge_builder.py`
* `evidence_linker.py`
* `rule_reducer.py`
* `exporters.py`
* optionally `contracts.py`

Do **not** add a new top-level CLI stage in `main.py`.
Task 11 should be a **shared provenance layer** used by the structured stages.

---

# Core design principles

## 1. Provenance must be preserved through every transformation

When the pipeline transforms:

* chunk data → `KnowledgeEvent`
* visual candidates → `EvidenceRef`
* events + evidence → `RuleCard`
* rule cards → markdown

the origin chain must remain recoverable.

## 2. Provenance must be structured, not ad hoc

Do not scatter one-off keys like:

* `origin_id`
* `source_ref`
* `source_info`
* `maybe_chunk`

Use a small, consistent set of fields and helper builders.

## 3. Preserve useful provenance, not raw blobs

Good provenance:

* lesson id
* chunk index
* timestamps
* source event ids
* evidence ids
* frame ids
* raw visual event ids

Bad provenance:

* full raw chunk JSON
* full raw visual events
* large transcript dumps
* copied dense-analysis blobs

## 4. Provenance must survive split and merge operations

If a rule card is built from 5 events and 2 evidence refs, all of those references must survive in the final rule.

## 5. Provenance should be easy to audit

A human or downstream script should be able to follow:

```text
RuleCard -> KnowledgeEvent IDs -> EvidenceRef IDs -> frame keys / timestamps
```

without guesswork.

---

# Scope

Task 11 should cover provenance for:

## A. `KnowledgeEvent`

Needs chunk / timing / local visual candidate provenance.

## B. `EvidenceRef`

Needs frame / time / raw visual event provenance.

## C. `RuleCard`

Needs source event ids and linked evidence ids.

## D. Exported markdown

Needs at least optional compact provenance for human QA, especially in review markdown.

---

# Functional requirements

## 1. Create `pipeline/component2/provenance.py`

This module will define shared provenance helpers and validators.

It should contain:

* provenance payload builders
* merge helpers
* normalization helpers
* validation functions
* optional markdown formatting helpers

---

## 2. Add provenance models or typed helper structures

You do **not** necessarily need to change the Task 2 schemas heavily, but you should define typed internal helpers for provenance handling.

Suggested lightweight dataclasses:

```python id="1"}
from dataclasses import dataclass, field


@dataclass(frozen=True)
class EventProvenance:
    lesson_id: str
    chunk_index: int | None
    chunk_start_time_seconds: float | None
    chunk_end_time_seconds: float | None
    transcript_line_count: int | None
    candidate_visual_frame_keys: list[str] = field(default_factory=list)
    candidate_visual_types: list[str] = field(default_factory=list)
    candidate_example_types: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class EvidenceProvenance:
    lesson_id: str
    timestamp_start: float | None
    timestamp_end: float | None
    frame_ids: list[str] = field(default_factory=list)
    screenshot_paths: list[str] = field(default_factory=list)
    raw_visual_event_ids: list[str] = field(default_factory=list)
    source_event_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RuleProvenance:
    lesson_id: str
    source_event_ids: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    source_sections: list[str] = field(default_factory=list)
    source_subsections: list[str] = field(default_factory=list)
    source_chunk_indexes: list[int] = field(default_factory=list)
```

### Notes

* These are helper structures, not necessarily direct stored schema objects
* the final stored schemas can still use compact fields already defined in Tasks 2–5

---

## 3. Standardize provenance field names

This is important.

The pipeline should consistently use these names:

### For `KnowledgeEvent`

* `lesson_id`
* `section`
* `subsection`
* `timestamp_start`
* `timestamp_end`
* `source_event_ids`
* `metadata.chunk_index`
* `metadata.chunk_start_time_seconds`
* `metadata.chunk_end_time_seconds`
* `metadata.transcript_line_count`
* `metadata.candidate_visual_frame_keys`
* `metadata.candidate_visual_types`
* `metadata.candidate_example_types`

### For `EvidenceRef`

* `lesson_id`
* `timestamp_start`
* `timestamp_end`
* `frame_ids`
* `screenshot_paths`
* `raw_visual_event_ids`
* `source_event_ids`

### For `RuleCard`

* `lesson_id`
* `source_event_ids`
* `evidence_refs`

Do not invent synonyms.

---

## 4. Add provenance builders for Step 3 (`KnowledgeEvent`)

Implement:

```python id="2"}
def build_knowledge_event_provenance(
    *,
    lesson_id: str,
    chunk_index: int | None,
    chunk_start_time_seconds: float | None,
    chunk_end_time_seconds: float | None,
    transcript_line_count: int | None,
    candidate_visual_frame_keys: list[str],
    candidate_visual_types: list[str],
    candidate_example_types: list[str],
) -> dict:
    ...
```

### Behavior

Return a compact metadata dict for insertion into `KnowledgeEvent.metadata`.

### Rules

* dedupe lists
* preserve order
* drop empty/null optional keys where possible
* do not include raw visual event blobs
* do not include raw transcript text

### Use in `knowledge_builder.py`

Every created `KnowledgeEvent` must use this helper rather than hand-building metadata.

---

## 5. Add provenance builders for Step 4 (`EvidenceRef`)

Implement:

```python id="3"}
def build_evidence_ref_provenance(
    *,
    lesson_id: str,
    timestamp_start: float | None,
    timestamp_end: float | None,
    frame_ids: list[str],
    screenshot_paths: list[str],
    raw_visual_event_ids: list[str],
    source_event_ids: list[str],
) -> dict:
    ...
```

### Behavior

Return normalized provenance pieces for `EvidenceRef`.

### Rules

* dedupe ids
* preserve order
* bound long lists if Task 8 already configured limits
* do not include raw dense-analysis content

### Use in `evidence_linker.py`

When building `EvidenceRef`, provenance fields must come from this helper or its lower-level building blocks.

---

## 6. Add provenance builders for Step 5 (`RuleCard`)

Implement:

```python id="4"}
def build_rule_card_provenance(
    *,
    lesson_id: str,
    source_events: list,
    linked_evidence: list,
) -> dict:
    ...
```

### Behavior

Return a compact provenance summary for a rule.

### Must include

* deduped `source_event_ids`
* deduped `evidence_refs`
* compact list of source sections
* compact list of source subsections
* compact list of source chunk indexes if available

### Use in `rule_reducer.py`

When building `RuleCard`, source event ids and evidence refs must come through this helper.

---

## 7. Add provenance merge helpers

This is critical because Task 5 merges and splits candidates.

Implement:

```python id="5"}
def dedupe_preserve_order(items: list[str | int]) -> list:
    ...

def merge_source_event_ids(*collections: list[str]) -> list[str]:
    ...

def merge_evidence_refs(*collections: list[str]) -> list[str]:
    ...

def merge_source_sections(events: list) -> list[str]:
    ...

def merge_source_subsections(events: list) -> list[str]:
    ...

def merge_source_chunk_indexes(events: list) -> list[int]:
    ...
```

### Rules

* dedupe
* preserve order
* ignore empty/null values
* keep stable output

These helpers should be used during candidate merging and splitting.

---

## 8. Add provenance validation

Implement:

```python id="6"}
def validate_knowledge_event_provenance(event) -> list[str]:
    ...

def validate_evidence_ref_provenance(evidence) -> list[str]:
    ...

def validate_rule_card_provenance(rule) -> list[str]:
    ...
```

### Behavior

Return a list of warnings/errors, not just a boolean.

### Validation examples

#### `KnowledgeEvent`

Warn if:

* missing `lesson_id`
* missing chunk index in metadata
* missing both timestamps and chunk timing
* has candidate visual types but no frame keys

#### `EvidenceRef`

Warn if:

* missing lesson id
* missing both timestamps
* missing both frame ids and raw visual event ids
* has screenshot paths but empty frame ids
* missing source event ids

#### `RuleCard`

Warn if:

* missing lesson id
* missing source event ids
* missing evidence refs where visual summary exists
* evidence refs present but empty list after trimming
* concept missing and source events span multiple sections

---

## 9. Add a provenance coverage checker

Implement:

```python id="7"}
def compute_provenance_coverage(
    *,
    knowledge_events: list,
    evidence_refs: list,
    rule_cards: list,
) -> dict:
    ...
```

### Output example

```json id="8"
{
  "knowledge_events_total": 120,
  "knowledge_events_with_chunk_index": 118,
  "knowledge_events_with_visual_candidates": 74,
  "evidence_refs_total": 28,
  "evidence_refs_with_frame_ids": 28,
  "evidence_refs_with_source_event_ids": 27,
  "rule_cards_total": 14,
  "rule_cards_with_source_event_ids": 14,
  "rule_cards_with_evidence_refs": 11
}
```

### Use

* in debug output
* in tests
* optionally in manifest

This is very useful for QA.

---

## 10. Integrate into Step 3 (`knowledge_builder.py`)

Every `KnowledgeEvent` must use provenance helpers.

### Required change

Replace ad hoc metadata construction with:

```python id="9"}
event.metadata = build_knowledge_event_provenance(
    lesson_id=lesson_id,
    chunk_index=chunk.chunk_index,
    chunk_start_time_seconds=chunk.start_time_seconds,
    chunk_end_time_seconds=chunk.end_time_seconds,
    transcript_line_count=len(chunk.transcript_lines),
    candidate_visual_frame_keys=chunk.candidate_visual_frame_keys,
    candidate_visual_types=chunk.candidate_visual_types,
    candidate_example_types=chunk.candidate_example_types,
)
```

### Optional

Write provenance validation warnings into `knowledge_debug.json`

---

## 11. Integrate into Step 4 (`evidence_linker.py`)

Every `EvidenceRef` must use provenance helpers.

### Required change

When converting candidate → `EvidenceRef`, use:

```python id="10"}
prov = build_evidence_ref_provenance(
    lesson_id=lesson_id,
    timestamp_start=candidate.timestamp_start,
    timestamp_end=candidate.timestamp_end,
    frame_ids=frame_ids,
    screenshot_paths=screenshot_paths,
    raw_visual_event_ids=raw_visual_event_ids,
    source_event_ids=linked_event_ids,
)
```

### Required behavior

* `source_event_ids` must be correct
* `frame_ids` and `raw_visual_event_ids` must survive
* screenshot paths stay optional but bounded

### Optional

Write provenance warnings into `evidence_debug.json`

---

## 12. Integrate into Step 5 (`rule_reducer.py`)

Every `RuleCard` must preserve upstream provenance.

### Required change

When converting `RuleCandidate` → `RuleCard`, use:

```python id="11"}
prov = build_rule_card_provenance(
    lesson_id=lesson_id,
    source_events=all_source_events,
    linked_evidence=linked_evidence,
)
```

Populate:

* `rule.source_event_ids = prov["source_event_ids"]`
* `rule.evidence_refs = prov["evidence_refs"]`

Optionally use metadata for:

* source sections
* source chunk indexes

### Important

This must happen **after** merge/split logic is final.

---

## 13. Add provenance-aware debug rows

Task 11 should improve debug artifacts.

### `knowledge_debug.json`

Each row may include:

* emitted event id
* provenance validation warnings

### `evidence_debug.json`

Each row may include:

* evidence id
* source event ids
* frame ids
* provenance validation warnings

### `rule_debug.json`

Each row may include:

* rule id
* source event ids
* evidence refs
* source chunk indexes
* provenance validation warnings

This makes debugging much easier.

---

## 14. Add optional provenance notes to review markdown

This is optional, but recommended.

In `review_markdown.md`, for each rule, you may include a compact provenance line like:

```markdown id="12"}
**Evidence refs:** evid_lesson2_3_0  
**Source events:** ke_lesson2_4_rule_statement_0, ke_lesson2_4_condition_0
```

### Recommendation

* include in **review markdown**
* do not include in **RAG markdown** by default

This matches the difference between QA output and retrieval output.

---

## 15. Do not overload final markdown with provenance

Task 11 is about preserving provenance, not turning markdown into a debug dump.

### Review markdown

May include compact provenance ids.

### RAG markdown

Should generally omit ids and raw provenance unless explicitly required.

---

## 16. Add config / debug toggle if useful

This is optional.

If you want, add to `config.py`:

* `include_provenance_in_review_markdown = True`
* `include_provenance_validation_in_debug = True`

But do **not** overcomplicate Task 11 with too many new flags.

---

## 17. Add one invariant rule

I would explicitly add this sentence to the task:

```text id="13"}
No RuleCard may be written without source_event_ids, and no EvidenceRef may be written without at least one of frame_ids or raw_visual_event_ids.
```

That is a very good provenance invariant.

---

# Suggested implementation skeleton

## `pipeline/component2/provenance.py`

```python id="14"}
from __future__ import annotations

from typing import Any


def dedupe_preserve_order(items):
    seen = set()
    result = []
    for item in items:
        if item in (None, "", []):
            continue
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def build_knowledge_event_provenance(
    *,
    lesson_id: str,
    chunk_index: int | None,
    chunk_start_time_seconds: float | None,
    chunk_end_time_seconds: float | None,
    transcript_line_count: int | None,
    candidate_visual_frame_keys: list[str],
    candidate_visual_types: list[str],
    candidate_example_types: list[str],
) -> dict:
    return {
        "chunk_index": chunk_index,
        "chunk_start_time_seconds": chunk_start_time_seconds,
        "chunk_end_time_seconds": chunk_end_time_seconds,
        "transcript_line_count": transcript_line_count,
        "candidate_visual_frame_keys": dedupe_preserve_order(candidate_visual_frame_keys),
        "candidate_visual_types": dedupe_preserve_order(candidate_visual_types),
        "candidate_example_types": dedupe_preserve_order(candidate_example_types),
    }
```

Then continue with evidence/rule builders and validators.

---

# Tests to implement

Create `tests/test_provenance.py`.

## Required tests

### 1. KnowledgeEvent provenance builder

Verify:

* correct keys
* deduped visual frame keys
* stable structure

### 2. EvidenceRef provenance builder

Verify:

* frame ids preserved
* raw visual ids preserved
* source event ids preserved

### 3. RuleCard provenance builder

Given multiple source events and evidence refs, verify:

* deduped source ids
* deduped evidence refs
* source chunk indexes collected

### 4. Validation warnings

Create intentionally bad objects and verify warnings are returned.

### 5. Coverage checker

Verify counts are correct for a small fixture set.

### 6. Merge stability

Given repeated ids in multiple source groups, merged output should stay deduped and ordered.

### 7. Review markdown provenance inclusion

If enabled, ensure review markdown includes compact provenance lines.

---

# Important implementation rules

## Do

* preserve provenance compactly and consistently
* keep builders/validators centralized
* make merge/split provenance deterministic
* include provenance in review/debug outputs where useful
* keep provenance ids stable

## Do not

* do not store raw blobs as provenance
* do not let stages invent their own provenance field names
* do not drop source event ids during merge/split
* do not overload RAG markdown with provenance detail
* do not make provenance optional for `RuleCard`

---

# Definition of done

Task 11 is complete when:

1. `pipeline/component2/provenance.py` exists
2. `KnowledgeEvent`, `EvidenceRef`, and `RuleCard` provenance is built via shared helpers
3. source event ids survive into `RuleCard`
4. frame/raw visual ids survive into `EvidenceRef`
5. provenance validation helpers exist
6. coverage can be measured
7. review/debug outputs can expose compact provenance where useful
8. no rule card is written without source event ids

---

# Copy-paste instruction for the coding agent

```text id="15"}
Implement Task 11 only: Preserve Provenance Everywhere.

Create:
- pipeline/component2/provenance.py
- tests/test_provenance.py

Update:
- knowledge_builder.py
- evidence_linker.py
- rule_reducer.py
- optionally exporters.py

Goal:
Ensure every structured artifact can be traced back to its source.

Requirements:
1. Add shared provenance helpers for:
   - KnowledgeEvent
   - EvidenceRef
   - RuleCard
2. Standardize provenance field names across the pipeline
3. Build compact provenance for KnowledgeEvent including:
   - lesson_id
   - chunk_index
   - chunk_start_time_seconds
   - chunk_end_time_seconds
   - transcript_line_count
   - candidate_visual_frame_keys
   - candidate_visual_types
   - candidate_example_types
4. Build compact provenance for EvidenceRef including:
   - lesson_id
   - timestamp_start
   - timestamp_end
   - frame_ids
   - screenshot_paths
   - raw_visual_event_ids
   - source_event_ids
5. Build compact provenance for RuleCard including:
   - lesson_id
   - source_event_ids
   - evidence_refs
   - optional source sections/subsections/chunk indexes
6. Add merge helpers for provenance dedupe and stability
7. Add provenance validation functions returning warning lists
8. Add a provenance coverage checker
9. Integrate provenance helpers into:
   - Step 3 knowledge_builder
   - Step 4 evidence_linker
   - Step 5 rule_reducer
10. Optionally show compact provenance in review markdown, but not in RAG markdown by default

Invariant:
- no RuleCard may be written without source_event_ids
- no EvidenceRef may be written without at least one of frame_ids or raw_visual_event_ids

Do not:
- store raw visual blobs as provenance
- invent stage-specific provenance field names
- drop provenance during rule merge/split
- overload final markdown with debug provenance
```

Yes — for **Task 11**, I would make it much more concrete.

**Confidence: High**

This is one of the tasks where exact helper behavior matters a lot. If provenance is implemented loosely, it becomes inconsistent very quickly.

Below is a **detailed implementation addendum** for Task 11, including function behavior and usable code.

---

# `pipeline/component2/provenance.py`

## 1. Core helpers

These should be the foundation for every provenance operation.

```python
from __future__ import annotations

from typing import Any, Iterable


def dedupe_preserve_order(items: Iterable[Any]) -> list[Any]:
    seen = set()
    result: list[Any] = []
    for item in items:
        if item in (None, "", [], {}):
            continue
        try:
            key = item
            if key in seen:
                continue
            seen.add(key)
        except TypeError:
            # fallback for unhashable values
            key = repr(item)
            if key in seen:
                continue
            seen.add(key)
        result.append(item)
    return result


def compact_nonempty_strs(items: Iterable[Any]) -> list[str]:
    out: list[str] = []
    for item in items:
        if item is None:
            continue
        text = str(item).strip()
        if text:
            out.append(text)
    return dedupe_preserve_order(out)


def compact_nonempty_ints(items: Iterable[Any]) -> list[int]:
    out: list[int] = []
    for item in items:
        if item is None or item == "":
            continue
        try:
            out.append(int(item))
        except (TypeError, ValueError):
            continue
    return dedupe_preserve_order(out)


def prune_none_values(payload: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in payload.items():
        if value is None:
            continue
        if isinstance(value, list) and not value:
            continue
        if isinstance(value, dict) and not value:
            continue
        result[key] = value
    return result
```

---

## 2. Knowledge-event provenance builder

This should be the only way `KnowledgeEvent.metadata` provenance is created.

```python
def build_knowledge_event_provenance(
    *,
    lesson_id: str,
    chunk_index: int | None,
    chunk_start_time_seconds: float | None,
    chunk_end_time_seconds: float | None,
    transcript_line_count: int | None,
    candidate_visual_frame_keys: list[str],
    candidate_visual_types: list[str],
    candidate_example_types: list[str],
) -> dict[str, Any]:
    payload = {
        "chunk_index": chunk_index,
        "chunk_start_time_seconds": chunk_start_time_seconds,
        "chunk_end_time_seconds": chunk_end_time_seconds,
        "transcript_line_count": transcript_line_count,
        "candidate_visual_frame_keys": compact_nonempty_strs(candidate_visual_frame_keys),
        "candidate_visual_types": compact_nonempty_strs(candidate_visual_types),
        "candidate_example_types": compact_nonempty_strs(candidate_example_types),
    }
    return prune_none_values(payload)
```

### Expected output shape

```json
{
  "chunk_index": 4,
  "chunk_start_time_seconds": 120.0,
  "chunk_end_time_seconds": 145.0,
  "transcript_line_count": 6,
  "candidate_visual_frame_keys": ["000120", "000122"],
  "candidate_visual_types": ["annotated_chart"],
  "candidate_example_types": ["false_breakout_example"]
}
```

---

## 3. Evidence provenance builder

This should normalize and bound evidence provenance.

```python
def build_evidence_ref_provenance(
    *,
    lesson_id: str,
    timestamp_start: float | None,
    timestamp_end: float | None,
    frame_ids: list[str],
    screenshot_paths: list[str],
    raw_visual_event_ids: list[str],
    source_event_ids: list[str],
) -> dict[str, Any]:
    payload = {
        "lesson_id": lesson_id,
        "timestamp_start": timestamp_start,
        "timestamp_end": timestamp_end,
        "frame_ids": compact_nonempty_strs(frame_ids),
        "screenshot_paths": compact_nonempty_strs(screenshot_paths),
        "raw_visual_event_ids": compact_nonempty_strs(raw_visual_event_ids),
        "source_event_ids": compact_nonempty_strs(source_event_ids),
    }
    return prune_none_values(payload)
```

### Important

This function should not include:

* raw visual event blobs
* `current_state`
* `previous_visual_state`
* dense-analysis JSON fragments

---

## 4. Rule-card provenance builder

This is the most important builder because it must survive merge/split logic.

```python
def merge_source_event_ids(*collections: list[str]) -> list[str]:
    merged: list[str] = []
    for collection in collections:
        merged.extend(collection or [])
    return compact_nonempty_strs(merged)


def merge_evidence_refs(*collections: list[str]) -> list[str]:
    merged: list[str] = []
    for collection in collections:
        merged.extend(collection or [])
    return compact_nonempty_strs(merged)


def merge_source_sections(events: list[Any]) -> list[str]:
    return compact_nonempty_strs(getattr(ev, "section", None) for ev in events)


def merge_source_subsections(events: list[Any]) -> list[str]:
    return compact_nonempty_strs(getattr(ev, "subsection", None) for ev in events)


def merge_source_chunk_indexes(events: list[Any]) -> list[int]:
    indexes: list[int] = []
    for ev in events:
        metadata = getattr(ev, "metadata", {}) or {}
        indexes.append(metadata.get("chunk_index"))
    return compact_nonempty_ints(indexes)


def build_rule_card_provenance(
    *,
    lesson_id: str,
    source_events: list[Any],
    linked_evidence: list[Any],
) -> dict[str, Any]:
    source_event_ids = merge_source_event_ids(
        [getattr(ev, "event_id", None) for ev in source_events]
    )
    evidence_refs = merge_evidence_refs(
        [getattr(ev, "evidence_id", None) for ev in linked_evidence]
    )

    payload = {
        "lesson_id": lesson_id,
        "source_event_ids": source_event_ids,
        "evidence_refs": evidence_refs,
        "source_sections": merge_source_sections(source_events),
        "source_subsections": merge_source_subsections(source_events),
        "source_chunk_indexes": merge_source_chunk_indexes(source_events),
    }
    return prune_none_values(payload)
```

### Expected output shape

```json
{
  "lesson_id": "lesson_2",
  "source_event_ids": [
    "ke_lesson2_4_rule_statement_0",
    "ke_lesson2_4_condition_0"
  ],
  "evidence_refs": ["evid_lesson2_3_0"],
  "source_sections": ["Level"],
  "source_subsections": ["level_rating"],
  "source_chunk_indexes": [4, 5]
}
```

---

## 5. Validation functions

These should return warnings, not throw immediately.

### `KnowledgeEvent`

```python
def validate_knowledge_event_provenance(event: Any) -> list[str]:
    warnings: list[str] = []

    if not getattr(event, "lesson_id", None):
        warnings.append("missing lesson_id")

    metadata = getattr(event, "metadata", {}) or {}

    if metadata.get("chunk_index") is None:
        warnings.append("missing metadata.chunk_index")

    if getattr(event, "timestamp_start", None) is None and metadata.get("chunk_start_time_seconds") is None:
        warnings.append("missing both event timestamp_start and metadata.chunk_start_time_seconds")

    if getattr(event, "timestamp_end", None) is None and metadata.get("chunk_end_time_seconds") is None:
        warnings.append("missing both event timestamp_end and metadata.chunk_end_time_seconds")

    frame_keys = metadata.get("candidate_visual_frame_keys", []) or []
    visual_types = metadata.get("candidate_visual_types", []) or []

    if visual_types and not frame_keys:
        warnings.append("visual types present but candidate_visual_frame_keys missing")

    return warnings
```

### `EvidenceRef`

```python
def validate_evidence_ref_provenance(evidence: Any) -> list[str]:
    warnings: list[str] = []

    if not getattr(evidence, "lesson_id", None):
        warnings.append("missing lesson_id")

    if getattr(evidence, "timestamp_start", None) is None and getattr(evidence, "timestamp_end", None) is None:
        warnings.append("missing both timestamp_start and timestamp_end")

    frame_ids = getattr(evidence, "frame_ids", []) or []
    raw_ids = getattr(evidence, "raw_visual_event_ids", []) or []

    if not frame_ids and not raw_ids:
        warnings.append("missing both frame_ids and raw_visual_event_ids")

    screenshot_paths = getattr(evidence, "screenshot_paths", []) or []
    if screenshot_paths and not frame_ids:
        warnings.append("screenshot_paths present but frame_ids missing")

    if not (getattr(evidence, "source_event_ids", []) or []):
        warnings.append("missing source_event_ids")

    return warnings
```

### `RuleCard`

```python
def validate_rule_card_provenance(rule: Any) -> list[str]:
    warnings: list[str] = []

    if not getattr(rule, "lesson_id", None):
        warnings.append("missing lesson_id")

    source_event_ids = getattr(rule, "source_event_ids", []) or []
    evidence_refs = getattr(rule, "evidence_refs", []) or []

    if not source_event_ids:
        warnings.append("missing source_event_ids")

    if getattr(rule, "visual_summary", None) and not evidence_refs:
        warnings.append("visual_summary present but evidence_refs missing")

    if not getattr(rule, "concept", None):
        warnings.append("missing concept")

    return warnings
```

---

## 6. Coverage checker

This is very useful for QA and manifests.

```python
def compute_provenance_coverage(
    *,
    knowledge_events: list[Any],
    evidence_refs: list[Any],
    rule_cards: list[Any],
) -> dict[str, int]:
    return {
        "knowledge_events_total": len(knowledge_events),
        "knowledge_events_with_chunk_index": sum(
            1 for ev in knowledge_events
            if ((getattr(ev, "metadata", {}) or {}).get("chunk_index") is not None)
        ),
        "knowledge_events_with_visual_candidates": sum(
            1 for ev in knowledge_events
            if ((getattr(ev, "metadata", {}) or {}).get("candidate_visual_frame_keys") or [])
        ),
        "evidence_refs_total": len(evidence_refs),
        "evidence_refs_with_frame_ids": sum(
            1 for ev in evidence_refs if (getattr(ev, "frame_ids", []) or [])
        ),
        "evidence_refs_with_source_event_ids": sum(
            1 for ev in evidence_refs if (getattr(ev, "source_event_ids", []) or [])
        ),
        "rule_cards_total": len(rule_cards),
        "rule_cards_with_source_event_ids": sum(
            1 for rule in rule_cards if (getattr(rule, "source_event_ids", []) or [])
        ),
        "rule_cards_with_evidence_refs": sum(
            1 for rule in rule_cards if (getattr(rule, "evidence_refs", []) or [])
        ),
    }
```

---

# Integration by file

## `knowledge_builder.py`

Every `KnowledgeEvent` should get provenance from the builder, not handcrafted.

### Exact integration

```python
from pipeline.component2.provenance import (
    build_knowledge_event_provenance,
    validate_knowledge_event_provenance,
)

metadata = build_knowledge_event_provenance(
    lesson_id=lesson_id,
    chunk_index=chunk.chunk_index,
    chunk_start_time_seconds=chunk.start_time_seconds,
    chunk_end_time_seconds=chunk.end_time_seconds,
    transcript_line_count=len(chunk.transcript_lines),
    candidate_visual_frame_keys=chunk.candidate_visual_frame_keys,
    candidate_visual_types=chunk.candidate_visual_types,
    candidate_example_types=chunk.candidate_example_types,
)

event = KnowledgeEvent(
    event_id=event_id,
    lesson_id=lesson_id,
    lesson_title=lesson_title,
    section=chunk.section,
    subsection=chunk.subsection,
    timestamp_start=str(chunk.start_time_seconds),
    timestamp_end=str(chunk.end_time_seconds),
    event_type=event_type,
    raw_text=statement.text,
    normalized_text=statement.text,
    concept=concept,
    subconcept=subconcept,
    evidence_refs=[],
    confidence=label,
    confidence_score=score,
    ambiguity_notes=statement.ambiguity_notes,
    metadata=metadata,
)

prov_warnings = validate_knowledge_event_provenance(event)
```

### Recommendation

Put `prov_warnings` into `knowledge_debug.json`, not the final event.

---

## `evidence_linker.py`

### Exact integration

```python
from pipeline.component2.provenance import (
    build_evidence_ref_provenance,
    validate_evidence_ref_provenance,
)

prov = build_evidence_ref_provenance(
    lesson_id=lesson_id,
    timestamp_start=candidate.timestamp_start,
    timestamp_end=candidate.timestamp_end,
    frame_ids=prov_payload["frame_ids"],
    screenshot_paths=prov_payload["screenshot_paths"],
    raw_visual_event_ids=prov_payload["raw_visual_event_ids"],
    source_event_ids=[ev.event_id for ev in linked_events],
)

evidence_ref = EvidenceRef(
    evidence_id=evidence_id,
    lesson_id=lesson_id,
    timestamp_start=str(candidate.timestamp_start) if candidate.timestamp_start is not None else None,
    timestamp_end=str(candidate.timestamp_end) if candidate.timestamp_end is not None else None,
    frame_ids=prov["frame_ids"],
    screenshot_paths=prov["screenshot_paths"],
    visual_type=candidate.visual_type,
    example_role=example_role,
    compact_visual_summary=summary,
    linked_rule_ids=[],
    raw_visual_event_ids=prov["raw_visual_event_ids"],
    source_event_ids=prov["source_event_ids"],
    metadata={},
)

prov_warnings = validate_evidence_ref_provenance(evidence_ref)
```

---

## `rule_reducer.py`

### Exact integration

```python
from pipeline.component2.provenance import (
    build_rule_card_provenance,
    validate_rule_card_provenance,
)

prov = build_rule_card_provenance(
    lesson_id=lesson_id,
    source_events=all_source_events,
    linked_evidence=linked_evidence,
)

rule = RuleCard(
    rule_id=rule_id,
    lesson_id=lesson_id,
    concept=concept or "unknown",
    subconcept=subconcept,
    title=title,
    rule_text=rule_text,
    conditions=conditions,
    context=context,
    invalidation=invalidation,
    exceptions=exceptions,
    comparisons=comparisons,
    algorithm_notes=algorithm_notes,
    visual_summary=visual_summary,
    evidence_refs=prov.get("evidence_refs", []),
    source_event_ids=prov.get("source_event_ids", []),
    confidence=confidence_label,
    confidence_score=confidence_score,
    candidate_features=[],
    positive_example_refs=positive_example_refs,
    negative_example_refs=negative_example_refs,
    ambiguous_example_refs=ambiguous_example_refs,
    labeling_guidance=labeling_guidance,
    metadata={
        "source_sections": prov.get("source_sections", []),
        "source_subsections": prov.get("source_subsections", []),
        "source_chunk_indexes": prov.get("source_chunk_indexes", []),
    },
)

prov_warnings = validate_rule_card_provenance(rule)
```

### Important

Use provenance builder **after** final merge/split is done.

---

## `exporters.py`

I recommend compact provenance in review markdown only.

### Helper

```python
def format_compact_provenance(rule: Any) -> str | None:
    source_event_ids = getattr(rule, "source_event_ids", []) or []
    evidence_refs = getattr(rule, "evidence_refs", []) or []

    lines: list[str] = []

    if evidence_refs:
        lines.append(f"**Evidence refs:** {', '.join(evidence_refs[:3])}")

    if source_event_ids:
        lines.append(f"**Source events:** {', '.join(source_event_ids[:3])}")

    if not lines:
        return None

    return "\n".join(lines)
```

### Use in review markdown

After rule sections:

```python
prov_block = format_compact_provenance(rule)
if prov_block:
    parts.append(prov_block)
```

### Do not use in RAG markdown by default.

---

# Tests

## `tests/test_provenance.py`

### Test 1 — knowledge event provenance builder

```python
def test_build_knowledge_event_provenance():
    payload = build_knowledge_event_provenance(
        lesson_id="lesson1",
        chunk_index=4,
        chunk_start_time_seconds=10.0,
        chunk_end_time_seconds=20.0,
        transcript_line_count=3,
        candidate_visual_frame_keys=["001", "001", "002"],
        candidate_visual_types=["annotated_chart", "annotated_chart"],
        candidate_example_types=["false_breakout", ""],
    )

    assert payload["chunk_index"] == 4
    assert payload["candidate_visual_frame_keys"] == ["001", "002"]
    assert payload["candidate_visual_types"] == ["annotated_chart"]
    assert payload["candidate_example_types"] == ["false_breakout"]
```

### Test 2 — evidence provenance builder

```python
def test_build_evidence_ref_provenance():
    payload = build_evidence_ref_provenance(
        lesson_id="lesson1",
        timestamp_start=12.0,
        timestamp_end=18.0,
        frame_ids=["001", "002", "001"],
        screenshot_paths=["a.png", "a.png", "b.png"],
        raw_visual_event_ids=["ve_raw_001", "ve_raw_002"],
        source_event_ids=["ke_1", "ke_2", "ke_1"],
    )

    assert payload["frame_ids"] == ["001", "002"]
    assert payload["screenshot_paths"] == ["a.png", "b.png"]
    assert payload["source_event_ids"] == ["ke_1", "ke_2"]
```

### Test 3 — rule provenance builder

```python
def test_build_rule_card_provenance():
    class E:
        def __init__(self, event_id, section, subsection, chunk_index):
            self.event_id = event_id
            self.section = section
            self.subsection = subsection
            self.metadata = {"chunk_index": chunk_index}

    class V:
        def __init__(self, evidence_id):
            self.evidence_id = evidence_id

    events = [
        E("ke_1", "Level", "rating", 4),
        E("ke_2", "Level", "rating", 5),
    ]
    evidence = [V("evid_1"), V("evid_1"), V("evid_2")]

    payload = build_rule_card_provenance(
        lesson_id="lesson1",
        source_events=events,
        linked_evidence=evidence,
    )

    assert payload["source_event_ids"] == ["ke_1", "ke_2"]
    assert payload["evidence_refs"] == ["evid_1", "evid_2"]
    assert payload["source_sections"] == ["Level"]
    assert payload["source_subsections"] == ["rating"]
    assert payload["source_chunk_indexes"] == [4, 5]
```

### Test 4 — validation warnings

```python
def test_validate_rule_card_provenance_warns_on_missing_source_ids():
    class Rule:
        lesson_id = "lesson1"
        source_event_ids = []
        evidence_refs = []
        visual_summary = None
        concept = "level"

    warnings = validate_rule_card_provenance(Rule())
    assert "missing source_event_ids" in warnings
```

### Test 5 — coverage checker

```python
def test_compute_provenance_coverage():
    class Event:
        def __init__(self, chunk_index=None, frame_keys=None):
            self.metadata = {
                "chunk_index": chunk_index,
                "candidate_visual_frame_keys": frame_keys or [],
            }

    class Evidence:
        def __init__(self, frame_ids=None, source_event_ids=None):
            self.frame_ids = frame_ids or []
            self.source_event_ids = source_event_ids or []

    class Rule:
        def __init__(self, source_event_ids=None, evidence_refs=None):
            self.source_event_ids = source_event_ids or []
            self.evidence_refs = evidence_refs or []

    stats = compute_provenance_coverage(
        knowledge_events=[Event(1, ["001"]), Event(None, [])],
        evidence_refs=[Evidence(["001"], ["ke_1"]), Evidence([], [])],
        rule_cards=[Rule(["ke_1"], ["evid_1"]), Rule([], [])],
    )

    assert stats["knowledge_events_total"] == 2
    assert stats["knowledge_events_with_chunk_index"] == 1
    assert stats["evidence_refs_with_source_event_ids"] == 1
    assert stats["rule_cards_with_source_event_ids"] == 1
```

---

# One more thing I would explicitly add

I would add this sentence to Task 11:

```text
All provenance merges must be deterministic, deduplicated, and order-preserving; provenance should never depend on incidental iteration order or transient debug state.
```

That matters a lot for reproducibility.

---

# My recommendation

Yes — for Task 11, I would absolutely include these implementation details.

Because provenance is only useful if it is:

* consistent
* compact
* deterministic
* preserved through transformations

Without exact builders and validators, each stage will drift.




