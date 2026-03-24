# Multimodal YouTube Video Transcript Enrichment Pipeline

This repo now has:

1. The main **`tim-class-pass` pipeline**, which extracts frame-level structured analysis and then runs the new Step 3 markdown synthesis flow.
2. A standalone **Component 2 + Step 3 runner** for re-running markdown synthesis from an existing VTT plus `dense_analysis.json`.

Primary purpose: **information extraction and structured lesson synthesis** from video + transcript + visual state.

---

## Requirements

| Tool | Purpose |
|------|---------|
| **Python 3.12+** via `uv` | Run the pipelines |
| **FFmpeg** (system PATH) | Extract frames from video |
| **yt-dlp** | Download video + subtitles |

### Environment Setup

```bash
cp .env.template .env
```

Edit `.env` (see `.env.template`).

For the dense pipeline, optional per-video config lives in:

```text
data/<video_id>/pipeline.yml
```

The loader reads the `default` section from that file.

> **ide** (IDE as AI agent) means any AI-driven IDE (e.g. Cursor) performs analysis: the pipeline writes prompt files and exits; you fill the response files and re-run — no external API calls needed.

---

## Pipeline Overview

### A. Main pipeline (`tim-class-pass`)

The main pipeline is controlled by the **`tim-class-pass`** CLI (Click, in `pipeline/main.py`) and runs in order:

**Step 0** (optional download) → **Step 1** (frame capture) → **Steps 1.5–1.7** (structural diff, LLM queue, prompts) → **Step 2** (batched frame analysis) → **Step 3** (Component 2 + markdown synthesis).

**Full step-by-step description:** [docs/pipeline.md](docs/pipeline.md).

```
YouTube URL / existing video_id
        │
        ▼
[Step 0] pipeline/downloader.py         — Download .mp4 + .vtt via yt-dlp (skipped if --video_id)
        │
        ▼
[Step 1] pipeline/dense_capturer.py     — Extract dense color frames (default 0.5 fps) → frames_dense/ + dense_index.json
        │
        ▼
[Step 1.5] pipeline/structural_compare.py — Grayscale+blur SSIM between consecutive frames → structural_index.json; rename frames with _diff_<value>; save structural compare artifacts
        │
        ▼
[Step 1.6] pipeline/select_llm_frames.py — Copy frames with configurable diff threshold (default 0.025) (+ previous frame) → llm_queue/ + manifest.json
        │
        ▼
[Step 1.7] pipeline/build_llm_prompts.py — Write single-frame *_prompt.txt for each file in llm_queue/
        │
        ▼
[Step 2] pipeline/dense_analyzer.py     — Analyze queued frames in batches; writes dense_analysis.json; IDE exits with code 10 per batch
        │
        ▼
[Step 3] pipeline/component2/main.py    — Filter invalid visuals, chunk lesson, synthesize markdown → filtered_visual_events.json + output_markdown/*.md
```

### Step 2 — Batch analysis

Step 2 uses **only** frames listed in `llm_queue/manifest.json`. Frames not in the queue are prefills (minimal JSON) so `dense_analysis.json` still has a full key set for downstream synthesis. Queued frames are processed in batches:

- Writes `batches/dense_batch_prompt_<start>-<end>.txt` and exits (code 10) when agent is **ide**.
- Agent writes `batches/dense_batch_response_<start>-<end>.json` (one structured JSON object per frame key).
- After each batch, the pipeline merges into `dense_analysis.json` and writes per-frame `frames_dense/frame_<key>.json`. Schema: [docs/trading_visual_extraction_spec.md](docs/trading_visual_extraction_spec.md) / `skills/trading_visual_extraction/SKILL.md`.

### Step 3 — Markdown synthesis

Step 3 runs the new Component 2 + Step 3 flow:

- invalidates non-instructional frames into `filtered_visual_events.json`
- parses the VTT and synchronizes transcript lines with filtered visual events
- synthesizes chronological intermediate markdown with Gemini structured outputs
- runs a second whole-document Gemini reduction pass
- writes both intermediate and final RAG-ready markdown outputs

### B. Component 2 + Step 3 markdown pipeline

The standalone markdown pipeline is implemented in `pipeline/component2/main.py`. It:

1. Reads a raw `.vtt` transcript and a dense frame-analysis `.json`
2. Runs the invalidation filter
3. Writes `filtered_visual_events.json`
4. Builds semantic lesson chunks
5. Calls Gemini structured outputs to synthesize chronological intermediate markdown
6. Runs a whole-document quant reduction pass for the final RAG-ready document
7. Writes intermediate, final, and debug artifacts

