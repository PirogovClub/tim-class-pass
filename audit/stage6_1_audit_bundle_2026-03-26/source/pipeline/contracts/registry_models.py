"""Pydantic models for lesson_registry.json (Stage 6.1)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class LessonArtifacts(BaseModel):
    knowledge_events_path: str
    rule_cards_path: str
    evidence_index_path: str
    concept_graph_path: str
    review_markdown_path: str | None = None
    rag_ready_path: str | None = None


class LessonRegistryEntryV1(BaseModel):
    lesson_id: str
    lesson_name: str | None = None
    lesson_slug: str | None = None
    status: Literal["valid", "invalid", "pending"] = "pending"
    source_artifact_version: str | None = None
    lesson_contract_version: str
    knowledge_schema_version: str
    rule_schema_version: str
    evidence_schema_version: str
    concept_graph_version: str
    registry_version: str
    artifacts: LessonArtifacts
    artifact_hashes: dict[str, str] = Field(default_factory=dict)
    record_counts: dict[str, int] = Field(default_factory=dict)
    validated_at: str | None = None
    validation_status: Literal["passed", "failed", "not_run"] = "not_run"
    validation_errors: list[str] = Field(default_factory=list)


class LessonRegistryFileV1(BaseModel):
    """Root object written to lesson_registry.json (list of entries)."""

    registry_version: str
    lesson_contract_version: str
    generated_at: str
    lessons: list[LessonRegistryEntryV1] = Field(default_factory=list)
    extra: dict[str, Any] = Field(default_factory=dict)
