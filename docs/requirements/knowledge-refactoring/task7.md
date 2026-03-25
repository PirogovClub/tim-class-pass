Below is the full Task 7 you can copy for the GPT-5.4 coding agent.

Confidence: High

This assumes:

Task 3 produces knowledge_events.json

Task 4 produces evidence_index.json

Task 5 produces rule_cards.json

Task 6 refactored llm_processor.py to support:

knowledge_extract

markdown_render

legacy markdown compatibility

Task 7 — Exporters: Make Markdown a Derived Projection

Implement Task 7 of the redesigned pipeline.

Goal

Create a dedicated exporter stage that generates human-readable markdown from structured JSON artifacts, not from raw chunk transcript replay.

This stage must generate:

output_review/<lesson>.review_markdown.md

output_rag_ready/<lesson>.rag_ready.md

These outputs must be derived from:

output_intermediate/<lesson>.rule_cards.json

output_intermediate/<lesson>.evidence_index.json

Optional supporting input:

output_intermediate/<lesson>.knowledge_events.json

This stage must not depend on raw LessonChunk transcript replay as the source of truth.

Why this stage exists

The old pipeline was markdown-first:

parse chunks

LLM enriches chunk markdown

reducer compresses whole document

final markdown becomes the main artifact

That is no longer correct for your architecture.

The new rule is:

structured JSON is the source of truth

markdown is a derived view

Task 7 is the stage that enforces that shift.

Deliverables

Create:

pipeline/component2/exporters.py

tests/test_exporters.py

Update:

pipeline/component2/main.py

Use schemas from earlier tasks:

RuleCard

RuleCardCollection

EvidenceRef

EvidenceIndex

optionally KnowledgeEventCollection

Use Task 6 render support where useful, but exporters should remain responsible for output structure and file writing.

Required outputs
1. Review markdown

Path:

output_review/<lesson>.review_markdown.md

Purpose:

human QA

richer explanation

inspect normalized rules and linked evidence

easier lesson review

2. RAG-ready markdown

Path:

output_rag_ready/<lesson>.rag_ready.md

Purpose:

compact retrieval-oriented projection

embed-friendly markdown

concise rule-centric output

no transcript replay

no frame-by-frame narration

Core design principles
1. Structured JSON is the source of truth

All markdown must be built from:

RuleCardCollection

EvidenceIndex

Optional:

KnowledgeEventCollection only for audit or fallback

Do not reconstruct markdown from raw chunks.

2. Deterministic structure first

Use deterministic markdown layout first.

Optional LLM rendering is allowed, but it should operate on structured rule/evidence input, not raw transcript.

3. Different outputs for different jobs

review_markdown.md and rag_ready.md should not be identical.

Review markdown

More complete and human-friendly.

RAG markdown

More compact and retrieval-oriented.

4. Preserve provenance lightly

Markdown should not be overloaded with debug data, but it may include:

section headings

concept/subconcept

confidence

brief evidence note

optional timestamps when useful

5. No visual spam

Do not dump raw visual event narration into markdown.

Only compact evidence summaries are allowed.

Functional requirements
1. Create pipeline/component2/exporters.py

This module is responsible for:

loading structured artifacts

grouping / ordering rule cards for presentation

rendering markdown in deterministic layouts

optionally calling Task 6 markdown_render mode

writing final files

2. Load validated structured inputs

Implement:

def load_rule_cards(path: Path) -> RuleCardCollection:
    ...

def load_evidence_index(path: Path) -> EvidenceIndex:
    ...

def load_knowledge_events(path: Path) -> KnowledgeEventCollection | None:
    ...
Rules

validate via Pydantic schemas

knowledge_events.json is optional for exporters

if optional file missing, do not fail

3. Build a stable export context

Create an internal context model.

Suggested dataclass:

from dataclasses import dataclass, field


@dataclass
class ExportContext:
    lesson_id: str
    lesson_title: str | None
    rule_cards: list[RuleCard]
    evidence_refs: list[EvidenceRef]
    knowledge_events: list | None = None
    rules_by_id: dict[str, RuleCard] = field(default_factory=dict)
    evidence_by_id: dict[str, EvidenceRef] = field(default_factory=dict)
