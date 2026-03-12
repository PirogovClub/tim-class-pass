# Framework Modules and Pipeline Flow

This document lists all modules, their functions, what they do, and how they are triggered during the main pipeline and the standalone Component 2 + Step 3 markdown pipeline. It complements [README.md](../README.md) and [pipeline.md](pipeline.md).

---

## README completeness note

The README describes the framework well: pipeline overview, steps 0–3, output files, CLI, config, and agent workflow. A few details to align elsewhere:

- **Output folders:** The pipeline writes to `output_intermediate/` (Pass 1 markdown + debug) and `output_rag_ready/` (final RAG markdown). The README diagram on line 72 says `output_markdown/*.md`; the actual code uses `output_intermediate/` and `output_rag_ready/`. The "Verify completion" section (e.g. line 363) references `output_markdown`; in practice check `output_intermediate/` and `output_rag_ready/`.

---

## 1. Entry points and orchestration

### 1.1 `src/tim_class_pass/main.py`

| Function | Purpose | When triggered |
|----------|---------|----------------|
| `main()` | Console script entry for `tim-class-pass`. Resolves project root so `pipeline` is importable, then delegates to `pipeline.main.main()`. | Running `uv run tim-class-pass` or the `tim-class-pass` console script. |

### 1.2 `pipeline/main.py`

| Function | Purpose | When triggered |
|----------|---------|----------------|
| `main(...)` | Click CLI for the main pipeline. Validates `--url` xor `--video_id`, loads config from `data/<video_id>/pipeline.yml`, sets up logging to `pipeline.log`, resolves agent/batch_size/workers/capture_fps/llm_queue_diff_threshold, then runs Steps 0 → 1 → 1.5 → 1.6 → 1.7 → 2 → 3 in order. Catches `SystemExit(10)` and re-raises so the process exits with code 10 when the IDE agent must fill a batch response. | Running `uv run tim-class-pass --url "..."` or `uv run tim-class-pass --video_id "<id>"` (or `uv run python -m pipeline.main` with same options). |

**Step invocation from `main()`:**

- **Step 0:** Only if `url` is set → `downloader.extract_video_id(url)` then `downloader.download_video_and_transcript(url, video_id_resolved)`.
- **Step 1:** `dense_capturer.extract_dense_frames(video_id_resolved, video_file_override=video_file, max_workers=max_workers, capture_fps=capture_fps)` (skipped if `dense_index.json` + `frames_dense/` exist unless `--recapture`).
- **Step 1.5:** `structural_compare.run_structural_compare(video_id_resolved, force=recompare or recapture, max_workers=max_workers, progress_callback=...)`.
- **Step 1.6:** `select_llm_frames.build_llm_queue(video_id_resolved, threshold=llm_queue_diff_threshold)`.
- **Step 1.7:** `build_llm_prompts.build_llm_prompts(video_id_resolved)`.
- **Step 2:** `dense_analyzer.run_analysis(video_id_resolved, batch_size_resolved, agent=..., parallel_batches=..., merge_only=..., max_batches=..., step2_*...)`. May exit with code 10 when agent is `ide` and the batch response file is missing.
- **Step 3:** For each VTT in the video dir, `run_component2_pipeline(vtt_path=..., visuals_json_path=dense_analysis_path, output_root=video_dir, video_id=..., model/provider/reducer_model/reducer_provider from config, progress_callback=...)`.

---

## 2. Step 0 — Download

### 2.1 `pipeline/downloader.py`

| Function | Purpose | When triggered |
|----------|---------|----------------|
| `extract_video_id(url)` | Uses yt-dlp in extract-only mode to get the video ID from a YouTube URL. Returns the ID or `None` on failure. | Called from `pipeline/main.py` when `--url` is provided, before downloading. |
| `download_video_and_transcript(url, video_id)` | Creates `data/<video_id>/`, runs yt-dlp to download best mp4 and VTT subtitles (en/ru), writes `<video_id>.mp4` and `*.vtt` into that folder. Returns `True` on success. | Called from `pipeline/main.py` after `extract_video_id` when using `--url`. |

---

## 3. Step 1 — Dense frame capture

### 3.1 `pipeline/dense_capturer.py`

