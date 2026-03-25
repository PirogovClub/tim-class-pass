"""Typed contracts for the Step 4.1 explorer backend."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from pipeline.rag.config import UnitType


class BrowserSearchFilters(BaseModel):
    lesson_ids: list[str] = Field(default_factory=list)
    concept_ids: list[str] = Field(default_factory=list)
    unit_types: list[UnitType] = Field(default_factory=list)
    support_basis: list[str] = Field(default_factory=list)
    evidence_requirement: list[str] = Field(default_factory=list)
    teaching_mode: list[str] = Field(default_factory=list)
    min_confidence_score: float | None = None


class BrowserSearchRequest(BaseModel):
    query: str = ""
    top_k: int = 20
    filters: BrowserSearchFilters = Field(default_factory=BrowserSearchFilters)
    return_groups: bool = True


class BrowserResultCard(BaseModel):
    doc_id: str
    unit_type: UnitType
    lesson_id: str | None = None
    title: str
    subtitle: str = ""
    snippet: str = ""
    concept_ids: list[str] = Field(default_factory=list)
    support_basis: str | None = None
    evidence_requirement: str | None = None
    teaching_mode: str | None = None
    confidence_score: float | None = None
    timestamps: list[dict[str, Any]] = Field(default_factory=list)
    evidence_count: int = 0
    related_rule_count: int = 0
    related_event_count: int = 0
    score: float | None = None
    why_retrieved: list[str] = Field(default_factory=list)


class BrowserSearchResponse(BaseModel):
    query: str
    cards: list[BrowserResultCard] = Field(default_factory=list)
    groups: dict[str, list[BrowserResultCard]] = Field(default_factory=dict)
    facets: dict[str, dict[str, int]] = Field(default_factory=dict)
    hit_count: int = 0


class RuleDetailResponse(BaseModel):
    doc_id: str
    lesson_id: str
    lesson_slug: str | None = None
    title: str
    concept: str | None = None
    subconcept: str | None = None
    canonical_concept_ids: list[str] = Field(default_factory=list)
    rule_text: str = ""
    rule_text_ru: str = ""
    conditions: list[str] = Field(default_factory=list)
    invalidation: list[str] = Field(default_factory=list)
    exceptions: list[str] = Field(default_factory=list)
    comparisons: list[str] = Field(default_factory=list)
    visual_summary: str | None = None
    frame_ids: list[str] = Field(default_factory=list)
    support_basis: str | None = None
    evidence_requirement: str | None = None
    teaching_mode: str | None = None
    confidence_score: float | None = None
    timestamps: list[dict[str, Any]] = Field(default_factory=list)
    evidence_refs: list[BrowserResultCard] = Field(default_factory=list)
    source_events: list[BrowserResultCard] = Field(default_factory=list)
    related_rules: list[BrowserResultCard] = Field(default_factory=list)


class EvidenceDetailResponse(BaseModel):
    doc_id: str
    lesson_id: str
    title: str
    snippet: str = ""
    timestamps: list[dict[str, Any]] = Field(default_factory=list)
    support_basis: str | None = None
    confidence_score: float | None = None
    evidence_strength: str | None = None
    evidence_role_detail: str | None = None
    visual_summary: str | None = None
    frame_ids: list[str] = Field(default_factory=list)
    source_rules: list[BrowserResultCard] = Field(default_factory=list)
    source_events: list[BrowserResultCard] = Field(default_factory=list)


class ConceptNeighbor(BaseModel):
    concept_id: str
    relation: str
    direction: str
    weight: float | None = None


class ConceptDetailResponse(BaseModel):
    concept_id: str
    aliases: list[str] = Field(default_factory=list)
    top_rules: list[BrowserResultCard] = Field(default_factory=list)
    top_events: list[BrowserResultCard] = Field(default_factory=list)
    lessons: list[str] = Field(default_factory=list)
    neighbors: list[ConceptNeighbor] = Field(default_factory=list)
    rule_count: int = 0
    event_count: int = 0
    evidence_count: int = 0


class LessonDetailResponse(BaseModel):
    lesson_id: str
    lesson_title: str | None = None
    rule_count: int = 0
    event_count: int = 0
    evidence_count: int = 0
    concept_count: int = 0
    support_basis_counts: dict[str, int] = Field(default_factory=dict)
    top_concepts: list[str] = Field(default_factory=list)
    top_rules: list[BrowserResultCard] = Field(default_factory=list)
    top_evidence: list[BrowserResultCard] = Field(default_factory=list)
