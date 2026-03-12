Below is a **copy-paste instruction** for a GPT-5.4 coding agent.

It is written so the agent can work directly on your codebase and implement the redesign in a disciplined way.

---

# Instruction for GPT-5.4 Coding Agent

You are modifying an existing Python pipeline for extracting knowledge from trading video lessons.

## Mission

Redesign the pipeline so that:

1. The **first video analysis pass remains dense and information-rich**
2. We **do not need to rerun visual recognition later**
3. The pipeline produces a **rule-centric knowledge base**
4. Visuals are preserved as **linked evidence**, not as verbose final prose
5. The main machine artifact becomes **structured JSON**, while markdown becomes a **derived human-readable output**
6. The resulting data can later support:

   * RAG retrieval
   * algorithm design
   * ML labeling / training for chart pattern recognition

---

# High-level target architecture

## Current direction to change

The current pipeline appears to end with:

* intermediate markdown
* reducer
* final `rag_ready.md`

That is no longer the primary goal.

## New primary goal

The primary product must become:

* `knowledge_events.json`
* `rule_cards.json`
* `evidence_index.json`
* `concept_graph.json`

Markdown outputs such as:

* `review_markdown.md`
* `rag_ready.md`

must become **derived views generated from structured JSON**, not the core intelligence artifact.

---

# Core design principles

1. **Do not discard information early**

   * keep the dense first pass rich
   * preserve timestamps, frame ids, visual event types, and local context

2. **Do not rely on prose markdown as the source of truth**

   * markdown is for humans
   * structured JSON is for the system

3. **Do not treat visuals as first-class RAG content**

   * visuals are evidence supporting rules
   * keep screenshot/frame references and compact visual summaries

4. **Do not let the LLM invent the structure**

   * use deterministic parsing and anchoring where possible
   * use the LLM for constrained extraction and normalization only

5. **Every normalized rule must preserve provenance**

   * source lesson
   * timestamps
   * source event ids
   * linked visual evidence

---

# Required outputs

For each processed lesson, produce these primary artifacts:

## 1. `knowledge_events.json`

Atomic extracted knowledge statements before full merging.

## 2. `rule_cards.json`

Normalized rule objects for RAG and algorithm-building.

## 3. `evidence_index.json`

Links to supporting visuals, timestamps, screenshots, frame ids, and example role.

## 4. `concept_graph.json`

Relationships between concepts, sub-concepts, and rules.

Also produce these derived outputs:

## 5. `review_markdown.md`

Readable lesson notes for human QA.

## 6. `rag_ready.md`

A compact markdown version generated from rule cards, not from raw visual narration.

---

# Implementation tasks

## Task 1 — Inspect the existing pipeline and preserve backward compatibility where reasonable

Review the existing modules and locate:

* main pipeline orchestration
* invalidation filter
* parse and sync logic
* LLM processor
* markdown synthesis
* reducer
* chunking/export logic

Do not break the dense analysis generation stage.

Goal:

* keep existing entry points working if possible
* extend the pipeline cleanly instead of doing a destructive rewrite

---

## Task 2 — Define the canonical internal schema

Create Python dataclasses or Pydantic models for these core entities:

### A. `KnowledgeEvent`

Represents one atomic extracted statement.

Suggested fields:

* `event_id`
* `lesson_id`
* `section`
* `timestamp_start`
* `timestamp_end`
* `event_type`
  Examples: `definition`, `rule_statement`, `condition`, `invalidation`, `comparison`, `example`, `warning`, `process_step`
* `raw_text`
* `normalized_text`
* `concept`
* `subconcept`
* `source_event_ids`
* `evidence_refs`
* `confidence`

### B. `RuleCard`

Represents one normalized retrievable rule.

Suggested fields:

* `rule_id`
* `lesson_id`
* `concept`
* `subconcept`
* `title`
* `rule_text`
* `conditions`
* `context`
* `invalidation`
* `exceptions`
* `algorithm_notes`
* `visual_summary`
* `evidence_refs`
* `source_event_ids`
* `confidence`

### C. `EvidenceRef`

Represents linked visual evidence.

Suggested fields:

* `evidence_id`
* `lesson_id`
* `timestamp_start`
* `timestamp_end`
* `frame_ids`
* `screenshot_paths`
* `visual_type`
* `example_role`
  Examples: `positive_example`, `negative_example`, `counterexample`, `ambiguous_example`, `illustration`
