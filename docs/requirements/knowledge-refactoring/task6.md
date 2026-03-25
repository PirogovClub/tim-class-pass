Below is the full Task 6 you can copy for the GPT-5.4 coding agent.

This version is now grounded in the actual current llm_processor.py and provider wrapper you uploaded.

The current state is:

pipeline/component2/llm_processor.py is still a Pass 1 literal-scribe markdown synthesizer built around LessonChunk -> EnrichedMarkdownChunk, with build_user_prompt(chunk), _call_provider(...), async chunk processing, markdown assembly, and debug writing. 

FRAMEWORK_MODULES

 

llm_processor

provider resolution already exists through resolve_provider_for_stage(...), resolve_model_for_stage(...), and get_provider(...).generate_text(...), with schema-aware structured output support. 

FRAMEWORK_MODULES

the target redesign requires two distinct modes:

knowledge_extract → structured JSON only

markdown_render → readable markdown from normalized rule cards + evidence refs. 

Response: Visual Decoding Review

So Task 6 should refactor the current LLM processor into a reusable structured-output engine, not leave it as a markdown-only stage.

Task 6 — Refactor the LLM Processor into Two Modes
Goal

Refactor the current pipeline/component2/llm_processor.py so it supports two explicit modes:

Mode A — knowledge_extract

Use the provider stack to extract structured JSON from synced chunk input.

Mode B — markdown_render

Use the provider stack to render readable markdown from normalized RuleCards and linked EvidenceRefs.

This task must preserve backward compatibility where practical, but the new architecture must treat markdown as a derived projection, not the primary artifact. 

Response: Visual Decoding Review

Why this task exists

Right now the current processor is optimized for:

chronological chunk prompt

“Literal Scribe” markdown output

EnrichedMarkdownChunk parsing

assembly into pass-1 markdown

later reducer pass. 

pipeline

 

llm_processor

But the redesigned pipeline requires:

structured extraction first

rule/evidence normalization next

markdown rendering only after rule_cards.json and evidence_index.json exist. 

Response: Visual Decoding Review

 

Response: Visual Decoding Review

So Task 6 is the bridge between the old processor and the new architecture.

Deliverables

Create or refactor:

pipeline/component2/llm_processor.py

tests/test_llm_processor.py

Update:

pipeline/component2/main.py

You may keep the same filename, but internally it must become a multi-mode processor, not a markdown-only literal scribe.

High-level refactor strategy
Do not delete the current behavior immediately

Keep the current legacy markdown behavior available for compatibility.

Add explicit mode-based APIs

Refactor the module so it exposes separate functions for:

extraction mode

render mode

optional legacy mode wrapper

Reuse the provider transport layer

Do not reinvent provider calling logic.

The current provider layer already supports:

provider resolution

model resolution

generate_text(...)

response_schema

structured JSON output 

FRAMEWORK_MODULES

Task 6 should reuse that.

Functional requirements
1. Keep and generalize provider/model resolution

The current file already contains:

_resolve_model(video_id, model)

_resolve_provider(video_id, provider) 

FRAMEWORK_MODULES

Refactor this into stage-aware helpers.

Implement
def _resolve_model_for_llm_mode(
    mode: str,
    video_id: str | None = None,
    model: str | None = None,
) -> str:
    ...

def _resolve_provider_for_llm_mode(
    mode: str,
    video_id: str | None = None,
    provider: str | None = None,
) -> str:
    ...
Mapping

Suggested stage mapping:

knowledge_extract → provider stage "component2" or "component2_extract"

markdown_render → provider stage "component2_render"

legacy_markdown → provider stage "component2"

Important

Preserve existing config/env fallback behavior as much as possible, because the current pipeline already relies on it. 

FRAMEWORK_MODULES

2. Replace one global system prompt with mode-specific prompts

The current file uses a single SYSTEM_PROMPT optimized for literal-scribe markdown generation. It preserves chronology, integrates visual deltas, and outputs EnrichedMarkdownChunk. 

llm_processor

This must be split.

Create:

KNOWLEDGE_EXTRACT_SYSTEM_PROMPT

MARKDOWN_RENDER_SYSTEM_PROMPT

optionally LEGACY_LITERAL_SCRIBE_SYSTEM_PROMPT

A. KNOWLEDGE_EXTRACT_SYSTEM_PROMPT

Must instruct the model to:

extract atomic trading knowledge only

return JSON only

split distinct ideas

avoid prose summaries

avoid frame-by-frame narration

preserve uncertainty explicitly

use visuals only as supporting context

Expected JSON sections:

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

