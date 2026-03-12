Below is the full updated Step 3 you can copy for the GPT-5.4 coding agent.

It is now aligned to your real *.chunks.json structure.

Step 3 — Structured Post-Parse Knowledge Extraction

Implement Step 3 of the redesigned pipeline.

Goal

Add a new JSON-first stage that runs after parse/sync and before legacy markdown rendering.

This stage must extract atomic trading knowledge from the real *.chunks.json output and write:

output_intermediate/<lesson>.knowledge_events.json

optionally output_intermediate/<lesson>.knowledge_debug.json

This stage must not break or replace the current markdown/reducer pipeline.

Why this stage exists

The current parser output already contains rich chunked lesson data:

transcript lines

visual events

previous visual state

timing boundaries

This stage should convert that chunked lesson data into structured machine-usable knowledge objects for:

later rule normalization

RAG

algorithm design

future ML labeling

Markdown is not the source of truth here.
KnowledgeEvent JSON is.

Confirmed input shape

The current *.chunks.json file is a JSON list of chunk objects.

Each chunk contains at least:

chunk_index

start_time_seconds

end_time_seconds

transcript_lines → list of:

start_seconds

end_seconds

text

visual_events → list of rich visual event objects

previous_visual_state

Your implementation must use this actual shape directly.

Deliverables

Create:

pipeline/component2/knowledge_builder.py

tests/test_knowledge_builder.py

Update:

pipeline/component2/main.py

Use schemas already defined in Task 2:

KnowledgeEvent

KnowledgeEventCollection

Functional requirements
1. Add a concrete chunk adapter

Inside knowledge_builder.py, create a concrete internal adapter for the real chunk format.

Suggested structure:

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class AdaptedChunk:
    chunk_index: int
    lesson_id: str
    lesson_title: Optional[str]
    section: Optional[str]
    subsection: Optional[str]
    start_time_seconds: float
    end_time_seconds: float
    transcript_lines: list[dict[str, Any]] = field(default_factory=list)
    transcript_text: str = ""
    visual_events: list[dict[str, Any]] = field(default_factory=list)
    previous_visual_state: Optional[dict[str, Any]] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def candidate_visual_frame_keys(self) -> list[str]:
        keys: list[str] = []
        for v in self.visual_events:
            frame_key = v.get("frame_key")
            if frame_key:
                keys.append(str(frame_key))
        return keys

    @property
    def candidate_visual_types(self) -> list[str]:
        values: list[str] = []
        for v in self.visual_events:
            val = v.get("visual_representation_type")
            if val:
                values.append(str(val))
        return values

    @property
    def candidate_example_types(self) -> list[str]:
        values: list[str] = []
        for v in self.visual_events:
            val = v.get("example_type")
            if val:
                values.append(str(val))
        return values
Notes

Do not access raw parser dicts everywhere in the module.

Normalize once into AdaptedChunk, then work only with that.

section / subsection may not exist explicitly in the current chunk; infer them conservatively from metadata if present, otherwise leave None.

2. Add chunk loading and adaptation helpers

Implement:

def load_chunks_json(path: Path) -> list[dict]:
    ...

def adapt_chunk(raw_chunk: dict, lesson_id: str, lesson_title: str | None = None) -> AdaptedChunk:
    ...

def adapt_chunks(raw_chunks: list[dict], lesson_id: str, lesson_title: str | None = None) -> list[AdaptedChunk]:
    ...
Rules

transcript_text must be built by joining cleaned transcript_lines[*]["text"]

ignore blank transcript lines

tolerate missing optional fields safely

default missing lists to empty lists

preserve previous_visual_state in metadata or direct field

3. Build transcript text from transcript_lines

For each chunk:

extract each line’s text

strip whitespace

ignore empty strings

join with newline or single space

preserve original transcript_lines for provenance

Suggested helper:

def build_transcript_text(transcript_lines: list[dict]) -> str:
    ...

Also implement:

def get_transcript_time_bounds(transcript_lines: list[dict], fallback_start: float, fallback_end: float) -> tuple[float, float]:
    ...

Use transcript bounds if available, otherwise fall back to chunk bounds.

4. Pre-summarize visual events for extraction

Do not send raw visual_events directly into the LLM prompt.

Create a compact summary layer.

Implement:

def summarize_single_visual_event(event: dict) -> str:
    ...

def summarize_visual_events_for_extraction(
    visual_events: list[dict],
    max_items: int = 5,
) -> list[str]:
    ...
