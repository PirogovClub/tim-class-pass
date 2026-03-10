"""
Central OpenAI API client: shared client, model resolution from config/env,
and chat helpers. Use this module instead of instantiating OpenAI in feature code.
Supports optional streaming progress via on_event callback.
"""
from __future__ import annotations

import os
from typing import Any

from helpers.clients.stream_events import (
    KIND_CHUNK,
    KIND_END,
    KIND_RETRY,
    KIND_START,
    PROVIDER_OPENAI,
    emit,
)

_client: Any = None


def get_client():
    """Return OpenAI client; uses OPENAI_API_KEY from env."""
    global _client
    if _client is None:
        from openai import OpenAI
        _client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _client


def get_model_for_step(step: str, video_id: str | None = None) -> str:
    """Resolve model name. step: images, dedup, gaps, vlm. Precedence: config > MODEL_* env > default."""
    default = "gpt-4o"
    if video_id:
        try:
            from helpers import config as pipeline_config
            cfg = pipeline_config.get_config_for_video(video_id)
            step_key = f"model_{step}"
            val = cfg.get(step_key) or cfg.get("model_name")
            if val and str(val).strip():
                return str(val).strip()
        except Exception:
            pass
    step_env = {"images": "MODEL_IMAGES", "dedup": "MODEL_DEDUP", "gaps": "MODEL_GAPS", "vlm": "MODEL_VLM"}.get(step)
    val = os.getenv(step_env or "MODEL_IMAGES") or os.getenv("MODEL_NAME")
    return (val or default).strip()


def chat_completion(
    messages: list[dict[str, Any]],
    *,
    model: str | None = None,
    step: str = "images",
    video_id: str | None = None,
    max_tokens: int = 2000,
    on_event: Any = None,
    stage: str = "openai_chat",
    frame_key: str | None = None,
) -> str:
    """Single completion; returns message content.
    If on_event is set, uses streaming and emits start/chunk/end.
    """
    client = get_client()
    model = model or get_model_for_step(step, video_id)
    if on_event is None:
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
        )
        return (resp.choices[0].message.content or "").strip()
    emit(on_event, provider=PROVIDER_OPENAI, stage=stage, kind=KIND_START, frame_key=frame_key)
    stream = client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        stream=True,
    )
    parts: list[str] = []
    for chunk in stream:
        delta = (chunk.choices[0].delta.content or "") if chunk.choices else ""
        if delta:
            parts.append(delta)
            emit(on_event, provider=PROVIDER_OPENAI, stage=stage, kind=KIND_CHUNK, text_delta=delta, frame_key=frame_key)
    emit(on_event, provider=PROVIDER_OPENAI, stage=stage, kind=KIND_END, frame_key=frame_key)
    return "".join(parts).strip()


def chat_completion_with_image(
    prompt: str,
    image_path: str,
    *,
    model: str | None = None,
    step: str = "images",
    video_id: str | None = None,
    max_tokens: int = 2000,
    on_event: Any = None,
    stage: str = "openai_images",
    frame_key: str | None = None,
) -> str:
    """Send one user message with text + image (base64); returns assistant content.
    If on_event is set, uses streaming and emits start/chunk/end.
    """
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
    return chat_completion(
        messages,
        model=model,
        step=step,
        video_id=video_id,
        max_tokens=max_tokens,
        on_event=on_event,
        stage=stage,
        frame_key=frame_key,
    )