| Function | Purpose | When triggered |
|----------|---------|----------------|
| `_frame_number_to_key(frame_number, capture_fps)` | Maps 1-based frame number to a 6-digit second-based key string (e.g. at 0.5 fps, frame 2 → `"000001"`). | Used internally when building the index and when merging segment frames. |
| `_run_ffmpeg_cmd(cmd)` | Runs an FFmpeg command; on failure tries again via `uv run ffmpeg`. Returns `True` if any run succeeds. | Used by `_extract_segment` and the single-FFmpeg path in `extract_dense_frames`. |
| `_probe_duration_seconds(video_file)` | Runs ffprobe to get format duration in seconds. Returns `None` on failure. | Used to decide whether to split into segments when `max_workers > 1` and duration > 60s. |
| `_extract_segment(video_file, start_seconds, duration_seconds, output_dir, label, capture_fps)` | Runs FFmpeg to extract a segment of the video as JPGs at the given fps (filter: fps, scale=1280:-1, qscale:v 2) into `output_dir`. | Called in parallel (one per segment) when using segmented extraction. |
| `extract_dense_frames(video_id, video_file_override=None, max_workers=None, capture_fps=1.0)` | Cleans `frames_dense/`, optional `frames_dense_seg_*/`, and `dense_index.json`. Resolves video file from override or first `.mp4` in `data/<video_id>/`. If duration > 60s and `max_workers > 1`, splits into ~60s segments, extracts in parallel, then merges into `frames_dense/` with global second-based keys; otherwise runs a single FFmpeg extraction. Builds a key → relative path index and writes `dense_index.json`. Returns frame count. | Called from `pipeline/main.py` in Step 1 when frames are not already present or `--recapture` is set. |

---

## 4. Step 1.5 — Structural compare (SSIM)

### 4.1 `helpers/utils/compare.py`

| Function | Purpose | When triggered |
|----------|---------|----------------|
| `_load_grayscale(image_path, size=None, blur_radius=0)` | Loads image as grayscale, optionally resizes and applies Gaussian blur. | Used by `compare_images` and `save_structural_artifact`. |
| `save_structural_artifact(source_image, destination, size=None, blur_radius=0)` | Saves a grayscale (optionally resized/blurred) version of the image to `destination`. Returns `[width, height]`. | Used by `compare_images` when `artifacts_dir` is set. |
| `compare_images(baseline_image, current_image, threshold=0.95, blur_radius=0, artifacts_dir=None)` | Loads both images as grayscale with optional blur, resizes current to baseline size, optionally writes preprocessed PNGs to `artifacts_dir`, computes SSIM via skimage. Returns `ComparisonResult(score, is_significant=score < threshold, threshold, metadata)`. | Called from `structural_compare._compare_pair` for each consecutive frame pair. |

### 4.2 `pipeline/structural_compare.py`

| Function | Purpose | When triggered |
|----------|---------|----------------|
| `_base_stem(stem)` | Strips `_same_as_before` and `_diff_*` from a filename stem. | Used when renaming frames with diff value. |
| `_rename_frames_with_diff(video_dir, index, results)` | For each frame in results, computes diff = 1 - score, renames file to `frame_<key>_diff_<value>.jpg`, updates `index` and persists `dense_index.json`. Returns count of renamed files. | Called at end of `run_structural_compare` when `rename_with_diff=True`. |
| `_compare_pair(current_key, previous_key, prev_path, cur_path, threshold, blur_radius, artifacts_dir)` | Calls `compare_images(prev_path, cur_path, ...)`, measures elapsed time, returns `(current_key, {previous_key, score, is_significant, threshold, metadata, compare_seconds})`. | Used for each (prev, cur) frame pair; may run in a process pool. |
| `run_structural_compare(video_id, force=False, rename_with_diff=True, max_workers=None, progress_callback=None)` | Reads `dense_index.json`, loads config (ssim_threshold, compare_blur_radius, compare_artifacts_dir). Skips if `structural_index.json` exists and not `force`. For first frame writes a synthetic result (score=1, is_significant=True, reason=first_frame). For each consecutive pair, runs `_compare_pair` (optionally in parallel with ProcessPoolExecutor). Optionally renames frames with `_diff_<value>` and updates dense_index. Writes `structural_index.json` and progress messages. Returns path to `structural_index.json`. | Called from `pipeline/main.py` in Step 1.5 (after Step 1). |

---

## 5. Step 1.6 — LLM queue selection

### 5.1 `pipeline/select_llm_frames.py`

