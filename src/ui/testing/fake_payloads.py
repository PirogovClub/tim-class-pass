from __future__ import annotations

import json
from typing import Any

from pipeline.component2.knowledge_builder import ChunkExtractionResult
from pipeline.component2.llm_processor import MarkdownRenderResult
from pipeline.component2.models import EnrichedMarkdownChunk
from pipeline.orchestrator import STAGE_KNOWLEDGE_EXTRACT, STAGE_MARKDOWN_RENDER, STAGE_VISION, parse_request_key


def fake_frame_analysis_payload(frame_key: str | None = None) -> dict[str, Any]:
    return {
        "frame_timestamp": "00:00:01",
        "material_change": True,
        "visual_representation_type": "text_slide",
        "example_type": "teaching",
        "change_summary": [f"Fake visual change for {frame_key or 'frame'}"],
        "current_state": {"label": "fake_state"},
        "extracted_entities": {"frame_key": frame_key or "unknown"},
    }


def fake_chunk_extraction_result() -> ChunkExtractionResult:
    return ChunkExtractionResult.model_validate(
        {
            "definitions": [
                {
                    "text": "Цена реагирует от уровня и подтверждает значимость уровня.",
                    "concept": "уровень",
                    "subconcept": None,
                    "source_type": "explicit",
                    "ambiguity_notes": [],
                    "source_line_indices": [0],
                    "source_quote": "Цена реагирует от уровня.",
                }
            ],
            "rule_statements": [],
            "conditions": [],
            "invalidations": [],
            "exceptions": [],
            "comparisons": [],
            "warnings": [],
            "process_steps": [],
            "algorithm_hints": [],
            "examples": [],
            "global_notes": [],
        }
    )


def fake_markdown_render_result() -> MarkdownRenderResult:
    return MarkdownRenderResult(markdown="# Review\n\n- Fake rule card output", metadata_tags=["fake", "ui"])


def fake_enriched_markdown_chunk() -> EnrichedMarkdownChunk:
    return EnrichedMarkdownChunk(
        synthesized_markdown="## Fake Section\n\nThis is deterministic fake markdown.",
        metadata_tags=["fake", "ui"],
    )


def fake_reducer_markdown() -> str:
    return "---\ntags:\n  - fake\n---\n\n# Fake Lesson\n\n## Fake Setup\n- **Rule 1:** Wait for confirmation.\n"


def fake_provider_text(response_schema: type | None, *, stage: str = "", frame_key: str | None = None) -> str:
    schema_name = getattr(response_schema, "__name__", "")
    if schema_name == "ChunkExtractionResult":
        return fake_chunk_extraction_result().model_dump_json()
    if schema_name == "MarkdownRenderResult":
        return fake_markdown_render_result().model_dump_json()
    if schema_name == "EnrichedMarkdownChunk":
        return fake_enriched_markdown_chunk().model_dump_json()
    if stage.endswith("reducer") or "reducer" in stage:
        return fake_reducer_markdown()
    return json.dumps(fake_frame_analysis_payload(frame_key))


def fake_batch_result_text_for_request_key(request_key: str) -> str:
    parsed = parse_request_key(request_key)
    stage_name = parsed["stage_name"]
    if stage_name == STAGE_VISION:
        return json.dumps(fake_frame_analysis_payload(parsed["entity_index"]), ensure_ascii=False)
    if stage_name == STAGE_KNOWLEDGE_EXTRACT:
        return fake_chunk_extraction_result().model_dump_json()
    if stage_name == STAGE_MARKDOWN_RENDER:
        return fake_markdown_render_result().model_dump_json()
    return json.dumps({"ok": True})

