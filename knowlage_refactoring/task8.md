Below is the full Task 8 you can copy for the GPT-5.4 coding agent.

Confidence: High

Task 8 should be implemented as a cross-cutting policy layer, not a new top-level CLI stage. Your current main.py already runs the structured stages in sequence — Step 3.2b knowledge events, Step 4 evidence linking, Step 4b rule cards, and the exporter stage — so Task 8 should plug into those stages rather than introducing another top-level step. 

main

 

main


Your path contracts already define the structured artifact paths and exporter outputs, and the existing feature flags already cover the staged rollout, so Task 8 should mostly add shared policy helpers and config, not a new CLI surface. 

contracts

 

contracts


This also fits the pipeline docs: Step 2 writes rich dense_analysis.json, and Step 3 reads that plus the VTT, writes filtered_visual_events.json, chunk debug output, legacy markdown artifacts, and final markdown. Task 8’s job is to preserve the richness of that first-pass visual extraction while compressing its downstream use. 

pipeline

 

pipeline

Task 8 — Keep Visual Extraction Rich, but Compress Its Downstream Use
Goal

Implement a shared visual compaction policy across Steps 3–7 so that:

the first pass remains rich and loss-minimizing

dense/frame-level provenance is preserved

downstream artifacts stay compact and retrieval-safe

frame-by-frame visual narration does not leak into:

knowledge_events.json

evidence_index.json

rule_cards.json

review_markdown.md

rag_ready.md

This task is not a new top-level stage.
It is a cross-cutting implementation layer that all structured stages must use.

Why this task exists

You explicitly want to avoid rerunning video recognition later.

So the correct strategy is:

Preserve richly at the source

Keep in the first pass:

timestamps

frame ids

dense visual classifications

annotations

entities

example types

screenshot candidates

chart/object relations

Compress only downstream

After first-pass extraction:

use compact summaries for extraction prompts

use compact summaries in evidence refs

use one short visual summary in rule cards

use only small review/RAG evidence notes in markdown

In other words:

rich source, compact downstream projection

Deliverables

Create:

pipeline/component2/visual_compaction.py

tests/test_visual_compaction.py

Update:

pipeline/component2/knowledge_builder.py

pipeline/component2/evidence_linker.py

pipeline/component2/rule_reducer.py

pipeline/component2/llm_processor.py

pipeline/component2/exporters.py

config.py

test_config.py

Optional:

pipeline/component2/visual_policy_debug.py if you want to separate debug-only helpers

High-level architecture

Task 8 should define four visual representations.

Representation A — raw source representation

This stays as-is in:

dense_analysis.json

frames_dense/frame_*.json

filtered_visual_events.json

chunk visual_events

This is the high-fidelity layer.

Representation B — extraction-context representation

Used only when sending visual context into Step 3 extraction prompts.

This should be:

compact

concept-focused

no frame-by-frame replay

max 3–5 summaries per chunk

Representation C — evidence representation

Used in EvidenceRef.

This should preserve:

timestamps

frame ids

screenshot paths if derivable

example role

compact visual summary

raw visual event ids

But it should not preserve giant raw blobs like full current_state, visual_facts, or previous_visual_state inside the final JSON.

Representation D — rule/export representation

Used in:

RuleCard.visual_summary

review_markdown.md

rag_ready.md

This should be:

one short summary per rule by default

small number of bullets at most in review markdown

even more compact in RAG markdown

Functional requirements
1. Create pipeline/component2/visual_compaction.py

This module is the shared policy layer for all downstream visual handling.

It should contain:

configuration defaults

low-value/noise filtering

compact summary builders

provenance extractors

screenshot candidate derivation

repetition guards

stage-specific render helpers

This module should be imported by:

knowledge_builder.py

evidence_linker.py

rule_reducer.py

llm_processor.py

exporters.py

2. Define a shared visual compaction config

Create an internal config model.

Suggested structure:

from dataclasses import dataclass


@dataclass(frozen=True)
class VisualCompactionConfig:
    max_visual_summaries_for_extract: int = 5
    max_annotations_per_visual: int = 3
    max_entities_per_visual: int = 6
    max_change_summaries_per_candidate: int = 3
    max_frames_per_evidence_ref: int = 12
    max_screenshot_paths_per_evidence_ref: int = 4
    max_visual_summary_chars_evidence: int = 240
    max_visual_summary_chars_rule: int = 180
    max_visual_bullets_review: int = 2
    max_visual_bullets_rag: int = 1
    include_screenshot_candidates: bool = True
    store_previous_visual_state_in_debug_only: bool = True
    store_raw_visual_blobs_in_structured_outputs: bool = False
Notes

keep this config internal and simple

it should control the behavior consistently across all downstream stages

3. Add config defaults in config.py