| Function | Purpose | When triggered |
|----------|---------|----------------|
| `_parse_diff_from_name(name)` | Extracts numeric diff from filename via regex `_diff_([0-9]*\.[0-9]+)`. Returns 0.0 if not found. | Used when selecting frames by diff threshold. |
| `build_llm_queue(video_id, threshold=None)` | Reads `dense_index.json`, resolves threshold from config if not given. Selects every frame whose filename diff > threshold (reason `above_threshold`) and also the immediately previous frame (reason `previous_of_threshold`). Recreates `llm_queue/`, copies selected JPGs from `frames_dense/` into it, writes `llm_queue/manifest.json` (video_id, threshold, total_selected, copied, items). Returns path to `llm_queue`. | Called from `pipeline/main.py` in Step 1.6. |

---

## 6. Step 1.7 — Build LLM prompts

### 6.1 `pipeline/build_llm_prompts.py`

| Function | Purpose | When triggered |
|----------|---------|----------------|
| `_build_prompt(frame_key, image_path)` | Builds a single-frame analysis prompt: `SINGLE_FRAME_PROMPT` plus “Analyze this single frame. Frame key: … Image path: …” and “Return only valid JSON…”. | Used per selected frame when writing prompt files. |
| `build_llm_prompts(video_id)` | Reads `llm_queue/manifest.json`, for each item resolves the image path under the video dir, and writes `llm_queue/<stem>_prompt.txt` with the single-frame prompt. Step 2 does not read these files; they are for inspection or external runners. Returns path to `llm_queue`. | Called from `pipeline/main.py` in Step 1.7. |

---

## 7. Step 2 — Dense analysis (batched)

### 7.1 `helpers/utils/frame_schema.py`

| Function | Purpose | When triggered |
|----------|---------|----------------|
| `key_to_timestamp(key)` | Converts 6-digit frame key to `HH:MM:SS` string. | Used when building minimal frame records and for display. |
| `minimal_no_change_frame(key, skip_reason="structural_unchanged")` | Returns a minimal frame dict: frame_timestamp, material_change=False, structural_change=False, structural_score=1.0, lesson_relevant=False, skip_reason, pipeline_status=compared. | Used in Step 2 when structural index says no significant change, or for prefill of non-queue frames. |
| `minimal_relevance_skip_frame(key, extracted_facts=None, skip_reason="lesson_irrelevant")` | Returns a frame record for relevance-skipped frames; preserves material_change from extraction when provided. | Used when a relevance gate skips a frame (if that path is used). |
| `ensure_material_change(entry)` | No-op; returns entry unchanged. Kept for backward compatibility; callers set material_change from extraction. | Called after each frame analysis in dense_analyzer before storing. |

### 7.2 `pipeline/dense_analyzer.py`