Purpose

This gives exporters a single normalized object for rendering.

Implement:

def build_export_context(
    rule_cards: RuleCardCollection,
    evidence_index: EvidenceIndex,
    knowledge_events: KnowledgeEventCollection | None = None,
    lesson_title: str | None = None,
) -> ExportContext:
    ...
4. Group and order rule cards for rendering

Markdown output must be stable and readable.

Implement:

def group_rule_cards_for_export(
    rules: list[RuleCard],
) -> dict[str, list[RuleCard]]:
    ...

def sort_rule_cards(
    rules: list[RuleCard],
) -> list[RuleCard]:
    ...
Recommended grouping

Group by:

concept
then optionally subgroup by:

subconcept

If concept is missing:

place under "Unclassified"

Recommended sort order

Within each group, sort by:

section/subsection if available in metadata

concept

subconcept

confidence descending

rule id for stability

Important

The same input should always render in the same order.

5. Add deterministic markdown builders

You must support deterministic rendering without LLM dependence.

Implement two deterministic renderers:

def render_review_markdown_deterministic(ctx: ExportContext) -> str:
    ...

def render_rag_markdown_deterministic(ctx: ExportContext) -> str:
    ...

These must work even if LLM rendering is disabled.

This is important for production stability.

6. Review markdown format

The review markdown should be more complete and easier for a human to inspect.

Suggested structure
# Lesson: <title or lesson_id>

## Concept: Level

### Rule: A level becomes stronger when price reacts to it multiple times.

**Subconcept:** level_rating  
**Confidence:** high (0.88)

**Conditions**
- Reactions occur near the same price zone.
- Reactions are structurally visible.

**Invalidation**
- A single isolated touch is not enough.
- Random local noise should not be treated as a strong level.

**Exceptions**
- ...

**Comparisons**
- ...

**Algorithm notes**
- Detect local extrema.
- Cluster candidate price zones.
- Count reaction frequency.

**Visual evidence**
- Annotated chart showing repeated reactions around the same price area.

**Evidence refs:** evid_lesson2_3_0  
**Source events:** ke_lesson2_4_rule_statement_0, ke_lesson2_4_condition_0
Rules

include section headers by concept

include subsections when useful

include confidence

include compact visual evidence if present

include source/evidence ids only in a compact way

do not dump metadata blobs

7. RAG markdown format

The RAG-ready markdown should be compact and optimized for retrieval.

Implement a deterministic compact layout.

Suggested structure
# Lesson: <title or lesson_id>

## Level

### level_rating
Rule: A level becomes stronger when price reacts to it multiple times.

Conditions:
- Reactions occur near the same price zone.

Invalidation:
- A single isolated touch is not enough.

Algorithm notes:
- Count reactions within clustered price zones.

Visual summary:
- Repeated reactions around one price zone illustrate level strength.
Rules

shorter than review markdown

no verbose provenance

no long narrative explanation

no raw transcript

no frame-by-frame visual description

embed-friendly plain rule text

8. Add shared formatting helpers

Implement helpers like:

def format_bullet_block(title: str, items: list[str]) -> str:
    ...

def format_compact_text_list(items: list[str]) -> list[str]:
    ...

def dedupe_preserve_order(items: list[str]) -> list[str]:
    ...

def clean_markdown_text(text: str) -> str:
    ...
Important

trim whitespace

dedupe repeated items

preserve order where meaningful

avoid blank sections

9. Add optional LLM-based rendering on top of structured context

Exporters should support both:

deterministic rendering

optional LLM-enhanced rendering via Task 6 markdown_render

Implement:

def render_review_markdown(
    ctx: ExportContext,
    *,
    use_llm: bool = False,
    video_id: str | None = None,
    model: str | None = None,
    provider: str | None = None,
) -> tuple[str, list[dict]]:
    ...

