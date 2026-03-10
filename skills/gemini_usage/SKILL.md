---
name: Gemini usage
description: How to use the Gemini API in this project — env, pipeline config, scripts, and central client.
---

# Gemini Usage

Use this skill when configuring or running the pipeline (or pipeline/gap_detector / pipeline/vlm_translator) with **Gemini** as the agent or provider. All Gemini calls go through the central **`helpers/clients/gemini_client.py`** module.

---

## 1. API key

- Set **`GEMINI_API_KEY`** in `.env` (copy from `.env.template`).
- If you run with `--agent gemini` or `--provider gemini` and the key is missing, the app fails immediately with a clear error instead of failing later in the API call.

---

## 2. Where Gemini is used

| Entry point | How to select Gemini | What runs |
|-------------|----------------------|-----------|
| **pipeline/main.py** (dense pipeline) | `--agent gemini` or `--agent-images gemini` / `--agent-dedup gemini`, or set `agent_images` / `agent_dedup` in `pipeline.yml` or env | Step 2 (frame analysis) and/or Step 3 (dedup) call Gemini |
| **pipeline/gap_detector.py** | `--provider gemini` or `LLM_PROVIDER=gemini` | Transcript → visual gap list (JSON) |
| **pipeline/vlm_translator.py** | `--provider gemini` | Image + context → VLM description per gap |

---

## 3. Model selection

**Precedence:** pipeline.yml (when a video_id is in use) **>** env **>** step default.

- **pipeline.yml**  
  Under `default` (and optionally under `videos:<video_id>`), you can set:
  - `model_name` — fallback for all steps.
  - `model_images`, `model_dedup`, `model_gaps`, `model_vlm` — per-step overrides.
  Example:
  ```yaml
  default:
    agent_images: gemini
    agent_dedup: gemini
    model_name: gemini-1.5-pro
    model_images: gemini-1.5-pro
    model_dedup: gemini-1.5-pro
    model_gaps: gemini-2.5-flash
    model_vlm: gemini-1.5-pro
  ```
- **Env**  
  `MODEL_NAME`, `MODEL_IMAGES`, `MODEL_DEDUP`, `MODEL_GAPS`, `MODEL_VLM` (see `.env.template`). Used when pipeline does not set a model for that step.
- **Step defaults** (if neither pipeline nor env set a model):  
  images/dedup/vlm → `gemini-1.5-pro`; gaps → `gemini-2.5-flash`.

When using **both** OpenAI and Gemini in the same project, set **step-specific** models (e.g. `model_images` in pipeline or `MODEL_IMAGES` in env) so Gemini steps use a Gemini model (e.g. `gemini-1.5-pro`) and not `MODEL_NAME=gpt-4o`.

---

## 4. Optional: streaming

For long dedup or gap-detection runs, set **`GEMINI_STREAMING=1`** in env. Dedup and gap detection will use streaming and then parse JSON once at the end. Default is non-streaming.

---

## 5. Central client (for developers)

- **`helpers/clients/gemini_client.py`** provides:
  - `get_client()` — shared Gemini client (requires `GEMINI_API_KEY`).
  - `get_model_for_step(step, video_id=None)` — model string for step `"images"` | `"dedup"` | `"gaps"` | `"vlm"`.
  - `generate_with_retry(...)` — `generate_content` with retries (429/503/500, exponential backoff).
  - `require_gemini_key()` — no-op if key set, else raises; call when agent/provider is gemini.
- Do **not** create a new `genai.Client` or read `GEMINI_API_KEY` / model env in feature code; use `gemini_client` instead.

---

## 6. More detail

- **Usage report and implementation notes:** `docs/gemini_api_usage_report.md`
- **Rate limits and quotas:** `docs/gemini_rate_limits.md` — 429 errors, free vs paid, official links, typical limits (Flash vs Pro).
- **README:** “Gemini usage” section and CLI table
- **Env template:** `.env.template` (model and key comments)