This matches the redesign target. 

Response: Visual Decoding Review

B. MARKDOWN_RENDER_SYSTEM_PROMPT

Must instruct the model to:

render human-readable markdown from normalized rule cards

preserve structure and meaning

not invent new rules

keep rules, conditions, invalidations, and compact visual evidence distinct

produce readable review markdown, not raw lesson replay

It must not behave like the current literal scribe.

C. LEGACY_LITERAL_SCRIBE_SYSTEM_PROMPT

Optional but recommended:

keep the current prompt as a legacy compatibility mode

used only when old pass-1 markdown flow is still required

3. Split prompt builders by mode

The current build_user_prompt(chunk) is hardwired to:

<previous_visual_state>

<transcript>

<visual_events>
for literal-scribe chunk synthesis. 

FRAMEWORK_MODULES

That is too specific.

Refactor into:
def build_knowledge_extract_prompt(
    *,
    lesson_id: str,
    chunk_index: int,
    section: str | None,
    transcript_text: str,
    visual_summaries: list[str],
    concept_context: dict | None = None,
) -> str:
    ...

def build_markdown_render_prompt(
    *,
    lesson_id: str,
    lesson_title: str | None,
    rule_cards: list[RuleCard],
    evidence_refs: list[EvidenceRef],
    render_mode: str = "review",
) -> str:
    ...

def build_legacy_markdown_prompt(chunk: LessonChunk) -> str:
    ...
Notes

build_legacy_markdown_prompt(...) can reuse the current build_user_prompt(chunk) behavior

extraction mode prompt should use compact visual summaries, not full raw visual events

render mode prompt should use normalized structured inputs, not transcript replay

4. Add typed parsing models for both modes

The current processor only parses:

EnrichedMarkdownChunk via parse_enriched_markdown_chunk(payload) 

FRAMEWORK_MODULES

Task 6 must support two parse targets.

Implement
def parse_knowledge_extraction(payload: str) -> ChunkExtractionResult:
    ...

def parse_markdown_render_result(payload: str) -> MarkdownRenderResult:
    ...

def parse_legacy_enriched_markdown_chunk(payload: str) -> EnrichedMarkdownChunk:
    ...
ChunkExtractionResult

Use the temporary structured extraction model already defined in Step 3.

MarkdownRenderResult

Create a small Pydantic model like:

class MarkdownRenderResult(BaseModel):
    markdown: str
    metadata_tags: list[str] = Field(default_factory=list)

This keeps render mode structured and testable.

Legacy

Keep EnrichedMarkdownChunk parsing for backward compatibility.

5. Introduce a generic provider call core

The current _call_provider(...) is specific to:

LessonChunk

legacy prompt builder

EnrichedMarkdownChunk

stage "{provider}_component2" 

llm_processor

Refactor this into a generic internal helper.

Implement
def _call_provider_for_mode(
    *,
    mode: str,
    user_text: str,
    response_schema,
    system_instruction: str,
    video_id: str | None = None,
    model: str | None = None,
    provider: str | None = None,
    temperature: float = 0.2,
    frame_key: str | None = None,
) -> tuple[BaseModel, list[dict]]:
    ...
Behavior

resolve provider/model via mode-aware helpers

call get_provider(...).generate_text(...)

pass response_mime_type="application/json"

pass response_schema=response_schema

validate response

return (parsed_model, usage_records)

Important

Reuse current provider infrastructure exactly where possible. The provider wrapper already supports schema-driven structured JSON for Gemini/OpenAI/Setra. 

FRAMEWORK_MODULES

6. Add explicit mode-level public APIs

The module should expose clear entrypoints instead of one hidden markdown-only path.

A. Knowledge extraction mode
async def process_chunk_knowledge_extract(
    chunk: AdaptedChunk,
    *,
    video_id: str | None = None,
    model: str | None = None,
    provider: str | None = None,
) -> tuple[ChunkExtractionResult, list[dict]]:
    ...
async def process_chunks_knowledge_extract(
    chunks: list[AdaptedChunk],
    *,
    video_id: str | None = None,
    model: str | None = None,
    provider: str | None = None,
    max_concurrency: int = 5,
    progress_callback = None,
) -> list[tuple[AdaptedChunk, ChunkExtractionResult, list[dict]]]:
    ...
B. Markdown render mode
def process_rule_cards_markdown_render(
    *,
    lesson_id: str,
    lesson_title: str | None,
    rule_cards: list[RuleCard],
    evidence_refs: list[EvidenceRef],
    render_mode: str = "review",
    video_id: str | None = None,
    model: str | None = None,
    provider: str | None = None,
) -> tuple[MarkdownRenderResult, list[dict]]:
    ...