The existing config.py already manages pipeline-level defaults such as provider/model values and step settings, so Task 8 should add small config knobs there, not new CLI flags. 

contracts

Add defaults such as:

DEFAULT_VISUAL_EXTRACT_MAX_SUMMARIES = 5
DEFAULT_VISUAL_EVIDENCE_SUMMARY_MAX_CHARS = 240
DEFAULT_VISUAL_RULE_SUMMARY_MAX_CHARS = 180
DEFAULT_VISUAL_REVIEW_MAX_BULLETS = 2
DEFAULT_VISUAL_RAG_MAX_BULLETS = 1
DEFAULT_VISUAL_INCLUDE_SCREENSHOT_CANDIDATES = True
DEFAULT_VISUAL_STORE_RAW_BLOBS = False

And expose config keys like:

visual_extract_max_summaries

visual_evidence_summary_max_chars

visual_rule_summary_max_chars

visual_review_max_bullets

visual_rag_max_bullets

visual_include_screenshot_candidates

visual_store_raw_blobs

Important

Do not add more CLI flags unless absolutely necessary.

This should be config-driven, not CLI-driven.

4. Add raw provenance extractors

Implement helpers to preserve raw provenance safely.

Suggested functions:

def extract_frame_key(event: dict) -> str | None:
    ...

def extract_timestamp_seconds(event: dict) -> float | None:
    ...

def build_raw_visual_event_id(frame_key: str | None) -> str | None:
    ...

def extract_visual_type(event: dict) -> str:
    ...

def extract_example_type(event: dict) -> str | None:
    ...
Rules

These helpers should be used everywhere downstream instead of ad hoc raw dict access.

5. Add screenshot candidate derivation

Implement:

def build_screenshot_candidate_paths(
    video_root: Path,
    frame_key: str | None,
) -> list[str]:
    ...
Behavior

Try to derive screenshot candidates from known project layout:

frames_dense/frame_<frame_key>.jpg

optionally llm_queue/<something> if stable and if file exists

