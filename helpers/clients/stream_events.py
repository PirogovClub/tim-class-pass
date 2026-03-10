"""
Shared streaming event contract for provider clients (Gemini, OpenAI, MLX).
Clients emit events via an optional on_event callback; callers see progress
while helpers still return final aggregated text.
"""
from __future__ import annotations

from typing import Any, Callable

# Event kinds
KIND_START = "start"
KIND_CHUNK = "chunk"
KIND_HEARTBEAT = "heartbeat"
KIND_END = "end"
KIND_RETRY = "retry"

# Providers
PROVIDER_MLX = "mlx"
PROVIDER_GEMINI = "gemini"
PROVIDER_OPENAI = "openai"

# Callback: receives one event dict, returns None
# Event dict: provider, stage, kind, text_delta (optional), attempt (optional),
#   frame_key (optional), meta (optional)
StreamEventCallback = Callable[[dict[str, Any]], None]


def emit(
    on_event: StreamEventCallback | None,
    *,
    provider: str,
    stage: str,
    kind: str,
    text_delta: str | None = None,
    attempt: int | None = None,
    frame_key: str | None = None,
    meta: dict[str, Any] | None = None,
) -> None:
    """Emit one stream event to the callback if provided."""
    if on_event is None:
        return
    event: dict[str, Any] = {
        "provider": provider,
        "stage": stage,
        "kind": kind,
    }
    if text_delta is not None:
        event["text_delta"] = text_delta
    if attempt is not None:
        event["attempt"] = attempt
    if frame_key is not None:
        event["frame_key"] = frame_key
    if meta is not None:
        event["meta"] = meta
    try:
        on_event(event)
    except Exception:
        pass  # do not let callback break the pipeline
