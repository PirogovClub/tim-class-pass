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

SupportBasis = Literal[
    "transcript_primary",
    "transcript_plus_visual",
    "visual_primary",
    "inferred",
]

EvidenceRequirement = Literal["none", "optional", "required"]

TeachingMode = Literal["theory", "example", "mixed"]

VisualSupportLevel = Literal[
    "none",
    "illustration",
    "supporting_example",
    "strong_example",
    "counterexample",
    "ambiguous",
]

TranscriptSupportLevel = Literal["weak", "moderate", "strong"]

EvidenceStrength = Literal["weak", "moderate", "strong"]

# ----- Phase 1: shared validation helpers -----

PLACEHOLDER_TEXTS: frozenset[str] = frozenset({
    "",
    "no rule text extracted.",
    "n/a",
    "unknown",
    "none",
})


def normalize_text(value: str | None) -> str:
    """Single-line normalized text (strip, collapse whitespace)."""
    if not value:
        return ""
    return " ".join(value.strip().split())


def is_placeholder_text(value: str | None) -> bool:
    """True if value is empty or a known placeholder after normalization."""
    return normalize_text(value).lower() in PLACEHOLDER_TEXTS


def is_compact_summary(value: str | None, max_len: int = 300) -> bool:
    """True if value is None or normalized length <= max_len."""
    if value is None:
        return True
    return len(normalize_text(value)) <= max_len


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


AnchorMatchSource = Literal[
    "llm_line_indices",
    "llm_source_quote",
    "heuristic_quote_match",
    "chunk_fallback",
]
TimestampConfidence = Literal["chunk", "span", "line"]


class TranscriptAnchor(SchemaBase):
    line_index: int = Field(ge=0)
    text: Optional[str] = None
    timestamp_start: Optional[str] = None
    timestamp_end: Optional[str] = None
    match_source: AnchorMatchSource = "chunk_fallback"


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
    source_language: str = "ru"
    related_concept_ids: List[str] = Field(default_factory=list)
    summary_primary: Optional[str] = None
    summary_language: Optional[str] = None
    summary_ru: Optional[str] = None
    summary_en: Optional[str] = None
    evidence_strength: Optional[EvidenceStrength] = None
    evidence_role_detail: Optional[str] = None


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
    source_chunk_index: Optional[int] = None
    source_line_start: Optional[int] = None
    source_line_end: Optional[int] = None
    source_quote: Optional[str] = None
    transcript_anchors: List[TranscriptAnchor] = Field(default_factory=list)
    timestamp_confidence: TimestampConfidence = "chunk"
    anchor_match_source: Optional[AnchorMatchSource] = None
    anchor_line_count: Optional[int] = None
    anchor_span_width: Optional[int] = None
    anchor_density: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    source_event_ids: List[str] = Field(
        default_factory=list,
        description=(
            "Optional upstream lineage for this event. "
            "For Phase 1, KnowledgeEvent is the primary extracted unit, so this "
            "field may be empty. Final export must not reject a KnowledgeEvent "
            "solely because source_event_ids is empty."
        ),
    )
    source_language: str = "ru"
    concept_id: Optional[str] = None
    subconcept_id: Optional[str] = None
    condition_ids: List[str] = Field(default_factory=list)
    invalidation_ids: List[str] = Field(default_factory=list)
    exception_ids: List[str] = Field(default_factory=list)
    rule_type: Optional[str] = None
    pattern_tags: List[str] = Field(default_factory=list)
    normalized_text_ru: Optional[str] = None
    concept_label_ru: Optional[str] = None
    subconcept_label_ru: Optional[str] = None
    support_basis: Optional[SupportBasis] = None
    evidence_requirement: Optional[EvidenceRequirement] = None
    teaching_mode: Optional[TeachingMode] = None
    visual_support_level: Optional[VisualSupportLevel] = None
    transcript_support_level: Optional[TranscriptSupportLevel] = None
    transcript_support_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    visual_support_score: Optional[float] = Field(None, ge=0.0, le=1.0)

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
    source_language: str = "ru"
    concept_id: Optional[str] = None
    subconcept_id: Optional[str] = None
    condition_ids: List[str] = Field(default_factory=list)
    invalidation_ids: List[str] = Field(default_factory=list)
    exception_ids: List[str] = Field(default_factory=list)
    rule_type: Optional[str] = None
    pattern_tags: List[str] = Field(default_factory=list)
    rule_text_ru: Optional[str] = None
    concept_label_ru: Optional[str] = None
    subconcept_label_ru: Optional[str] = None
    support_basis: Optional[SupportBasis] = None
    evidence_requirement: Optional[EvidenceRequirement] = None
    teaching_mode: Optional[TeachingMode] = None
    visual_support_level: Optional[VisualSupportLevel] = None
    transcript_support_level: Optional[TranscriptSupportLevel] = None
    transcript_support_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    visual_support_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    has_visual_evidence: bool = False
    transcript_anchor_count: Optional[int] = None  # rule-level aggregate; not on KnowledgeEvent
    transcript_repetition_count: Optional[int] = None  # rule-level aggregate; not on KnowledgeEvent

    @field_validator("concept", "rule_text")
    @classmethod
    def required_text_must_not_be_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Required text fields must not be blank")
        return v.strip()


