"""
Load pipeline.yml from the project folder (data/<video_id>/). All config and work for a run lives there.
Precedence: CLI > data/<video_id>/pipeline.yml (default section) > env > hardcoded default.
"""
import os
from pathlib import Path

CONFIG_FILENAME = "pipeline.yml"
DATA_DIR = "data"
DEFAULT_AGENT = "ide"
DEFAULT_BATCH_SIZE = 10
DEFAULT_CAPTURE_FPS = 0.5
DEFAULT_LLM_QUEUE_DIFF_THRESHOLD = 0.025
DEFAULT_COMPARE_BLUR_RADIUS = 1.5

# Task 8: visual compaction (config-driven, no broad CLI switch)
DEFAULT_VISUAL_EXTRACT_MAX_SUMMARIES = 5
DEFAULT_VISUAL_EVIDENCE_SUMMARY_MAX_CHARS = 240
DEFAULT_VISUAL_RULE_SUMMARY_MAX_CHARS = 180
DEFAULT_VISUAL_REVIEW_MAX_BULLETS = 2
DEFAULT_VISUAL_RAG_MAX_BULLETS = 1
DEFAULT_VISUAL_INCLUDE_SCREENSHOT_CANDIDATES = True
DEFAULT_VISUAL_STORE_RAW_BLOBS = False