def render_rag_markdown(
    ctx: ExportContext,
    *,
    use_llm: bool = False,
    video_id: str | None = None,
    model: str | None = None,
    provider: str | None = None,
) -> tuple[str, list[dict]]:
    ...
Rules

If use_llm=False:

use deterministic renderer

return empty usage list

If use_llm=True:

call Task 6 process_rule_cards_markdown_render(...)

pass only structured inputs:

lesson id/title

rule cards

evidence refs

render mode (review or rag)

do not pass raw chunk transcript data

10. Add export file writers

Implement:

def save_review_markdown(markdown: str, output_path: Path) -> None:
    ...

def save_rag_markdown(markdown: str, output_path: Path) -> None:
    ...

def save_export_debug(debug_rows: list[dict], output_path: Path) -> None:
    ...
Paths

Use Task 1 path contracts or extend them if needed:

output_review/<lesson>.review_markdown.md

output_rag_ready/<lesson>.rag_ready.md

Optional debug:

output_review/<lesson>.review_render_debug.json

output_rag_ready/<lesson>.rag_render_debug.json

11. Ensure output directories exist

Implement or reuse helper:

def ensure_parent_dir(path: Path) -> None:
    ...

Before writing:

create output_review/ if missing

create output_rag_ready/ if missing

12. Add export orchestration functions

Expose public functions:

def export_review_markdown(
    *,
    lesson_id: str,
    lesson_title: str | None,
    rule_cards_path: Path,
    evidence_index_path: Path,
    knowledge_events_path: Path | None = None,
    output_path: Path,
    use_llm: bool = False,
    video_id: str | None = None,
    model: str | None = None,
    provider: str | None = None,
) -> tuple[str, list[dict]]:
    ...

def export_rag_markdown(
    *,
    lesson_id: str,
    lesson_title: str | None,
    rule_cards_path: Path,
    evidence_index_path: Path,
    knowledge_events_path: Path | None = None,
    output_path: Path,
    use_llm: bool = False,
    video_id: str | None = None,
    model: str | None = None,
    provider: str | None = None,
) -> tuple[str, list[dict]]:
    ...
Behavior

Each function should:

load validated JSON artifacts

build export context

render markdown

write output file

return markdown + usage/debug records

13. Integrate into pipeline/component2/main.py

Add the exporter stage after Task 5 rule-card creation.

Conceptual flow
if feature_flags.enable_knowledge_events:
    knowledge_collection = ...

if feature_flags.enable_evidence_linking:
    evidence_index = ...

if feature_flags.enable_rule_cards:
    rule_cards = ...

if feature_flags.enable_exporters:
    export_review_markdown(...)
    export_rag_markdown(...)
Feature flags

Add:

enable_exporters

use_llm_review_render

use_llm_rag_render

Safe default:

enable_exporters=False

use_llm_review_render=False

use_llm_rag_render=False

That means:

exporters are opt-in initially

deterministic render is default when exporters are enabled

14. Maintain legacy behavior during migration

Do not delete the old markdown/reducer path yet.

The system should support both:

Legacy path

chunk markdown

reducer