C. Legacy compatibility

Keep or wrap:

async def process_chunk_legacy_markdown(...)
async def process_chunks_legacy_markdown(...)

These can delegate to the existing behavior.

7. Keep the concurrency pattern, but make it reusable

The current process_chunks(...) already has:

semaphore-based concurrency

ordered results by chunk index

progress callback

per-chunk elapsed time. 

llm_processor

Refactor this into a generic runner if helpful.

Option A

Keep separate implementations per mode but share a small helper.

Option B

Create a generic async chunk runner:

async def _process_chunks_generic(
    items: list,
    worker_fn,
    *,
    max_concurrency: int = 5,
    progress_callback = None,
    order_key = None,
) -> list[tuple]:
    ...

Either approach is fine, but do not duplicate a lot of concurrency code.

8. Change debug writing to support multiple modes

The current write_llm_debug(...) writes:

chunk_index

time bounds

visual count

result

request_usage 

FRAMEWORK_MODULES

Task 6 should generalize debug writing.

Implement
def write_llm_debug(
    path: Path | str,
    rows: list[dict],
) -> None:
    ...
Or add mode-specific wrappers
def write_extract_debug(...)
def write_render_debug(...)
def write_legacy_markdown_debug(...)
For extraction rows include

chunk index

transcript range

compact visual summaries used

parsed extraction result

request usage

For render rows include

number of rule cards

number of evidence refs

render mode

rendered markdown preview or full result

request usage

9. Stop coupling markdown assembly to chunk replay

The current assemble_video_markdown(...) concatenates chunk-level markdown with separators and a lesson header. 

FRAMEWORK_MODULES

That is legacy behavior.

For Task 6:

Keep legacy assembly

under assemble_legacy_video_markdown(...)

Do not use it for new render mode

New render mode should be:

one lesson-level render call over rule_cards + evidence_refs

not chunk-by-chunk transcript replay

That is one of the most important architecture shifts in Task 6.

10. Add render targets for future exporters

Task 6 is not Task 7, but it should prepare for it.

Support:

render_mode="review"

render_mode="rag"

The prompt can remain similar for now, but the render target should be explicit.

Review render

Readable, fuller markdown for human QA.

RAG render

More compact, retrieval-oriented markdown.

Task 7 can later move these into exporters, but Task 6 should support the distinction now.

11. Maintain backward compatibility in component2/main.py

The current Step 3 flow is:

invalidation filter

parse/sync

llm_processor.py pass-1 markdown

assemble markdown

reducer to RAG-ready markdown 

pipeline

Task 6 must not break that path when feature flags are off.

Add feature flags

enable_knowledge_events

enable_evidence_linking

enable_rule_cards

enable_new_markdown_render

preserve_legacy_markdown

Safe default behavior

For initial rollout:

preserve_legacy_markdown=True

enable_new_markdown_render=False

That means:

old flow still works

new extraction/render modes can be adopted incrementally

12. Required refactor of llm_processor.py
Recommended internal structure
1. imports
2. model/provider resolution helpers
3. system prompts
4. prompt builders
5. parse helpers
6. generic provider call
7. knowledge_extract public APIs
8. markdown_render public APIs
9. legacy_markdown compatibility APIs
10. debug writers
11. legacy assembly helpers

Do not keep one giant prompt-specific file.

Concrete public API to expose

The refactored llm_processor.py should expose at least:

def build_knowledge_extract_prompt(...)
def build_markdown_render_prompt(...)
def parse_knowledge_extraction(...)
def parse_markdown_render_result(...)

async def process_chunk_knowledge_extract(...)
async def process_chunks_knowledge_extract(...)

def process_rule_cards_markdown_render(...)

async def process_chunk_legacy_markdown(...)
async def process_chunks_legacy_markdown(...)

def write_llm_debug(...)

Optional:

def assemble_legacy_video_markdown(...)
Prompt requirements
A. Knowledge extraction prompt

The prompt must:

use transcript + compact visual context

request JSON only

enforce atomic extraction

forbid freeform lesson summaries

avoid visual narration bloat

This is aligned with the redesign brief. 

Response: Visual Decoding Review

B. Markdown render prompt

The prompt must:

consume normalized RuleCard + EvidenceRef

produce readable markdown only

not invent rules

not restitch the original lesson chronology

keep sections like:

rule

conditions

invalidation

exceptions

visual evidence

Suggested data contract for render mode