Preferred source fields

When building compact summaries, prefer these if present:

visual_representation_type

example_type

change_summary

trading_relevant_interpretation

current_state.visible_annotations

current_state.extracted_entities

any short pattern/setup hints

Ignore or downweight

decorative UI facts

raw long visual_facts

repetitive layout descriptions

frame-by-frame motion narration

large nested blobs

Good summary examples

Annotated chart, false-breakout example: brief move above level fails to hold and returns below.

Hand-drawn teaching example about level strength from repeated reactions.

Diagram with visible annotation mentioning false breakout level.

Cap

Return at most 3–5 summaries per chunk.

Prefer representative and trading-relevant summaries.

5. Define temporary extraction models

Inside knowledge_builder.py, define temporary models for the LLM response.

from pydantic import BaseModel, Field
from typing import Optional


class ExtractedStatement(BaseModel):
    text: str
    concept: Optional[str] = None
    subconcept: Optional[str] = None
    ambiguity_notes: list[str] = Field(default_factory=list)


class ChunkExtractionResult(BaseModel):
    definitions: list[ExtractedStatement] = Field(default_factory=list)
    rule_statements: list[ExtractedStatement] = Field(default_factory=list)
    conditions: list[ExtractedStatement] = Field(default_factory=list)
    invalidations: list[ExtractedStatement] = Field(default_factory=list)
    exceptions: list[ExtractedStatement] = Field(default_factory=list)
    comparisons: list[ExtractedStatement] = Field(default_factory=list)
    warnings: list[ExtractedStatement] = Field(default_factory=list)
    process_steps: list[ExtractedStatement] = Field(default_factory=list)
    algorithm_hints: list[ExtractedStatement] = Field(default_factory=list)
    examples: list[ExtractedStatement] = Field(default_factory=list)
    global_notes: list[str] = Field(default_factory=list)
Rules

JSON only

no prose paragraphs

no markdown

atomic statements only

6. Build the extraction prompt

Implement:

def build_knowledge_extraction_prompt(chunk: AdaptedChunk, visual_summaries: list[str]) -> str:
    ...
Prompt requirements

Tell the model to:

extract atomic trading knowledge

return valid JSON only

split distinct ideas into separate entries

prefer explicit teaching rules over narration

keep statements short and normalized

keep visuals as supporting evidence only

avoid frame-by-frame descriptions

avoid summarizing the whole lesson

do not invent absent information

leave concept/subconcept null when unclear

note ambiguity explicitly

Include in prompt

lesson id

chunk index

approximate time range

transcript text

compact visual summaries

Output schema in prompt

Must include these buckets:

definitions

rule_statements

conditions

invalidations

exceptions

comparisons

warnings

process_steps

algorithm_hints

examples

global_notes

7. Add LLM extraction wrapper

Implement:

def extract_chunk_knowledge(
    chunk: AdaptedChunk,
    llm_client,
    max_visual_summaries: int = 5,
) -> tuple[ChunkExtractionResult, dict]:
    ...
Behavior

build compact visual summaries

build prompt

call model

parse JSON safely

validate into ChunkExtractionResult

return both:

parsed result

debug payload

Debug payload should include

chunk index

transcript excerpt or full transcript text

compact visual summaries used

raw model response

parsed extraction dict

Error handling

If parsing fails:

either retry once with a repair prompt

or return an empty ChunkExtractionResult and record failure in debug payload

Do not crash the whole lesson because one chunk fails.

8. Add conservative concept inference fallback

Implement:

def infer_concept_from_text(text: str) -> tuple[str | None, str | None]:
    ...

def infer_concept_from_visuals(visual_events: list[dict]) -> tuple[str | None, str | None]:
    ...

def resolve_concept(
    statement_concept: str | None,
    statement_subconcept: str | None,
    chunk: AdaptedChunk,
    statement_text: str,
) -> tuple[str | None, str | None]:
    ...
Fallback order

LLM-provided concept/subconcept

transcript text keywords

visual annotation text

example titles / example type

conservative keyword map

Be conservative

If unsure:

leave concept=None

leave subconcept=None

Example keyword mapping

Use only a small initial map, for example:

level, support, resistance → level

false breakout, failed breakout, ложный пробой → false_breakout

breakout, break, пробой → break_confirmation

trend break → trend_break_level

reaction, touches, multiple reactions → level_rating

