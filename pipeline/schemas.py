"""Canonical pipeline schemas (Task 2). Minimal surface for KnowledgeEvent extraction."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

EventType = Literal[
    "definition",
    "rule_statement",
    "condition",
    "invalidation",
    "exception",
    "comparison",
    "example",
    "warning",
    "process_step",
    "algorithm_hint",
    "observation",
]

ConfidenceLabel = Literal["low", "medium", "high"]

VisualType = Literal[
    "annotated_chart",
    "plain_chart",
    "hand_drawing",
    "diagram",
    "text_slide",
    "mixed_visual",
    "unknown",
]

ExampleRole = Literal[
    "positive_example",
    "negative_example",
    "counterexample",
    "ambiguous_example",
    "illustration",
    "unknown",
]


class SchemaBase(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    def save_json(self, path: Path) -> None:
        path.write_text(self.model_dump_json(indent=2), encoding="utf-8")


class ProvenanceMixin(SchemaBase):
    lesson_id: str
    lesson_title: Optional[str] = None
    section: Optional[str] = None
    subsection: Optional[str] = None
    source_event_ids: List[str] = Field(default_factory=list)


class TimeRangeMixin(SchemaBase):
    timestamp_start: Optional[str] = None
    timestamp_end: Optional[str] = None


class EvidenceRef(ProvenanceMixin, TimeRangeMixin):
    evidence_id: str
    frame_ids: List[str] = Field(default_factory=list)
    screenshot_paths: List[str] = Field(default_factory=list)
    visual_type: VisualType = "unknown"
    example_role: ExampleRole = "unknown"
    compact_visual_summary: Optional[str] = None
    linked_rule_ids: List[str] = Field(default_factory=list)
    raw_visual_event_ids: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class KnowledgeEvent(ProvenanceMixin, TimeRangeMixin):
    event_id: str
    event_type: EventType
    raw_text: str
    normalized_text: str
    concept: Optional[str] = None
    subconcept: Optional[str] = None
    evidence_refs: List[str] = Field(default_factory=list)
    confidence: ConfidenceLabel = "medium"
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    ambiguity_notes: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("raw_text", "normalized_text")
    @classmethod
    def must_not_be_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Text fields must not be blank")
        return v.strip()


class RuleCard(ProvenanceMixin):
    rule_id: str
    concept: str
    subconcept: Optional[str] = None
    title: Optional[str] = None
    rule_text: str
    conditions: List[str] = Field(default_factory=list)
    context: List[str] = Field(default_factory=list)
    invalidation: List[str] = Field(default_factory=list)
    exceptions: List[str] = Field(default_factory=list)
    comparisons: List[str] = Field(default_factory=list)
    algorithm_notes: List[str] = Field(default_factory=list)
    visual_summary: Optional[str] = None
    evidence_refs: List[str] = Field(default_factory=list)
    confidence: ConfidenceLabel = "medium"
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    candidate_features: List[str] = Field(default_factory=list)
    positive_example_refs: List[str] = Field(default_factory=list)
    negative_example_refs: List[str] = Field(default_factory=list)
    ambiguous_example_refs: List[str] = Field(default_factory=list)
    labeling_guidance: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("concept", "rule_text")
    @classmethod
    def required_text_must_not_be_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Required text fields must not be blank")
        return v.strip()


class KnowledgeEventCollection(SchemaBase):
    schema_version: str = "1.0"
    lesson_id: str
    events: List[KnowledgeEvent] = Field(default_factory=list)


class EvidenceIndex(SchemaBase):
    """Structured output for evidence_index.json (Step 4)."""

    schema_version: str = "1.0"
    lesson_id: str
    lesson_title: Optional[str] = None
    evidence_refs: List[EvidenceRef] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RuleCardCollection(SchemaBase):
    """Structured output for rule_cards.json (Task 5)."""

    schema_version: str = "1.0"
    lesson_id: str
    rules: List[RuleCard] = Field(default_factory=list)


class LessonKnowledgeBundle(SchemaBase):
    schema_version: str = "1.0"
    lesson_id: str
    lesson_title: Optional[str] = None
    knowledge_events: List[KnowledgeEvent] = Field(default_factory=list)
    evidence_index: List[EvidenceRef] = Field(default_factory=list)
    rule_cards: List[RuleCard] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
