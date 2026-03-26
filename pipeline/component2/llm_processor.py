from __future__ import annotations

import asyncio
import json
import os
import re
import time
from pathlib import Path
from typing import Callable

from pydantic import BaseModel, Field, ValidationError

from helpers import config as pipeline_config
from helpers.clients import gemini_batch_client
from helpers.clients.providers import get_provider, resolve_model_for_stage, resolve_provider_for_stage
from pipeline.component2.knowledge_builder import (
    AdaptedChunk,
    ChunkExtractionResult,
    build_knowledge_events_from_extraction_results,
    save_knowledge_debug,
    save_knowledge_events,
)
from pipeline.component2.models import EnrichedMarkdownChunk, LessonChunk
from pipeline.component2 import visual_compaction
from pipeline.component2.visual_compaction import (
    VisualCompactionConfig,
    assert_no_raw_visual_blob_leak,
    from_pipeline_config as visual_compaction_from_pipeline_config,
)
from pipeline.component2.parser import seconds_to_mmss
from pipeline.path_contracts import PipelinePaths
from pipeline.io_utils import atomic_write_json
from pipeline.orchestrator import (
    STAGE_KNOWLEDGE_EXTRACT,
    STAGE_MARKDOWN_RENDER,
    STAGE_RUN_STATUS_FAILED,
    STAGE_RUN_STATUS_MATERIALIZING,
    STAGE_RUN_STATUS_READY,
    STAGE_RUN_STATUS_SPOOLING,
    STAGE_RUN_STATUS_SUCCEEDED,
    make_request_key,
    parse_request_key,
    slugify_lesson_name,
    stable_sha256,
    utc_now_iso,
)
from pipeline.schemas import EvidenceRef, RuleCard


DEFAULT_COMPONENT2_MODEL = "gemini-2.5-flash-lite"

# Local model for markdown render output
class MarkdownRenderResult(BaseModel):
    markdown: str
    metadata_tags: list[str] = Field(default_factory=list)


# ----- Mode → stage mapping -----

def _stage_for_llm_mode(mode: str) -> str:
    if mode == "knowledge_extract":
        return "component2_extract"
    if mode == "markdown_render":
        return "component2_render"
    if mode == "legacy_markdown":
        return "component2"
    return "component2"


def _resolve_model_for_llm_mode(
    mode: str,
    video_id: str | None = None,
    model: str | None = None,
) -> str:
    resolved_stage = _stage_for_llm_mode(mode)
    resolved = resolve_model_for_stage(
        resolved_stage, video_id=video_id, explicit_model=model
    )
    if resolved and resolved.strip():
        return resolved
    if model and str(model).strip():
        return str(model).strip()
    config_candidates: list[str] = []
    if video_id:
        cfg = pipeline_config.get_config_for_video(video_id)
        config_candidates.extend(
            [
                str(cfg.get("model_component2") or ""),
                str(cfg.get("model_vlm") or ""),
                str(cfg.get("model_name") or ""),
            ]
        )
    env_candidates = [
        os.getenv("MODEL_COMPONENT2") or "",
        os.getenv("MODEL_VLM") or "",
        os.getenv("MODEL_NAME") or "",
    ]
    for candidate in [*config_candidates, *env_candidates]:
        candidate = (candidate or "").strip()
        if candidate.lower().startswith("gemini-"):
            return candidate
    return DEFAULT_COMPONENT2_MODEL


def _resolve_provider_for_llm_mode(
    mode: str,
    video_id: str | None = None,
    provider: str | None = None,
) -> str:
    resolved_stage = _stage_for_llm_mode(mode)
    return resolve_provider_for_stage(
        resolved_stage, video_id=video_id, explicit_provider=provider
    )


# ----- System prompts -----