This should stay simple in Step 3.

9. Add confidence scoring

Implement:

def score_event_confidence(
    text: str,
    event_type: str,
    concept: str | None,
    ambiguity_notes: list[str],
    chunk: AdaptedChunk,
) -> tuple[str, float]:
    ...
Suggested heuristics

Increase confidence when:

statement is explicit and short

it sounds definitional or rule-like

concept is present

ambiguity notes are empty

transcript wording is strong

supporting visual summaries align with the same idea

Lower confidence when:

concept is missing

ambiguity exists

statement sounds inferred from example only

text is vague or overly generic

Output

Return:

confidence label: low / medium / high

confidence_score: float in [0,1]

Keep this heuristic simple.

10. Map extracted statements into KnowledgeEvent

Implement:

def extraction_result_to_knowledge_events(
    extraction: ChunkExtractionResult,
    chunk: AdaptedChunk,
) -> list[KnowledgeEvent]:
    ...
Bucket mapping
bucket	event_type
definitions	definition
rule_statements	rule_statement
conditions	condition
invalidations	invalidation
exceptions	exception
comparisons	comparison
warnings	warning
process_steps	process_step
algorithm_hints	algorithm_hint
examples	example
For each emitted KnowledgeEvent, populate:

event_id

lesson_id

lesson_title

section

subsection

timestamp_start

timestamp_end

event_type

raw_text

normalized_text

concept

subconcept

source_event_ids

evidence_refs → empty list for now is acceptable

confidence

confidence_score

ambiguity_notes

metadata

Provenance metadata required

In metadata, include:

chunk_index

chunk_start_time_seconds

chunk_end_time_seconds

transcript_line_count

candidate_visual_frame_keys

candidate_visual_types

candidate_example_types

optionally has_previous_visual_state

Event id strategy

Use deterministic ids, e.g.:

ke_<lesson_slug>_<chunk_index>_<event_type>_<index>
11. Filter bad or empty extracted statements

Implement a small validation layer before creating KnowledgeEvent.

Skip statements when:

text is blank

normalized text is too short to be meaningful

it is obvious duplicate noise inside the same bucket

Suggested helper:

def normalize_statement_text(text: str) -> str:
    ...

def dedupe_statements(statements: list[ExtractedStatement]) -> list[ExtractedStatement]:
    ...

Keep dedupe simple:

case-insensitive

whitespace-normalized

exact-text dedupe only for Step 3

12. Create collection output

Implement:

def build_knowledge_events_from_chunks(
    chunks: list[AdaptedChunk],
    lesson_id: str,
    lesson_title: str | None,
    llm_client,
    debug: bool = False,
) -> tuple[KnowledgeEventCollection, list[dict]]:
    ...

And:

def build_knowledge_events_from_file(
    chunks_path: Path,
    lesson_id: str,
    lesson_title: str | None,
    llm_client,
    debug: bool = False,
) -> tuple[KnowledgeEventCollection, list[dict]]:
    ...

The function should:

adapt chunks

extract chunk knowledge one chunk at a time

emit KnowledgeEvents

collect debug payloads

return:

KnowledgeEventCollection

debug records

13. Save outputs

Implement:

def save_knowledge_events(
    collection: KnowledgeEventCollection,
    output_path: Path,
) -> None:
    ...

def save_knowledge_debug(
    debug_rows: list[dict],
    output_path: Path,
) -> None:
    ...
Output paths

Use Task 1 path contracts:

output_intermediate/<lesson>.knowledge_events.json

output_intermediate/<lesson>.knowledge_debug.json

14. Integrate into pipeline.component2.main

Insert this stage after parser/sync and before legacy markdown generation.

Example conceptual flow
filtered_visuals = ...
chunks = parse_and_sync(...)

if feature_flags.enable_knowledge_events:
    knowledge_collection, debug_rows = build_knowledge_events_from_chunks(
        chunks=chunks,
        lesson_id=lesson_id,
        lesson_title=lesson_title,
        llm_client=llm_client,
        debug=True,
    )
    save_knowledge_events(...)
    save_knowledge_debug(...)

# existing path remains unchanged
markdown_outputs = run_llm_markdown(...)
run_reducer(...)
Feature flag

Add:

enable_knowledge_events

Safe default for initial rollout:

False

When disabled:

there must be no behavior change

15. Logging

Add stage-level logging:

number of chunks loaded

number of chunks successfully extracted

