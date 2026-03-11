# Gemini API Usage & Improvement Report

**Project:** tim-class-pass  
**Date:** 2025-03-08  
**Dependency:** `google-genai>=1.66.0`

---

## Implementation status (current)

As of the Gemini client implementation, the project has:

- **Central client:** All Gemini calls go through **`gemini_client.py`** (`get_client()`, `get_model_for_step()`, `generate_with_retry()`). No per-module client creation.
- **Model selection:** **pipeline.yml** first (optional `model_name`, `model_images`, `model_dedup`, `model_gaps`, `model_vlm` under `default` or `videos`), then env (`MODEL_NAME`, `MODEL_IMAGES`, etc.), then step defaults. See [README.md](../README.md) “Gemini usage” and [.env.template](../.env.template).
- **Startup validation:** When agent or provider is `gemini`, `require_gemini_key()` runs before any step; missing `GEMINI_API_KEY` fails fast with a clear error.
- **Retries:** `generate_with_retry()` retries on 429/503/500 with exponential backoff (1s, 2s, 4s).
- **Streaming:** Optional `GEMINI_STREAMING=1` uses streaming for dedup and gap detection; default remains non-streaming.
- **Generation config:** All Gemini call sites use `GenerateContentConfig` (temperature, `response_mime_type` for JSON where applicable). Empty responses are handled (raise or safe default).

**How to use:** Set `GEMINI_API_KEY` in `.env`. Optionally set models in `pipeline.yml` or env. Run with `--agent gemini` or `AGENT_IMAGES`/`AGENT_DEDUP`=gemini (main pipeline), or `--provider gemini` (gap_detector, vlm_translator). See README and the skill `skills/gemini_usage/SKILL.md`.

The sections below describe the **original** state and improvement ideas; many of the latter are now implemented.

---

## 1. Where the Gemini API Key Is Used

| File | Function | Purpose |
|------|----------|---------|
| `pipeline/dense_analyzer.py` | `_analyze_frame_gemini()` | Frame-by-frame image + text analysis (trading visuals) |
| `pipeline/deduplicator.py` | `_dedup_gemini()` | Text-only deduplication of scene descriptions → JSON |
| `pipeline/gap_detector.py` | `extract_gaps_gemini()` | Transcript → structured gaps (JSON with Pydantic schema) |
| `pipeline/vlm_translator.py` | `translate_gemini()` | Image + context → VLM description (visual gap translation) |

**Configuration:** `GEMINI_API_KEY` is read from environment (`.env` / `.env.template`). No in-repo validation that the key is set when `--agent gemini` or `AGENT_IMAGES`/`AGENT_DEDUP`=gemini is used.

---

## 2. Current Client Usage

- **No shared client.** Each of the four modules does:
  - Lazy `from google import genai` and `from google.genai import types`
  - `client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))` inside the Gemini-specific function
- **No central config.** Model names and options are scattered:
  - `dense_analyzer`: `MODEL_NAME` / `MODEL_IMAGES` (default `gemini-1.5-pro`)
  - `deduplicator`: `MODEL_NAME` / `MODEL_DEDUP` (default `gemini-1.5-pro`)
  - `gap_detector`: `MODEL_NAME` (default `gemini-2.5-flash`)
  - `vlm_translator`: `MODEL_NAME` (default `gemini-1.5-pro`)
- **Single API surface used:** `client.models.generate_content(...)` with `types.Content` / `types.Part` (and in `gap_detector` only: `types.GenerateContentConfig` with `response_mime_type` / `response_schema`).

So the project uses a **valid** client (`genai.Client`) but in a duplicated, ad-hoc way with no reuse or centralized configuration.

---

## 3. What the SDK Supports vs What We Use

| SDK capability | Used in project? | Notes |
|----------------|------------------|--------|
| `generate_content` (sync) | ✅ Yes | All four Gemini call sites |
| `generate_content_stream` | ❌ No | Could improve UX for long dedup/gap runs |
| `GenerateContentConfig` (temperature, top_p, top_k, etc.) | ⚠️ Partial | Only in `gap_detector` (response schema + MIME); no temperature/top_p elsewhere |
| Structured output (Pydantic / response_schema) | ⚠️ Partial | Only `gap_detector`; dedup/analyzer/translator parse JSON manually |
| Embeddings | ❌ No | Not used (could be relevant for semantic dedup/similarity) |
| Files API (upload once, reference by ID) | ❌ No | Every frame sends raw bytes; upload+reference could reduce payload and reuse |
| Chat / multi-turn | ❌ No | All single-turn prompts |
| Retries / backoff | ❌ No | No explicit retry on rate limit or transient errors |
| Safety / content filter config | ❌ No | Defaults only |
| Async client | ❌ No | All sync; batching is sequential in `dense_analyzer` |

