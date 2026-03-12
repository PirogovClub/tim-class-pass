from __future__ import annotations

from typing import Any

from helpers.clients.provider_types import AIProvider, ProviderResponse

PROVIDER_CHOICES = ("openai", "gemini", "mlx", "setra", "ide")
API_PROVIDER_CHOICES = ("openai", "gemini", "mlx", "setra")


def _response_format_for_request(response_mime_type: str | None = None, response_schema: Any = None) -> Any:
    if response_schema is not None and hasattr(response_schema, "model_json_schema"):
        return {
            "type": "json_schema",
            "json_schema": {
                "name": getattr(response_schema, "__name__", "response_schema"),
                "schema": response_schema.model_json_schema(),
            },
        }
    if response_mime_type == "application/json":
        return {"type": "json_object"}
    return None


class GeminiProvider(AIProvider):
    name = "gemini"

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
        from google.genai import types

        from helpers.clients import gemini_client

        config_kwargs: dict[str, Any] = {}
        if system_instruction is not None:
            config_kwargs["system_instruction"] = system_instruction
        if response_mime_type is not None:
            config_kwargs["response_mime_type"] = response_mime_type
        if response_schema is not None:
            config_kwargs["response_schema"] = response_schema
        if temperature is not None:
            config_kwargs["temperature"] = temperature
        if max_tokens is not None:
            config_kwargs["max_output_tokens"] = max_tokens
        config = types.GenerateContentConfig(**config_kwargs)
        return gemini_client.generate_content_result(
            model=model,
            contents=user_text,
            config=config,
            on_event=on_event,
            stage=stage,
            frame_key=frame_key,
        )

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
        from google.genai import types

        from helpers.clients import gemini_client

        with open(image_path, "rb") as f:
            image_bytes = f.read()
        config_kwargs: dict[str, Any] = {}
        if response_mime_type is not None:
            config_kwargs["response_mime_type"] = response_mime_type
        if response_schema is not None:
            config_kwargs["response_schema"] = response_schema
        if temperature is not None:
            config_kwargs["temperature"] = temperature
        if max_tokens is not None:
            config_kwargs["max_output_tokens"] = max_tokens
        config = types.GenerateContentConfig(**config_kwargs)
        return gemini_client.generate_content_stream_result(
            model=model,
            contents=[
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(text=prompt),
                        types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                    ],
                )
            ],
            config=config,
            on_event=on_event,
            stage=stage,
            frame_key=frame_key,
        )


class OpenAIProvider(AIProvider):
    name = "openai"

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
        from helpers.clients import openai_client

        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": user_text})
        return openai_client.chat_completion_result(
            messages,
            model=model,
            max_tokens=max_tokens or 2000,
            response_format=_response_format_for_request(
                response_mime_type=response_mime_type,
                response_schema=response_schema,
            ),
            on_event=on_event,
            stage=stage,
            frame_key=frame_key,
        )

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
        from helpers.clients import openai_client

        return openai_client.chat_completion_with_image_result(
            prompt,
            image_path,
            model=model,
            max_tokens=max_tokens or 2000,
            response_format=_response_format_for_request(
                response_mime_type=response_mime_type,
                response_schema=response_schema,
            ),
            on_event=on_event,
            stage=stage,
            frame_key=frame_key,
        )


class MLXProvider(AIProvider):
    name = "mlx"

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
        raise NotImplementedError("MLX provider currently supports image tasks only.")

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
        from helpers.clients import mlx_client

        return mlx_client.chat_image_result(
            model,
            prompt,
            image_path,
            on_event=on_event,
            stage=stage,
            frame_key=frame_key,
        )


class SetraProvider(AIProvider):
    name = "setra"

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
        from helpers.clients import setra_client

        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": user_text})
        return setra_client.chat_completion_result(
            messages,
            model=model,
            max_tokens=max_tokens or 2000,
            response_format=_response_format_for_request(
                response_mime_type=response_mime_type,
                response_schema=response_schema,
            ),
            on_event=on_event,
            stage=stage,
            frame_key=frame_key,
        )

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
        from helpers.clients import setra_client

        return setra_client.chat_completion_with_image_result(
            prompt,
            image_path,
            model=model,
            max_tokens=max_tokens or 2000,
            response_format=_response_format_for_request(
                response_mime_type=response_mime_type,
                response_schema=response_schema,
            ),
            on_event=on_event,
            stage=stage,
            frame_key=frame_key,
        )


def get_provider(name: str) -> AIProvider:
    normalized = str(name or "").strip().lower()
    providers: dict[str, AIProvider] = {
        "gemini": GeminiProvider(),
        "openai": OpenAIProvider(),
        "mlx": MLXProvider(),
        "setra": SetraProvider(),
    }
    if normalized not in providers:
        raise ValueError(f"Unsupported provider: {name}")
    return providers[normalized]


def _provider_key_for_stage(stage: str) -> str:
    return f"provider_{stage}"


def _model_key_for_stage(stage: str) -> str:
    return f"model_{stage}"


def resolve_provider_for_stage(stage: str, video_id: str | None = None, explicit_provider: str | None = None) -> str:
    if explicit_provider:
        return str(explicit_provider).strip().lower()
    if video_id:
        try:
            from helpers import config as pipeline_config

            cfg = pipeline_config.get_config_for_video(video_id)
            configured = cfg.get(_provider_key_for_stage(stage))
            if configured:
                return str(configured).strip().lower()
            if stage == "images" and cfg.get("agent_images"):
                return str(cfg.get("agent_images")).strip().lower()
        except Exception:
            pass
    defaults = {
        "images": "gemini",
        "component2": "gemini",
        "component2_extract": "gemini",
        "component2_render": "gemini",
        "component2_reducer": "gemini",
        "gaps": "gemini",
        "vlm": "gemini",
        "analyze_extract": "gemini",
        "analyze_relevance": "gemini",
    }
    return defaults.get(stage, "gemini")


def resolve_model_for_stage(stage: str, video_id: str | None = None, explicit_model: str | None = None) -> str | None:
    if explicit_model:
        return explicit_model
    if video_id:
        try:
            from helpers import config as pipeline_config

            cfg = pipeline_config.get_config_for_video(video_id)
            configured = cfg.get(_model_key_for_stage(stage))
            if configured:
                return str(configured).strip()
        except Exception:
            pass
    provider = resolve_provider_for_stage(stage, video_id=video_id)
    if provider == "gemini":
        from helpers.clients import gemini_client

        return gemini_client.get_model_for_step(stage if stage in {"images", "gaps", "vlm"} else "images", video_id)
    if provider == "openai":
        from helpers.clients import openai_client

        return openai_client.get_model_for_step(stage if stage in {"images", "gaps", "vlm"} else "images", video_id)
    if provider == "mlx":
        return "mlx-vision_ocr"
    if provider == "setra":
        from helpers.clients import setra_client

        return setra_client.get_model_for_step(stage if stage in {"images", "gaps", "vlm"} else "images", video_id)
    return None
