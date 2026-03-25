Step 4 — Evidence Linker

Implement Step 4 of the redesigned pipeline.

Goal

Add a deterministic-first evidence linking stage that runs after Step 3 knowledge extraction and produces:

output_intermediate/<lesson>.evidence_index.json

optionally output_intermediate/<lesson>.evidence_debug.json

This stage must map visual evidence to nearby KnowledgeEvents and prepare clean, provenance-preserving EvidenceRef objects for later use in:

rule normalization

RAG

human review

future ML labeling

This stage must not yet merge final rules and must not replace the current markdown pipeline.

Why this stage exists

Step 3 extracts atomic knowledge from synced chunks. Step 4 must then connect those knowledge statements to the actual visual evidence that supports them.

The architecture goal is clear:

visuals are evidence

not the primary knowledge object

provenance must be preserved

timestamps and frame references must survive

long frame-by-frame narrative must not leak downstream 

Response: Visual Decoding Review

 

Response: Visual Decoding Review

Inputs

Step 4 must consume:

Required

output_intermediate/<lesson>.knowledge_events.json

output_intermediate/<lesson>.chunks.json

Strongly recommended

dense_analysis.json

Optional

filtered_visual_events.json if separate loading is easier than using chunk-contained visual events

The current pipeline already produces filtered visual events and synchronized chunks before the markdown phase. 

pipeline

 

pipeline

Outputs

Write:

output_intermediate/<lesson>.evidence_index.json

optional output_intermediate/<lesson>.evidence_debug.json

This matches the intended primary structured outputs for the redesign. 

Response: Visual Decoding Review

Deliverables

Create:

pipeline/component2/evidence_linker.py

tests/test_evidence_linker.py

Update:

pipeline/component2/main.py

Use Task 2 schemas:

EvidenceRef

EvidenceIndex

KnowledgeEventCollection

Core design principles
1. Deterministic first

Do not use an LLM for first-pass evidence linking.

Use:

timestamps

chunk boundaries

frame keys

visual metadata

concept matching

simple heuristics

LLM use, if any, should only be a later optional refinement.

2. Preserve provenance

Every EvidenceRef must preserve:

lesson id

time range

frame keys

linked rule/event ids

visual type

example role

compact visual summary

3. Compact evidence, not narrative

Do not store long raw visual text in evidence output.

4. One visual can support multiple events

The design must allow many-to-many:

one visual event may support several KnowledgeEvents

one KnowledgeEvent may map to multiple visual events

Assumptions based on the real data shape

Use the real chunk structure already present in the project:

chunk_index

start_time_seconds

end_time_seconds

transcript_lines

visual_events

previous_visual_state 

The Invalidation Filter

The framework modules doc also confirms VisualEvent includes:

timestamp_seconds

frame_key

visual_representation_type

example_type

change_summary

current_state

extracted_entities 

FRAMEWORK_MODULES

Your uploaded sample dense_analysis.json also confirms that frame-level records carry rich metadata such as:

material_change

change_summary

visual_representation_type

example_type

current_state

extracted_entities

timing fields

request usage

So Step 4 should take advantage of that richness and not reduce it prematurely.

Functional requirements
1. Create pipeline/component2/evidence_linker.py

This module is responsible for:

loading knowledge events

loading chunks

optionally loading dense/frame-level analysis

building candidate visual evidence groups

linking those groups to KnowledgeEvents

writing EvidenceIndex

The architecture doc already names this module and role explicitly. 

Response: Visual Decoding Review

2. Add a concrete visual candidate adapter

Create internal adapter models for the evidence linker.

Suggested internal dataclasses:

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class AdaptedVisualEvent:
    timestamp_seconds: float
    frame_key: str
    visual_representation_type: str
    example_type: str | None
    change_summary: str | None
    current_state: dict[str, Any]
    extracted_entities: dict[str, Any]
    chunk_index: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class VisualEvidenceCandidate:
    candidate_id: str
    lesson_id: str
    chunk_index: int | None
    timestamp_start: float
    timestamp_end: float
    frame_keys: list[str] = field(default_factory=list)
    visual_events: list[AdaptedVisualEvent] = field(default_factory=list)
    compact_visual_summary: str | None = None
    visual_type: str = "unknown"
    example_role: str = "unknown"
    concept_hints: list[str] = field(default_factory=list)
    subconcept_hints: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
Notes

VisualEvidenceCandidate is an internal grouping object, not the final schema

final output must be EvidenceRef

3. Load and adapt chunk visual events

Implement:

def load_chunks_json(path: Path) -> list[dict]:
    ...

def adapt_visual_events_from_chunks(
    raw_chunks: list[dict],
    lesson_id: str,
) -> list[AdaptedVisualEvent]:
    ...