LEGACY_LITERAL_SCRIBE_SYSTEM_PROMPT = """You are the Literal Scribe for a trading-lesson pipeline. Your objective is to produce a faithful English markdown transcript that preserves the lesson's information density before any later reduction step.

<instructions>
1. TRANSLATION WITH MAXIMUM RETENTION: Translate the spoken Russian text into clear English, but do not summarize, compress, reorganize by topic, or turn the material into an algorithmic rulebook. Preserve the chronological flow of the lesson.
2. KEEP TEACHING CONTENT: Keep examples, clarifications, and explanatory detail unless they are pure verbal noise (for example, repeated filler sounds with no informational content). When in doubt, keep the content.
3. TECHNICAL FIDELITY: Preserve the exact meaning of all trading mechanics, rules, mathematics, and definitions.
4. VISUAL INTEGRATION (THE DELTA RULE): Insert the provided Visual Events chronologically.
    - Use <previous_visual_state> as the baseline. For new events, describe what changed based on the change_summary and the visible state.
    - INLINE MICRO-TIMESTAMPS: Anchor every visual insertion by placing the exact timestamp in bold immediately before the blockquote.
    - EXAMPLE TYPES: Prefix the visual description with the provided example_type formatted in Title Case.
    - FORMAT EXACTLY LIKE THIS: **[MM:SS]** > [*Example Type*: Your synthesized description of the chart changes.]
5. NO GLOBAL REDUCTION: Do not merge distant concepts, do not group by topic, and do not eliminate repeated but potentially useful lesson information. That happens in a later pass.
6. METADATA TAGGING: Extract any unique trading concepts mentioned. Output them matching the exact English terms in the glossary.
</instructions>

<glossary>
# Basic Terms
* Трейдинг внутри дня / Интрадей = Intraday trading
* Свинг-трейдинг = Swing trading
* Скальпинг = Scalping
* Поводырь = Market Leader
* Домашка = Daily Watchlist
* Засаженные игроки = Trapped players
* Шортокрыл = Short squeeze participant

# Chart Elements & Levels
* Бар сформировавший уровень (БСУ) = Bar Forming the Level (BSU)
* Бар подтверждающий уровень 1 / 2 (БПУ1 / БПУ2) = Bar Confirming the Level 1 / 2 (BPU1 / BPU2)
* Копейка в копейку = Tick-for-tick
* Уровень излома тренда = Trend Break Level
* Зеркальный уровень = Mirror Level
* Уровень лимитного игрока = Limit Player Level
* Исторический уровень = Historical Level
* Уровень образованный паранормальным баром = Paranormal Bar Level
* Уровень от ГЭПа = Gap Level
* Плавающий уровень = Floating Level
* Граница отката = Retracement Boundary
* Хвост / Шпилька = Wick / Tail
* Паранормальный бар = Paranormal Bar

# Orders, Execution & Energy
* Рыночный ордер (Маркет) = Market order
* Лимитный ордер = Limit order
* Стоп-маркет = Stop-market order
* Стоп-лимит = Stop-limit order
* Стоп-лосс / Тейк-профит = Stop-loss / Take-profit
* Проскальзывание / Спред / Бид / Аск = Slippage / Spread / Bid / Ask
* Безубыток (Б/У) = Breakeven
* Люфт = Luft / Allowance
* ATR расчетный / технический = Calculated ATR / Technical ATR
* Запас хода = Profit Potential
* Энергия = Market Fuel / Energy
* Проторговка / Накопление / Консолидация = Consolidation / Accumulation
* Дистрибуция / Реализация = Distribution
* Контртренд = Counter-trend
* Шорт-сквиз = Short Squeeze
* Зона зараженности = Choppy Zone
* Свободная / чистая зона = Clear Zone

# Trading Styles & Patterns
* Пробой = Breakout
* Ложный пробой (ЛП) = False Breakout (FB)
* Сложный ложный пробой (СЛП) = Complex False Breakout
* Отбой от уровня = Rebound
* Поджатие = Price compression / Squeezing
* Прилипание к уровню = Sticking to the level
* Ближний ретест = Near Retest
* Дальний ретест = Distant Retest
* Откат = Pullback
* V-формация = V-formation
* Задерг против тренда = Upthrust
* Срыв базы = Base Breakdown
* Распил уровня = Whipsaw

# Risk Management
* Риск-менеджмент / Мани-менеджмент = Risk management / Money management
* Риск на сделку / Риск на день = Risk per trade / Daily risk limit
* Соотношение риска к прибыли = Risk-Reward Ratio (R:R)
* Технический стоп = Technical stop
* Расчетный стоп = Calculated stop
* Размер позиции / Лотность / Плечо = Position size / Lot size / Leverage
* Точка входа (ТВХ) = Entry Point (TVX)
</glossary>
"""

SYSTEM_PROMPT = LEGACY_LITERAL_SCRIBE_SYSTEM_PROMPT

KNOWLEDGE_EXTRACT_SYSTEM_PROMPT = """You are a trading knowledge extraction engine.

Your task is to extract only atomic, reusable trading knowledge from the provided lesson chunk.
The lesson chunk may contain transcript text, chart screenshots, drawings, annotations, or other visual teaching aids.

Return valid JSON only.
Return exactly one JSON object.
Do not include markdown.
Do not include commentary.
Do not include any text before or after the JSON.
The transcript is in Russian. All extracted text must remain in Russian.

OUTPUT SCHEMA

Return exactly these top-level keys:
{
  "definitions": [],
  "rule_statements": [],
  "conditions": [],
  "invalidations": [],
  "exceptions": [],
  "comparisons": [],
  "warnings": [],
  "process_steps": [],
  "algorithm_hints": [],
  "examples": [],
  "global_notes": []
}

ITEM FORMAT

For every bucket except "global_notes", each item must be an object with exactly these fields:
{
  "text": "string",
  "concept": "string or null",
  "subconcept": "string or null",
  "source_type": "explicit | inferred | mixed",
  "ambiguity_notes": ["string", "..."],
  "source_line_indices": [0, 1],
  "source_quote": "string or null"
}

For "global_notes", each item must be a short string.

ANCHOR RULES

- source_line_indices must use chunk-local zero-based transcript line indices.
- If the statement is supported by one line, return a one-element array.
- If it spans multiple adjacent transcript lines, return all relevant indices.
- If the exact line indices are unclear, return an empty array and use source_quote when possible.
- source_quote should be a short verbatim or near-verbatim anchor from the transcript, not a paraphrase.
- If neither line indices nor a short quote can be identified confidently, use [] and null.

CORE EXTRACTION RULES

1. Extract only trading knowledge that is actually supported by the lesson content.
2. Do not invent rules, terminology, definitions, steps, conditions, or conclusions.
3. Keep entries atomic: one entry = one idea; do not combine multiple rules into one entry.
4. Keep entries normalized, short, and reusable.
5. Do not write summaries of the lesson. Do not write prose explanations.
6. Do not repeat the same idea across multiple buckets. If the same idea appears multiple times, keep only one clean normalized version.
7. Prefer extracting generalizable trading knowledge over narration.
8. Preserve uncertainty instead of resolving it by guessing.

HOW TO USE VISUALS

1. Visuals are supporting evidence, not the main output.
2. Use visuals only when they materially help identify a teaching point.
3. Do not describe charts frame by frame. Do not describe decorative or irrelevant visual details.
4. If a visual suggests a rule but the lesson does not clearly teach it, mark source_type as "inferred" and explain the uncertainty in ambiguity_notes.

BUCKET DEFINITIONS

- definitions: Use for explicit meanings of terms, setups, structures, or concepts.
- rule_statements: Use for direct trading principles, pattern rules, or decision rules.
- conditions: Use for prerequisites, confirming factors, contextual requirements, or "only when" statements.
- invalidations: Use for signals that a setup, read, or expectation is no longer valid.
- exceptions: Use for stated cases where a normal rule does not apply.
- comparisons: Use for meaningful distinctions between two concepts, patterns, contexts, or outcomes.
- warnings: Use for cautionary guidance, common mistakes, traps, or misuse.
- process_steps: Use for ordered or semi-ordered procedural actions a trader should take.
- algorithm_hints: Use for ideas that could help encode the knowledge into programmatic logic. Keep them faithful to the source. Do not invent quantitative thresholds unless explicitly stated.
- examples: Use for concrete positive or negative examples taught in the lesson. Keep them short and abstracted when possible.
- global_notes: Use only for important lesson-level notes that do not fit the other buckets and are still atomic and useful. Do not use this as a dump bucket.

SOURCE_TYPE RULES

- "explicit" = directly stated or clearly taught in the lesson
- "inferred" = inferred from example or visual, but not directly stated
- "mixed" = partly stated and partly inferred

AMBIGUITY RULES

1. ambiguity_notes must be an array. Use an empty array when there is no ambiguity.
2. Record uncertainty when: wording is vague; the visual suggests something but does not prove it; the example is partial; a threshold is implied but not stated; a term could have multiple interpretations.
3. Do not use ambiguity_notes for general commentary.

NORMALIZATION RULES

1. Rewrite statements into clean, reusable knowledge units.
2. Remove filler language, motivational language, and teaching rhetoric.
3. Convert conversational phrasing into structured trading language. Keep the original meaning intact.
4. LANGUAGE: The transcript is in Russian. ALL output text fields (text, concept, subconcept, source_quote) MUST be in Russian. Do not translate to English. Keep trading terminology in the original Russian form as used by the instructor.
5. Do not make the statement stronger than the source supports.

IMPORTANT EXCLUSIONS

Do NOT extract: motivational talk; storytelling with no trading rule; repeated filler; frame-by-frame narration; purely decorative chart description; unsupported assumptions; your own market knowledge; knowledge that is common in trading but not present in the lesson.

QUALITY BAR

Before producing the JSON, check: Is each entry atomic? Is each entry supported by the lesson? Is each entry placed in the best single bucket? Did I avoid duplication? Did I preserve uncertainty honestly? Did I keep only reusable trading knowledge?

If a bucket has no valid items, return an empty array.

Return JSON only."""

