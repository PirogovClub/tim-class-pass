Here is the complete, consolidated master document for **Component 2 (The Clean, Merge & Translate Pipeline)**.

Status note: the repository now contains an implemented version of this design as:

- `pipeline/invalidation_filter.py`
- `pipeline/component2/parser.py`
- `pipeline/component2/llm_processor.py`
- `pipeline/component2/main.py`

Run it with:

```bash
uv run python -m pipeline.component2.main --vtt "data/<video_id>/<lesson>.vtt" --visuals-json "data/<video_id>/dense_analysis.json" --output-root "data/<video_id>" --video-id "<video_id>"
```

The sections below remain the design/BRD reference for the current implementation.

---

# 🏗️ Master BRD & Agent Prompts: Component 2

**Pipeline:** The Clean, Merge, & Translate Engine
**Objective:** Ingest raw Russian `.vtt` transcripts and visual analytics `.json` files, filter out noise, translate to English, and merge them into dense, chronologically accurate Markdown (`.md`) textbooks optimized for RAG.

---

## 📋 Agent Task Prompt: Module 2.1 - Semantic Parsing & Synchronization

**Role:** You are an expert Python data engineer building a highly resilient parsing and synchronization module for an algorithmic trading video pipeline.

**Objective:** Write a Python script (`parser.py`) that reads a WebVTT (`.vtt`) transcript and a custom JSON frame analytics file. The script must parse the data, apply strict visual noise filters, and chunk the text semantically (snapping to sentence boundaries, not hard math). It must output synchronized `LessonChunk` Pydantic objects.

**Tech Stack:**

* Python 3.10+
* `pydantic` (for strict data modeling)
* `pendulum` (for all time/duration math)
* `webvtt-py` (for `.vtt` parsing)

**Implementation Requirements:**

**Step 1: Define the Pydantic Data Models**
Create the following schemas to hold the synchronized data:

* `VisualEvent`:
* `timestamp_seconds` (int)
* `change_summary` (list of strings)
* `current_state` (dict)
* `extracted_entities` (dict)
* `example_type` (str) - *Critical for distinguishing abstract concepts from real market examples.*


* `TranscriptLine`:
* `start_seconds` (float)
* `end_seconds` (float)
* `text` (str)


* `LessonChunk`:
* `chunk_index` (int)
* `start_time_seconds` (float)
* `end_time_seconds` (float)
* `transcript_lines` (List[TranscriptLine])
* `visual_events` (List[VisualEvent])
* `previous_visual_state` (Optional[dict]) - *Used to pass the chart state across chunk boundaries.*



**Step 2: The Parsing & Double-Filter Logic**

* **VTT Parser:** Use `webvtt.read()`. Convert the `start` and `end` timestamps into total seconds (float) using `pendulum`. Clean the text of basic WebVTT formatting artifacts if present.
* **JSON Parser (The Double Filter):** Load the JSON. The keys are zero-padded string integers representing total seconds (e.g., `"000085"`).
* *Rule:* You MUST drop the frame unless it passes **both** conditions: `material_change == True` AND `visual_representation_type != "unknown"`. (This prevents logging useless "talking head" frames).



**Step 3: The Semantic Chunking Engine**
Create a function `create_lesson_chunks(vtt_lines: List[TranscriptLine], visual_events: List[VisualEvent], target_duration_seconds=120) -> List[LessonChunk]:`

* **Semantic Slicing:** Do NOT slice blindly at exactly 120 seconds. Iterate through `vtt_lines`. Once you cross the 120-second threshold, continue aggregating lines until you hit a line whose `text` ends with a terminal punctuation mark (`.`, `?`, `!`) OR where the gap to the next line is > 1.5 seconds. Cut the chunk there.
* **Event Synchronization:** For each finalized chunk window, append any `VisualEvent` whose `timestamp_seconds` falls between the chunk's `start_time_seconds` and `end_time_seconds`.
* **State Persistence (Crucial):** For `Chunk N+1`, populate its `previous_visual_state` with the `current_state` dictionary of the *very last* `VisualEvent` from `Chunk N`. If `Chunk N` had no visual events, pass `None` or carry over the state from `Chunk N-1`.

**Output Generation:**

* Expose a main function: `def parse_and_sync(vtt_path: str, json_path: str) -> List[LessonChunk]:`
* Include a `__main__` block that runs this on sample files and `print()`s the JSON representation of the first two chunks to the console.

---

## 📋 Agent Task Prompt: Module 2.2 & 2.3 - LLM Synthesis & Translation Engine

**Role:** You are an expert Python AI Engineer specializing in LLM pipeline orchestration and structured data extraction.

**Objective:** Write a Python script (`llm_processor.py`) that takes `LessonChunk` objects, constructs a highly specific multimodal prompt, and calls the Google Gemini API (`gemini-2.5-flash`) using **Structured Outputs** to translate, clean, and merge the transcript and visual data into cohesive English Markdown.

**Tech Stack:**

* Python 3.10+
* `pydantic`
* `google-genai` (the official Google GenAI SDK)
* `tenacity` (for automatic API retry logic)