CLI entrypoint:

```bash
uv run python -m pipeline.component2.main --help
```

---

## Output Files

For the full layout (directories, per-lesson artifacts, legacy vs new filenames, and optional structured outputs), see **[docs/pipeline_structure_and_features.md](docs/pipeline_structure_and_features.md)**.

### Main pipeline

```
data/<video_id>/
├── <video_id>.mp4                     # Original video
├── *.vtt                              # Original spoken transcript
├── frames_dense/
│   ├── frame_000002_diff_0.XXXX.jpg   # Dense color frames (default 0.5fps; renamed with SSIM diff after Step 1.5)
│   ├── frame_000001.json              # Per-frame structured extraction (Step 2)
│   └── ...
├── structural_index.json              # SSIM structural diff results (Step 1.5)
├── frames_structural_preprocessed/    # Step 1.5 grayscale+blur images used for comparison
├── llm_queue/                         # Selected frames for LLM processing (Step 1.6)
│   ├── frame_000123_diff_0.1523.jpg
│   ├── frame_000122_diff_0.0412.jpg   # previous frame included
│   ├── frame_000123_diff_0.1523_prompt.txt
│   └── manifest.json
├── dense_index.json                   # Second → frame path index
├── dense_analysis.json                # Full merged analysis
├── ai_usage_summary.json              # Per-run token/request summary across available artifacts
├── batches/                           # Step 2 intermediate files
│   ├── dense_batch_prompt_NNN-MMM.txt   # Batch prompt (agent input)
│   └── dense_batch_response_NNN-MMM.json # Batch response (agent output)
├── filtered_visual_events.json        # Step 3 filtered instructional events
├── filtered_visual_events.debug.json  # Step 3 filter report
├── output_intermediate/
│   ├── <lesson_name>.md               # Pass 1 literal-scribe markdown
│   ├── <lesson_name>.chunks.json      # Chunk debug output
│   ├── <lesson_name>.llm_debug.json   # LLM result debug output + per-chunk request usage
│   └── <lesson_name>.reducer_usage.json # Pass 2 reducer request usage
└── output_rag_ready/
    ├── <lesson_name>.md               # ✅ FINAL: topic-grouped RAG-ready markdown
```

The structural compare artifacts are for inspection only. Step 2 still sends the original color JPGs from `llm_queue/` to Gemini.

---

### Component 2 + Step 3 markdown pipeline

Given a VTT and dense frame-analysis JSON, the markdown pipeline writes (at minimum):

```text
<output-root>/
├── filtered_visual_events.json
├── filtered_visual_events.debug.json
├── output_intermediate/
│   ├── <lesson_name>.md
│   ├── <lesson_name>.chunks.json
│   ├── <lesson_name>.llm_debug.json
│   └── <lesson_name>.reducer_usage.json
└── output_rag_ready/
    └── <lesson_name>.md
```

With optional flags (`--enable-knowledge-events`, `--enable-evidence-linking`, `--enable-rule-cards`, `--enable-concept-graph`, `--enable-exporters`) it also produces `*.knowledge_events.json`, `*.evidence_index.json`, `*.rule_cards.json`, `*.concept_graph.json`, `output_review/*.review_markdown.md`, `output_rag_ready/*.rag_ready.md`, and `*.export_manifest.json`. See [docs/pipeline_structure_and_features.md](docs/pipeline_structure_and_features.md).

## Testing and coverage

Tests use **pytest**; coverage uses **pytest-cov** (installed with the dev dependency group).

```bash
uv sync --group dev
uv run pytest tests/ -m "not live_provider" -v
```

Coverage report (sources: `pipeline`, `helpers`; branch coverage enabled):

```bash
uv run pytest tests/ --cov --cov-report=term-missing -m "not live_provider"
```

HTML report:

```bash
uv run pytest tests/ --cov --cov-report=html -m "not live_provider"
```

Open `htmlcov/index.html` to browse. Optional live-provider tests (require API keys) run only with:

```bash
uv run pytest -m live_provider
```

Unit vs integration (12-phase2): run only fast unit tests, or include slow integration tests that read Lesson 2 artifacts:

```bash
uv run pytest tests/unit -q
uv run pytest tests/integration -m integration -q
uv run pytest tests/unit tests/integration -m integration -q
```

## Running the Pipelines

### Main pipeline: from a new YouTube URL