When rendering markdown, pass a structured JSON-like payload containing:

{
  "lesson_id": "...",
  "lesson_title": "...",
  "render_mode": "review",
  "rule_cards": [...],
  "evidence_refs": [...]
}

Do not feed raw chunk transcript text to render mode.

Tests to implement

Create tests/test_llm_processor.py.

Required tests
1. Legacy prompt still builds

Ensure build_legacy_markdown_prompt(...) still produces the current expected structure:

<previous_visual_state>

<transcript>

<visual_events> 

FRAMEWORK_MODULES

2. Knowledge extract prompt builds correctly

Ensure transcript and compact visual summaries are present, and no legacy literal-scribe instructions leak in.

3. Markdown render prompt builds correctly

Ensure it uses RuleCard/EvidenceRef input, not chunk transcript input.

4. Generic provider call handles structured schemas

Mock provider response and verify:

parsing works

usage records propagate

5. Knowledge extraction processing works

Mock one chunk, mock provider JSON, verify ChunkExtractionResult is returned.

6. Markdown render processing works

Mock rule cards/evidence refs and verify MarkdownRenderResult is returned.

7. Legacy processing still works

Mock legacy markdown response and verify EnrichedMarkdownChunk still parses.

8. Debug writing works for multiple modes

Ensure debug file writes correctly for extraction and render rows.

9. Backward compatibility

When new flags are disabled, component2/main.py still follows the old markdown path.

Important implementation rules
Do

reuse provider transport logic

make mode explicit everywhere

keep extraction and rendering separate

keep legacy path available during migration

use structured response schemas

keep debug output per mode

Do not

do not let render mode consume raw lesson replay data

do not let extraction mode output prose markdown

do not keep one global prompt for all tasks

do not break old EnrichedMarkdownChunk flow immediately

do not duplicate provider-calling code unnecessarily

Definition of done

Task 6 is complete when:

pipeline/component2/llm_processor.py supports:

knowledge_extract

markdown_render

legacy markdown compatibility

it uses mode-specific prompts

it uses mode-specific parse targets

it reuses the provider layer for structured output

it supports debug writing for extraction/render flows

component2/main.py can choose the new or legacy path via feature flags

the old markdown pipeline still works when legacy mode is enabled

Copy-paste instruction for the coding agent
Implement Task 6 only: refactor pipeline/component2/llm_processor.py into a multi-mode LLM processor.

Goal:
Support two explicit modes:
1. knowledge_extract -> structured JSON only
2. markdown_render -> readable markdown from RuleCards + EvidenceRefs

Keep legacy markdown behavior available during migration.

Current state:
- llm_processor.py is a Pass 1 literal-scribe markdown synthesizer based on LessonChunk -> EnrichedMarkdownChunk
- it uses build_user_prompt(chunk), _call_provider(...), process_chunks(...), assemble_video_markdown(...), and write_llm_debug(...)
- providers.py already supports provider/model resolution and schema-based structured output

Requirements:
1. Keep and generalize provider/model resolution into mode-aware helpers
2. Replace one global system prompt with:
   - KNOWLEDGE_EXTRACT_SYSTEM_PROMPT
   - MARKDOWN_RENDER_SYSTEM_PROMPT
   - optional LEGACY_LITERAL_SCRIBE_SYSTEM_PROMPT
3. Split prompt builders into:
   - build_knowledge_extract_prompt(...)
   - build_markdown_render_prompt(...)
   - build_legacy_markdown_prompt(...)
4. Add mode-specific parse helpers:
   - parse_knowledge_extraction(...)
   - parse_markdown_render_result(...)
   - parse_legacy_enriched_markdown_chunk(...)
5. Add a generic _call_provider_for_mode(...) that reuses get_provider(...).generate_text(...)
6. Expose public APIs:
   - process_chunk_knowledge_extract(...)
   - process_chunks_knowledge_extract(...)
   - process_rule_cards_markdown_render(...)
   - process_chunk_legacy_markdown(...)
   - process_chunks_legacy_markdown(...)
7. Keep concurrency pattern reusable
8. Generalize debug writing for extraction and render modes
9. Rename legacy assembly to assemble_legacy_video_markdown(...)
10. Do not let new markdown_render mode use raw transcript replay
11. Integrate into component2/main.py behind feature flags:
   - preserve_legacy_markdown
   - enable_new_markdown_render

Do not:
- use one prompt for all modes
- let extraction mode return prose markdown
- let render mode reconstruct the lesson from raw chunks
- break the existing legacy markdown path by default

If you want, I can do Task 7 next in the same exact format.