MARKDOWN_RENDER_SYSTEM_PROMPT = """You render human-readable markdown from normalized rule cards and evidence references. Preserve the structure of rules, conditions, invalidations, and compact visual evidence. Do not invent rules or add content not present in the input. Keep rules, conditions, invalidations and compact visual evidence distinct. Support render_mode: use "review" for human review (clear sections, readable) or "rag" for RAG-oriented compact output."""


# ----- Prompt builders -----

def build_knowledge_extract_prompt(
    *,
    lesson_id: str,
    chunk_index: int,
    section: str | None = None,
    transcript_text: str,
    transcript_lines: list | None = None,
    visual_summaries: list[str],
    concept_context: str | None = None,
    start_time_seconds: float | None = None,
    end_time_seconds: float | None = None,
) -> str:
    """Build minimal user prompt: content-focused, no instruction block (instructions are in system prompt)."""
    if transcript_lines:
        rendered_lines = []
        for idx, line in enumerate(transcript_lines):
            if isinstance(line, dict):
                start_s = float(line.get("start_seconds", 0) or 0)
                end_s = float(line.get("end_seconds", 0) or 0)
                text = (line.get("text") or "").strip()
            else:
                start_s = float(getattr(line, "start_seconds", None) or 0)
                end_s = float(getattr(line, "end_seconds", None) or 0)
                text = (getattr(line, "text", None) or "").strip()
            if not text:
                continue
            start = seconds_to_mmss(start_s)
            end = seconds_to_mmss(end_s)
            rendered_lines.append(f"[L{idx} {start}-{end}] {text}")
        transcript_block = "\n".join(rendered_lines) if rendered_lines else "(empty)"
    else:
        transcript_block = transcript_text or "(empty)"
    parts = [
        "Extract knowledge from this lesson chunk:",
        "",
        f"Lesson ID: {lesson_id}",
        f"Chunk index: {chunk_index}",
    ]
    if start_time_seconds is not None and end_time_seconds is not None:
        parts.append(f"Time range: {seconds_to_mmss(start_time_seconds)} - {seconds_to_mmss(end_time_seconds)}")
    if section:
        parts.append(f"Section: {section}")
    if concept_context:
        parts.append(f"Concept context: {concept_context}")
    parts.append("")
    parts.append("<transcript>")
    parts.append(transcript_block)
    parts.append("</transcript>")
    parts.append("")
    visual_block = "\n".join(f"- {s}" for s in visual_summaries) if visual_summaries else "(none)"
    parts.append("<compact_visual_summaries>")
    parts.append(visual_block)
    parts.append("</compact_visual_summaries>")
    return "\n".join(parts)


def build_markdown_render_prompt(
    *,
    lesson_id: str,
    lesson_title: str | None = None,
    rule_cards: list,
    evidence_refs: list,
    render_mode: str = "review",
) -> str:
    title_line = f"Lesson: {lesson_title}" if lesson_title else f"Lesson ID: {lesson_id}"
    rules_json = json.dumps(
        [r.model_dump() if hasattr(r, "model_dump") else r for r in rule_cards],
        ensure_ascii=False,
        indent=2,
    )
    refs_json = json.dumps(
        [r.model_dump() if hasattr(r, "model_dump") else r for r in evidence_refs],
        ensure_ascii=False,
        indent=2,
    )
    return f"""Render human-readable markdown from the following rule cards and evidence references. Preserve structure; do not invent rules. render_mode={render_mode}.

{title_line}

<rule_cards>
{rules_json}
</rule_cards>

<evidence_refs>
{refs_json}
</evidence_refs>

Output valid JSON with keys: markdown (string), metadata_tags (list of strings)."""