old output_rag_ready/*.md

New path

rule cards

exporters

review_markdown.md

rag_ready.md

During migration:

both may coexist

feature flags choose path

15. Optional: add a small export manifest

For operational clarity, optionally write:

{
  "lesson_id": "...",
  "review_markdown_path": "...",
  "rag_markdown_path": "...",
  "used_llm_review_render": false,
  "used_llm_rag_render": false,
  "rule_count": 12,
  "evidence_count": 8
}

This is optional but useful.

Suggested internal helper functions

Implement at least:

def build_export_context(...)
def group_rule_cards_for_export(...)
def sort_rule_cards(...)
def render_review_markdown_deterministic(...)
def render_rag_markdown_deterministic(...)
def render_review_markdown(...)
def render_rag_markdown(...)
def save_review_markdown(...)
def save_rag_markdown(...)
def export_review_markdown(...)
def export_rag_markdown(...)

Keep them small and testable.

Recommended deterministic rendering rules
Review markdown should include

lesson title

concept grouping

rule text

subconcept if present

confidence

conditions

invalidation

exceptions

comparisons

algorithm notes

compact visual evidence

compact refs

RAG markdown should include

lesson title

concept grouping

rule text

only the most relevant conditions/invalidation

algorithm notes if useful

visual summary only if it adds retrieval value

Review markdown should not include

raw debug metadata

full source event ids unless compact

giant evidence dumps

RAG markdown should not include

confidence noise unless helpful

long provenance blocks

raw ids everywhere

human-review chatter

Tests to implement

Create tests/test_exporters.py.

Required tests
1. Load valid structured inputs

Ensure valid RuleCardCollection and EvidenceIndex can be loaded.

2. Build export context

Ensure context maps rule/evidence ids correctly.

3. Deterministic review render

Given sample rule cards and evidence refs, verify review markdown contains:

concept heading

rule text

conditions

invalidation

visual evidence section

4. Deterministic RAG render

Verify compact output:

includes rule text

excludes verbose provenance

excludes transcript replay

5. Grouping and ordering stability

For same input, render order must remain stable.

6. Empty optional sections omitted

If a rule has no exceptions or comparisons, those sections should not appear.

7. LLM render integration path

Mock Task 6 render function and verify exporters pass structured inputs only.

8. Save output files

Ensure:

review markdown path is written

rag markdown path is written

parent dirs are created if needed

9. Feature-flag-safe integration

When exporters are disabled, pipeline behavior remains unchanged.

10. No raw chunk transcript dependency

Ensure deterministic exporters do not require raw chunk input.

Important implementation rules
Do

make markdown a derived view from structured artifacts

support deterministic export without LLM

keep review and rag outputs distinct

keep output stable and readable

use Task 6 render mode only on structured input

Do not

do not rebuild markdown from raw transcript chunks

do not require the legacy reducer for new exports

do not dump evidence/debug metadata verbatim

do not make review and rag outputs identical

do not depend on raw video analysis at export time

Definition of done

Task 7 is complete when:

pipeline/component2/exporters.py exists

it loads rule_cards.json and evidence_index.json

it builds a stable export context

it can render:

review_markdown.md

rag_ready.md

deterministic rendering works without LLM

optional LLM rendering works only on structured inputs

files are written to:

output_review/

output_rag_ready/

legacy markdown/reducer path remains untouched when exporters are disabled

Copy-paste instruction for the coding agent
Implement Task 7 only: Exporters.

Create:
- pipeline/component2/exporters.py
- tests/test_exporters.py

Goal:
Generate markdown as a derived view from structured artifacts, not from raw chunk transcript replay.

Required outputs:
- output_review/<lesson>.review_markdown.md
- output_rag_ready/<lesson>.rag_ready.md

Inputs:
- output_intermediate/<lesson>.rule_cards.json
- output_intermediate/<lesson>.evidence_index.json
- optional output_intermediate/<lesson>.knowledge_events.json

Requirements:
1. Load validated RuleCardCollection and EvidenceIndex
2. Build a stable ExportContext
3. Group and order RuleCards by concept/subconcept with deterministic ordering
4. Implement deterministic renderers:
   - render_review_markdown_deterministic(...)
   - render_rag_markdown_deterministic(...)
5. Review markdown should be richer and human-friendly
6. RAG markdown should be compact and retrieval-oriented
7. Add optional LLM-enhanced rendering via Task 6 markdown_render mode
8. LLM rendering must consume only structured inputs:
   - rule_cards
   - evidence_refs
   - lesson metadata
   and must not consume raw chunk transcript replay
9. Save output files to:
   - output_review/
   - output_rag_ready/
10. Integrate into component2/main.py behind feature flags:
   - enable_exporters
   - use_llm_review_render
   - use_llm_rag_render
11. Do not break legacy markdown/reducer path

Do not:
- reconstruct markdown from raw chunks
- require the old reducer for new exports
- dump raw evidence/debug metadata directly into final markdown
- make review and rag outputs identical
