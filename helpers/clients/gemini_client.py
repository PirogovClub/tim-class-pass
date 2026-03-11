"""
Central Gemini API client: shared client, model selection from pipeline/env,
retries, and startup key validation. Use this module whenever the agent/provider is gemini.
Supports optional streaming progress via on_event callback.
"""
from __future__ import annotations

import os
import time
from typing import Any

from dotenv import load_dotenv

from helpers.clients.stream_events import (
    KIND_CHUNK,
    KIND_END,
    KIND_RETRY,
    KIND_START,
    PROVIDER_GEMINI,
    emit,
)

_client: Any = None

load_dotenv()

GEMINI_KEY_ERROR_MSG = (
    "GEMINI_API_KEY is required when using agent=gemini. Set it in .env or environment."
)

_STEP_ENV_SUFFIX = {
    "images": "MODEL_IMAGES",
    "gaps": "MODEL_GAPS",
    "vlm": "MODEL_VLM",
}
# Benchmark winner for frame extraction: fastest passing, good quality (see docs/benchmarking.md).
# Override via pipeline.yml (model_images) or env (MODEL_IMAGES, MODEL_NAME).
_DEFAULT_GEMINI_MODEL = "gemini-2.5-flash-lite-preview-09-2025"

_STEP_DEFAULTS = {
    "images": _DEFAULT_GEMINI_MODEL,
    "gaps": _DEFAULT_GEMINI_MODEL,
    "vlm": _DEFAULT_GEMINI_MODEL,
}

_RETRY_ATTEMPTS = 3
_RETRY_DELAYS = (1.0, 2.0, 4.0)


def require_gemini_key() -> None:
    if not (os.getenv("GEMINI_API_KEY") or "").strip():
        raise ValueError(GEMINI_KEY_ERROR_MSG)


def get_client():
    global _client
    require_gemini_key()
    if _client is None:
        from google import genai
        _client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    return _client


def get_model_for_step(step: str, video_id: str | None = None) -> str:
    if step not in _STEP_DEFAULTS:
        return _STEP_DEFAULTS.get("images", _DEFAULT_GEMINI_MODEL)
    default_model = _STEP_DEFAULTS[step]

    def _is_gemini_model(name: str) -> bool:
        return bool(name and str(name).strip().lower().startswith("gemini-"))

    if video_id:
        try:
            from helpers import config as pipeline_config
            cfg = pipeline_config.get_config_for_video(video_id)
            step_key = f"model_{step}"
            if _is_gemini_model(cfg.get(step_key) or ""):
                return (cfg.get(step_key) or "").strip()
            if _is_gemini_model(cfg.get("model_name") or ""):
                return (cfg.get("model_name") or "").strip()
        except Exception:
            pass
    env_key = _STEP_ENV_SUFFIX[step]
    value = os.getenv(env_key) or os.getenv("MODEL_NAME")
    if value and value.strip().lower().startswith("gemini-"):
        return value.strip()
    return default_model


def _is_retryable(err: BaseException) -> bool:
    err_str = str(err).upper()
    if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
        return True
    if "503" in err_str or "UNAVAILABLE" in err_str:
        return True
    if "500" in err_str or "INTERNAL" in err_str:
        return True
    return False


def generate_with_retry(model: str, contents: Any, config: Any = None, **kwargs: Any) -> Any:
    client = get_client()
    last_err: BaseException | None = None
    for attempt in range(_RETRY_ATTEMPTS):
        try:
            return client.models.generate_content(
                model=model,
                contents=contents,
                config=config,
                **kwargs,
            )
        except Exception as e:
            last_err = e
            if not _is_retryable(e) or attempt == _RETRY_ATTEMPTS - 1:
                raise
            time.sleep(_RETRY_DELAYS[attempt])
    if last_err is not None:
        raise last_err
    raise RuntimeError("generate_with_retry: unexpected state")


def generate_with_retry_stream(
    model: str,
    contents: Any,
    config: Any = None,
    *,
    on_event: Any = None,
    stage: str = "gemini_stream",
    frame_key: str | None = None,
    **kwargs: Any,
) -> str:
    """Stream generation; returns final concatenated text.
    If on_event is set, emits start/chunk/end (and retry on retries).
    """
    client = get_client()
    last_err: BaseException | None = None
    for attempt in range(_RETRY_ATTEMPTS):
        try:
            if attempt > 0 and on_event is not None:
                emit(on_event, provider=PROVIDER_GEMINI, stage=stage, kind=KIND_RETRY, attempt=attempt, frame_key=frame_key)
            if on_event is not None:
                emit(on_event, provider=PROVIDER_GEMINI, stage=stage, kind=KIND_START, frame_key=frame_key)
            chunks = client.models.generate_content_stream(
                model=model,
                contents=contents,
                config=config,
                **kwargs,
            )
            parts: list[str] = []
            last_chunk: Any = None
            for c in chunks:
                last_chunk = c
                text = c.text or ""
                if text:
                    parts.append(text)
                    if on_event is not None:
                        emit(on_event, provider=PROVIDER_GEMINI, stage=stage, kind=KIND_CHUNK, text_delta=text, frame_key=frame_key)
            usage_meta: dict[str, Any] | None = None
            if last_chunk is not None:
                um = getattr(last_chunk, "usage_metadata", None)
                if um is not None:
                    pt = getattr(um, "prompt_token_count", None) or getattr(um, "input_token_count", None)
                    ot = getattr(um, "candidates_token_count", None) or getattr(um, "output_token_count", None)
                    if pt is not None or ot is not None:
                        usage_meta = {
                            "prompt_tokens": pt if pt is not None else 0,
                            "output_tokens": ot if ot is not None else 0,
                            "prompt_eval_duration_ns": None,
                            "eval_duration_ns": None,
                        }
            if on_event is not None:
                emit(
                    on_event,
                    provider=PROVIDER_GEMINI,
                    stage=stage,
                    kind=KIND_END,
                    frame_key=frame_key,
                    meta={"usage": usage_meta} if usage_meta is not None else None,
                )
            return "".join(parts).strip()
        except Exception as e:
            last_err = e
            if not _is_retryable(e) or attempt == _RETRY_ATTEMPTS - 1:
                raise
            time.sleep(_RETRY_DELAYS[attempt])
    if last_err is not None:
        raise last_err
    return ""