* `linked_rule_ids`
* `compact_visual_summary`

### D. `ConceptNode` / `ConceptGraph`

Represents concept hierarchy and relations.

Suggested fields:

* `concept_id`
* `name`
* `type`
* `parent_id`
* `related_ids`
* `relations`

---

## Task 3 — Add a structured post-parse stage

Create a new module, for example:

```python
pipeline/component2/knowledge_builder.py
```

This module must run after the parser/sync stage and before markdown rendering.

### Input

* parsed lesson chunks
* synced transcript spans
* filtered visual events
* dense analysis metadata if available

### Output

* a list of `KnowledgeEvent`
* grouped candidate concepts
* raw evidence mapping

### Responsibilities

* extract atomic rule statements
* extract conditions / invalidations / exceptions
* detect definitions and key distinctions
* attach local section/concept anchors
* attach source timestamps and evidence ids

Important:

* this stage should be JSON-first
* do not output prose-first markdown here

---

## Task 4 — Add an evidence linker

Create:

```python
pipeline/component2/evidence_linker.py
```

### Responsibilities

* map filtered visual events to nearby knowledge events / rule candidates
* preserve:

  * timestamps
  * frame ids
  * screenshot references
  * visual type
* generate `EvidenceRef` objects
* assign example roles when possible:

  * positive example
  * counterexample
  * ambiguous example
  * illustration

### Important rules

* visuals must be stored as evidence, not verbose narrative
* generate only a **compact visual summary**
* do not allow long frame-by-frame descriptions into final rule cards

---

## Task 5 — Add rule normalization and merge logic

Create:

```python
pipeline/component2/rule_reducer.py
```

### Responsibilities

* merge duplicate or overlapping knowledge events into rule cards
* split overly broad rule cards into atomic rules
* preserve source provenance
* assign confidence

### Merging rules

Merge events only if they share:

* same concept/subconcept
* strong semantic overlap
* same teaching intent

Do not merge if they differ on:

* condition vs invalidation
* general rule vs exception
* positive example vs counterexample

### Output

* `rule_cards.json`

---

## Task 6 — Refactor the LLM processor into structured extraction mode

Modify the existing LLM processing logic so it supports two modes:

### Mode A — `knowledge_extract`

Input:

* synced transcript span
* relevant visual evidence
* local section title
* local concept context

Output:

* structured JSON only

Expected JSON sections:

* definitions
* rule_statements
* conditions
* invalidations
* exceptions
* comparisons
* examples
* algorithm_hints
* ambiguities

### Mode B — `markdown_render`

Input:

* normalized rule cards
* evidence refs

Output:

* readable markdown

Important:

* the LLM must not be asked to directly write the final lesson from scratch
* extraction and rendering must be separate steps

---

## Task 7 — Make markdown a derived projection

Create an exporter module, for example:

```python
pipeline/component2/exporters.py
```

This module must generate:

### A. `review_markdown.md`

For human review:

* section headers
* rule cards
* compact visual summaries
* source timestamps if useful

### B. `rag_ready.md`

For lightweight markdown-based retrieval:

* concise normalized rules
* conditions
* invalidations
* brief visual evidence only if helpful

### Critical rule

Both markdown files must be generated from `rule_cards.json` and `evidence_index.json`, not from raw dense visual narration.

---

## Task 8 — Keep visual extraction rich, but compress its downstream use

Do **not** reduce the richness of the first pass if it may be useful later.

Preserve from the first pass:

* timestamps
* frame ids
* visual event classifications
* screenshot candidates
* chart/object relations if available

But downstream:

* convert visuals into evidence refs
* keep only compact summaries in final structured outputs
* do not store frame-by-frame narration in rule cards or final RAG markdown

---

## Task 9 — Introduce file outputs and folder organization

For each lesson, write outputs in a predictable structure such as:

```text
output_intermediate/
  <lesson_name>.knowledge_events.json
  <lesson_name>.evidence_index.json
  <lesson_name>.concept_graph.json
  <lesson_name>.rule_cards.json

output_review/
  <lesson_name>.review_markdown.md

output_rag_ready/
  <lesson_name>.rag_ready.md
```

If the current project uses different folder names, adapt consistently, but preserve the same logical separation.

---

## Task 10 — Add confidence scoring

For both `KnowledgeEvent` and `RuleCard`, assign a confidence score.