**Implementation Requirements:**

**Step 1: The Pydantic Output Schema**

```python
from pydantic import BaseModel, Field
from typing import List

class EnrichedMarkdownChunk(BaseModel):
    synthesized_markdown: str = Field(description="The clean, translated English Markdown text with integrated micro-timestamps and blockquotes.")
    metadata_tags: List[str] = Field(description="A list of strict English terminology tags (from the glossary) found in this chunk.")

```

**Step 2: The Prompt Builder Function**
Create `build_user_prompt(chunk: LessonChunk) -> str` formatting data with XML tags:

* **`<previous_visual_state>`:** If `chunk.previous_visual_state` exists, dump it here.
* **`<transcript>`:** Combine all `transcript_lines` into a single string. *Prefix each logical sentence/block with its timestamp* (e.g., `[02:45] Итак...`).
* **`<visual_events>`:** Iterate through `chunk.visual_events`. List the `timestamp` (MM:SS), `example_type`, and `change_summary`.

**Step 3: The System Prompt (The Ruleset)**
Define `SYSTEM_PROMPT` containing exactly:

```text
You are an expert quantitative trading analyst and technical translator. Your objective is to process raw Russian trading lecture transcripts and their associated visual chart analytics, synthesizing them into a clean, highly structured English textbook section.

<instructions>
1. TRANSLATION & CLEANUP: Translate the spoken Russian text into formal, professional English. Strip out all conversational filler and fix spoken grammatical errors.
2. TECHNICAL FIDELITY: Strictly preserve the exact meaning of all trading mechanics, rules, mathematics, and definitions.
3. VISUAL INTEGRATION (THE DELTA RULE): Seamlessly integrate the provided Visual Events into the English narrative chronologically. 
    - Use `<previous_visual_state>` as your baseline. For new events, ONLY describe what changed based on the `change_summary`.
    - INLINE MICRO-TIMESTAMPS: Anchor visual descriptions by placing the exact timestamp in bold immediately before the blockquote.
    - EXAMPLE TYPES: Prefix the visual description with the provided `example_type` formatted in Title Case.
    - FORMAT EXACTLY LIKE THIS: **[MM:SS]** > [*Example Type*: Your synthesized description of the chart changes.]
4. METADATA TAGGING: Extract any unique trading concepts mentioned. Output them matching the exact English terms in the glossary.
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

```

**Step 4: The LLM Execution Engine**

* Create `async def process_chunk(chunk: LessonChunk) -> EnrichedMarkdownChunk:`
* Initialize Gemini client: `client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))`
* Call `client.models.generate_content` (model: `gemini-2.5-flash`). Pass `SYSTEM_PROMPT` in `system_instruction` and `EnrichedMarkdownChunk` to `response_schema`. Use `@retry`.

**Step 5: Markdown Assembly & Tag Injection**

* Create `format_final_markdown(enriched_chunk: EnrichedMarkdownChunk) -> str:`
* Logic: `return enriched_chunk.synthesized_markdown + "\n\n**Tags:** " + ", ".join(enriched_chunk.metadata_tags)`

---

## 📋 Agent Task Prompt: Module 2.4 - Pipeline Orchestrator & Exporter

**Role:** You are an expert Python Software Engineer specializing in asynchronous batch processing and file I/O operations.

**Objective:** Write the master orchestration script (`main.py`) that ties together `parser.py` and `llm_processor.py`. It must scan for `.vtt`/`.json` pairs, dispatch chunks concurrently to the Gemini API, reassemble them chronologically, and save the final `.md` files.

**Tech Stack:**

* Python 3.10+
* `asyncio`
* `pathlib`
* `logging` or `loguru`

**Implementation Requirements:**

**Step 1: Directory Setup & Pair Matching**

* Define `input_transcripts/`, `input_visuals/`, and `output_markdown/`.
* Match `[video_name].vtt` with exactly `[video_name].json`. Log a warning and skip if one is missing.

**Step 2: State-Safe Asynchronous Processing**

* Create `async def process_video(video_name: str, vtt_path: Path, json_path: Path, output_path: Path):`
* Call `parse_and_sync()` to get `LessonChunk` objects.
* Use `asyncio.gather` with `asyncio.Semaphore(5)` to process up to 5 chunks concurrently via `process_chunk()`.

**Step 3: Assembly and Export**

* Sort the returned `EnrichedMarkdownChunk` objects strictly by `chunk_index`.
* Apply `format_final_markdown()` to each.
* Join all strings using `\n\n---\n\n`. Add `# [Video Name]` header at the top.
* Write to `output_markdown/[video_name].md`.

**Step 4: Idempotency Check (Resume Capability)**

* Before processing, check if `output_markdown/[video_name].md` exists. If so, log `"Skipping [video_name] - already processed"` and continue.

**Output Generation:**

* Create `async def main():` loop to process all matched files. Run via `asyncio.run(main())`.

---

Are you ready to move into Phase 2 (Workflow B) and define the PostgreSQL/pgvector database architecture to store these files, or do you want to feed these prompts to your agent and review the Python code it generates first?