The pipeline docs confirm the existence of frames_dense/frame_*.jpg, llm_queue/*.jpg, dense_analysis.json, and later structured outputs. 

pipeline

 

pipeline

Rules

include only paths that exist

cap the number of screenshot candidates

keep paths only in EvidenceRef, not in RuleCard or markdown text

6. Add low-value visual-noise filtering helpers

Implement:

def is_low_value_visual_phrase(text: str) -> bool:
    ...

def is_layout_or_ui_noise(text: str) -> bool:
    ...

def is_frame_by_frame_motion_narration(text: str) -> bool:
    ...
Purpose

Remove phrases like:

decorative UI layout comments

repeated “the chart moves slightly…” wording

layout-only descriptions

stylistic or cinematic details

duplicate chart-state narration with no teaching meaning

Important

This is not about deleting raw source data.
It is about preventing leakage into structured artifacts.

7. Add normalized text extraction helpers

Implement:

def normalize_visual_text(text: str) -> str:
    ...

def dedupe_visual_phrases(items: list[str]) -> list[str]:
    ...

def clamp_text_length(text: str, max_chars: int) -> str:
    ...

These helpers must be reused across all stages.

8. Add stage-specific compaction helpers

Task 8 should define separate helpers for each downstream use case.

A. For Step 3 extraction prompts

Implement:

def summarize_visual_event_for_extraction(event: dict, cfg: VisualCompactionConfig) -> str | None:
    ...

def summarize_visual_events_for_extraction(
    visual_events: list[dict],
    cfg: VisualCompactionConfig,
) -> list[str]:
    ...
Rules

keep only teaching-relevant information

prefer:

visual_representation_type

example_type

change_summary

visible annotation text

trading-relevant interpretation

extracted entities if useful

return max N compact summaries

do not return raw visual blobs

B. For Step 4 evidence refs

Implement:

def summarize_visual_candidate_for_evidence(
    candidate,
    cfg: VisualCompactionConfig,
) -> str | None:
    ...

def build_evidence_provenance_payload(
    candidate,
    video_root: Path | None,
    cfg: VisualCompactionConfig,
) -> dict:
    ...
Rules

Evidence must preserve:

timestamps

frame ids

raw visual event ids

screenshot paths

visual type

example role

compact visual summary

But final EvidenceRef must not embed:

full current_state

full previous_visual_state

giant visual_facts

long annotations list

giant entity dumps

If raw rich data must survive for debugging, put it in debug artifacts only.

C. For Step 5 rule cards

Implement:

def summarize_evidence_for_rule_card(
    evidence_refs: list,
    cfg: VisualCompactionConfig,
) -> str | None:
    ...
Rules

choose one best evidence summary by default

optionally merge two if clearly complementary

max one short summary string

do not carry forward raw ids or screenshots into RuleCard.visual_summary

Also add:

def trim_rule_card_visual_refs(
    evidence_refs: list[str],
    max_refs: int = 3,
) -> list[str]:
    ...

Because RuleCard.evidence_refs can stay richer than markdown, but should still be bounded.

D. For Step 7 exporters

Implement:

def summarize_evidence_for_review_markdown(
    evidence_refs: list,
    cfg: VisualCompactionConfig,
) -> list[str]:
    ...

def summarize_evidence_for_rag_markdown(
    evidence_refs: list,
    cfg: VisualCompactionConfig,
) -> list[str]:
    ...
Rules

For review markdown:

max 2 bullets by default

enough for a human reviewer

For RAG markdown:

max 1 bullet or short line by default

retrieval-focused only

No frame-by-frame narration allowed.

9. Add structured-output guards

Implement:

def strip_raw_visual_blobs_from_metadata(metadata: dict) -> dict:
    ...

def assert_no_raw_visual_blob_leak(obj) -> None:
    ...
Purpose

Before writing:

knowledge_events.json

evidence_index.json

rule_cards.json

run guards to ensure no large raw visual blobs leaked into structured outputs.

Forbidden downstream payload examples

Do not allow large copies of:

current_state

previous_visual_state

visual_facts

full frame extraction JSON

large OCR/annotation dumps

Allowed:

frame ids

timestamps

screenshot paths

compact summaries

concept hints

example types

small provenance fields

10. Integrate into Step 3 (knowledge_builder.py)

Update Task 3 implementation so that:

Allowed in final KnowledgeEvent.metadata

chunk_index

chunk_start_time_seconds

chunk_end_time_seconds

transcript_line_count

candidate_visual_frame_keys

candidate_visual_types

candidate_example_types

Not allowed in final KnowledgeEvent.metadata

raw visual_events

raw previous_visual_state

full annotation arrays

full extracted-entity blobs

If needed for QA:

keep them only in knowledge_debug.json

Required change

Use visual_compaction.summarize_visual_events_for_extraction(...) in Step 3 prompt construction instead of ad hoc summarization.

11. Integrate into Step 4 (evidence_linker.py)

Update Task 4 implementation so that:

Preserve in final EvidenceRef

timestamp_start

timestamp_end

frame_ids

screenshot_paths

visual_type

example_role

compact_visual_summary

raw_visual_event_ids

source_event_ids

Do not preserve in final EvidenceRef

full current_state

full previous_visual_state

raw dense-analysis frame payloads

long visual_facts

If you need them:

store in evidence_debug.json only

Required change

Use:

summarize_visual_candidate_for_evidence(...)

build_evidence_provenance_payload(...)

12. Integrate into Step 5 (rule_reducer.py)

Update Task 5 implementation so that:

RuleCard.visual_summary

must be produced only from compact evidence summaries, never from raw visual payloads.

RuleCard.evidence_refs

may keep ids, but:

cap count if necessary

do not duplicate raw visual provenance here

Required change

Use:

summarize_evidence_for_rule_card(...)

trim_rule_card_visual_refs(...)

13. Integrate into Task 6 (llm_processor.py)

Update Task 6 implementation so that:

In knowledge_extract mode

Prompt builder uses only compact visual summaries from visual_compaction.py

In markdown_render mode

Do not pass raw transcript or raw visual event data.
Only pass:

rule cards

evidence refs

compact visual summaries already prepared

Important

Task 6 must never re-expand visual richness once Task 8 is in place.

14. Integrate into Task 7 (exporters.py)

Update Task 7 implementation so that:

Review markdown

Uses:

summarize_evidence_for_review_markdown(...)

RAG markdown

Uses:

summarize_evidence_for_rag_markdown(...)

Important

This stage must be the final gate that prevents visual spam from leaking into markdown.

15. Add a repetition and leakage validator

Implement:

def detect_visual_spam_lines(lines: list[str]) -> list[str]:
    ...

def validate_markdown_visual_compaction(markdown: str) -> list[str]:
    ...
Purpose

Used in tests and optionally in exporters.

Detect

repeated near-duplicate visual bullets

frame-by-frame narration patterns

repeated “price moved / touched / moved / touched” style lines

excessive mention of frame/time details in final markdown

Use

in tests

optionally as a warning logger in exporters

16. Add a small visual compaction debug path

Optional but recommended:

write output_intermediate/<lesson>.visual_compaction_debug.json

This can include:

candidate summary before/after compaction

dropped low-value phrases

kept screenshot candidates

blocked raw fields

This is optional, but useful while tuning.

17. Do not add a new top-level CLI flag unless necessary

Because the current pipeline already has staged flags for:

knowledge events

evidence linking

rule cards

exporters

new markdown render 

contracts

Task 8 should preferably be:

always active when structured stages run

controlled by config defaults in config.py

If you absolutely need a flag, use something like:

enable_visual_compaction_debug

But do not create a broad “turn Task 8 on/off” switch unless there is a strong operational reason.

Suggested module API

Expose at least these functions in visual_compaction.py:

def summarize_visual_events_for_extraction(...)
def summarize_visual_candidate_for_evidence(...)
def summarize_evidence_for_rule_card(...)
def summarize_evidence_for_review_markdown(...)
def summarize_evidence_for_rag_markdown(...)
def build_screenshot_candidate_paths(...)
def strip_raw_visual_blobs_from_metadata(...)
def assert_no_raw_visual_blob_leak(...)
def validate_markdown_visual_compaction(...)

Keep helper functions small and testable.

Tests to implement

Create tests/test_visual_compaction.py.

Required tests
1. Raw richness remains preserved upstream

Given sample dense/frame visual input, verify Task 8 helpers do not mutate or truncate the source objects.

2. Extraction summaries are compact

Given several noisy visual events, verify:

max N summaries returned

low-value phrases removed

summaries are short

3. Evidence summaries preserve provenance

Verify EvidenceRef-bound summary logic keeps:

timestamps

frame ids

screenshot paths
but does not include raw blobs.

4. Rule card summaries are compact

Verify RuleCard.visual_summary is short and does not contain frame-by-frame narration.

5. Review markdown visual bullets are bounded

Ensure at most configured number of bullets appear.

6. RAG markdown visual bullets are bounded

Ensure only very compact visual evidence appears.

7. Raw blob leakage is blocked

Given metadata with current_state / previous_visual_state / visual_facts, verify guards strip or reject it before final structured write.

8. Repetition validator catches spam

Given repeated frame-by-frame style text, ensure validate_markdown_visual_compaction(...) flags it.

9. Screenshot candidates are derived conservatively

Only existing files should be included, and count should be capped.

10. Integration regression

Run a small fixture through Step 3 → Step 4 → Step 5 → exporter helpers and verify:

frame provenance still exists in evidence

rule card summary is compact

final markdown has no visual spam

Important implementation rules
Do

preserve first-pass richness

compress downstream use

centralize compaction logic in one shared module

keep provenance strong in evidence

keep final summaries compact

use config defaults instead of many new flags

keep raw rich visual data in debug/artifact layers, not final structured outputs

Do not

do not weaken Step 2 or filtered visual output

do not drop frame ids or timestamps

do not store full visual blobs in KnowledgeEvent, EvidenceRef, or RuleCard

do not let exporters recreate raw visual narration

do not reintroduce frame-by-frame detail through LLM render mode

Definition of done

Task 8 is complete when:

pipeline/component2/visual_compaction.py exists

Step 3 uses compact visual summaries for extraction prompts

Step 4 preserves evidence provenance but writes compact EvidenceRefs

Step 5 produces compact RuleCard.visual_summary

Step 7 exporters use compact visual evidence notes only

raw first-pass richness remains available upstream

final structured outputs contain no leaked raw visual blobs

final markdown contains no frame-by-frame visual spam

Copy-paste instruction for the coding agent
Implement Task 8 only: keep visual extraction rich, but compress its downstream use.

Create:
- pipeline/component2/visual_compaction.py
- tests/test_visual_compaction.py

Update:
- knowledge_builder.py
- evidence_linker.py
- rule_reducer.py
- llm_processor.py
- exporters.py
- config.py
- test_config.py

Goal:
Preserve the full richness of first-pass visual extraction, but enforce compact downstream visual representations in:
- knowledge_events.json
- evidence_index.json
- rule_cards.json
- review_markdown.md
- rag_ready.md

Requirements:
1. Create a shared VisualCompactionConfig with limits for:
   - extraction summaries
   - evidence summary length
   - rule summary length
   - review/rag visual bullet counts
   - screenshot candidate counts
2. Add config defaults in config.py, not new broad CLI flags
3. Implement helpers for:
   - screenshot candidate path derivation
   - low-value visual-noise filtering
   - normalized text cleanup
   - extraction-context summaries
   - evidence summaries
   - rule-card summaries
   - review/rag markdown summaries
   - raw visual blob stripping
   - visual spam validation
4. Step 3 must use compact visual summaries for extraction prompts
5. Step 4 must preserve provenance in EvidenceRef but not embed raw visual blobs
6. Step 5 must build RuleCard.visual_summary only from compact evidence summaries
7. Task 6 markdown_render mode must consume only structured/compacted visual info
8. Task 7 exporters must use compact visual summaries only
9. Add guards so final structured outputs never contain raw current_state / previous_visual_state / visual_facts blobs
10. Add tests covering compaction, provenance preservation, screenshot derivation, leakage blocking, and no visual spam in final markdown

Do not:
- reduce richness in dense_analysis.json or filtered_visual_events.json
- drop frame ids/timestamps from evidence
- store raw visual blobs in final structured artifacts
- let frame-by-frame narration leak into rule cards or exported markdown

The only caveat is that a few older uploads have expired on my side, but the key current files for Task 8 were available, so this plan matches the current staged pipeline and path contracts.

and more details for you
Yes — and I recommend it.

**Confidence: High**

For Task 8, the more exact the function behavior is, the less chance the coding agent will implement “compaction” too loosely and accidentally lose important provenance or keep too much noise.

Below is a **more exact implementation spec** for the main functions in `visual_compaction.py` and how they should be called from Steps 3–7.

---

# `pipeline/component2/visual_compaction.py`

## 1. Config object

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
import re


@dataclass(frozen=True)
class VisualCompactionConfig:
    max_visual_summaries_for_extract: int = 5
    max_annotations_per_visual: int = 3
    max_entities_per_visual: int = 6
    max_change_summaries_per_candidate: int = 3
    max_frames_per_evidence_ref: int = 12
    max_screenshot_paths_per_evidence_ref: int = 4
    max_visual_summary_chars_evidence: int = 240
    max_visual_summary_chars_rule: int = 180
    max_visual_bullets_review: int = 2
    max_visual_bullets_rag: int = 1
    include_screenshot_candidates: bool = True
    store_previous_visual_state_in_debug_only: bool = True
    store_raw_visual_blobs_in_structured_outputs: bool = False
```

---

## 2. Low-level extraction helpers

These should be used everywhere instead of raw dict access.

```python
def extract_frame_key(event: dict[str, Any]) -> str | None:
    value = event.get("frame_key")
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def extract_timestamp_seconds(event: dict[str, Any]) -> float | None:
    value = event.get("timestamp_seconds")
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def build_raw_visual_event_id(frame_key: str | None) -> str | None:
    if not frame_key:
        return None
    return f"ve_raw_{frame_key}"


def extract_visual_type(event: dict[str, Any]) -> str:
    value = event.get("visual_representation_type")
    if not value:
        return "unknown"
    return str(value).strip() or "unknown"


def extract_example_type(event: dict[str, Any]) -> str | None:
    value = event.get("example_type")
    if value is None:
        return None
    value = str(value).strip()
    return value or None
```

---

## 3. Text cleanup and filtering

This is the base layer. Every summary builder should call these.

```python
_UI_NOISE_PATTERNS = [
    r"\btoolbar\b",
    r"\bpanel\b",
    r"\bwindow\b",
    r"\bmenu\b",
    r"\blayout\b",
    r"\bbutton\b",
    r"\bicon\b",
    r"\bcolor\b",
    r"\bborder\b",
    r"\bbackground\b",
]

_FRAME_BY_FRAME_PATTERNS = [
    r"\bslightly moves\b",
    r"\bthen moves\b",
    r"\bcontinues moving\b",
    r"\bnext frame\b",
    r"\bin this frame\b",
    r"\bchart shifts a little\b",
    r"\bsmall movement\b",
]

_LOW_VALUE_PATTERNS = _UI_NOISE_PATTERNS + _FRAME_BY_FRAME_PATTERNS


def normalize_visual_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    text = text.replace(" ,", ",").replace(" .", ".")
    return text


def is_layout_or_ui_noise(text: str) -> bool:
    text_norm = normalize_visual_text(text).lower()
    return any(re.search(p, text_norm) for p in _UI_NOISE_PATTERNS)


def is_frame_by_frame_motion_narration(text: str) -> bool:
    text_norm = normalize_visual_text(text).lower()
    return any(re.search(p, text_norm) for p in _FRAME_BY_FRAME_PATTERNS)


def is_low_value_visual_phrase(text: str) -> bool:
    text_norm = normalize_visual_text(text)
    if not text_norm:
        return True
    return (
        is_layout_or_ui_noise(text_norm)
        or is_frame_by_frame_motion_narration(text_norm)
        or len(text_norm) < 12
    )


def dedupe_visual_phrases(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        norm = normalize_visual_text(item).lower()
        if not norm or norm in seen:
            continue
        seen.add(norm)
        result.append(normalize_visual_text(item))
    return result


def clamp_text_length(text: str, max_chars: int) -> str:
    text = normalize_visual_text(text)
    if len(text) <= max_chars:
        return text
    trimmed = text[: max_chars - 1].rstrip()
    if " " in trimmed:
        trimmed = trimmed.rsplit(" ", 1)[0]
    return trimmed + "…"
```

---

## 4. Pull the meaningful visual fields

This is the critical part. Instead of dumping the whole event, selectively collect high-value pieces.

```python
def _extract_visible_annotations(event: dict[str, Any], cfg: VisualCompactionConfig) -> list[str]:
    current_state = event.get("current_state") or {}
    annotations = current_state.get("visible_annotations") or []
    out: list[str] = []

    for item in annotations[: cfg.max_annotations_per_visual]:
        if isinstance(item, str):
            text = item
        elif isinstance(item, dict):
            text = item.get("text") or item.get("label") or ""
        else:
            text = ""
        text = normalize_visual_text(text)
        if text and not is_low_value_visual_phrase(text):
            out.append(text)

    return dedupe_visual_phrases(out)


def _extract_entities(event: dict[str, Any], cfg: VisualCompactionConfig) -> list[str]:
    extracted_entities = event.get("extracted_entities") or {}
    out: list[str] = []

    if isinstance(extracted_entities, dict):
        for _, value in extracted_entities.items():
            if isinstance(value, list):
                for item in value:
                    if len(out) >= cfg.max_entities_per_visual:
                        break
                    if isinstance(item, str):
                        text = item
                    elif isinstance(item, dict):
                        text = item.get("text") or item.get("label") or item.get("name") or ""
                    else:
                        text = ""
                    text = normalize_visual_text(text)
                    if text and not is_low_value_visual_phrase(text):
                        out.append(text)
            if len(out) >= cfg.max_entities_per_visual:
                break

    return dedupe_visual_phrases(out)
```

---

## 5. Step 3 extraction-context summaries

These are the summaries sent into the LLM extraction prompt. They must be compact and concept-focused.

```python
def summarize_visual_event_for_extraction(
    event: dict[str, Any],
    cfg: VisualCompactionConfig,
) -> str | None:
    visual_type = extract_visual_type(event)
    example_type = extract_example_type(event)

    parts: list[str] = []

    if visual_type != "unknown":
        parts.append(visual_type.replace("_", " "))

    if example_type:
        parts.append(example_type.replace("_", " "))

    change_summary = normalize_visual_text(str(event.get("change_summary") or ""))
    if change_summary and not is_low_value_visual_phrase(change_summary):
        parts.append(change_summary)

    tri = normalize_visual_text(str(event.get("trading_relevant_interpretation") or ""))
    if tri and not is_low_value_visual_phrase(tri):
        parts.append(tri)

    annotations = _extract_visible_annotations(event, cfg)
    if annotations:
        parts.append("annotations: " + "; ".join(annotations[: cfg.max_annotations_per_visual]))

    entities = _extract_entities(event, cfg)
    if entities:
        parts.append("entities: " + "; ".join(entities[: cfg.max_entities_per_visual]))

    parts = dedupe_visual_phrases(parts)
    parts = [p for p in parts if not is_low_value_visual_phrase(p)]

    if not parts:
        return None

    summary = ". ".join(parts)
    summary = clamp_text_length(summary, cfg.max_visual_summary_chars_evidence)
    return summary


def summarize_visual_events_for_extraction(
    visual_events: list[dict[str, Any]],
    cfg: VisualCompactionConfig,
) -> list[str]:
    summaries: list[str] = []
    for event in visual_events:
        summary = summarize_visual_event_for_extraction(event, cfg)
        if summary:
            summaries.append(summary)

    summaries = dedupe_visual_phrases(summaries)
    return summaries[: cfg.max_visual_summaries_for_extract]
```

### How Step 3 should call it

In `knowledge_builder.py`:

```python
visual_summaries = summarize_visual_events_for_extraction(chunk.visual_events, cfg)
prompt = build_knowledge_extraction_prompt(chunk=chunk, visual_summaries=visual_summaries)
```

---

## 6. Screenshot candidate derivation

```python
def build_screenshot_candidate_paths(
    video_root: Path,
    frame_key: str | None,
    cfg: VisualCompactionConfig,
) -> list[str]:
    if not cfg.include_screenshot_candidates or not frame_key:
        return []

    candidates = [
        video_root / "frames_dense" / f"frame_{frame_key}.jpg",
        video_root / "frames_dense" / f"frame_{frame_key}.png",
        video_root / "llm_queue" / f"{frame_key}.jpg",
        video_root / "llm_queue" / f"{frame_key}.png",
    ]

    existing = [str(p) for p in candidates if p.exists()]
    return existing[: cfg.max_screenshot_paths_per_evidence_ref]
```

---

## 7. Evidence-level compaction

This is the summary that ends up in `EvidenceRef.compact_visual_summary`.

```python
def summarize_visual_candidate_for_evidence(
    candidate,
    cfg: VisualCompactionConfig,
) -> str | None:
    phrases: list[str] = []

    if getattr(candidate, "visual_type", None) and candidate.visual_type != "unknown":
        phrases.append(str(candidate.visual_type).replace("_", " "))

    if getattr(candidate, "example_role", None) and candidate.example_role != "unknown":
        phrases.append(str(candidate.example_role).replace("_", " "))

    for event in getattr(candidate, "visual_events", [])[: cfg.max_change_summaries_per_candidate]:
        change_summary = normalize_visual_text(str(getattr(event, "change_summary", "") or ""))
        if change_summary and not is_low_value_visual_phrase(change_summary):
            phrases.append(change_summary)

    concept_hints = getattr(candidate, "concept_hints", []) or []
    if concept_hints:
        phrases.append("concepts: " + ", ".join(dedupe_visual_phrases(concept_hints)[:3]))

    phrases = dedupe_visual_phrases(phrases)
    phrases = [p for p in phrases if not is_low_value_visual_phrase(p)]

    if not phrases:
        return None

    summary = ". ".join(phrases)
    return clamp_text_length(summary, cfg.max_visual_summary_chars_evidence)
```

### Evidence provenance payload

```python
def build_evidence_provenance_payload(
    candidate,
    video_root: Path | None,
    cfg: VisualCompactionConfig,
) -> dict[str, Any]:
    frame_keys = list(dict.fromkeys(getattr(candidate, "frame_keys", []) or []))
    frame_keys = frame_keys[: cfg.max_frames_per_evidence_ref]

    screenshot_paths: list[str] = []
    if video_root is not None:
        for frame_key in frame_keys:
            screenshot_paths.extend(build_screenshot_candidate_paths(video_root, frame_key, cfg))
    screenshot_paths = list(dict.fromkeys(screenshot_paths))[: cfg.max_screenshot_paths_per_evidence_ref]

    raw_ids = [build_raw_visual_event_id(k) for k in frame_keys]
    raw_ids = [x for x in raw_ids if x]

    return {
        "frame_ids": frame_keys,
        "screenshot_paths": screenshot_paths,
        "raw_visual_event_ids": raw_ids,
    }
```

### How Step 4 should use it

In `evidence_linker.py`, when building `EvidenceRef`:

```python
prov = build_evidence_provenance_payload(candidate, video_root=video_root, cfg=cfg)

evidence_ref = EvidenceRef(
    evidence_id=...,
    lesson_id=lesson_id,
    timestamp_start=...,
    timestamp_end=...,
    frame_ids=prov["frame_ids"],
    screenshot_paths=prov["screenshot_paths"],
    raw_visual_event_ids=prov["raw_visual_event_ids"],
    visual_type=candidate.visual_type,
    example_role=infer_example_role(candidate, linked_events),
    compact_visual_summary=summarize_visual_candidate_for_evidence(candidate, cfg),
    ...
)
```

---

## 8. Rule-card compaction

A rule card should get only one short visual summary.

```python
def summarize_evidence_for_rule_card(
    evidence_refs: list[Any],
    cfg: VisualCompactionConfig,
) -> str | None:
    phrases = [
        normalize_visual_text(str(getattr(ev, "compact_visual_summary", "") or ""))
        for ev in evidence_refs
    ]
    phrases = [p for p in phrases if p and not is_low_value_visual_phrase(p)]
    phrases = dedupe_visual_phrases(phrases)

    if not phrases:
        return None

    best = phrases[0]
    return clamp_text_length(best, cfg.max_visual_summary_chars_rule)


def trim_rule_card_visual_refs(
    evidence_refs: list[str],
    max_refs: int = 3,
) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for ref in evidence_refs:
        if not ref or ref in seen:
            continue
        seen.add(ref)
        result.append(ref)
        if len(result) >= max_refs:
            break
    return result
```

### How Step 5 should call it

```python
rule.visual_summary = summarize_evidence_for_rule_card(candidate.linked_evidence, cfg)
rule.evidence_refs = trim_rule_card_visual_refs([e.evidence_id for e in candidate.linked_evidence])
```

---

## 9. Export compaction

### Review markdown

```python
def summarize_evidence_for_review_markdown(
    evidence_refs: list[Any],
    cfg: VisualCompactionConfig,
) -> list[str]:
    phrases = [
        normalize_visual_text(str(getattr(ev, "compact_visual_summary", "") or ""))
        for ev in evidence_refs
    ]
    phrases = [p for p in phrases if p and not is_low_value_visual_phrase(p)]
    phrases = dedupe_visual_phrases(phrases)
    phrases = [clamp_text_length(p, cfg.max_visual_summary_chars_rule) for p in phrases]
    return phrases[: cfg.max_visual_bullets_review]
```

### RAG markdown

```python
def summarize_evidence_for_rag_markdown(
    evidence_refs: list[Any],
    cfg: VisualCompactionConfig,
) -> list[str]:
    phrases = summarize_evidence_for_review_markdown(evidence_refs, cfg)
    return phrases[: cfg.max_visual_bullets_rag]
```

### How exporters should use it

```python
review_visuals = summarize_evidence_for_review_markdown(linked_evidence, cfg)
rag_visuals = summarize_evidence_for_rag_markdown(linked_evidence, cfg)
```

---

## 10. Raw-blob stripping and guards

This is very important.

```python
_FORBIDDEN_VISUAL_KEYS = {
    "current_state",
    "previous_visual_state",
    "visual_facts",
    "raw_visual_events",
    "dense_analysis_frame",
    "full_annotations",
    "full_extracted_entities",
}


def strip_raw_visual_blobs_from_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    clean: dict[str, Any] = {}
    for key, value in (metadata or {}).items():
        if key in _FORBIDDEN_VISUAL_KEYS:
            continue
        clean[key] = value
    return clean


def assert_no_raw_visual_blob_leak(obj: Any) -> None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in _FORBIDDEN_VISUAL_KEYS:
                raise ValueError(f"Forbidden raw visual blob leaked into structured output: {key}")
            assert_no_raw_visual_blob_leak(value)
    elif isinstance(obj, list):
        for item in obj:
            assert_no_raw_visual_blob_leak(item)
```

### Where to call it

Before writing:

* `knowledge_events.json`
* `evidence_index.json`
* `rule_cards.json`

For example:

```python
payload = collection.model_dump()
assert_no_raw_visual_blob_leak(payload)
output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
```

---

## 11. Final-markdown spam validator

```python
def detect_visual_spam_lines(lines: list[str]) -> list[str]:
    flagged: list[str] = []
    seen_norm: set[str] = set()

    for line in lines:
        norm = normalize_visual_text(line).lower()
        if not norm:
            continue

        repeated = norm in seen_norm
        noisy = is_frame_by_frame_motion_narration(norm)

        if repeated or noisy:
            flagged.append(line)

        seen_norm.add(norm)

    return flagged


def validate_markdown_visual_compaction(markdown: str) -> list[str]:
    lines = [line.strip() for line in markdown.splitlines() if line.strip()]
    return detect_visual_spam_lines(lines)
```

### Where to use it

In `exporters.py` after rendering:

```python
warnings = validate_markdown_visual_compaction(markdown)
if warnings:
    logger.warning("Visual compaction warnings detected: %d", len(warnings))
```

---

# Exact integration changes by file

## `knowledge_builder.py`

Replace any local visual-summary logic with:

```python
from pipeline.component2.visual_compaction import summarize_visual_events_for_extraction
```

and ensure `KnowledgeEvent.metadata` only keeps compact provenance fields, not raw visual blobs.

## `evidence_linker.py`

Use:

* `summarize_visual_candidate_for_evidence`
* `build_evidence_provenance_payload`
* `strip_raw_visual_blobs_from_metadata`

## `rule_reducer.py`

Use:

* `summarize_evidence_for_rule_card`
* `trim_rule_card_visual_refs`

## `llm_processor.py`

In `knowledge_extract` mode, only send:

* compact visual summaries
  not raw visual events.

In `markdown_render` mode, only send:

* structured `RuleCard` + `EvidenceRef`
  not transcript replay or raw visual payloads.

## `exporters.py`

Use:

* `summarize_evidence_for_review_markdown`
* `summarize_evidence_for_rag_markdown`
* `validate_markdown_visual_compaction`

---

# More exact tests I would add

## `tests/test_visual_compaction.py`

### Test 1 — extraction summaries stay compact

Mock 8 noisy visual events and verify:

* only 5 summaries max
* summaries exclude layout/UI noise
* no raw blobs returned

### Test 2 — evidence provenance preserved

Mock a candidate with 20 frame keys and verify:

* frame ids are capped
* raw visual event ids are generated
* screenshot paths only include existing files

### Test 3 — forbidden keys stripped

Pass metadata with `current_state` and `visual_facts` and verify they are removed.

### Test 4 — rule summary stays short

Provide 4 evidence refs and verify only one compact summary is returned.

### Test 5 — review vs rag output differ

Ensure review returns up to 2 bullets, rag only 1.

### Test 6 — spam detection

Give repeated frame-by-frame lines and verify warnings are produced.

---

# My recommendation

Yes — I would add these exact implementations into the Task 8 spec.

That gives the coding agent:

* less room to improvise badly
* clearer reuse points
* a single policy module for all downstream visual handling
* fewer accidental leaks of raw visual payloads

The next best move is to turn this into a **single copy-paste “Task 8 addendum”** for the coding agent.
