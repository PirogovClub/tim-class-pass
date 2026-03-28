from __future__ import annotations

import os

from helpers import config as pipeline_config
from helpers.clients import gemini_client
from helpers.clients.providers import get_provider, resolve_model_for_stage, resolve_provider_for_stage

DEFAULT_REDUCER_MODEL = "gemini-2.5-flash-lite"

QUANT_SYSTEM_PROMPT = """You are an expert Quantitative Trading Architect. Your job is to take a translated, chronological transcript of a trading lecture and transform it into a strict, topic-based algorithmic rulebook optimized for a RAG Vector Database.

You must solve the following architectural problems inherent in the raw transcript:

1. FIX NARRATIVE FLUFF: Discard conversational anecdotes, stories about past trades, and teaching fluff. Extract only the hard mathematical rules, market mechanics, and If/Then execution logic.
2. FIX SEMANTIC POLLUTION (TOPIC CHUNKING): Abandon the strict chronological flow. Reorganize the document by Trading Topics using Markdown Header 2 (`##`). Group related rules together even if they appeared far apart in the original lesson.
3. SYNTHESIZE VISUAL CLUSTERS: The raw text contains clustered visual blockquotes (for example, `> [*Abstract Teaching Example*: ...]`). Synthesize them into concise visual-state descriptions that directly support the trading rule instead of repeating every micro-change blindly.
4. PRESERVE VERIFICATION TIMESTAMPS: Keep the bolded micro-timestamps (for example, **[10:53]**) attached to the relevant rules or visual descriptions so the result remains auditable against the source video.
5. YAML FRONTMATTER (TAGGING): Extract all inline `**Tags:**` sections from the raw markdown, deduplicate them, and output them as strict YAML frontmatter at the very top of the response.

<output_format>
---
tags:
  - Tag 1
  - Tag 2
---

# [Video Lesson Title]

## [Trading Concept / Setup Name]
- **Rule 1:** [Strict If/Then logic]
- **Rule 2:** [Strict If/Then logic]
**[MM:SS]** > [*Visual Context*: Synthesized description of the chart setup.]
</output_format>

Return markdown only.
"""


def _resolve_reducer_model(video_id: str | None = None, model: str | None = None) -> str:
    resolved = resolve_model_for_stage("component2_reducer", video_id=video_id, explicit_model=model)
    if resolved:
        return resolved
    if model:
        return model
    config_candidates: list[str] = []
    if video_id:
        cfg = pipeline_config.get_config_for_video(video_id)
        config_candidates.extend(
            [
                str(cfg.get("model_component2_reducer") or ""),
                str(cfg.get("model_component2") or ""),
                str(cfg.get("model_vlm") or ""),
                str(cfg.get("model_name") or ""),
            ]
        )
    env_candidates = [
        os.getenv("MODEL_COMPONENT2_REDUCER") or "",
        os.getenv("MODEL_COMPONENT2") or "",
        os.getenv("MODEL_VLM") or "",
        os.getenv("MODEL_NAME") or "",
    ]
    for candidate in [*config_candidates, *env_candidates]:
        candidate = candidate.strip()
        if candidate.lower().startswith("gemini-"):
            return candidate
    return DEFAULT_REDUCER_MODEL


def _resolve_reducer_provider(video_id: str | None = None, provider: str | None = None) -> str:
    return resolve_provider_for_stage("component2_reducer", video_id=video_id, explicit_provider=provider)


def synthesize_full_document(
    raw_markdown: str,
    *,
    video_id: str | None = None,
    model: str | None = None,
    provider: str | None = None,
) -> tuple[str, list[dict]]:
    resolved_provider = _resolve_reducer_provider(video_id=video_id, provider=provider)
    resolved_model = _resolve_reducer_model(video_id=video_id, model=model)
    response = get_provider(resolved_provider).generate_text(
        model=resolved_model,
        user_text=raw_markdown,
        system_instruction=QUANT_SYSTEM_PROMPT,
        temperature=0.2,
        max_tokens=8192,
        stage=f"{resolved_provider}_component2_reducer",
        frame_key="component2_reducer",
    )
    reduced_markdown = (response.text or "").strip()
    if not reduced_markdown:
        raise ValueError(f"{resolved_provider} returned empty response for quant reduction.")
    return reduced_markdown, response.usage_records