| Function | Purpose | When triggered |
|----------|---------|----------------|
| `_normalize_agent(agent)` | Maps `"antigravity"` to `"ide"`. | Used at start of `run_analysis`. |
| `_parse_json_from_response(text)` | Strips markdown code blocks, parses JSON; on failure tries trimming trailing junk and re-parsing. | Used after API responses for frame analysis. |
| `_encode_image(path)` | Reads file and returns base64-encoded string. | Not used in current flow (providers read file themselves). |
| `_single_frame_prompt(frame_key, frame_path, previous_state)` | Builds prompt with PRODUCTION_PROMPT, previous frame state, frame key/path, and “Return only valid JSON…”. | Used when calling API per frame (sequential or chunk mode). |
| `_analyze_frame_provider(provider_name, frame_path, prompt_text, video_id, on_event, frame_key)` | Gets provider via `get_provider(provider_name)`, calls `generate_text_with_image` with model from `resolve_model_for_stage("images", video_id)`, parses JSON; on parse failure retries once, then returns `minimal_no_change_frame(key, skip_reason="json_parse_failed")`. | Used by the agent-specific wrappers. |
| `_analyze_frame_openai|_analyze_frame_gemini|_analyze_frame_mlx|_analyze_frame_setra(...)` | Thin wrappers that call `_analyze_frame_provider` with the corresponding provider name. | Called from the batch/chunk processing loop when agent is openai/gemini/mlx/setra. |
| `get_batch_prompt(batch_entries, video_dir, previous_state)` | Builds the full batch prompt: PRODUCTION_PROMPT, previous state, list of “Frame key: path”, instructions for JSON object keyed by frame key, and example shape. | Used when writing the batch prompt file for IDE or when building prompt for the first chunk in chunk mode. |
| `get_batch_prompt_independent(batch_entries, video_dir)` | Same as get_batch_prompt but without previous_state (for parallel independent batches). | Used in Option B (parallel batches) when generating task files. |
| `_previous_frame_key(all_keys, current_key)` | Returns the key immediately before `current_key` in the sorted list, or None. | Used when building previous state. |
| `_last_relevant_key(analysis)` | Returns the last key in analysis that has lesson_relevant=True or material_change=True (for backward compat). | Used to track context for next batch. |
| `_write_processing_status(video_dir, analysis, total_frames, in_flight=None)` | Writes `processing_status.json` with completed/remaining counts, ETA, and counts (structural_skips, relevance_skips, accepted_scene_changes, failures). | Called after batch/chunk updates when telemetry is enabled. |
| `_load_structural_index(video_dir)` | Loads `structural_index.json` if present; returns dict or {}. | Called at start of `run_analysis`. |
| `_chunk_label(chunk_keys)` | Returns `"{first_key}-{last_key}"`. | Used for batch/chunk labels in file names and logs. |
| `partition_queue_keys(queue_keys, chunk_size)` | Splits queue_keys into consecutive chunks of size `chunk_size`. | Used in Step 2 chunk mode to partition remaining keys. |
| `_resolve_step2_chunk_workers(requested_workers)` | Resolves worker count from config/env with cap 8 and floor 1. | Used when running parallel chunks. |
| `_write_analysis_outputs(analysis, analysis_file, frames_dir)` | Sorts analysis by key, writes `dense_analysis.json` and per-frame `frames_dense/frame_<key>.json`. | Called after merging a batch or chunk result. |
| `_entries_meaningfully_different(left, right)` | Compares two frame entries as normalized JSON; returns True if different. | Used to decide whether boundary reprocessing changed the boundary frame. |
| `_process_chunk_sequential(...)` | Processes one chunk of frames sequentially: for each frame builds prompt, checks structural_index for auto-skip, calls the appropriate _analyze_frame_* or uses minimal_no_change_frame, ensures material_change, writes status. Returns dict of frame_key → entry. | Called for each chunk in chunk mode (and for boundary reprocess/replay). |
| `_reprocess_chunk_boundary(...)` | Processes only the first frame of a chunk with the previous chunk’s last state. Returns (corrected_boundary_dict, True if boundary key was in result). | Called when step2_reprocess_boundaries is True to fix chunk boundaries. |
| `_merge_chunk_results(analysis, chunk_result)` | Merges chunk_result into analysis and returns sorted combined dict. | Used after each chunk (and optional boundary correction) in chunk mode. |
| `run_analysis(video_id, batch_size=10, agent="ide", parallel_batches=False, merge_only=False, max_batches=None, step2_parallel_chunks=None, step2_reprocess_boundaries=None, step2_chunk_size=None, step2_chunk_workers=None)` | **Merge-only:** Finds all `dense_batch_response_*.json`, merges into one analysis, writes dense_analysis.json and per-frame JSONs, writes processing status and usage summary, returns. **Otherwise:** Loads dense_index and structural_index, requires llm_queue/manifest.json; builds queue_index (key → abs path in llm_queue). **Option B (parallel_batches + ide):** Generates one task file per batch with independent prompt, writes batches/manifest.json, exits 10. **Otherwise:** Prefills analysis with minimal entries for all non-queue keys, then either (A) chunk mode: partitions remaining queue keys into chunks, runs chunks in parallel with ThreadPoolExecutor, optionally reprocesses boundaries and replays chunks if boundary changed, merges after each chunk and writes outputs; or (B) sequential batches: takes next batch_size keys, writes batch prompt and response path; if agent is ide and response missing, writes last_agent_task.json and exits 10; else calls API per frame, merges batch, writes outputs. Repeats until no remaining keys or max_batches. Writes usage summary. | Called from `pipeline/main.py` in Step 2. |

---

## 8. Step 3 — Component 2 + markdown synthesis

### 8.1 `helpers/config.py`