def _default_pipeline_workers() -> int:
    return max((os.cpu_count() or 1) // 2, 1)


def _default_step2_chunk_workers() -> int:
    return _default_pipeline_workers()


def _parse_int(raw: str | None, default: int | None = None) -> int | None:
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _parse_float(raw: str | None, default: float | None = None) -> float | None:
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _parse_bool(raw: str | None, default: bool = False) -> bool:
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def load_pipeline_config_for_video(video_id: str) -> dict | None:
    """Load pipeline.yml from project folder data/<video_id>/pipeline.yml. Returns raw dict or None."""
    path = Path(DATA_DIR) / video_id / CONFIG_FILENAME
    if not path.is_file():
        return None
    try:
        import yaml
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception:
        return None


def get_config_for_video(video_id: str) -> dict:
    """
    Return effective config from the project folder (data/<video_id>/).
    Config file: data/<video_id>/pipeline.yml, section "default".
    Optional video_file and vtt_file: filenames relative to data/<video_id>/.
    Precedence: CLI > project pipeline.yml default > env > hardcoded.
    """
    raw = load_pipeline_config_for_video(video_id)
    yaml_default = {}
    if raw:
        yaml_default = dict(raw.get("default") or raw if isinstance(raw, dict) else {})
    result = {
        "agent_images": os.getenv("AGENT_IMAGES") or os.getenv("AGENT") or DEFAULT_AGENT,
        "provider_images": os.getenv("PROVIDER_IMAGES") or os.getenv("AGENT_IMAGES") or os.getenv("AGENT") or DEFAULT_AGENT,
        "provider_component2": os.getenv("PROVIDER_COMPONENT2") or "gemini",
        "provider_component2_reducer": os.getenv("PROVIDER_COMPONENT2_REDUCER") or os.getenv("PROVIDER_COMPONENT2") or "gemini",
        "provider_gaps": os.getenv("PROVIDER_GAPS") or os.getenv("LLM_PROVIDER") or "gemini",
        "provider_vlm": os.getenv("PROVIDER_VLM") or os.getenv("LLM_PROVIDER") or "gemini",
        "provider_analyze_extract": os.getenv("PROVIDER_ANALYZE_EXTRACT") or os.getenv("PROVIDER_IMAGES") or os.getenv("AGENT_IMAGES") or os.getenv("AGENT") or "gemini",
        "provider_analyze_relevance": os.getenv("PROVIDER_ANALYZE_RELEVANCE") or os.getenv("PROVIDER_IMAGES") or os.getenv("AGENT_IMAGES") or os.getenv("AGENT") or "gemini",
        "batch_size": DEFAULT_BATCH_SIZE,
        "parallel_batches": False,
        "workers": _parse_int(os.getenv("WORKERS") or os.getenv("MAX_WORKERS"), _default_pipeline_workers()),
        "video_file": None,
        "vtt_file": None,
        "model_name": os.getenv("MODEL_NAME"),
        "model_images": os.getenv("MODEL_IMAGES") or os.getenv("MODEL_NAME"),
        "model_component2": os.getenv("MODEL_COMPONENT2") or os.getenv("MODEL_VLM") or os.getenv("MODEL_NAME"),
        "model_gaps": os.getenv("MODEL_GAPS") or os.getenv("MODEL_NAME"),
        "model_vlm": os.getenv("MODEL_VLM") or os.getenv("MODEL_NAME"),
        "model_analyze_extract": os.getenv("MODEL_ANALYZE_EXTRACT") or os.getenv("MODEL_IMAGES") or os.getenv("MODEL_NAME"),
        "model_analyze_relevance": os.getenv("MODEL_ANALYZE_RELEVANCE") or os.getenv("MODEL_IMAGES") or os.getenv("MODEL_NAME"),
        "ssim_threshold": _parse_float(os.getenv("SSIM_THRESHOLD"), 0.95),
        "capture_fps": _parse_float(os.getenv("CAPTURE_FPS"), DEFAULT_CAPTURE_FPS),
        "llm_queue_diff_threshold": _parse_float(
            os.getenv("LLM_QUEUE_DIFF_THRESHOLD"),
            DEFAULT_LLM_QUEUE_DIFF_THRESHOLD,
        ),
        "compare_blur_radius": _parse_float(os.getenv("COMPARE_BLUR_RADIUS"), DEFAULT_COMPARE_BLUR_RADIUS),
        "compare_artifacts_dir": os.getenv("COMPARE_ARTIFACTS_DIR") or "frames_structural_preprocessed",
        "step2_parallel_chunks": _parse_bool(os.getenv("STEP2_PARALLEL_CHUNKS"), False),
        "step2_reprocess_boundaries": _parse_bool(os.getenv("STEP2_REPROCESS_BOUNDARIES"), True),
        "step2_chunk_size": _parse_int(os.getenv("STEP2_CHUNK_SIZE"), None),
        "step2_chunk_workers": _parse_int(os.getenv("STEP2_CHUNK_WORKERS"), _default_step2_chunk_workers()),
        "model_component2_reducer": os.getenv("MODEL_COMPONENT2_REDUCER") or os.getenv("MODEL_COMPONENT2") or os.getenv("MODEL_NAME"),
        "telemetry_enabled": _parse_bool(os.getenv("TELEMETRY_ENABLED"), True),
        "visual_extract_max_summaries": _parse_int(os.getenv("VISUAL_EXTRACT_MAX_SUMMARIES"), DEFAULT_VISUAL_EXTRACT_MAX_SUMMARIES),
        "visual_evidence_summary_max_chars": _parse_int(os.getenv("VISUAL_EVIDENCE_SUMMARY_MAX_CHARS"), DEFAULT_VISUAL_EVIDENCE_SUMMARY_MAX_CHARS),
        "visual_rule_summary_max_chars": _parse_int(os.getenv("VISUAL_RULE_SUMMARY_MAX_CHARS"), DEFAULT_VISUAL_RULE_SUMMARY_MAX_CHARS),
        "visual_review_max_bullets": _parse_int(os.getenv("VISUAL_REVIEW_MAX_BULLETS"), DEFAULT_VISUAL_REVIEW_MAX_BULLETS),
        "visual_rag_max_bullets": _parse_int(os.getenv("VISUAL_RAG_MAX_BULLETS"), DEFAULT_VISUAL_RAG_MAX_BULLETS),
        "visual_include_screenshot_candidates": _parse_bool(os.getenv("VISUAL_INCLUDE_SCREENSHOT_CANDIDATES"), DEFAULT_VISUAL_INCLUDE_SCREENSHOT_CANDIDATES),
        "visual_store_raw_blobs": _parse_bool(os.getenv("VISUAL_STORE_RAW_BLOBS"), DEFAULT_VISUAL_STORE_RAW_BLOBS),
        "enable_visual_compaction_debug": _parse_bool(os.getenv("ENABLE_VISUAL_COMPACTION_DEBUG"), False),
        "include_provenance_in_review_markdown": _parse_bool(os.getenv("INCLUDE_PROVENANCE_IN_REVIEW_MARKDOWN"), True),
        "include_provenance_validation_in_debug": _parse_bool(os.getenv("INCLUDE_PROVENANCE_VALIDATION_IN_DEBUG"), True),
    }
    batch_env = os.getenv("BATCH_SIZE")
    if batch_env is not None:
        try:
            result["batch_size"] = int(batch_env)
        except ValueError:
            pass
    _model_keys = (
        "model_name",
        "model_images",
        "model_component2",
        "model_component2_reducer",
        "model_gaps",
        "model_vlm",
        "model_analyze_extract",
        "model_analyze_relevance",
    )
    _provider_keys = (
        "provider_images",
        "provider_component2",
        "provider_component2_reducer",
        "provider_gaps",
        "provider_vlm",
        "provider_analyze_extract",
        "provider_analyze_relevance",
    )
    _override_keys = (
        "video_file",
        "vtt_file",
        "agent_images",
        "batch_size",
        "parallel_batches",
        "workers",
        "ssim_threshold",
        "capture_fps",
        "llm_queue_diff_threshold",
        "compare_blur_radius",
        "compare_artifacts_dir",
        "step2_parallel_chunks",
        "step2_reprocess_boundaries",
        "step2_chunk_size",
        "step2_chunk_workers",
        "telemetry_enabled",
        "visual_extract_max_summaries",
        "visual_evidence_summary_max_chars",
        "visual_rule_summary_max_chars",
        "visual_review_max_bullets",
        "visual_rag_max_bullets",
        "visual_include_screenshot_candidates",
        "visual_store_raw_blobs",
        "enable_visual_compaction_debug",
        "include_provenance_in_review_markdown",
        "include_provenance_validation_in_debug",
        *_provider_keys,
        *_model_keys,
    )
    for key, value in yaml_default.items():
        if value is not None and key in _override_keys:
            if key == "batch_size" and isinstance(value, str):
                try:
                    value = int(value)
                except ValueError:
                    value = result["batch_size"]
            if key == "ssim_threshold" and isinstance(value, str):
                value = _parse_float(value, result["ssim_threshold"])
            if key == "workers" and isinstance(value, str):
                value = _parse_int(value, result["workers"])
            if key == "step2_chunk_size" and isinstance(value, str):
                value = _parse_int(value, result["step2_chunk_size"])
            if key == "step2_chunk_workers" and isinstance(value, str):
                value = _parse_int(value, result["step2_chunk_workers"])
            if key in {"capture_fps", "llm_queue_diff_threshold", "compare_blur_radius"} and isinstance(value, str):
                value = _parse_float(value, result[key])
            if key in {"visual_extract_max_summaries", "visual_evidence_summary_max_chars", "visual_rule_summary_max_chars", "visual_review_max_bullets", "visual_rag_max_bullets"} and isinstance(value, str):
                value = _parse_int(value, result.get(key))
            if key in {"visual_include_screenshot_candidates", "visual_store_raw_blobs", "enable_visual_compaction_debug"} and isinstance(value, str):
                value = _parse_bool(value, result.get(key, False))
            result[key] = value
    if isinstance(result["batch_size"], str):
        try:
            result["batch_size"] = int(result["batch_size"])
        except ValueError:
            result["batch_size"] = DEFAULT_BATCH_SIZE
    return result
