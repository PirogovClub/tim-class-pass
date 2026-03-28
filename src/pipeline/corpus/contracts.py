"""Frozen v1 corpus contract: Pydantic models and schema version loader."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from pipeline.schemas import (
    ConceptGraph,
    ConceptGraphStats,
    ConceptNode,
    ConceptRelation,
    EvidenceIndex,
    EvidenceRef,
    KnowledgeEvent,
    KnowledgeEventCollection,
    RuleCard,
    RuleCardCollection,
)

__all__ = [
    "KnowledgeEvent",
    "RuleCard",
    "EvidenceRef",
    "ConceptNode",
    "ConceptRelation",
    "ConceptGraph",
    "ConceptGraphStats",
    "KnowledgeEventCollection",
    "RuleCardCollection",
    "EvidenceIndex",
    "LessonRecord",
    "CorpusMetadata",
    "load_schema_versions",
    "SCHEMA_VERSIONS",
]

_VERSIONS_PATH = Path(__file__).resolve().parent.parent / "contracts" / "schema_versions.json"


def load_schema_versions() -> dict[str, str]:
    return json.loads(_VERSIONS_PATH.read_text(encoding="utf-8"))


SCHEMA_VERSIONS: dict[str, str] = load_schema_versions()


class LessonRecord(BaseModel):
    lesson_id: str
    lesson_slug: str
    lesson_title: str | None = None
    source_language: str = "ru"
    available_artifacts: dict[str, bool] = Field(default_factory=dict)
    artifact_paths: dict[str, str] = Field(default_factory=dict)
    artifact_counts: dict[str, int] = Field(default_factory=dict)
    schema_versions: dict[str, str] = Field(default_factory=dict)
    build_timestamp: str = ""
    content_hashes: dict[str, str] = Field(default_factory=dict)
    status: Literal["valid", "warning", "invalid"] = "valid"
    warnings: list[str] = Field(default_factory=list)


class CorpusMetadata(BaseModel):
    corpus_contract_version: str
    generated_at: str
    lesson_count: int = 0
    knowledge_event_count: int = 0
    rule_card_count: int = 0
    evidence_ref_count: int = 0
    concept_node_count: int = 0
    concept_relation_count: int = 0
    source_root: str = ""
    builder_version: str = "1.0.0"
    validation_status: str = "unknown"
    evidence_coverage_pct: float = 0.0
    rules_without_evidence: int = 0
    fallback_linked_rules: int = 0
    transcript_primary_rules: int = 0
    transcript_plus_visual_rules: int = 0
    visual_primary_rules: int = 0
    inferred_rules: int = 0
    notes: list[str] = Field(default_factory=list)
