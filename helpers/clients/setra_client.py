"""
Setra API client using an OpenAI-compatible chat interface.
Configure via SETRA_BASE_URL, SETRA_API_KEY, and optional SETRA_MODEL.
"""
from __future__ import annotations

import os
import time
from typing import Any

from helpers.clients.provider_types import ProviderRequestError, ProviderResponse
from helpers.clients.stream_events import (
    KIND_CHUNK,
    KIND_END,
    KIND_RETRY,
    KIND_START,
    emit,
)
from helpers.clients.usage import normalize_usage_record

PROVIDER_SETRA = "setra"

_client: Any = None
_RETRY_ATTEMPTS = 3
_RETRY_DELAYS = (1.0, 2.0, 4.0)


def require_setra_config() -> None:
    if not (os.getenv("SETRA_BASE_URL") or "").strip():
        raise ValueError("SETRA_BASE_URL is required when using provider=setra.")


def get_client():
    global _client
    require_setra_config()
    if _client is None:
        from openai import OpenAI

        _client = OpenAI(
            api_key=os.getenv("SETRA_API_KEY") or "setra",
            base_url=os.getenv("SETRA_BASE_URL"),
        )
    return _client


def get_model_for_step(step: str, video_id: str | None = None) -> str:
    if video_id:
        try:
            from helpers import config as pipeline_config

            cfg = pipeline_config.get_config_for_video(video_id)
            val = cfg.get(f"model_{step}") or cfg.get("model_name")
            if val and str(val).strip():
                return str(val).strip()
        except Exception:
            pass
    env_key = {"images": "MODEL_IMAGES", "gaps": "MODEL_GAPS", "vlm": "MODEL_VLM"}.get(step)
    return (
        os.getenv(env_key or "MODEL_NAME")
        or os.getenv("SETRA_MODEL")
        or "setra-default"
    ).strip()


def _is_retryable(err: BaseException) -> bool:
    err_str = str(err).upper()
    return any(token in err_str for token in ("429", "500", "503", "TIMEOUT", "UNAVAILABLE", "RATE LIMIT"))


def chat_completion_result(
    messages: list[dict[str, Any]],
    *,
    model: str | None = None,
    step: str = "images",
    video_id: str | None = None,
    max_tokens: int = 2000,
    response_format: dict[str, Any] | None = None,
    on_event: Any = None,
    stage: str = "setra_chat",
    frame_key: str | None = None,
) -> ProviderResponse:
    client = get_client()
    model = model or get_model_for_step(step, video_id)
    usage_records: list[dict[str, Any]] = []
    for attempt in range(_RETRY_ATTEMPTS):
        try:
            if attempt > 0 and on_event is not None:
                emit(on_event, provider=PROVIDER_SETRA, stage=stage, kind=KIND_RETRY, attempt=attempt, frame_key=frame_key)
            if on_event is None:
                resp = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    max_tokens=max_tokens,
                    response_format=response_format,
                )
                usage_record = normalize_usage_record(
                    provider=PROVIDER_SETRA,
                    model=model,
                    usage=getattr(resp, "usage", None),
                    stage=stage,
                    operation="chat",
                    attempt=attempt + 1,
                    status="succeeded",
                    extra={"frame_key": frame_key},
                )
                usage_records.append(usage_record)
                return ProviderResponse(
                    text=(resp.choices[0].message.content or "").strip(),
                    provider=PROVIDER_SETRA,
                    model=model,
                    usage_records=usage_records,
                    raw_response=resp,
                )

            emit(on_event, provider=PROVIDER_SETRA, stage=stage, kind=KIND_START, frame_key=frame_key)
            stream = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                response_format=response_format,
                stream=True,
                stream_options={"include_usage": True},
            )
            parts: list[str] = []
            usage_obj: Any = None
            for chunk in stream:
                delta = (chunk.choices[0].delta.content or "") if chunk.choices else ""
                if delta:
                    parts.append(delta)
                    emit(on_event, provider=PROVIDER_SETRA, stage=stage, kind=KIND_CHUNK, text_delta=delta, frame_key=frame_key)
                usage_obj = getattr(chunk, "usage", None) or usage_obj
            usage_record = normalize_usage_record(
                provider=PROVIDER_SETRA,
                model=model,
                usage=usage_obj,
                stage=stage,
                operation="chat",
                attempt=attempt + 1,
                status="succeeded",
                extra={"frame_key": frame_key},
            )
            usage_records.append(usage_record)
            emit(
                on_event,
                provider=PROVIDER_SETRA,
                stage=stage,
                kind=KIND_END,
                frame_key=frame_key,
                meta={"usage": usage_record, "usage_records": usage_records},
            )
            return ProviderResponse(
                text="".join(parts).strip(),
                provider=PROVIDER_SETRA,
                model=model,
                usage_records=usage_records,
                raw_response=None,
            )
        except Exception as e:
            usage_records.append(
                normalize_usage_record(
                    provider=PROVIDER_SETRA,
                    model=model,
                    usage=None,
                    stage=stage,
                    operation="chat",
                    attempt=attempt + 1,
                    status="failed",
                    error=str(e),
                    extra={"frame_key": frame_key},
                )
            )
            if not _is_retryable(e) or attempt == _RETRY_ATTEMPTS - 1:
                raise ProviderRequestError(str(e), usage_records=usage_records) from e
            time.sleep(_RETRY_DELAYS[attempt])
    raise ProviderRequestError("Setra request failed unexpectedly", usage_records=usage_records)


def chat_completion(
    messages: list[dict[str, Any]],
    *,
    model: str | None = None,
    step: str = "images",
    video_id: str | None = None,
    max_tokens: int = 2000,
    response_format: dict[str, Any] | None = None,
    on_event: Any = None,
    stage: str = "setra_chat",
    frame_key: str | None = None,
) -> str:
    return chat_completion_result(
        messages,
        model=model,
        step=step,
        video_id=video_id,
        max_tokens=max_tokens,
        response_format=response_format,
        on_event=on_event,
        stage=stage,
        frame_key=frame_key,
    ).text


def chat_completion_with_image_result(
    prompt: str,
    image_path: str,
    *,
    model: str | None = None,
    step: str = "images",
    video_id: str | None = None,
    max_tokens: int = 2000,
    response_format: dict[str, Any] | None = None,
    on_event: Any = None,
    stage: str = "setra_images",
    frame_key: str | None = None,
) -> ProviderResponse:
    import base64

    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
            ],
        }
    ]
    return chat_completion_result(
        messages,
        model=model,
        step=step,
        video_id=video_id,
        max_tokens=max_tokens,
        response_format=response_format,
        on_event=on_event,
        stage=stage,
        frame_key=frame_key,
    )


def chat_completion_with_image(
    prompt: str,
    image_path: str,
    *,
    model: str | None = None,
    step: str = "images",
    video_id: str | None = None,
    max_tokens: int = 2000,
    response_format: dict[str, Any] | None = None,
    on_event: Any = None,
    stage: str = "setra_images",
    frame_key: str | None = None,
) -> str:
    return chat_completion_with_image_result(
        prompt,
        image_path,
        model=model,
        step=step,
        video_id=video_id,
        max_tokens=max_tokens,
        response_format=response_format,
        on_event=on_event,
        stage=stage,
        frame_key=frame_key,
    ).text