| Function | Purpose | When triggered |
|----------|---------|----------------|
| `load_pipeline_config_for_video(video_id)` | Loads `data/<video_id>/pipeline.yml` with yaml.safe_load. Returns raw dict or None. | Used by `get_config_for_video`. |
| `get_config_for_video(video_id)` | Merges defaults (agent_images, providers, models, batch_size, workers, capture_fps, llm_queue_diff_threshold, ssim_threshold, compare_*, step2_*, telemetry_enabled, etc.) with env vars and with the `default` section of pipeline.yml. Returns effective config dict. | Called from main.py and from pipeline modules (structural_compare, select_llm_frames, dense_analyzer, component2 llm_processor, quant_reducer) and from providers for model/provider resolution. |

### 8.2 `pipeline/invalidation_filter.py`

| Function | Purpose | When triggered |
|----------|---------|----------------|
| `_timestamp_to_seconds(raw)` | Parses timestamp string (HH:MM:SS or MM:SS with optional fractional part) to integer seconds. | Used when normalizing visual event timestamps. |
| `_entry_timestamp_seconds(frame_key, entry)` | Gets timestamp from entry’s frame_timestamp or falls back to frame_key as seconds. | Used when building VisualEvent. |
| `load_dense_analysis(path)` | Loads JSON from path; validates it is a dict. | Called at start of Step 3 and by standalone markdown pipeline. |
| `is_valid_visual_event(entry)` | Returns True if material_change is true and (visual_representation_type is not in UNKNOWN_VISUAL_TYPES, or _has_instructional_signal(entry)). | Used to filter which frames become visual events. |
| `rejection_reason(entry)` | Returns "no_material_change" or "unknown_visual_type_without_instructional_signal". | Used in debug report for rejected frames. |
| `_has_instructional_signal(entry)` | Checks change_summary, educational_event_type, current_state (annotations, drawn_objects, structural_pattern, cursor_or_highlight), extracted_entities, screen_type + visual_facts for instructional keywords and negative phrases. Returns True if entry should be kept despite unknown visual type. | Used by is_valid_visual_event. |
| `_normalize_visual_event(frame_key, entry)` | Builds a `VisualEvent` (timestamp_seconds, frame_key, visual_representation_type, example_type, change_summary, current_state, extracted_entities). | Used when building the filtered events list. |
| `filter_visual_events(raw_analysis)` | Iterates raw_analysis in sorted key order; for each entry, if is_valid_visual_event, appends _normalize_visual_event to list. Returns list of VisualEvent. | Called in Step 3 and standalone markdown pipeline. |
| `build_debug_report(raw_analysis, events)` | Builds dict: input_frames, kept_events, rejected_frames, kept_frame_keys, rejected_frame_keys (map of key → rejection_reason). | Called after filtering to write debug file. |
| `write_filtered_events(path, events)` | Writes events as JSON array (model_dump per event). | Called to write filtered_visual_events.json. |
| `write_debug_report(path, report)` | Writes report dict as JSON. | Called to write filtered_visual_events.debug.json. |
| `run_invalidation_filter(input_path, output_path=None, debug_path=None)` | Loads dense analysis, runs filter_visual_events, optionally writes filtered events and debug report. Returns events list. | Can be used standalone; Step 3 does the steps explicitly in component2/main. |

### 8.3 `pipeline/component2/models.py`

| Type | Purpose |
|------|---------|
| `TranscriptLine` | start_seconds, end_seconds, text. |
| `VisualEvent` | timestamp_seconds, frame_key, visual_representation_type, example_type, change_summary, current_state, extracted_entities. |
| `LessonChunk` | chunk_index, start_time_seconds, end_time_seconds, transcript_lines, visual_events, previous_visual_state. |
| `EnrichedMarkdownChunk` | synthesized_markdown, metadata_tags. |

### 8.4 `pipeline/component2/parser.py`