total KnowledgeEvents emitted

number of failed chunks

output file paths

Keep logs concise and operational.

Public API to expose

In knowledge_builder.py, expose at least:

def build_knowledge_events_from_file(...)
def build_knowledge_events_from_chunks(...)
def save_knowledge_events(...)
def save_knowledge_debug(...)

These should be the only functions other modules need.

Debug output structure

The optional debug output should be a list of per-chunk records like:

{
  "chunk_index": 3,
  "start_time_seconds": 120.0,
  "end_time_seconds": 165.0,
  "transcript_text": "...",
  "compact_visual_summaries": [
    "Annotated chart, false-breakout example..."
  ],
  "raw_model_response": "{...}",
  "parsed_extraction": {
    "definitions": [],
    "rule_statements": [...]
  },
  "emitted_event_ids": [
    "ke_lesson2_3_rule_statement_0"
  ],
  "error": null
}

This file is for QA only and should not be used as the main artifact.

Tests to implement

Create tests/test_knowledge_builder.py.

Required tests
1. Adapt chunk from real shape

Given a mock chunk in the real format, ensure adapt_chunk() returns a valid AdaptedChunk.

2. Build transcript text

Given transcript lines with blanks and spaces, ensure transcript text is normalized correctly.

3. Visual pre-summarization

Given several mock visual events, ensure compact summaries are:

non-empty

capped

trading-relevant

do not dump the whole raw event

4. Extraction mapping

Given a mock ChunkExtractionResult, verify correct mapping into KnowledgeEvents.

5. Deterministic ids

For the same chunk and extraction result, emitted ids must be stable.

6. Provenance metadata present

Each KnowledgeEvent.metadata must include:

chunk_index

candidate_visual_frame_keys

candidate_visual_types

candidate_example_types

7. Collection serialization

KnowledgeEventCollection should serialize cleanly.

8. Feature-flag-safe integration

When enable_knowledge_events=False, legacy pipeline path remains unchanged.

9. Bad statements skipped

Blank extracted statements should not produce invalid KnowledgeEvents.

Important implementation rules
Do

keep extraction atomic

preserve provenance strongly

use visuals only as supporting extraction context

write structured JSON as the main output

fail gracefully per chunk, not per lesson

Do not

do not merge rules yet

do not emit RuleCard yet

do not rewrite the markdown pipeline

do not store giant raw visual blobs in final KnowledgeEvent

do not let the LLM produce freeform lesson summaries

Definition of done

Step 3 is complete when:

knowledge_builder.py exists

it consumes the real *.chunks.json shape

it emits valid KnowledgeEventCollection

it writes knowledge_events.json

it optionally writes knowledge_debug.json

each event preserves chunk-level provenance

legacy markdown/reducer flow still works unchanged when feature flag is off

Short copy-paste version
Implement Step 3 only.

Create:
- pipeline/component2/knowledge_builder.py
- tests/test_knowledge_builder.py

Goal:
Add a structured post-parse stage that consumes the real .chunks.json format and writes:
- output_intermediate/<lesson>.knowledge_events.json
- optional output_intermediate/<lesson>.knowledge_debug.json

Input chunk shape:
- chunk_index
- start_time_seconds
- end_time_seconds
- transcript_lines[{start_seconds, end_seconds, text}]
- visual_events[]
- previous_visual_state

Requirements:
1. Build a concrete AdaptedChunk for this exact shape
2. Join transcript_lines into transcript_text, preserving transcript_lines
3. Pre-summarize visual_events into compact trading-relevant summaries for LLM input
4. Define temporary extraction models:
   - ExtractedStatement
   - ChunkExtractionResult
5. Use a strict JSON-only extraction prompt
6. Map extraction buckets into Task 2 KnowledgeEvent objects
7. Preserve metadata:
   - chunk_index
   - chunk_start_time_seconds
   - chunk_end_time_seconds
   - transcript_line_count
   - candidate_visual_frame_keys
   - candidate_visual_types
   - candidate_example_types
8. Add conservative concept inference fallback
9. Add simple confidence scoring
10. Save KnowledgeEventCollection JSON
11. Integrate after parser/sync and before legacy markdown, behind feature flag:
   - enable_knowledge_events
12. Do not break current markdown/reducer flow

Do not:
- merge final rules yet
- create RuleCard yet
- replace legacy markdown pipeline
- dump raw visual event blobs into final KnowledgeEvent