```bash
uv run tim-class-pass --url "https://www.youtube.com/watch?v=VIDEO_ID" --batch-size 10
```

### Main pipeline: from an existing video folder

```bash
uv run tim-class-pass --video_id VIDEO_ID --batch-size 10
```

### Main pipeline: force re-extract frames

```bash
uv run tim-class-pass --video_id VIDEO_ID --recapture --batch-size 10
```

### Main pipeline: useful flow-control flags

```bash
uv run tim-class-pass --video_id VIDEO_ID --stop-after 2
uv run tim-class-pass --video_id VIDEO_ID --max-batches 3
uv run tim-class-pass --video_id VIDEO_ID --parallel
uv run tim-class-pass --video_id VIDEO_ID --merge-only
```

### Component 2 + Step 3 markdown pipeline

```bash
uv run python -m pipeline.component2.main ^
  --vtt "data/Lesson 2. Levels part 1/Lesson 2. Levels part 1.vtt" ^
  --visuals-json "data/Lesson 2. Levels part 1/dense_analysis.json" ^
  --output-root "data/Lesson 2. Levels part 1" ^
  --video-id "Lesson 2. Levels part 1"
```

Optional overrides:

- `--model` to force a model for markdown synthesis
- `--provider` to force a provider for markdown synthesis
- `--reducer-model` to force a model for the reducer pass
- `--reducer-provider` to force a provider for the reducer pass
- `--target-duration-seconds` to change chunk size
- `--max-concurrency` to cap simultaneous Gemini requests

### Main pipeline config (`data/<video_id>/pipeline.yml`)

One config file per processed video folder:

```text
data/<video_id>/pipeline.yml
```

Optional `video_file` and `vtt_file` are filenames inside `data/<video_id>/`.

```yaml
default:
  agent_images: ide
  provider_images: gemini
  provider_component2: gemini
  provider_component2_reducer: gemini
  provider_gaps: gemini
  provider_vlm: gemini
  provider_analyze_extract: gemini
  provider_analyze_relevance: gemini
  batch_size: 10
  workers: 4
  capture_fps: 0.5
  llm_queue_diff_threshold: 0.025
  compare_blur_radius: 1.5
  compare_artifacts_dir: "frames_structural_preprocessed"
  video_file: "Lesson 2. Levels part 1.mp4"
  vtt_file: "Lesson 2. Levels part 1.vtt"
  model_images: gemini-2.5-flash-lite
  model_component2: gemini-2.5-flash-lite
  model_component2_reducer: gemini-2.5-flash-lite
  model_gaps: gemini-2.5-flash-lite
  model_vlm: gemini-2.5-flash-lite
  model_analyze_extract: gemini-2.5-flash-lite
  model_analyze_relevance: gemini-2.5-flash-lite
```

**Precedence:** CLI > `data/<video_id>/pipeline.yml` (`default`) > env > built-in default.

Worker defaults now resolve to `max(1, floor(cpu_count / 2))` when not explicitly configured.

### AI Provider Usage

Set the provider-specific credentials you actually use:

- `GEMINI_API_KEY` for Gemini
- `OPENAI_API_KEY` for OpenAI
- `SETRA_BASE_URL` and optional `SETRA_API_KEY` for Setra
- `MLX_SERVICE_BASE_URL` for MLX-local image tasks

- Project YAML can now make provider/model choice explicit per stage with `provider_*` and `model_*` keys.
- Request usage is stored inline where available and summarized into `data/<video_id>/ai_usage_summary.json`.
- You can rebuild the summary at any time with `uv run python -m pipeline.usage_report --video-id "<video_id>" --print-summary`.

Provider transports live under `helpers/clients/`.

### CLI Reference

The main pipeline entry point is **`tim-class-pass`** (Click). Run `uv run tim-class-pass --help` for full options.

| Flag | Default | Description |
|------|---------|-------------|
| `--url URL` | — | YouTube URL to download and process |
| `--video_id ID` | — | Use existing `data/<ID>/` folder (skip download) |
| `--agent-images` | from config | Agent for Step 2 (frame analysis): `ide`, `openai`, `gemini`, `mlx`, `setra` |
| `--agent` | from config | Alias for `--agent-images` |
| `--batch-size N` | from config | Frames per agent batch (5–20 recommended) |
| `--workers N` | from config | Max workers for Step 1 + 1.5 (cap 8; default `floor(cpu_count / 2)`) |
| `--recapture` | off | Force re-extract frames even if already done |
| `--recompare` | off | Force re-run structural compare (SSIM) even if already done |
| `--parallel` | off | Step 2: generate batch task files + manifest, exit 10; then re-run with `--merge-only` |
| `--merge-only` | off | Step 2: merge batch responses into dense_analysis.json, then continue to Step 3 |
| `--stop-after N` | off | Stop after Step `1`, `2`, or `3` |
| `--max-batches N` | off | Step 2 only: stop after N batches |