| Function | Purpose | When triggered |
|----------|---------|----------------|
| `timestamp_to_seconds(raw)` | Parses VTT-style timestamp to float seconds. | Used when parsing VTT. |
| `seconds_to_timestamp(seconds)` | Formats seconds as HH:MM:SS. | Used for display. |
| `seconds_to_mmss(seconds)` | Formats seconds as MM:SS. | Used in prompts and logs. |
| `clean_vtt_text(text)` | Strips WebVTT tags, normalizes entities and whitespace. | Used when parsing caption text. |
| `_parse_vtt_manually(vtt_path)` | Parses VTT line-by-line: finds timestamp lines, collects following text lines, builds TranscriptLine list. | Fallback when webvtt library fails or is not used. |
| `parse_vtt(vtt_path)` | Tries webvtt.read(); on success builds TranscriptLine list; on failure uses _parse_vtt_manually. | Called at start of parse_and_sync. |
| `parse_filtered_visual_events(events_path)` | Loads filtered_visual_events.json, validates as list, deserializes to VisualEvent list, sorts by (timestamp_seconds, frame_key). | Called in parse_and_sync. |
| `create_lesson_chunks(vtt_lines, visual_events, target_duration_seconds=120)` | Splits transcript into chunks by target_duration_seconds and sentence boundaries (terminal punctuation or gap > 1.5s). For each chunk, assigns visual events whose timestamp falls in [chunk_start, chunk_end], carries previous_visual_state from last event of previous chunk. Returns list of LessonChunk. | Called inside parse_and_sync. |
| `parse_and_sync(vtt_path, filtered_events_path, target_duration_seconds=120)` | Parses VTT and filtered events, then create_lesson_chunks. Returns list of LessonChunk. | Called from component2/main in Step 3.2. |
| `write_lesson_chunks(path, chunks)` | Writes chunks as JSON array (model_dump). | Called to write <lesson>.chunks.json. |

### 8.5 `pipeline/component2/llm_processor.py`

| Function | Purpose | When triggered |
|----------|---------|----------------|
| `_resolve_model(video_id, model)` | Resolves model: explicit model, then config (model_component2, model_vlm, model_name), then env (MODEL_COMPONENT2, MODEL_VLM, MODEL_NAME), then default gemini-2.5-flash-lite. | Used when calling the Pass 1 synthesis provider. |
| `_resolve_provider(video_id, provider)` | Uses resolve_provider_for_stage("component2", video_id, provider). | Used when calling the Pass 1 synthesis provider. |
| `build_user_prompt(chunk)` | Builds XML-style user message: &lt;previous_visual_state&gt;, &lt;transcript&gt; (lines with [MM:SS]), &lt;visual_events&gt; (per-event timestamp, example_type, change_summary, current_state, extracted_entities). | Called per chunk when requesting Pass 1 markdown. |
| `parse_enriched_markdown_chunk(payload)` | Deserializes JSON to EnrichedMarkdownChunk. | Called after provider response. |
| `_call_provider(chunk, video_id, model, provider)` | Resolves provider and model, calls get_provider(...).generate_text with SYSTEM_PROMPT (Literal Scribe), build_user_prompt(chunk), response_schema=EnrichedMarkdownChunk, temperature=0.2. Returns (EnrichedMarkdownChunk, usage_records). | Used by process_chunk. |
| `process_chunk(chunk, video_id, model, provider)` | Async wrapper: runs _call_provider in thread. | Called from process_chunks workers. |
| `process_chunks(chunks, video_id, model, provider, max_concurrency=5, progress_callback)` | Runs process_chunk for each chunk with a semaphore; preserves order; calls progress_callback(completed, total, chunk, elapsed). Returns list of (chunk, enriched, usage_records). | Called from component2/main in Step 3.3. |
| `format_final_markdown(enriched_chunk)` | Appends "**Tags:** " + metadata_tags to synthesized_markdown if tags present. | Used when assembling Pass 1 document. |
| `assemble_video_markdown(lesson_name, processed_chunks)` | Sorts by chunk_index, formats each with format_final_markdown, joins with "---", adds "# {lesson_name}" header. Returns full markdown string. | Called in Step 3.4 to produce intermediate markdown. |
| `write_llm_debug(path, processed_chunks)` | Writes JSON array of {chunk_index, start/end_time_seconds, visual_event_count, result (model_dump), request_usage}. | Called in Step 3.4 to write <lesson>.llm_debug.json. |

### 8.6 `pipeline/component2/quant_reducer.py`

| Function | Purpose | When triggered |
|----------|---------|----------------|
| `_resolve_reducer_model(video_id, model)` | Resolves reducer model from explicit, config (model_component2_reducer, model_component2, model_vlm, model_name), env, then default gemini-2.5-flash-lite. | Used when calling the reducer. |
| `_resolve_reducer_provider(video_id, provider)` | Uses resolve_provider_for_stage("component2_reducer", video_id, provider). | Used when calling the reducer. |
| `synthesize_full_document(raw_markdown, video_id, model, provider)` | Resolves provider and model, calls get_provider(...).generate_text with QUANT_SYSTEM_PROMPT (Quantitative Trading Architect), raw_markdown as user text, temperature=0.2, max_tokens=8192. Returns (reduced_markdown, usage_records). | Called from component2/main in Step 3.5. |

