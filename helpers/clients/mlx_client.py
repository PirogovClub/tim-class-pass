"""
MLX-native API client for local vision tasks.
Uses GET /api/v1/models, POST /api/v1/chat with task/prompt and image_base64.
Sending base64 avoids needing the image on the server filesystem.
"""
from __future__ import annotations

import base64
import json
import os
import time
from pathlib import Path
from typing import Any

from helpers.clients.stream_events import (
    KIND_CHUNK,
    KIND_END,
    KIND_RETRY,
    KIND_START,
    PROVIDER_MLX,
    emit,
)

def normalize_mlx_host(host: str | None = None) -> str:
    """Return MLX service base URL from env or argument (for display / scripts)."""
    return _base_url(host)


def _base_url(host: str | None = None) -> str:
    if host:
        return host if host.startswith("http") else f"http://{host}"
    return (
        os.environ.get("MLX_SERVICE_BASE_URL")
        or os.environ.get("LOCAL_MLX_SERVER")
        or "http://127.0.0.1:11434"
    ).rstrip("/")


def _path_on_server(local_path: str | Path) -> str:
    """Convert local path to server path if mapping is configured."""
    local = str(Path(local_path).resolve())
    prefix = os.environ.get("MLX_LOCAL_PATH_PREFIX")
    server_prefix = os.environ.get("MLX_SERVER_PATH_PREFIX")
    if prefix and server_prefix and local.replace("\\", "/").startswith(prefix.replace("\\", "/")):
        return server_prefix.rstrip("/") + local[len(prefix.rstrip("/\\")) :].replace("\\", "/")
    return local.replace("\\", "/")


# Vision tasks returned as "models" for benchmark compatibility
MLX_VISION_TASKS = ("vision_ocr", "vision_strategy")

_RETRY_ATTEMPTS = 3
_RETRY_DELAYS = (1.0, 2.0, 4.0)


def _is_retryable(err: BaseException) -> bool:
    s = str(err).upper()
    if "429" in s or "503" in s or "500" in s or "UNAVAILABLE" in s or "ECONNREFUSED" in s:
        return True
    return False


def list_models(host: str | None = None) -> list[str]:
    """
    Return list of vision task names for the MLX API (mlx-vision_ocr, mlx-vision_strategy).
    Uses GET /api/v1/models; only tasks that accept images are returned as "models".
    """
    import urllib.request

    base = _base_url(host)
    url = f"{base}/api/v1/models"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read().decode())
    models_list = data.get("models") or []
    names = []
    for m in models_list:
        task = m.get("task") if isinstance(m, dict) else None
        if task in MLX_VISION_TASKS:
            names.append(f"mlx-{task}")
    return sorted(names)


def chat_image(
    model: str,
    prompt: str,
    image_path: Path | str,
    *,
    host: str | None = None,
    options: dict[str, Any] | None = None,
    request_kwargs: dict[str, Any] | None = None,
    on_event: Any = None,
    stage: str = "mlx_images",
    frame_key: str | None = None,
) -> str:
    """
    Send image + prompt to MLX POST /api/v1/chat. Accepts a path: client reads the file,
    converts to base64, sends image_base64 (no image_path). Per lmg-ai-chats docs we use
    non-streaming for vision to avoid "incomplete chunked read"; if on_event is set we
    emit start/chunk/end after receiving the full response.
    """
    if not model.startswith("mlx-"):
        raise ValueError(f"MLX chat_image expects model like mlx-vision_ocr, got: {model}")
    task = model[4:]  # strip "mlx-"
    if task not in MLX_VISION_TASKS:
        raise ValueError(f"MLX task must be one of {MLX_VISION_TASKS}, got: {task}")

    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {path}")

    image_base64_str = base64.b64encode(path.read_bytes()).decode("ascii")
    base = _base_url(host)
    url = f"{base}/api/v1/chat"
    # Prefer non-streaming for vision (docs: avoids "incomplete chunked read")
    payload: dict[str, Any] = {
        "task": task,
        "prompt": prompt,
        "image_base64": image_base64_str,
    }

    last_err: BaseException | None = None
    for attempt in range(_RETRY_ATTEMPTS):
        try:
            if attempt > 0 and on_event is not None:
                emit(on_event, provider=PROVIDER_MLX, stage=stage, kind=KIND_RETRY, attempt=attempt, frame_key=frame_key)
            return _chat_image_impl(url, payload, on_event, stage, frame_key)
        except Exception as e:
            last_err = e
            if attempt == _RETRY_ATTEMPTS - 1:
                raise
            if not _is_retryable(e):
                raise
            time.sleep(_RETRY_DELAYS[attempt])
    if last_err is not None:
        raise last_err
    return ""


def _chat_image_impl(
    url: str,
    payload: dict[str, Any],
    on_event: Any,
    stage: str,
    frame_key: str | None,
) -> str:
    import urllib.request

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    # Vision: we send stream=false (see client-migration.md); long timeout for inference
    with urllib.request.urlopen(req, timeout=300) as r:
        out = json.loads(r.read().decode())
    response_text = (out.get("response") or "").strip()
    if on_event is not None:
        emit(on_event, provider=PROVIDER_MLX, stage=stage, kind=KIND_START, frame_key=frame_key)
        if response_text:
            emit(on_event, provider=PROVIDER_MLX, stage=stage, kind=KIND_CHUNK, text_delta=response_text, frame_key=frame_key)
        emit(on_event, provider=PROVIDER_MLX, stage=stage, kind=KIND_END, frame_key=frame_key)
    return response_text