**Video audio extraction:** `uv run extract-video-audio <DIR> [--output-dir PATH] [--recursive] [--overwrite] [--max-workers N] [--quiet]` — extracts AAC `.m4a` tracks from videos in `DIR` (default output: `DIR/audio/`). With **more than one** video, runs up to `min(file_count, cpu_cores/2)` FFmpeg jobs in parallel (same cap idea as the main pipeline’s `--workers`); override with `--max-workers` or set `--max-workers 1` for serial. By default prints overall count, parallel worker hint, per-file `[i/n]` lines, and **live encode lines** from FFmpeg (`time` / `speed`, throttled). When **ffprobe** can read the file duration, each line also shows an **ETA** (remaining media time ÷ speed). Use `--quiet` for summary (and errors) only.

Markdown pipeline CLI:

```bash
uv run python -m pipeline.component2.main --help
```

| Flag | Default | Description |
|------|---------|-------------|
| `--vtt` | required | Raw transcript file |
| `--visuals-json` | required | Dense frame-analysis JSON to filter and synthesize |
| `--output-root` | VTT parent | Root folder for filtered events and markdown outputs |
| `--video-id` | off | Optional config/model lookup hint |
| `--model` | off | Gemini model override for synthesis |
| `--target-duration-seconds` | `120.0` | Target chunk duration before semantic extension |
| `--max-concurrency` | `5` | Max simultaneous Gemini chunk requests |
| `--enable-concept-graph` | off | Task 12: build concept graph from rule cards → write `*.concept_graph.json` (requires rule_cards) |

---

## Starting the Pipeline as an Agent

When you (an AI agent) are asked to run the main pipeline on a video, follow these steps:

### 1. Trigger the workflow

```
/multimodal_transcript_pipeline
```

This workflow has `// turbo-all` — all shell commands auto-run without approval.

### 2. Run the initial pipeline command

```bash
uv run tim-class-pass --video_id <VIDEO_ID> --batch-size 10
```

- If downloading: use `--url` instead. You can also run `uv run python -m pipeline.main` with the same options.
- The pipeline will exit immediately after writing the first batch prompt (when using ide for Step 2).

### 3. Loop until Step 2 is complete

Read the `dense_batch_prompt_NNN-MMM.txt` file. It tells you which frames to analyze.

For each frame in the batch:
1. `view_file` on the absolute path to the `.jpg`
2. Write description (what is on screen) + delta (what changed vs. previous)
3. Save `dense_batch_response_NNN-MMM.json`
4. Re-run the pipeline command

**Do this autonomously in a loop** — do not wait for user confirmation between batches. Survey keyframes ahead of time to understand scene structure, then write entire segments efficiently.

```json
{
  "000001": { "description": "...", "delta": "Scene start" },
  "000002": { "description": "...", "delta": "No change" }
}
```

### 4. Let Step 3 complete

After all batches are processed, re-run the pipeline once more. It will automatically run the invalidation filter and markdown synthesis flow.

### 5. Verify completion

```bash
# Check frame count
(Get-ChildItem "data\<VIDEO_ID>\frames_dense" -Filter "*.txt").Count

# Check outputs exist
Get-ChildItem "data\<VIDEO_ID>" -Filter "filtered_visual_events.json"
Get-ChildItem "data\<VIDEO_ID>\output_markdown" -Filter "*.md"
```

Read the first part of `output_intermediate/<lesson>.md` to confirm Pass 1 retained the chronology and visual evidence, then inspect `output_rag_ready/<lesson>.md` to confirm the final reducer grouped the material by topic.

---

## Tips for Efficient Agent Analysis

| Situation | Strategy |
|-----------|----------|
| Static lecture scene (slides, chart) | Survey every 20–50 frames, write "No change" for identical ones |
| Active drawing / annotations | View every frame — changes happen every 1–3 seconds |
| Transition detected | Mark as `"Scene change: <description>"` in delta |
| Long repeated scene | Write one batch response covering all frames with "No change" |

**Batch size guidance:** Default 10 is safe. Increase to 20 for fast-moving content you've already surveyed. Reduce to 5 for dense annotation scenes.