### 8.7 `pipeline/component2/main.py`

| Function | Purpose | When triggered |
|----------|---------|----------------|
| `run_component2_pipeline(vtt_path, visuals_json_path, output_root=None, video_id=None, model=None, provider=None, reducer_model=None, reducer_provider=None, target_duration_seconds=120, max_concurrency=5, progress_callback=None)` | Step 3.1: Loads dense analysis, filter_visual_events, build_debug_report, write_filtered_events, write_debug_report. Step 3.2: parse_and_sync(vtt, filtered_events_path, target_duration_seconds), write_lesson_chunks. Step 3.3: process_chunks(...) with progress. Step 3.4: assemble_video_markdown, write intermediate markdown and write_llm_debug. Step 3.5: synthesize_full_document, write RAG-ready markdown and reducer usage JSON, write_video_usage_summary. Returns dict of output paths (filtered_events_path, chunk_debug_path, llm_debug_path, reducer_usage_path, intermediate_markdown_path, rag_ready_markdown_path, etc.). | Called from pipeline/main.py for each VTT in Step 3; also entry point for the standalone markdown pipeline. |
| `main()` | Click CLI: --vtt, --visuals-json, --output-root, --video-id, --model, --provider, --reducer-model, --reducer-provider, --target-duration-seconds, --max-concurrency. Calls run_component2_pipeline and echoes output paths. | Running `uv run python -m pipeline.component2.main` (standalone markdown pipeline). |

---

## 9. Helpers — clients and usage

### 9.1 `helpers/clients/provider_types.py`

| Type | Purpose |
|------|---------|
| `ProviderResponse` | text, provider, model, usage_records, raw_response. |
| `ProviderRequestError` | RuntimeError with optional usage_records. |
| `AIProvider` | Abstract base: generate_text(...), generate_text_with_image(...). |

### 9.2 `helpers/clients/providers.py`

| Function / Class | Purpose | When triggered |
|------------------|---------|----------------|
| `get_provider(name)` | Returns GeminiProvider, OpenAIProvider, MLXProvider, or SetraProvider for name in (openai, gemini, mlx, setra). | Called from dense_analyzer (frame analysis), llm_processor (Pass 1), quant_reducer (Pass 2). |
| `resolve_provider_for_stage(stage, video_id, explicit_provider)` | Returns explicit_provider if set, else config provider for stage (e.g. provider_component2, provider_images), else defaults (images/component2/component2_reducer/gaps/vlm/analyze_* → gemini). | Used when resolving which API to call for each stage. |
| `resolve_model_for_stage(stage, video_id, explicit_model)` | Returns explicit_model if set, else config model_&lt;stage&gt;, else provider-specific default (e.g. gemini_client.get_model_for_step). | Used by dense_analyzer, llm_processor, quant_reducer. |
| `GeminiProvider` | generate_text → gemini_client.generate_content_result; generate_text_with_image → gemini_client.generate_content_stream_result with image part. | Used when provider is gemini. |
| `OpenAIProvider` | generate_text → openai_client.chat_completion_result; generate_text_with_image → openai_client.chat_completion_with_image_result. | Used when provider is openai. |
| `MLXProvider` | generate_text raises NotImplementedError; generate_text_with_image → mlx_client.chat_image_result. | Used when provider is mlx. |
| `SetraProvider` | generate_text / generate_text_with_image → setra_client.chat_completion_result / chat_completion_with_image_result. | Used when provider is setra. |

### 9.3 `helpers/clients/usage.py`

| Function | Purpose | When triggered |
|----------|---------|----------------|
| `normalize_usage_record(provider, model, usage, stage, operation, attempt, status, request_id, error, extra)` | Builds a standard usage record dict (request_id, provider, model, stage, prompt_tokens, output_tokens, total_tokens, status, etc.) from provider-specific usage objects. | Used by client implementations when reporting usage. |
| `summarize_usage_records(records)` | Aggregates totals (request_count, succeeded, failed, prompt_tokens, output_tokens, total_tokens) and by provider, model, stage, status. | Called from helpers/usage_report.build_video_usage_summary. |