Required behavior

For each chunk:

iterate visual_events

preserve chunk_index

preserve timestamp_seconds

preserve frame_key

preserve visual_representation_type

preserve example_type

preserve change_summary

preserve current_state

preserve extracted_entities

Important

Do not flatten away chunk context.

That chunk context is critical because Step 3 knowledge events are chunk-anchored.

4. Optionally enrich from dense_analysis.json

Implement:

def load_dense_analysis(path: Path) -> dict[str, dict]:
    ...

def enrich_visual_event_from_dense_analysis(
    event: AdaptedVisualEvent,
    dense_analysis: dict[str, dict],
) -> AdaptedVisualEvent:
    ...
Purpose

Chunk visual events already carry the core fields, but dense_analysis.json may contain:

more complete current state

more consistent timing info

extra frame metadata

Matching rule

Match by frame_key.

The framework describes dense_analysis.json as the full per-frame extraction and frames_dense/frame_<key>.json as per-frame JSON derived from it. 

pipeline

Fallback

If no dense analysis entry exists for a given frame key:

keep the chunk version

do not fail

5. Build visual evidence candidates by grouping neighboring events

Do not create one EvidenceRef per raw visual event by default.

Group nearby events into evidence candidates when they clearly belong to the same teaching example.

Implement:

def group_visual_events_into_candidates(
    visual_events: list[AdaptedVisualEvent],
    max_time_gap_seconds: float = 20.0,
) -> list[VisualEvidenceCandidate]:
    ...
Grouping rules

Group consecutive visual events together if all are true:

same chunk_index

same or compatible example_type

same or compatible visual_representation_type

time gap between events is below threshold

change summaries and/or visible annotations indicate continuity

Split when

chunk index changes

example type shifts materially

concept hints shift strongly

long time gap appears

event looks like a new example rather than continuation

Why this matters

You do not want:

hundreds of tiny evidence refs

or giant merged blobs

You want teaching-example-level evidence units.

6. Extract concept hints from visual metadata

Implement:

def extract_visual_concept_hints(event: AdaptedVisualEvent) -> tuple[list[str], list[str]]:
    ...
Use these sources, in order

visible annotation text

extracted entity labels

change_summary

trading_relevant_interpretation

example_type

Example mappings

Keep this initial map simple:

level, support, resistance → level

false breakout, failed breakout, ложный пробой → false_breakout

breakout, пробой → break_confirmation

trend break → trend_break_level

multiple reactions, touch, reaction count → level_rating

Important

These are only hints.
Do not force a concept if unclear.

7. Build compact visual summaries

Implement:

def summarize_candidate(candidate: VisualEvidenceCandidate) -> str:
    ...
Summary rules

The compact summary should be:

1–2 lines max

useful for human review and retrieval

not frame-by-frame

not overloaded with raw OCR/annotation text

focused on teaching meaning

Example outputs

Annotated chart showing a false-breakout level: price briefly moves beyond the level but fails to hold above it.

Teaching diagram for level strength based on repeated reactions within the same price zone.

Preferred inputs

Use:

candidate-level merged concept hints

dominant example type

dominant change summary

dominant annotations

dominant trading interpretation

8. Assign evidence role heuristically

Implement:

def infer_example_role(
    candidate: VisualEvidenceCandidate,
    linked_events: list,
) -> str:
    ...

Return one of the schema roles:

positive_example

negative_example

counterexample

ambiguous_example

illustration

unknown

Suggested heuristics

Use the linked knowledge events and candidate content together.

positive_example

Use when:

candidate supports a normal rule or condition

there is no invalidation/counterexample language

teaching intent looks confirmatory

counterexample

Use when:

linked event type is invalidation, exception, or warning

annotations or summaries mention failure, false move, mistake, trap

ambiguous_example

Use when:

the visuals are not clearly confirmatory or contradictory

multiple concept hints conflict

transcript/knowledge extraction is uncertain

illustration

Use when:

the visual clarifies a definition or concept but is not a concrete positive/negative example

Start simple. Do not overfit this logic in Step 4.

9. Map evidence candidates to KnowledgeEvents deterministically

This is the heart of Step 4.

Implement:

def link_candidates_to_knowledge_events(
    candidates: list[VisualEvidenceCandidate],
    knowledge_events: list[KnowledgeEvent],
) -> tuple[list[tuple[VisualEvidenceCandidate, list[KnowledgeEvent]]], list[dict]]:
    ...
Matching dimensions

For each candidate, score each KnowledgeEvent using:

A. chunk match

Strong boost if:

candidate chunk index == event metadata chunk index

B. time overlap

Boost if:

candidate time range overlaps event time range

or candidate is within a small window of event time range

C. concept match

Boost if:

candidate concept hints intersect with event concept/subconcept

D. event type compatibility

Boost or reduce:

definition / comparison events often fit illustration

invalidation events fit counterexample

rule / condition events fit positive_example

E. transcript proximity, if available

Optional:

if event metadata includes transcript line counts or finer timing, use it

Output

For each candidate:

zero or more linked knowledge events

debug scoring info

Important

Allow:

one candidate linked to multiple events

one event linked to multiple candidates

10. Add a scoring function

Implement:

def score_candidate_event_match(
    candidate: VisualEvidenceCandidate,
    event: KnowledgeEvent,
) -> tuple[float, dict]:
    ...
Suggested scoring weights

Initial version:

same chunk index: +0.40

time overlap or close proximity: +0.25

concept exact match: +0.20

subconcept match: +0.10

event type compatibility: +0.05

Cap total at 1.0.

Threshold

Only link if score >= 0.50 initially.

Make threshold configurable.

Debug info

Return breakdown:

{
  "chunk_match": 0.40,
  "time_overlap": 0.20,
  "concept_match": 0.20,
  "type_compatibility": 0.05,
  "total": 0.85
}

This is very useful for QA.

11. Convert linked candidates into final EvidenceRef

Implement:

def candidate_to_evidence_ref(
    candidate: VisualEvidenceCandidate,
    linked_events: list[KnowledgeEvent],
    lesson_id: str,
    lesson_title: str | None = None,
) -> EvidenceRef:
    ...
Populate

evidence_id

lesson_id

lesson_title

section

subsection

timestamp_start

timestamp_end

frame_ids

screenshot_paths

visual_type

example_role

compact_visual_summary

linked_rule_ids → empty for now

raw_visual_event_ids

source_event_ids → linked KnowledgeEvent.event_ids

metadata

Section/subsection

For now:

if all linked events share the same section/subsection, use it

otherwise leave None

raw_visual_event_ids

Since your raw visuals are frame-based, use stable ids like:

ve_raw_<frame_key>

Screenshot paths

If the project convention allows deriving screenshot paths from frame keys, do it.

For example:

data/<video_id>/llm_queue/<frame_key>.jpg
or

data/<video_id>/frames_dense/frame_<frame_key>.jpg

Do this only if path conventions are already stable in the codebase; otherwise keep empty for now.

12. Update KnowledgeEvent references if desired

If your Task 2 schema allows it, you may optionally update knowledge events in-memory to include evidence_refs.

Implement optional helper:

def attach_evidence_refs_to_knowledge_events(
    knowledge_events: list[KnowledgeEvent],
    evidence_refs: list[EvidenceRef],
) -> list[KnowledgeEvent]:
    ...
Rule

This is optional in Step 4.

At minimum:

EvidenceRef.source_event_ids must be correct

reverse linkage can be added if easy

13. Build final EvidenceIndex

Implement:

def build_evidence_index(
    lesson_id: str,
    knowledge_events: list[KnowledgeEvent],
    chunks: list[dict],
    dense_analysis: dict[str, dict] | None = None,
) -> tuple[EvidenceIndex, list[dict]]:
    ...

The function should:

adapt visual events

enrich with dense analysis if available

group into candidates

score/link candidates to knowledge events

convert to EvidenceRef

collect debug records

return:

EvidenceIndex

debug rows

14. Write outputs

Implement:

def save_evidence_index(index: EvidenceIndex, output_path: Path) -> None:
    ...

def save_evidence_debug(debug_rows: list[dict], output_path: Path) -> None:
    ...
Paths

Use Task 1 path contracts:

output_intermediate/<lesson>.evidence_index.json

output_intermediate/<lesson>.evidence_debug.json

15. Integrate into pipeline.component2.main

Insert Step 4 after Step 3 knowledge extraction and before later rule reduction.

Conceptual flow
chunks = parse_and_sync(...)
if feature_flags.enable_knowledge_events:
    knowledge_collection = ...

if feature_flags.enable_evidence_linking:
    evidence_index, evidence_debug = build_evidence_index(
        lesson_id=lesson_id,
        knowledge_events=knowledge_collection.events,
        chunks=raw_or_adapted_chunks,
        dense_analysis=dense_analysis,
    )
    save_evidence_index(...)
    save_evidence_debug(...)

# legacy markdown path still continues unchanged
Feature flag

Add:

enable_evidence_linking

Safe default:

False

Do not change legacy behavior when disabled.

Debug output requirements

Write a per-candidate debug structure like:

{
  "candidate_id": "evcand_lesson2_3_0",
  "chunk_index": 3,
  "frame_keys": ["000120", "000122", "000124"],
  "timestamp_start": 120.0,
  "timestamp_end": 128.0,
  "concept_hints": ["level", "false_breakout"],
  "compact_visual_summary": "Annotated chart showing a failed breakout at a level.",
  "candidate_scores": [
    {
      "event_id": "ke_lesson2_3_rule_statement_0",
      "score_breakdown": {
        "chunk_match": 0.4,
        "time_overlap": 0.25,
        "concept_match": 0.2,
        "type_compatibility": 0.05,
        "total": 0.9
      }
    }
  ],
  "linked_event_ids": ["ke_lesson2_3_rule_statement_0"],
  "example_role": "counterexample"
}

This makes QA and threshold tuning much easier.

Public functions to expose

In evidence_linker.py, expose at least:

def build_evidence_index(...)
def save_evidence_index(...)
def save_evidence_debug(...)

Keep all other helpers internal unless they are useful for tests.

Tests to implement

Create tests/test_evidence_linker.py.

Required tests
1. Adapt chunk visual events

Given a mock chunk in the real format, verify AdaptedVisualEvents are created correctly.

2. Dense analysis enrichment

Given a visual event and matching dense analysis entry, verify enrichment preserves frame key and adds richer metadata.

3. Grouping logic

Given several nearby visual events:

same chunk

same example type

close timestamps

verify they become one VisualEvidenceCandidate.

Also test a split case.

4. Concept hint extraction

Given annotation text like “false breakout level”, verify concept hints include level and false_breakout.

5. Candidate-event scoring

Given a candidate and event in same chunk with matching concept, score must exceed threshold.

6. Candidate-event mismatch

Different chunk + unrelated concept must stay below threshold.

7. EvidenceRef generation

Verify final EvidenceRef contains:

timestamps

frame ids

source event ids

compact summary

example role

8. Evidence index serialization

Ensure EvidenceIndex serializes correctly.

9. Feature-flag-safe integration

When enable_evidence_linking=False, legacy behavior remains unchanged.

Important implementation rules
Do

keep linking deterministic first

preserve timestamps and frame ids

preserve raw traceability

group visuals into teaching-example-level evidence units

keep summaries compact

allow many-to-many linkage

Do not

do not use the LLM as the primary linker

do not collapse away frame provenance

do not emit frame-by-frame prose

do not merge final rules here

do not require screenshot paths if path derivation is uncertain

Definition of done

Step 4 is complete when:

pipeline/component2/evidence_linker.py exists

it consumes knowledge_events.json + chunk visual events

it optionally enriches from dense_analysis.json

it builds grouped evidence candidates

it links them to knowledge events using deterministic scoring

it emits valid EvidenceIndex

it writes evidence_index.json

it optionally writes evidence_debug.json

legacy markdown flow remains unchanged when feature flag is off

Short copy-paste version
Implement Step 4 only: Evidence Linker.

Create:
- pipeline/component2/evidence_linker.py
- tests/test_evidence_linker.py

Goal:
After Step 3 knowledge extraction, build structured visual evidence links and write:
- output_intermediate/<lesson>.evidence_index.json
- optional output_intermediate/<lesson>.evidence_debug.json

Inputs:
- output_intermediate/<lesson>.knowledge_events.json
- output_intermediate/<lesson>.chunks.json
- optional dense_analysis.json
- optional filtered_visual_events.json

Requirements:
1. Adapt chunk visual events into an internal AdaptedVisualEvent model
2. Optionally enrich visual events from dense_analysis.json by frame_key
3. Group nearby visual events into teaching-example-level VisualEvidenceCandidate objects
4. Extract concept hints from:
   - visible annotations
   - extracted entities
   - change_summary
   - trading_relevant_interpretation
   - example_type
5. Build compact visual summaries for each candidate
6. Score candidate-to-KnowledgeEvent matches using:
   - same chunk
   - time overlap/proximity
   - concept/subconcept match
   - event type compatibility
7. Link candidates to one or more KnowledgeEvents using a configurable threshold
8. Convert linked candidates into Task 2 EvidenceRef objects
9. Preserve provenance:
   - timestamps
   - frame ids
   - source event ids
   - raw visual event ids
   - example role
10. Save EvidenceIndex JSON
11. Integrate behind feature flag:
   - enable_evidence_linking
12. Do not break legacy markdown/reducer flow

Do not:
- use an LLM as the primary linker
- merge final rules yet
- emit frame-by-frame narrative
- drop frame provenance

One note: a few older uploaded files have expired on the file side, so I based this Step 4 on the framework docs plus the currently re-uploaded chunk and dense-analysis samples. The critical pieces for Step 4 were available, so this plan is solid.