def build_legacy_markdown_prompt(chunk: LessonChunk) -> str:
    previous_visual_state = (
        json.dumps(chunk.previous_visual_state, ensure_ascii=False, indent=2)
        if chunk.previous_visual_state is not None
        else "null"
    )
    transcript_lines = "\n".join(
        f"[{seconds_to_mmss(line.start_seconds)}] {line.text}" for line in chunk.transcript_lines
    )
    if chunk.visual_events:
        visual_event_lines = []
        for event in chunk.visual_events:
            visual_event_lines.append(
                "\n".join(
                    [
                        f"- timestamp: {seconds_to_mmss(event.timestamp_seconds)}",
                        f"  example_type: {event.example_type}",
                        f"  visual_representation_type: {event.visual_representation_type}",
                        "  change_summary:",
                        *[f"    - {item}" for item in event.change_summary],
                        f"  current_state: {json.dumps(event.current_state, ensure_ascii=False, sort_keys=True)}",
                        f"  extracted_entities: {json.dumps(event.extracted_entities, ensure_ascii=False, sort_keys=True)}",
                    ]
                )
            )
        visual_events_block = "\n\n".join(visual_event_lines)
    else:
        visual_events_block = "none"
    return (
        "<previous_visual_state>\n"
        f"{previous_visual_state}\n"
        "</previous_visual_state>\n\n"
        "<transcript>\n"
        f"{transcript_lines}\n"
        "</transcript>\n\n"
        "<visual_events>\n"
        f"{visual_events_block}\n"
        "</visual_events>"
    )


build_user_prompt = build_legacy_markdown_prompt


# ----- Parsers -----

