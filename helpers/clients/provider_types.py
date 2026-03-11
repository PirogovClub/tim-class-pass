from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ProviderResponse:
    text: str
    provider: str
    model: str
    usage_records: list[dict[str, Any]] = field(default_factory=list)
    raw_response: Any = None


class ProviderRequestError(RuntimeError):
    def __init__(self, message: str, *, usage_records: list[dict[str, Any]] | None = None) -> None:
        super().__init__(message)
        self.usage_records = usage_records or []


class AIProvider(ABC):
    name: str

    @abstractmethod
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
        raise NotImplementedError

    @abstractmethod
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
        raise NotImplementedError
