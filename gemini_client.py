"""
Central Gemini API client: shared client, model selection from pipeline/env,
retries, and startup key validation. Use this module whenever the agent/provider is gemini.
"""
import os
import time
from typing import Any

# Lazy import to avoid loading google.genai when gemini is not used
_client: Any = None

GEMINI_KEY_ERROR_MSG = (
    "GEMINI_API_KEY is required when using agent=gemini. Set it in .env or environment."
)

# Step -> env key suffix -> default model
_STEP_ENV_SUFFIX = {
    "images": "MODEL_IMAGES",
    "dedup": "MODEL_DEDUP",
    "gaps": "MODEL_GAPS",
    "vlm": "MODEL_VLM",
}
_STEP_DEFAULTS = {
    "images": "gemini-1.5-pro",
    "dedup": "gemini-1.5-pro",
    "gaps": "gemini-2.5-flash",
    "vlm": "gemini-1.5-pro",
}

# Retry: 3 attempts, exponential backoff 1s, 2s, 4s
_RETRY_ATTEMPTS = 3
_RETRY_DELAYS = (1.0, 2.0, 4.0)


def require_gemini_key() -> None:
    """Raise if GEMINI_API_KEY is not set. Call when agent/provider is gemini."""
    if not (os.getenv("GEMINI_API_KEY") or "").strip():
        raise ValueError(GEMINI_KEY_ERROR_MSG)


def get_client():
    """Return a shared Gemini client. Raises ValueError if GEMINI_API_KEY is missing."""
    global _client
    require_gemini_key()
    if _client is None:
        from google import genai
        _client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    return _client


def get_model_for_step(step: str, video_id: str | None = None) -> str:
    """
    Resolve Gemini model for a pipeline step.
    Precedence: pipeline.yml (when video_id set) > env > step default.
    step: one of "images", "dedup", "gaps", "vlm".
    """
    if step not in _STEP_DEFAULTS:
        return _STEP_DEFAULTS.get("images", "gemini-1.5-pro")
    default_model = _STEP_DEFAULTS[step]
    # From pipeline config when video_id is available
    if video_id:
        try:
            import config as pipeline_config
            cfg = pipeline_config.get_config_for_video(video_id)
            step_key = f"model_{step}"  # model_images, model_dedup, etc.
            if cfg.get(step_key):
                return cfg[step_key]
            if cfg.get("model_name"):
                return cfg["model_name"]
        except Exception:
            pass
    # From env
    env_key = _STEP_ENV_SUFFIX[step]
    value = os.getenv(env_key) or os.getenv("MODEL_NAME")
    if value:
        return value
    return default_model


def _is_retryable(err: BaseException) -> bool:
    """True if we should retry on this exception (rate limit, server error)."""
    err_str = str(err).upper()
    if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
        return True
    if "503" in err_str or "UNAVAILABLE" in err_str:
        return True
    if "500" in err_str or "INTERNAL" in err_str:
        return True
    return False


def generate_with_retry(model: str, contents: Any, config: Any = None, **kwargs: Any) -> Any:
    """
    Call client.models.generate_content with retries on 429, 503, 500.
    Returns the same response type as generate_content.
    Callers should validate response.text before parsing (e.g. empty string).
    """
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


def generate_with_retry_stream(model: str, contents: Any, config: Any = None, **kwargs: Any) -> str:
    """
    Call client.models.generate_content_stream with retries; aggregate chunks and return full text.
    Use when GEMINI_STREAMING=1 for long-running dedup/gap steps. Same retry logic as generate_with_retry.
    """
    client = get_client()
    last_err: BaseException | None = None
    for attempt in range(_RETRY_ATTEMPTS):
        try:
            chunks = client.models.generate_content_stream(
                model=model,
                contents=contents,
                config=config,
                **kwargs,
            )
            return "".join(c.text or "" for c in chunks).strip()
        except Exception as e:
            last_err = e
            if not _is_retryable(e) or attempt == _RETRY_ATTEMPTS - 1:
                raise
            time.sleep(_RETRY_DELAYS[attempt])
    if last_err is not None:
        raise last_err
    return ""
