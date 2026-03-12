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