class KnowledgeEventCollection(SchemaBase):
    schema_version: str = "1.0"
    lesson_id: str
    lesson_title: Optional[str] = None
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


# ----- Phase 1: per-entity validators (return list of error/warning strings) -----


def validate_knowledge_event(event: KnowledgeEvent) -> List[str]:
    """Return list of validation errors/warnings for a KnowledgeEvent."""
    errors: List[str] = []
    if not (event.event_id or "").strip():
        errors.append("event_id must not be empty")
    if not (event.lesson_id or "").strip():
        errors.append("lesson_id must not be empty")
    if not event.event_type:
        errors.append("event_type must be set")
    if is_placeholder_text(event.normalized_text):
        errors.append("normalized_text is placeholder or empty")
    if is_placeholder_text(event.raw_text):
        errors.append("raw_text is placeholder or empty")
    if event.confidence_score is not None and not (0.0 <= event.confidence_score <= 1.0):
        errors.append("confidence_score must be in [0, 1]")

    if event.timestamp_confidence in {"line", "span"}:
        if event.source_line_start is None or event.source_line_end is None:
            errors.append(
                f"timestamp_confidence='{event.timestamp_confidence}' requires source_line_start/source_line_end"
            )
        if not event.transcript_anchors:
            errors.append(
                f"timestamp_confidence='{event.timestamp_confidence}' requires transcript_anchors"
            )

    if event.timestamp_confidence == "line":
        if event.anchor_match_source is None:
            errors.append("timestamp_confidence='line' requires anchor_match_source")
        if event.anchor_line_count is None:
            errors.append("timestamp_confidence='line' requires anchor_line_count")
        if event.anchor_span_width is None:
            errors.append("timestamp_confidence='line' requires anchor_span_width")
        if event.anchor_density is None:
            errors.append("timestamp_confidence='line' requires anchor_density")
        if event.anchor_span_width is not None and event.anchor_span_width > 3:
            errors.append("timestamp_confidence='line' cannot have anchor_span_width > 3")
        if event.anchor_density is not None and event.anchor_density < 0.60:
            errors.append("timestamp_confidence='line' requires anchor_density >= 0.60")

    return errors