def _strip_json_code_fences(payload: str) -> str:
    text = str(payload or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```\w*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()

def parse_knowledge_extraction(payload: str) -> ChunkExtractionResult:
    return ChunkExtractionResult.model_validate_json(_strip_json_code_fences(payload))


def parse_markdown_render_result(payload: str) -> MarkdownRenderResult:
    return MarkdownRenderResult.model_validate_json(_strip_json_code_fences(payload))


def parse_legacy_enriched_markdown_chunk(payload: str) -> EnrichedMarkdownChunk:
    return EnrichedMarkdownChunk.model_validate_json(_strip_json_code_fences(payload))


parse_enriched_markdown_chunk = parse_legacy_enriched_markdown_chunk


# ----- Generic provider call -----

def _max_tokens_for_llm_mode(mode: str, attempt: int) -> int | None:
    """Cap model output. Large knowledge JSON can exceed provider defaults and truncate mid-string."""
    if mode == "knowledge_extract":
        base = int(os.environ.get("KNOWLEDGE_EXTRACT_MAX_OUTPUT_TOKENS", "65536"))
        if attempt == 0:
            return max(4096, base)
        return min(max(base * 2, 131072), 131072)
    if mode == "markdown_render":
        # Single-field "markdown" can be huge (hundreds of rules × sections).
        base = int(os.environ.get("MARKDOWN_RENDER_MAX_OUTPUT_TOKENS", "65536"))
        if attempt == 0:
            return max(8192, base)
        return min(max(base * 2, 131072), 131072)
    return None


def _is_truncated_json_validation_error(exc: ValidationError) -> bool:
    for item in exc.errors():
        if item.get("type") != "json_invalid":
            continue
        ctx = item.get("ctx") or {}
        err_obj = ctx.get("error")
        msg = str(err_obj) if err_obj is not None else str(item.get("msg", ""))
        if "EOF" in msg or "end of input" in msg.lower():
            return True
    return False


def _call_provider_for_mode(
    *,
    mode: str,
    user_text: str,
    response_schema: type[BaseModel],
    system_instruction: str,
    video_id: str | None = None,
    model: str | None = None,
    provider: str | None = None,
    temperature: float = 0.2,
    frame_key: str | None = None,
) -> tuple[BaseModel, list[dict]]:
    resolved_stage = _stage_for_llm_mode(mode)
    resolved_provider = _resolve_provider_for_llm_mode(mode, video_id=video_id, provider=provider)
    resolved_model = _resolve_model_for_llm_mode(mode, video_id=video_id, model=model)
    usage_accum: list[dict] = []
    last_raw = ""
    for attempt in range(2):
        max_tokens = _max_tokens_for_llm_mode(mode, attempt)
        response = get_provider(resolved_provider).generate_text(
            model=resolved_model,
            user_text=user_text,
            system_instruction=system_instruction,
            response_mime_type="application/json",
            response_schema=response_schema,
            temperature=temperature,
            max_tokens=max_tokens,
            stage=resolved_stage,
            frame_key=frame_key,
        )
        usage_accum.extend(response.usage_records)
        raw_text = (response.text or "").strip()
        last_raw = raw_text
        if not raw_text:
            raise ValueError(
                f"{resolved_provider} returned empty response for mode={mode}."
            )
        try:
            parsed = response_schema.model_validate_json(raw_text)
            return (parsed, usage_accum)
        except ValidationError as e:
            if attempt == 0 and _is_truncated_json_validation_error(e):
                continue
            raise ValueError(
                f"{resolved_provider} JSON parse failed for mode={mode} after "
                f"max_output_tokens={max_tokens}: {e}\n"
                f"Response tail (500 chars): ...{raw_text[-500:]!r}"
            ) from e
    raise ValueError(
        f"{resolved_provider} JSON still invalid after retry for mode={mode}. "
        f"Response tail: ...{last_raw[-500:]!r}"
    )


# ----- Public APIs: Extraction -----

async def process_chunk_knowledge_extract(
    chunk: AdaptedChunk,
    *,
    video_id: str | None = None,
    model: str | None = None,
    provider: str | None = None,
    compaction_cfg: VisualCompactionConfig | None = None,
) -> tuple[ChunkExtractionResult, list[dict]]:
    if compaction_cfg is None and video_id:
        cfg_dict = pipeline_config.get_config_for_video(video_id)
        compaction_cfg = visual_compaction_from_pipeline_config(cfg_dict)
    if compaction_cfg is None:
        compaction_cfg = VisualCompactionConfig()
    visual_summaries = visual_compaction.summarize_visual_events_for_extraction(
        chunk.visual_events, compaction_cfg
    )
    prompt = build_knowledge_extract_prompt(
        lesson_id=chunk.lesson_id,
        chunk_index=chunk.chunk_index,
        section=getattr(chunk, "section", None),
        transcript_text=chunk.transcript_text or "",
        transcript_lines=getattr(chunk, "transcript_lines", None),
        visual_summaries=visual_summaries,
        concept_context=getattr(chunk, "concept_context", None),
        start_time_seconds=chunk.start_time_seconds,
        end_time_seconds=chunk.end_time_seconds,
    )
    parsed, usage = _call_provider_for_mode(
        mode="knowledge_extract",
        user_text=prompt,
        response_schema=ChunkExtractionResult,
        system_instruction=KNOWLEDGE_EXTRACT_SYSTEM_PROMPT,
        video_id=video_id,
        model=model,
        provider=provider,
        temperature=0.2,
        frame_key=f"chunk_{chunk.chunk_index:03d}",
    )
    return (parsed, usage)


async def process_chunks_knowledge_extract(
    chunks: list[AdaptedChunk],
    *,
    video_id: str | None = None,
    model: str | None = None,
    provider: str | None = None,
    max_concurrency: int = 5,
    progress_callback: Callable[[int, int, AdaptedChunk, float], None] | None = None,
    compaction_cfg: VisualCompactionConfig | None = None,
) -> list[tuple[AdaptedChunk, ChunkExtractionResult, list[dict]]]:
    semaphore = asyncio.Semaphore(max(1, max_concurrency))
    ordered_results: list[tuple[AdaptedChunk, ChunkExtractionResult, list[dict]] | None] = [
        None
    ] * len(chunks)
    completed = 0
    progress_lock = asyncio.Lock()

    async def _worker(c: AdaptedChunk) -> None:
        nonlocal completed
        async with semaphore:
            started_at = time.perf_counter()
            result, usage_records = await process_chunk_knowledge_extract(
                c, video_id=video_id, model=model, provider=provider, compaction_cfg=compaction_cfg
            )
            ordered_results[c.chunk_index] = (c, result, usage_records)
            if progress_callback is not None:
                async with progress_lock:
                    completed += 1
                    progress_callback(completed, len(chunks), c, time.perf_counter() - started_at)

    await asyncio.gather(*(_worker(c) for c in chunks))
    return [item for item in ordered_results if item is not None]


# ----- Public APIs: Render -----

def process_rule_cards_markdown_render(
    *,
    lesson_id: str,
    lesson_title: str | None = None,
    rule_cards: list,
    evidence_refs: list,
    render_mode: str = "review",
    video_id: str | None = None,
    model: str | None = None,
    provider: str | None = None,
) -> tuple[MarkdownRenderResult, list[dict]]:
    # Only rule_cards and evidence_refs (already compact) are passed to the LLM.
    rule_dumps = [r.model_dump() if hasattr(r, "model_dump") else r for r in rule_cards]
    ref_dumps = [r.model_dump() if hasattr(r, "model_dump") else r for r in evidence_refs]
    assert_no_raw_visual_blob_leak(rule_dumps)
    assert_no_raw_visual_blob_leak(ref_dumps)
    prompt = build_markdown_render_prompt(
        lesson_id=lesson_id,
        lesson_title=lesson_title,
        rule_cards=rule_cards,
        evidence_refs=evidence_refs,
        render_mode=render_mode,
    )
    parsed, usage = _call_provider_for_mode(
        mode="markdown_render",
        user_text=prompt,
        response_schema=MarkdownRenderResult,
        system_instruction=MARKDOWN_RENDER_SYSTEM_PROMPT,
        video_id=video_id,
        model=model,
        provider=provider,
        temperature=0.2,
    )
    return (parsed, usage)


def emit_batch_spool_for_knowledge_extract(
    *,
    chunks: list[AdaptedChunk],
    lesson_id: str,
    video_id: str,
    paths: PipelinePaths,
    state_store,
    compaction_cfg: VisualCompactionConfig | None = None,
    model: str | None = None,
    provider: str | None = None,
) -> Path:
    paths.ensure_batch_dirs(STAGE_KNOWLEDGE_EXTRACT)
    lesson_slug = slugify_lesson_name(lesson_id)
    fragment_name = f"{lesson_slug}__knowledge_extract"
    spool_path = paths.batch_spool_requests_path(STAGE_KNOWLEDGE_EXTRACT, fragment_name)
    manifest_path = paths.batch_spool_manifest_path(STAGE_KNOWLEDGE_EXTRACT, fragment_name)
    stage_run = state_store.create_or_reuse_stage_run(
        lesson_id=lesson_id,
        stage_name=STAGE_KNOWLEDGE_EXTRACT,
        execution_mode="gemini_batch",
        status=STAGE_RUN_STATUS_SPOOLING,
    )

    resolved_provider = _resolve_provider_for_llm_mode(
        "knowledge_extract",
        video_id=video_id,
        provider=provider,
    )
    resolved_model = _resolve_model_for_llm_mode(
        "knowledge_extract",
        video_id=video_id,
        model=model,
    )

    lines: list[dict] = []
    request_keys: list[str] = []
    for chunk in chunks:
        visual_summaries = visual_compaction.summarize_visual_events_for_extraction(
            chunk.visual_events,
            compaction_cfg or VisualCompactionConfig(),
        )
        prompt = build_knowledge_extract_prompt(
            lesson_id=chunk.lesson_id,
            chunk_index=chunk.chunk_index,
            section=getattr(chunk, "section", None),
            transcript_text=chunk.transcript_text or "",
            transcript_lines=getattr(chunk, "transcript_lines", None),
            visual_summaries=visual_summaries,
            concept_context=getattr(chunk, "concept_context", None),
            start_time_seconds=chunk.start_time_seconds,
            end_time_seconds=chunk.end_time_seconds,
        )
        request_key = make_request_key(
            video_id=video_id,
            lesson_slug=lesson_slug,
            stage_name=STAGE_KNOWLEDGE_EXTRACT,
            entity_kind="chunk",
            entity_index=str(chunk.chunk_index),
        )
        line = gemini_batch_client.build_generate_content_batch_line(
            request_key=request_key,
            contents=[{"role": "user", "parts": [{"text": prompt}]}],
            system_instruction=KNOWLEDGE_EXTRACT_SYSTEM_PROMPT,
        )
        lines.append(line)
        request_keys.append(request_key)
        state_store.record_spool_request(
            request_key=request_key,
            stage_run_id=stage_run["stage_run_id"],
            video_id=video_id,
            lesson_id=lesson_id,
            stage_name=STAGE_KNOWLEDGE_EXTRACT,
            entity_kind="chunk",
            entity_index=str(chunk.chunk_index),
            payload_sha256=stable_sha256(line),
            spool_file_path=spool_path,
        )

    gemini_batch_client.write_jsonl_lines(spool_path, lines)
    atomic_write_json(
        manifest_path,
        {
            "lesson_id": lesson_id,
            "video_id": video_id,
            "stage_name": STAGE_KNOWLEDGE_EXTRACT,
            "provider": resolved_provider,
            "model": resolved_model,
            "spool_file_path": str(spool_path),
            "request_count": len(lines),
            "request_keys": request_keys,
            "created_at": utc_now_iso(),
        },
    )
    state_store.update_stage_run(
        stage_run["stage_run_id"],
        status=STAGE_RUN_STATUS_READY,
        request_manifest_path=manifest_path,
        started_at=stage_run.get("started_at") or utc_now_iso(),
    )
    return spool_path


def materialize_batch_results_for_knowledge_extract(
    results_jsonl_path,
    adapted_chunks: list[AdaptedChunk],
    lesson_name: str,
    paths: PipelinePaths,
    state_store,
):
    artifact_lesson_name = lesson_name.split("::", 1)[-1]
    stage_runs = state_store.list_stage_runs(
        lesson_id=lesson_name,
        stage_name=STAGE_KNOWLEDGE_EXTRACT,
        execution_mode="gemini_batch",
    )
    stage_run_id = stage_runs[-1]["stage_run_id"] if stage_runs else None
    if stage_run_id:
        state_store.update_stage_run(stage_run_id, status=STAGE_RUN_STATUS_MATERIALIZING)

    chunk_by_index = {chunk.chunk_index: chunk for chunk in adapted_chunks}
    lesson_slug = slugify_lesson_name(lesson_name)
    parsed_by_index: dict[int, ChunkExtractionResult] = {}
    usage_by_index: dict[int, list[dict]] = {}
    failures: list[dict[str, str]] = []
    decoded = Path(results_jsonl_path).read_text(encoding="utf-8")
    for result_line in gemini_batch_client.iter_result_jsonl(decoded):
        request_key = str(result_line.get("key") or "")
        if not request_key:
            failures.append({"request_key": "", "error": "missing key"})
            continue
        parsed_key = parse_request_key(request_key)
        if parsed_key["lesson_slug"] != lesson_slug:
            continue
        chunk_index = int(parsed_key["entity_index"])
        try:
            text = gemini_batch_client.extract_result_text(result_line)
            if not text:
                raise ValueError("missing response text")
            parsed = parse_knowledge_extraction(text)
            parsed_by_index[chunk_index] = parsed
            usage_by_index[chunk_index] = result_line.get("usage") or []
            state_store.mark_request_parsed(request_key, output_path=paths.knowledge_events_path(artifact_lesson_name))
        except Exception as exc:
            failures.append({"request_key": request_key, "error": str(exc)})
            state_store.mark_request_failed(request_key, str(exc))

    missing_indices = sorted(set(chunk_by_index) - set(parsed_by_index))
    if missing_indices:
        raise ValueError(f"Missing batch responses for chunk indices: {missing_indices}")

    ordered_chunks = [chunk_by_index[idx] for idx in sorted(chunk_by_index)]
    ordered_results = [parsed_by_index[idx] for idx in sorted(chunk_by_index)]
    collection, debug_rows = build_knowledge_events_from_extraction_results(
        ordered_chunks,
        ordered_results,
        lesson_name,
        None,
    )
    for row in debug_rows:
        row["request_usage"] = usage_by_index.get(row["chunk_index"], [])

    save_knowledge_events(collection, paths.knowledge_events_path(artifact_lesson_name))
    save_knowledge_debug(debug_rows, paths.knowledge_debug_path(artifact_lesson_name))
    atomic_write_json(
        paths.batch_materialization_debug_path(STAGE_KNOWLEDGE_EXTRACT),
        {
            "stage_name": STAGE_KNOWLEDGE_EXTRACT,
            "results_jsonl_path": str(results_jsonl_path),
            "parsed_count": len(ordered_results),
            "failed_count": len(failures),
            "failures": failures,
            "artifacts": {
                "knowledge_events": str(paths.knowledge_events_path(artifact_lesson_name)),
                "knowledge_debug": str(paths.knowledge_debug_path(artifact_lesson_name)),
            },
        },
    )
    if stage_run_id:
        state_store.update_stage_run(
            stage_run_id,
            status=STAGE_RUN_STATUS_SUCCEEDED if not failures else STAGE_RUN_STATUS_FAILED,
            result_manifest_path=paths.batch_materialization_debug_path(STAGE_KNOWLEDGE_EXTRACT),
            finished_at=utc_now_iso(),
        )
    return collection


def emit_batch_spool_for_markdown_render(
    *,
    lesson_id: str,
    rule_cards: list[RuleCard] | list[dict],
    evidence_refs: list[EvidenceRef] | list[dict],
    paths: PipelinePaths,
    state_store,
    render_mode: str = "review",
    video_id: str | None = None,
    model: str | None = None,
    provider: str | None = None,
) -> Path:
    paths.ensure_batch_dirs(STAGE_MARKDOWN_RENDER)
    lesson_slug = slugify_lesson_name(lesson_id)
    fragment_name = f"{lesson_slug}__markdown_render__{render_mode}"
    spool_path = paths.batch_spool_requests_path(STAGE_MARKDOWN_RENDER, fragment_name)
    manifest_path = paths.batch_spool_manifest_path(STAGE_MARKDOWN_RENDER, fragment_name)
    stage_run = state_store.create_or_reuse_stage_run(
        lesson_id=lesson_id,
        stage_name=STAGE_MARKDOWN_RENDER,
        execution_mode="gemini_batch",
        status=STAGE_RUN_STATUS_SPOOLING,
    )
    resolved_provider = _resolve_provider_for_llm_mode(
        "markdown_render",
        video_id=video_id,
        provider=provider,
    )
    resolved_model = _resolve_model_for_llm_mode(
        "markdown_render",
        video_id=video_id,
        model=model,
    )
    prompt = build_markdown_render_prompt(
        lesson_id=lesson_id,
        lesson_title=None,
        rule_cards=rule_cards,
        evidence_refs=evidence_refs,
        render_mode=render_mode,
    )
    request_key = make_request_key(
        video_id=video_id or lesson_id,
        lesson_slug=lesson_slug,
        stage_name=STAGE_MARKDOWN_RENDER,
        entity_kind="section",
        entity_index=render_mode,
    )
    line = gemini_batch_client.build_generate_content_batch_line(
        request_key=request_key,
        contents=[{"role": "user", "parts": [{"text": prompt}]}],
        system_instruction=MARKDOWN_RENDER_SYSTEM_PROMPT,
    )
    gemini_batch_client.write_jsonl_lines(spool_path, [line])
    state_store.record_spool_request(
        request_key=request_key,
        stage_run_id=stage_run["stage_run_id"],
        video_id=video_id or lesson_id,
        lesson_id=lesson_id,
        stage_name=STAGE_MARKDOWN_RENDER,
        entity_kind="section",
        entity_index=render_mode,
        payload_sha256=stable_sha256(line),
        spool_file_path=spool_path,
    )
    atomic_write_json(
        manifest_path,
        {
            "lesson_id": lesson_id,
            "video_id": video_id or lesson_id,
            "stage_name": STAGE_MARKDOWN_RENDER,
            "render_mode": render_mode,
            "provider": resolved_provider,
            "model": resolved_model,
            "spool_file_path": str(spool_path),
            "request_count": 1,
            "request_keys": [request_key],
            "created_at": utc_now_iso(),
        },
    )
    state_store.update_stage_run(
        stage_run["stage_run_id"],
        status=STAGE_RUN_STATUS_READY,
        request_manifest_path=manifest_path,
        started_at=stage_run.get("started_at") or utc_now_iso(),
    )
    return spool_path


def materialize_batch_results_for_markdown_render(
    results_jsonl_path,
    lesson_name: str,
    paths: PipelinePaths,
    state_store,
):
    artifact_lesson_name = lesson_name.split("::", 1)[-1]
    stage_runs = state_store.list_stage_runs(
        lesson_id=lesson_name,
        stage_name=STAGE_MARKDOWN_RENDER,
        execution_mode="gemini_batch",
    )
    stage_run_id = stage_runs[-1]["stage_run_id"] if stage_runs else None
    if stage_run_id:
        state_store.update_stage_run(stage_run_id, status=STAGE_RUN_STATUS_MATERIALIZING)

    decoded = Path(results_jsonl_path).read_text(encoding="utf-8")
    lesson_slug = slugify_lesson_name(lesson_name)
    written: dict[str, str] = {}
    failures: list[dict[str, str]] = []
    last_result: MarkdownRenderResult | None = None
    for result_line in gemini_batch_client.iter_result_jsonl(decoded):
        request_key = str(result_line.get("key") or "")
        if not request_key:
            failures.append({"request_key": "", "error": "missing key"})
            continue
        parsed_key = parse_request_key(request_key)
        if parsed_key["lesson_slug"] != lesson_slug:
            continue
        render_mode = parsed_key["entity_index"]
        try:
            text = gemini_batch_client.extract_result_text(result_line)
            if not text:
                raise ValueError("missing response text")
            result = parse_markdown_render_result(text)
            last_result = result
            if render_mode == "rag":
                destination = paths.rag_ready_export_path(artifact_lesson_name)
                debug_path = paths.rag_render_debug_path(artifact_lesson_name)
            else:
                destination = paths.review_markdown_path(artifact_lesson_name)
                debug_path = paths.review_render_debug_path(artifact_lesson_name)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(result.markdown, encoding="utf-8")
            write_llm_debug(
                debug_path,
                [
                    {
                        "render_mode": render_mode,
                        "markdown_preview": result.markdown[:500],
                        "metadata_tags": result.metadata_tags,
                        "request_usage": result_line.get("usage") or [],
                    }
                ],
            )
            written[render_mode] = str(destination)
            state_store.mark_request_parsed(request_key, output_path=destination)
        except Exception as exc:
            failures.append({"request_key": request_key, "error": str(exc)})
            state_store.mark_request_failed(request_key, str(exc))

    atomic_write_json(
        paths.batch_materialization_debug_path(STAGE_MARKDOWN_RENDER),
        {
            "stage_name": STAGE_MARKDOWN_RENDER,
            "results_jsonl_path": str(results_jsonl_path),
            "written": written,
            "failed_count": len(failures),
            "failures": failures,
        },
    )
    if stage_run_id:
        state_store.update_stage_run(
            stage_run_id,
            status=STAGE_RUN_STATUS_SUCCEEDED if not failures else STAGE_RUN_STATUS_FAILED,
            result_manifest_path=paths.batch_materialization_debug_path(STAGE_MARKDOWN_RENDER),
            finished_at=utc_now_iso(),
        )
    if last_result is None:
        raise ValueError(f"No markdown render results were materialized from {results_jsonl_path}")
    return last_result


# ----- Public APIs: Legacy -----

def _call_provider_legacy(
    chunk: LessonChunk,
    *,
    video_id: str | None = None,
    model: str | None = None,
    provider: str | None = None,
) -> tuple[EnrichedMarkdownChunk, list[dict]]:
    resolved_provider = _resolve_provider_for_llm_mode(
        "legacy_markdown", video_id=video_id, provider=provider
    )
    resolved_model = _resolve_model_for_llm_mode(
        "legacy_markdown", video_id=video_id, model=model
    )
    response = get_provider(resolved_provider).generate_text(
        model=resolved_model,
        user_text=build_legacy_markdown_prompt(chunk),
        system_instruction=LEGACY_LITERAL_SCRIBE_SYSTEM_PROMPT,
        response_mime_type="application/json",
        response_schema=EnrichedMarkdownChunk,
        temperature=0.2,
        stage="component2",
        frame_key=f"chunk_{chunk.chunk_index:03d}",
    )
    raw_text = (response.text or "").strip()
    if not raw_text:
        raise ValueError(
            f"{resolved_provider} returned empty response for markdown chunk synthesis."
        )
    return parse_legacy_enriched_markdown_chunk(raw_text), response.usage_records


async def process_chunk_legacy_markdown(
    chunk: LessonChunk,
    *,
    video_id: str | None = None,
    model: str | None = None,
    provider: str | None = None,
) -> tuple[EnrichedMarkdownChunk, list[dict]]:
    return await asyncio.to_thread(
        _call_provider_legacy,
        chunk,
        video_id=video_id,
        model=model,
        provider=provider,
    )


async def process_chunks_legacy_markdown(
    chunks: list[LessonChunk],
    *,
    video_id: str | None = None,
    model: str | None = None,
    provider: str | None = None,
    max_concurrency: int = 5,
    progress_callback: Callable[[int, int, LessonChunk, float], None] | None = None,
) -> list[tuple[LessonChunk, EnrichedMarkdownChunk, list[dict]]]:
    semaphore = asyncio.Semaphore(max(1, max_concurrency))
    ordered_results: list[tuple[LessonChunk, EnrichedMarkdownChunk, list[dict]] | None] = [
        None
    ] * len(chunks)
    completed = 0
    progress_lock = asyncio.Lock()

    async def _worker(chunk: LessonChunk) -> None:
        nonlocal completed
        async with semaphore:
            started_at = time.perf_counter()
            enriched, usage_records = await process_chunk_legacy_markdown(
                chunk, video_id=video_id, model=model, provider=provider
            )
            ordered_results[chunk.chunk_index] = (chunk, enriched, usage_records)
            if progress_callback is not None:
                async with progress_lock:
                    completed += 1
                    progress_callback(
                        completed, len(chunks), chunk, time.perf_counter() - started_at
                    )

    await asyncio.gather(*(_worker(chunk) for chunk in chunks))
    return [item for item in ordered_results if item is not None]


process_chunk = process_chunk_legacy_markdown
process_chunks = process_chunks_legacy_markdown


# ----- Assembly -----

def format_final_markdown(enriched_chunk: EnrichedMarkdownChunk) -> str:
    tags = ", ".join(enriched_chunk.metadata_tags)
    if tags:
        return enriched_chunk.synthesized_markdown + "\n\n**Tags:** " + tags
    return enriched_chunk.synthesized_markdown


def assemble_legacy_video_markdown(
    lesson_name: str,
    processed_chunks: list[tuple],
) -> str:
    ordered = sorted(processed_chunks, key=lambda item: item[0].chunk_index)
    sections = [format_final_markdown(item[1]) for item in ordered]
    body = "\n\n---\n\n".join(section.strip() for section in sections if section.strip())
    return f"# {lesson_name}\n\n{body}\n"


assemble_video_markdown = assemble_legacy_video_markdown


# ----- Debug -----

def legacy_debug_rows(
    processed_chunks: list[tuple[LessonChunk, EnrichedMarkdownChunk, list[dict]]],
) -> list[dict]:
    """Convert legacy processed_chunks (chunk, enriched, usage) to rows for write_llm_debug."""
    return [
        {
            "chunk_index": c.chunk_index,
            "start_time_seconds": c.start_time_seconds,
            "end_time_seconds": c.end_time_seconds,
            "visual_event_count": len(c.visual_events),
            "result": e.model_dump(),
            "request_usage": u,
        }
        for (c, e, u) in sorted(processed_chunks, key=lambda x: x[0].chunk_index)
    ]


def write_llm_debug(path: Path | str, rows: list[dict]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8"
    )


# Backward compatibility: resolvers used by main for legacy/knowledge client
def _resolve_model(video_id: str | None = None, model: str | None = None) -> str:
    return _resolve_model_for_llm_mode("legacy_markdown", video_id=video_id, model=model)


def _resolve_provider(video_id: str | None = None, provider: str | None = None) -> str:
    return _resolve_provider_for_llm_mode(
        "legacy_markdown", video_id=video_id, provider=provider
    )