### 9.4 `helpers/usage_report.py`

| Function | Purpose | When triggered |
|----------|---------|----------------|
| `is_usage_record(value)` | True if value is a dict with provider, model, attempt, status. | Used when collecting usage from nested structures. |
| `collect_usage_records(value)` | Recursively collects all usage records from a dict/list tree. | Used when building video usage summary from dense_analysis and output_intermediate files. |
| `build_video_usage_summary(video_dir)` | Scans dense_analysis.json, targets.json (if present), output_intermediate/*.llm_debug.json, output_intermediate/*.reducer_usage.json; collects all usage records; calls summarize_usage_records; adds video_dir and sources. Returns summary dict. | Called by write_video_usage_summary and by pipeline/usage_report CLI. |
| `write_video_usage_summary(video_dir, output_path=None)` | Builds summary, writes to output_path or data/&lt;video_id&gt;/ai_usage_summary.json. Returns destination path. | Called after Step 2 (merge or batch) and at end of Step 3 (component2/main). |

### 9.5 `pipeline/usage_report.py`

| Function | Purpose | When triggered |
|----------|---------|----------------|
| `main()` | Click CLI: --video-id, --output, --print-summary. Writes ai_usage_summary.json and optionally prints totals. | Running `uv run python -m pipeline.usage_report --video-id "<id>" [--print-summary]`. |

---

## 10. Auxiliary / optional modules (not on main pipeline path)

These are used by scripts or separate workflows, not by the default `tim-class-pass` or Component 2 main flow:

| Module | Functions | Purpose / trigger |
|--------|-----------|-------------------|
| `pipeline/gap_detector.py` | Gap-detection and filler logic using LLM (provider/model from config). | Separate workflow for transcript gap detection; uses providers and write_video_usage_summary. |
| `pipeline/vlm_translator.py` | VLM-based translation of transcript/segments. | Separate workflow for translation; uses providers and write_video_usage_summary. |
| `pipeline/frame_extractor.py` | Frame extraction utilities. | May be used by scripts; not called from pipeline/main. |
| `pipeline/stitcher.py` | Stitching/merging utilities. | May be used by scripts; not called from pipeline/main. |
| `helpers/analyze.py` | Analysis helpers. | Used by tests or scripts; not in main pipeline. |

---

## 11. Pipeline trigger summary (main pipeline)

| Step | Trigger | Module(s) | Key functions |
|------|--------|-----------|---------------|
| 0 | `--url` provided | downloader | extract_video_id, download_video_and_transcript |
| 1 | No dense_index + frames_dense or --recapture | dense_capturer | extract_dense_frames |
| 1.5 | Always (skip if structural_index exists and not force) | structural_compare, helpers.utils.compare | run_structural_compare, compare_images |
| 1.6 | Always | select_llm_frames | build_llm_queue |
| 1.7 | Always | build_llm_prompts | build_llm_prompts |
| 2 | Always after 1.7 | dense_analyzer, frame_schema, providers, usage_report | run_analysis, get_batch_prompt*, _analyze_frame_*, _write_analysis_outputs, write_video_usage_summary |
| 3 | After Step 2 completes (no exit 10) | component2/main, invalidation_filter, parser, llm_processor, quant_reducer, usage_report | run_component2_pipeline, filter_visual_events, parse_and_sync, process_chunks, assemble_video_markdown, synthesize_full_document, write_video_usage_summary |

---

## 12. Standalone markdown pipeline trigger summary

| Step | Trigger | Module(s) | Key functions |
|------|--------|-----------|---------------|
| — | `uv run python -m pipeline.component2.main --vtt ... --visuals-json ...` | component2/main | main() → run_component2_pipeline |
| 3.1 | Inside run_component2_pipeline | invalidation_filter | load_dense_analysis, filter_visual_events, build_debug_report, write_filtered_events, write_debug_report |
| 3.2 | After 3.1 | component2/parser | parse_and_sync, write_lesson_chunks |
| 3.3 | After 3.2 | component2/llm_processor | process_chunks |
| 3.4 | After 3.3 | component2/llm_processor | assemble_video_markdown, write_llm_debug |
| 3.5 | After 3.4 | component2/quant_reducer, usage_report | synthesize_full_document, write_video_usage_summary |

This completes the full list of modules, functions, and pipeline triggers for the framework.
