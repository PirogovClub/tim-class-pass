from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Callable

from helpers import config as pipeline_config
from helpers.clients import gemini_client
from helpers.clients.providers import get_provider, resolve_model_for_stage, resolve_provider_for_stage
from pipeline.component2.models import EnrichedMarkdownChunk, LessonChunk
from pipeline.component2.parser import seconds_to_mmss


DEFAULT_COMPONENT2_MODEL = "gemini-2.5-flash-lite"

SYSTEM_PROMPT = """You are the Literal Scribe for a trading-lesson pipeline. Your objective is to produce a faithful English markdown transcript that preserves the lesson's information density before any later reduction step.

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


def _resolve_model(video_id: str | None = None, model: str | None = None) -> str:
    resolved = resolve_model_for_stage("component2", video_id=video_id, explicit_model=model)
    if resolved:
        return resolved
    if model:
        return model
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
        candidate = candidate.strip()
        if candidate.lower().startswith("gemini-"):
            return candidate
    return DEFAULT_COMPONENT2_MODEL


def _resolve_provider(video_id: str | None = None, provider: str | None = None) -> str:
    return resolve_provider_for_stage("component2", video_id=video_id, explicit_provider=provider)


def build_user_prompt(chunk: LessonChunk) -> str:
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


def parse_enriched_markdown_chunk(payload: str) -> EnrichedMarkdownChunk:
    return EnrichedMarkdownChunk.model_validate_json(payload)


def _call_provider(
    chunk: LessonChunk,
    *,
    video_id: str | None = None,
    model: str | None = None,
    provider: str | None = None,
) -> tuple[EnrichedMarkdownChunk, list[dict]]:
    resolved_provider = _resolve_provider(video_id=video_id, provider=provider)
    resolved_model = _resolve_model(video_id=video_id, model=model)
    response = get_provider(resolved_provider).generate_text(
        model=resolved_model,
        user_text=build_user_prompt(chunk),
        system_instruction=SYSTEM_PROMPT,
        response_mime_type="application/json",
        response_schema=EnrichedMarkdownChunk,
        temperature=0.2,
        stage=f"{resolved_provider}_component2",
        frame_key=f"chunk_{chunk.chunk_index:03d}",
    )
    raw_text = (response.text or "").strip()
    if not raw_text:
        raise ValueError(f"{resolved_provider} returned empty response for markdown chunk synthesis.")
    return parse_enriched_markdown_chunk(raw_text), response.usage_records


async def process_chunk(
    chunk: LessonChunk,
    *,
    video_id: str | None = None,
    model: str | None = None,
    provider: str | None = None,
) -> tuple[EnrichedMarkdownChunk, list[dict]]:
    return await asyncio.to_thread(_call_provider, chunk, video_id=video_id, model=model, provider=provider)


async def process_chunks(
    chunks: list[LessonChunk],
    *,
    video_id: str | None = None,
    model: str | None = None,
    provider: str | None = None,
    max_concurrency: int = 5,
    progress_callback: Callable[[int, int, LessonChunk, float], None] | None = None,
) -> list[tuple[LessonChunk, EnrichedMarkdownChunk, list[dict]]]:
    semaphore = asyncio.Semaphore(max(1, max_concurrency))
    ordered_results: list[tuple[LessonChunk, EnrichedMarkdownChunk, list[dict]] | None] = [None] * len(chunks)
    completed = 0
    progress_lock = asyncio.Lock()

    async def _worker(chunk: LessonChunk) -> None:
        nonlocal completed
        async with semaphore:
            started_at = time.perf_counter()
            enriched, usage_records = await process_chunk(chunk, video_id=video_id, model=model, provider=provider)
            ordered_results[chunk.chunk_index] = (chunk, enriched, usage_records)
            if progress_callback is not None:
                async with progress_lock:
                    completed += 1
                    progress_callback(completed, len(chunks), chunk, time.perf_counter() - started_at)

    await asyncio.gather(*(_worker(chunk) for chunk in chunks))
    return [item for item in ordered_results if item is not None]


def format_final_markdown(enriched_chunk: EnrichedMarkdownChunk) -> str:
    tags = ", ".join(enriched_chunk.metadata_tags)
    if tags:
        return enriched_chunk.synthesized_markdown + "\n\n**Tags:** " + tags
    return enriched_chunk.synthesized_markdown


def assemble_video_markdown(
    lesson_name: str,
    processed_chunks: list[tuple],
) -> str:
    ordered = sorted(processed_chunks, key=lambda item: item[0].chunk_index)
    sections = [format_final_markdown(item[1]) for item in ordered]
    body = "\n\n---\n\n".join(section.strip() for section in sections if section.strip())
    return f"# {lesson_name}\n\n{body}\n"


def write_llm_debug(path: Path | str, processed_chunks: list[tuple]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = [
        {
            "chunk_index": item[0].chunk_index,
            "start_time_seconds": item[0].start_time_seconds,
            "end_time_seconds": item[0].end_time_seconds,
            "visual_event_count": len(item[0].visual_events),
            "result": item[1].model_dump(),
            "request_usage": item[2] if len(item) > 2 else [],
        }
        for item in sorted(processed_chunks, key=lambda item: item[0].chunk_index)
    ]
    destination.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
