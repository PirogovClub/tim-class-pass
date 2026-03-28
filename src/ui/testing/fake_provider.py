from __future__ import annotations

import json
import os
import time
from typing import Any

from helpers.clients.provider_types import AIProvider, ProviderResponse
from ui.testing.fake_payloads import fake_frame_analysis_payload, fake_provider_text


def _fake_delay_seconds() -> float:
    raw_value = os.getenv("UI_FAKE_DELAY_SECONDS", "0")
    try:
        return max(0.0, float(raw_value))
    except ValueError:
        return 0.0


class FakeProvider(AIProvider):
    def __init__(self, name: str = "fake") -> None:
        self.name = name

    def _response(
        self,
        *,
        model: str,
        response_schema: Any = None,
        stage: str = "",
        frame_key: str | None = None,
    ) -> ProviderResponse:
        delay = _fake_delay_seconds()
        if delay > 0:
            time.sleep(delay)
        payload = fake_provider_text(response_schema, stage=stage, frame_key=frame_key)
        return ProviderResponse(
            text=payload,
            provider=self.name,
            model=model,
            usage_records=[{"provider": self.name, "model": model, "mock": True}],
            raw_response={"mock": True},
        )

    def generate_text(
        self,
        *,
        model: str,
        user_text: str,
        system_instruction: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        response_mime_type: str | None = None,
        response_schema: Any = None,
        on_event: Any = None,
        stage: str = "text",
        frame_key: str | None = None,
    ) -> ProviderResponse:
        return self._response(model=model, response_schema=response_schema, stage=stage, frame_key=frame_key)

    def generate_text_with_image(
        self,
        *,
        model: str,
        prompt: str,
        image_path: str,
        max_tokens: int | None = None,
        temperature: float | None = None,
        response_mime_type: str | None = None,
        response_schema: Any = None,
        on_event: Any = None,
        stage: str = "image",
        frame_key: str | None = None,
    ) -> ProviderResponse:
        delay = _fake_delay_seconds()
        if delay > 0:
            time.sleep(delay)
        if on_event is not None:
            on_event({"kind": "mock_progress", "frame_key": frame_key})
        return ProviderResponse(
            text=json.dumps(fake_frame_analysis_payload(frame_key), ensure_ascii=False),
            provider=self.name,
            model=model,
            usage_records=[{"provider": self.name, "model": model, "mock": True}],
            raw_response={"mock": True, "image_path": image_path},
        )