So we use only a **small subset** of the SDK: one-off sync `generate_content` with minimal config.

---

## 4. Improvement Recommendations

### 4.1 Central Gemini Client and Config (high impact)

- **Add a single Gemini client factory** (e.g. in a new `gemini_client.py` or inside `config.py`):
  - Read `GEMINI_API_KEY` once; raise a clear error at pipeline start if provider is `gemini` and key is missing.
  - Return a shared `genai.Client(api_key=...)` (or a thin wrapper) so all four modules use the same client and key source.
- **Centralize model and generation defaults** (e.g. in config or env):
  - e.g. `MODEL_IMAGES`, `MODEL_DEDUP`, `MODEL_GAPS`, `MODEL_VLM` with fallback to `MODEL_NAME`, so behavior is consistent and easy to tune per step.

This reduces duplication, ensures one place to add retries/logging, and makes it easier to switch to Vertex or another backend later.

### 4.2 Use Full `GenerateContentConfig` Where Useful (medium impact)

- **Dedup and analyzer:** Pass `GenerateContentConfig` with:
  - `response_mime_type="application/json"`
  - `response_schema=...` (Pydantic model where applicable) so the model returns valid JSON and we can drop ad-hoc `_parse_json_from_response` where possible.
- **All Gemini calls:** Consider explicit `temperature` / `top_p` (e.g. lower for dedup/gaps, slightly higher for creative descriptions) so behavior is reproducible and tunable.

### 4.3 Retries and Robustness (high impact)

- **Wrap Gemini calls** (in the central client or in each call site) with retries:
  - Retry on 429 (rate limit), 503, and possibly 500, with exponential backoff.
- **Validate `response.text` (and candidates)** before parsing JSON; handle empty or malformed responses with a clear error or fallback instead of raw `model_validate_json`/dict access that can raise.

### 4.4 Streaming for Long-Running Steps (medium impact)

- For **dedup** and **gap detection**, which can have long prompts and long outputs:
  - Use `generate_content_stream()` and aggregate the streamed text, then parse JSON once at the end.
  - Improves perceived responsiveness and can help with timeouts on large payloads.

### 4.5 Files API for Dense Frames (lower priority, higher complexity)

- In **dense_analyzer** and **vlm_translator**, frames are sent as raw bytes every time.
  - The SDK supports uploading files and referencing them by ID; for repeated or large batches, upload once per frame (or per video) and reference by ID in `generate_content`.
  - Reduces payload size and can help with rate limits; implement after central client and retries are in place.

### 4.6 Optional: Async and Concurrency (medium impact, higher effort)

- **dense_analyzer** runs frames in a loop and could run multiple Gemini requests in parallel (e.g. with `asyncio` and an async Gemini client) to speed up batch analysis.
  - Requires introducing async and possibly an async-capable client usage pattern; do after centralizing the client.

### 4.7 API Key and Provider Validation at Startup (low effort)

- When the main pipeline (`tim-class-pass` / `pipeline.main`) or any script selects `gemini` as the agent (from CLI or config):
  - Check `os.getenv("GEMINI_API_KEY")` and fail fast with a clear message if missing, instead of failing later inside a Gemini call with a generic API error.

### 4.8 Documentation and .env.template (low effort)

- In `.env.template` and README, document:
  - Which steps use Gemini when `AGENT_IMAGES` / `AGENT_DEDUP` or `--agent gemini` is set.
  - Optional env vars: `MODEL_IMAGES`, `MODEL_DEDUP`, `MODEL_NAME`, etc.
- Add a short “Gemini usage” section in the README pointing to this report and to the central client once it exists.

---

## 5. Summary

| Area | Current state | Suggested direction |
|------|----------------|---------------------|
| **Client** | New client per call, no reuse | Single shared client + central config |
| **Config** | Scattered env vars and defaults | Central model/config per step (with env overrides) |
| **Generation config** | Minimal (only in gap_detector) | Use `GenerateContentConfig` (temperature, schema, MIME) everywhere it helps |
| **Structured output** | Only gap_detector uses schema | Extend to dedup (and analyzer if we define Pydantic models) |
| **Resilience** | No retries, ad-hoc JSON parsing | Retries + backoff; validate response before parse |
| **Streaming** | Not used | Use for long-running text (dedup, gaps) |
| **Startup** | No key check | Validate Gemini key when provider is gemini |
| **Docs** | Env mentioned, no Gemini-specific doc | Document Gemini usage and env vars; link this report |

We do have a proper client in the sense of using the official `google-genai` SDK and `genai.Client`, but we underuse it: no shared client, no retries, no streaming, and only one place using structured output and generation config. Implementing the high-impact items (central client, retries, and key validation) will make Gemini usage more robust and easier to extend (streaming, Files API, async) later.
