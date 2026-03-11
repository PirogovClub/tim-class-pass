from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class TranscriptLine(BaseModel):
    start_seconds: float
    end_seconds: float
    text: str


class VisualEvent(BaseModel):
    timestamp_seconds: int
    frame_key: str
    visual_representation_type: str
    example_type: str = "unknown"
    change_summary: list[str] = Field(default_factory=list)
    current_state: dict[str, Any] = Field(default_factory=dict)
    extracted_entities: dict[str, Any] = Field(default_factory=dict)


class LessonChunk(BaseModel):
    chunk_index: int
    start_time_seconds: float
    end_time_seconds: float
    transcript_lines: list[TranscriptLine] = Field(default_factory=list)
    visual_events: list[VisualEvent] = Field(default_factory=list)
    previous_visual_state: dict[str, Any] | None = None


class EnrichedMarkdownChunk(BaseModel):
    synthesized_markdown: str = Field(
        description="The clean, translated English Markdown text with integrated micro-timestamps and blockquotes."
    )
    metadata_tags: list[str] = Field(
        default_factory=list,
        description="A list of strict English terminology tags found in this chunk.",
    )