def validate_rule_card(rule: RuleCard) -> List[str]:
    """Return list of validation errors/warnings for a RuleCard. Empty list = valid."""
    errors: List[str] = []
    if not (rule.rule_text or "").strip():
        errors.append("rule_text must not be empty")
    if is_placeholder_text(rule.rule_text):
        errors.append("rule_text is placeholder (e.g. 'No rule text extracted.')")
    if not (rule.source_event_ids or []):
        errors.append("source_event_ids must not be empty")
    all_empty = (
        not (rule.rule_text or "").strip()
        and not (rule.conditions or [])
        and not (rule.invalidation or [])
        and not (rule.exceptions or [])
        and not (rule.comparisons or [])
        and not (rule.algorithm_notes or [])
    )
    if all_empty:
        errors.append("all of rule_text, conditions, invalidation, exceptions, comparisons, algorithm_notes are empty")
    ev_req = getattr(rule, "evidence_requirement", None) or "optional"
    if (rule.visual_summary or "").strip() and not (rule.evidence_refs or []) and ev_req != "none":
        errors.append("visual_summary present but evidence_refs empty")
    if rule.labeling_guidance and is_placeholder_text(rule.rule_text):
        errors.append("labeling_guidance should be empty when rule is invalid")
    return errors


def validate_evidence_ref(
    evidence: EvidenceRef,
    allow_unlinked_rules: bool = True,
) -> List[str]:
    """Return list of validation errors/warnings for an EvidenceRef."""
    errors: List[str] = []
    if not (evidence.lesson_id or "").strip():
        errors.append("lesson_id must not be empty")
    if not (evidence.frame_ids or []) and not (evidence.raw_visual_event_ids or []):
        errors.append("both frame_ids and raw_visual_event_ids are empty")
    if not allow_unlinked_rules and not (evidence.linked_rule_ids or []):
        errors.append("linked_rule_ids empty (not allowed in final artifact)")
    if evidence.compact_visual_summary is not None and not is_compact_summary(evidence.compact_visual_summary, max_len=300):
        errors.append("compact_visual_summary exceeds 300 chars")
    return errors