Suggested heuristic inputs:

* transcript clarity
* repeated confirmation in nearby text
* clean concept anchor
* evidence support present
* ambiguity detected or not

Confidence can be:

* float 0.0–1.0
  or
* enum: `low`, `medium`, `high`

This is important for later rule review and ML labeling.

---

## Task 11 — Preserve provenance everywhere

Every rule card must preserve:

* source lesson id
* source section
* source event ids
* evidence refs
* timestamps where possible

The system must support traceability from:
`rule_card -> knowledge_event -> source chunk / evidence`

No normalized rule should become detached from its original lesson evidence.

---

## Task 12 — Add lightweight concept graph generation

Build a simple concept graph from extracted rules.

Example relations:

* `level` -> `level_recognition`
* `level_recognition` -> `level_rating`
* `level_rating` -> `false_breakout`
* `false_breakout` is related to `break_confirmation`

Keep this simple and useful. Do not over-engineer it.

Purpose:

* future synthesis across multiple lessons
* better retrieval
* later algorithm planning

---

## Task 13 — Prepare the data model for future ML

Without implementing the ML system now, make sure the schemas support future expansion.

Add optional fields to `RuleCard` or related schemas such as:

* `candidate_features`
* `positive_example_refs`
* `negative_example_refs`
* `ambiguous_example_refs`
* `labeling_guidance`

Do not populate aggressively unless the data clearly supports it, but leave the structure ready.

---

## Task 14 — Add regression tests and acceptance checks

Create tests for at least these cases:

### Test 1 — Structured extraction exists

Given one processed lesson, verify that:

* `knowledge_events.json` exists
* `rule_cards.json` exists
* `evidence_index.json` exists

### Test 2 — Rule cards preserve provenance

Every rule card must have:

* lesson id
* source event ids
* evidence refs or explicit empty list

### Test 3 — Markdown derived from rule cards

Verify that `rag_ready.md` is generated from normalized structures, not raw dense text.

### Test 4 — Visual spam does not leak

Check that repetitive frame-by-frame visual narration is absent from final `rag_ready.md`.

### Test 5 — Evidence remains accessible

A rule with linked visual evidence must preserve timestamp/frame/screenshot linkage.

---

## Task 15 — Keep implementation incremental

Do not attempt a full rewrite in one step.

Implement in this order:

### Phase 1

* add schemas
* add `knowledge_builder.py`
* add `evidence_linker.py`
* produce JSON artifacts

### Phase 2

* add `rule_reducer.py`
* generate `rule_cards.json`

### Phase 3

* generate markdown from rule cards

### Phase 4

* add confidence scoring, concept graph, and tests

This order matters.

---

# Important behavior rules for the agent

## Do

* prefer deterministic parsing where possible
* keep JSON schemas explicit
* keep functions small and testable
* preserve backward compatibility when not too costly
* document all new outputs and pipeline flow
* add logging for each new stage

## Do not

* do not make final markdown the source of truth
* do not delete useful dense first-pass information
* do not compress away timestamps/frame provenance
* do not produce large frame-by-frame visual text in the final outputs
* do not rely on one giant LLM prompt to do the whole job

---

# Expected final pipeline flow

Implement the pipeline so it conceptually becomes:

```text
1. Dense video analysis
2. Invalidation filter
3. Parse and sync transcript + visuals
4. Atomic knowledge extraction (JSON)
5. Evidence linking
6. Rule normalization / merge
7. Concept graph generation
8. Export:
   - knowledge_events.json
   - evidence_index.json
   - rule_cards.json
   - concept_graph.json
   - review_markdown.md
   - rag_ready.md
```

---

# Deliverables required from the agent

1. Updated code
2. New schema definitions
3. New modules:

   * `knowledge_builder.py`
   * `evidence_linker.py`
   * `rule_reducer.py`
   * `exporters.py`
     or equivalent naming if better aligned with the codebase
4. Updated orchestration
5. Tests
6. Short implementation notes in markdown:

   * what changed
   * new pipeline flow
   * output file descriptions
   * known limitations

---

# Final objective

The final system must be optimized for this downstream use case:

* extract once from video
* preserve maximum reusable intelligence
* build a structured trading knowledge base
* support rule retrieval now
* support algorithm design next
* support ML pattern labeling later

The implementation should be pragmatic, testable, and production-safe.


