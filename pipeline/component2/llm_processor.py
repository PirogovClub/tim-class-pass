from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Callable

from pydantic import BaseModel, Field

from helpers import config as pipeline_config
from helpers.clients.providers import get_provider, resolve_model_for_stage, resolve_provider_for_stage
from pipeline.component2.knowledge_builder import (
    AdaptedChunk,
    ChunkExtractionResult,
    summarize_visual_events_for_extraction,
)
from pipeline.component2.models import EnrichedMarkdownChunk, LessonChunk
from pipeline.component2.parser import seconds_to_mmss
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

KNOWLEDGE_EXTRACT_SYSTEM_PROMPT = """You are a trading knowledge extractor. Extract only atomic trading knowledge from the given lesson chunk. Respond with valid JSON only.

Use these sections: definitions, rule_statements, conditions, invalidations, exceptions, comparisons, warnings, process_steps, algorithm_hints, examples, global_notes. Split distinct ideas into separate entries. Avoid prose and frame-by-frame narration. Preserve uncertainty in ambiguity_notes where applicable. Use visuals as supporting context only. Do not invent rules or facts. Keep statements short and normalized. Output a single JSON object with the exact keys listed; use empty lists for missing buckets. No markdown, no explanation."""

MARKDOWN_RENDER_SYSTEM_PROMPT = """You render human-readable markdown from normalized rule cards and evidence references. Preserve the structure of rules, conditions, invalidations, and compact visual evidence. Do not invent rules or add content not present in the input. Keep rules, conditions, invalidations and compact visual evidence distinct. Support render_mode: use "review" for human review (clear sections, readable) or "rag" for RAG-oriented compact output."""


# ----- Prompt builders -----

def build_knowledge_extract_prompt(
    *,
    lesson_id: str,
    chunk_index: int,
    section: str | None = None,
    transcript_text: str,
    visual_summaries: list[str],
    concept_context: str | None = None,
) -> str:
    parts = [
        f"Lesson ID: {lesson_id}",
        f"Chunk index: {chunk_index}",
    ]
    if section:
        parts.append(f"Section: {section}")
    if concept_context:
        parts.append(f"Concept context: {concept_context}")
    header = "\n".join(parts)
    visual_block = "\n".join(f"- {s}" for s in visual_summaries) if visual_summaries else "(none)"
    return f"""Extract atomic trading knowledge from this lesson chunk. Output valid JSON only. Split distinct ideas into separate entries. Prefer explicit teaching rules over narration. Keep statements short and normalized. Use visuals as supporting evidence only. Do not describe frame-by-frame. Do not summarize the whole lesson. Do not invent absent information. Leave concept/subconcept null when unclear; note ambiguity in ambiguity_notes.

{header}

<transcript>
{transcript_text or "(empty)"}
</transcript>

<compact_visual_summaries>
{visual_block}
</compact_visual_summaries>

Output a single JSON object with exactly these keys (each a list of objects with text, optional concept, optional subconcept, optional ambiguity_notes list): definitions, rule_statements, conditions, invalidations, exceptions, comparisons, warnings, process_steps, algorithm_hints, examples, global_notes (list of strings). Use empty lists for missing buckets. No markdown, no prose."""


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

def parse_knowledge_extraction(payload: str) -> ChunkExtractionResult:
    return ChunkExtractionResult.model_validate_json(payload)


def parse_markdown_render_result(payload: str) -> MarkdownRenderResult:
    return MarkdownRenderResult.model_validate_json(payload)


def parse_legacy_enriched_markdown_chunk(payload: str) -> EnrichedMarkdownChunk:
    return EnrichedMarkdownChunk.model_validate_json(payload)


parse_enriched_markdown_chunk = parse_legacy_enriched_markdown_chunk


# ----- Generic provider call -----

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
    response = get_provider(resolved_provider).generate_text(
        model=resolved_model,
        user_text=user_text,
        system_instruction=system_instruction,
        response_mime_type="application/json",
        response_schema=response_schema,
        temperature=temperature,
        stage=resolved_stage,
        frame_key=frame_key,
    )
    raw_text = (response.text or "").strip()
    if not raw_text:
        raise ValueError(
            f"{resolved_provider} returned empty response for mode={mode}."
        )
    parsed = response_schema.model_validate_json(raw_text)
    return (parsed, response.usage_records)


# ----- Public APIs: Extraction -----

async def process_chunk_knowledge_extract(
    chunk: AdaptedChunk,
    *,
    video_id: str | None = None,
    model: str | None = None,
    provider: str | None = None,
) -> tuple[ChunkExtractionResult, list[dict]]:
    visual_summaries = summarize_visual_events_for_extraction(chunk.visual_events)
    prompt = build_knowledge_extract_prompt(
        lesson_id=chunk.lesson_id,
        chunk_index=chunk.chunk_index,
        section=chunk.section,
        transcript_text=chunk.transcript_text or "",
        visual_summaries=visual_summaries,
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
                c, video_id=video_id, model=model, provider=provider
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