def dedupe_preserve_order(items: List[str]) -> List[str]:
    """Deduplicate list of strings while preserving order."""
    seen: set[str] = set()
    out: List[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def validate_rule_card_for_export(rule: RuleCard) -> List[str]:
    """Strict export-level validation; use before writing rule_cards.json or ML manifests."""
    errors = list(validate_rule_card(rule))

    if not (rule.lesson_id or "").strip():
        errors.append("lesson_id must not be empty for final export")

    if not (rule.concept or "").strip():
        errors.append("concept must not be empty for final export")

    if rule.labeling_guidance and is_placeholder_text(rule.rule_text):
        errors.append("labeling_guidance must be empty for placeholder rule_text")

    return dedupe_preserve_order(errors)


def validate_rule_card_collection_for_export(
    collection: RuleCardCollection,
) -> tuple[RuleCardCollection, List[dict]]:
    """Filter collection to export-valid rules only; return (valid_collection, debug_rows for rejected)."""
    valid_rules: List[RuleCard] = []
    debug_rows: List[dict] = []

    for rule in collection.rules:
        errors = validate_rule_card_for_export(rule)
        if errors:
            debug_rows.append({
                "stage": "export_validation",
                "entity_type": "rule_card",
                "entity_id": rule.rule_id,
                "rule_id": rule.rule_id,
                "reason_rejected": errors,
                "source_event_ids": list(rule.source_event_ids or []),
                "concept": rule.concept,
                "subconcept": rule.subconcept,
            })
            continue
        valid_rules.append(rule)

    return (
        RuleCardCollection(
            schema_version=collection.schema_version,
            lesson_id=collection.lesson_id,
            rules=valid_rules,
        ),
        debug_rows,
    )


def validate_knowledge_event_for_export(event: KnowledgeEvent) -> List[str]:
    errors = list(validate_knowledge_event(event))

    metadata = getattr(event, "metadata", {}) or {}
    if metadata.get("chunk_index") is None:
        errors.append("metadata.chunk_index must not be empty for final export")

    # IMPORTANT:
    # KnowledgeEvent is the primary extracted object in Phase 1.
    # source_event_ids is optional here and should not be used as a hard export gate.
    # Stronger upstream lineage belongs to Phase 2 (e.g. transcript anchors / span ids).

    return dedupe_preserve_order(errors)


def validate_knowledge_event_collection_for_export(
    collection: KnowledgeEventCollection,
) -> tuple[KnowledgeEventCollection, List[dict]]:
    valid_events: List[KnowledgeEvent] = []
    debug_rows: List[dict] = []

    for event in collection.events:
        errors = validate_knowledge_event_for_export(event)
        if errors:
            debug_rows.append({
                "stage": "export_validation",
                "entity_type": "knowledge_event",
                "entity_id": event.event_id,
                "event_id": event.event_id,
                "reason_rejected": errors,
                "source_event_ids": list(event.source_event_ids or []),
                "concept": event.concept,
                "subconcept": event.subconcept,
            })
            continue
        valid_events.append(event)

    return (
        KnowledgeEventCollection(
            schema_version=collection.schema_version,
            lesson_id=collection.lesson_id,
            lesson_title=collection.lesson_title,
            events=valid_events,
        ),
        debug_rows,
    )


def validate_evidence_ref_for_export(evidence: EvidenceRef) -> List[str]:
    errors = list(validate_evidence_ref(evidence, allow_unlinked_rules=False))

    if not (evidence.source_event_ids or []):
        errors.append("source_event_ids empty (not allowed in final artifact)")

    return dedupe_preserve_order(errors)


def validate_evidence_index_for_export(
    index: EvidenceIndex,
) -> tuple[EvidenceIndex, List[dict]]:
    valid_refs: List[EvidenceRef] = []
    debug_rows: List[dict] = []

    for ref in index.evidence_refs:
        errors = validate_evidence_ref_for_export(ref)
        if errors:
            debug_rows.append({
                "stage": "export_validation",
                "entity_type": "evidence_ref",
                "entity_id": ref.evidence_id,
                "evidence_id": ref.evidence_id,
                "reason_rejected": errors,
                "source_event_ids": list(ref.source_event_ids or []),
                "linked_rule_ids": list(ref.linked_rule_ids or []),
                "frame_ids": list(ref.frame_ids or []),
                "raw_visual_event_ids": list(ref.raw_visual_event_ids or []),
            })
            continue
        valid_refs.append(ref)

    return (
        EvidenceIndex(
            schema_version=index.schema_version,
            lesson_id=index.lesson_id,
            lesson_title=index.lesson_title,
            evidence_refs=valid_refs,
            metadata=index.metadata,
        ),
        debug_rows,
    )


# ----- Task 12: Concept graph schemas -----

ConceptNodeType = Literal[
    "concept", "subconcept", "condition", "invalidation", "exception", "pattern", "rule_group",
]


class ConceptNode(SchemaBase):
    """Single node in a lesson-level concept graph."""

    concept_id: str
    name: str
    type: ConceptNodeType = "concept"
    parent_id: Optional[str] = None
    aliases: List[str] = Field(default_factory=list)
    source_rule_ids: List[str] = Field(default_factory=list)
    canonical_label: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ConceptRelation(SchemaBase):
    """Typed directed relation between two concept nodes."""

    relation_id: str
    source_id: str
    target_id: str
    relation_type: str
    weight: int = 1
    source_rule_ids: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ConceptGraphStats(SchemaBase):
    """Summary statistics for a concept graph."""

    node_count: int = 0
    edge_count: int = 0


class ConceptGraph(SchemaBase):
    """Lesson-level concept graph (Task 12)."""

    lesson_id: str
    graph_version: str = "1.0"
    nodes: List[ConceptNode] = Field(default_factory=list)
    relations: List[ConceptRelation] = Field(default_factory=list)
    stats: ConceptGraphStats = Field(default_factory=ConceptGraphStats)


class LessonKnowledgeBundle(SchemaBase):
    schema_version: str = "1.0"
    lesson_id: str
    lesson_title: Optional[str] = None
    knowledge_events: List[KnowledgeEvent] = Field(default_factory=list)
    evidence_index: List[EvidenceRef] = Field(default_factory=list)
    rule_cards: List[RuleCard] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
