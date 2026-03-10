"""Tests for MLX client: path → base64 → POST /api/v1/chat (no image_path in payload)."""
from __future__ import annotations

import base64
import json
import tempfile
from pathlib import Path

from helpers.clients import mlx_client


# Minimal 1x1 PNG (same as lmg-ai-chats test_mlx_service) for vision tests.
MINIMAL_PNG_B64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="


def test_chat_image_converts_path_to_base64_and_sends_image_base64(monkeypatch) -> None:
    """When given an image path, client must read the file, encode as base64, and send image_base64 to /api/v1/chat (no image_path)."""
    request_body: list[dict] = []

    def fake_urlopen(req, timeout=None):
        request_body.append(json.loads(req.data.decode("utf-8")))
        # Return a minimal success response like the server (non-stream).
        body = json.dumps({"response": "ocr-result"}).encode("utf-8")
        return type("R", (), {"read": lambda self, size=-1: body, "__enter__": lambda s: s, "__exit__": lambda s, *a: None})()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        f.write(base64.b64decode(MINIMAL_PNG_B64))
        path = f.name
    try:
        result = mlx_client.chat_image(
            "mlx-vision_ocr",
            "extract text",
            path,
        )
    finally:
        Path(path).unlink(missing_ok=True)

    assert result == "ocr-result"
    assert len(request_body) == 1
    payload = request_body[0]
    assert payload.get("task") == "vision_ocr"
    assert payload.get("prompt") == "extract text"
    assert "image_base64" in payload
    assert payload["image_base64"] == MINIMAL_PNG_B64
    assert "image_path" not in payload


def test_chat_image_with_on_event_emits_events_after_non_stream_response(monkeypatch) -> None:
    """With on_event, we use non-streaming (no stream in payload); after full response we emit start/chunk/end."""
    request_body: list[dict] = []
    events = []

    def fake_urlopen(req, timeout=None):
        request_body.append(json.loads(req.data.decode("utf-8")))
        body = json.dumps({"response": "xy"}).encode("utf-8")
        return type("R", (), {"read": lambda self, size=-1: body, "__enter__": lambda s: s, "__exit__": lambda s, *a: None})()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        f.write(base64.b64decode(MINIMAL_PNG_B64))
        path = f.name
    try:
        result = mlx_client.chat_image(
            "mlx-vision_ocr",
            "extract",
            path,
            on_event=events.append,
            stage="test",
        )
    finally:
        Path(path).unlink(missing_ok=True)

    assert result == "xy"
    assert "stream" not in request_body[0] or request_body[0].get("stream") is False
    assert request_body[0].get("image_base64") == MINIMAL_PNG_B64
    kinds = [e["kind"] for e in events]
    assert "start" in kinds
    assert "chunk" in kinds
    assert "end" in kinds
