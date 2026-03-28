"""Shared validators for pipeline artifacts. Used by tests and optional runtime QA."""

from __future__ import annotations

from typing import Any

from pipeline.schemas import (
    ConceptGraph,
    EvidenceIndex,
    EvidenceRef,
    KnowledgeEvent,
    KnowledgeEventCollection,
    RuleCard,
    RuleCardCollection,
    is_placeholder_text,
)

VALID_CONFIDENCE_LABELS = frozenset({"low", "medium", "high"})
FORBIDDEN_KEYS = frozenset({
    "current_state",
    "previous_visual_state",
    "visual_facts",
    "dense_analysis_frame",
    "raw_visual_events",
})
MAX_VISUAL_SUMMARY_LENGTH = 500


def _walk_forbidden_keys(obj: Any, path: str = "root") -> list[str]:
    errors: list[str] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in FORBIDDEN_KEYS:
                errors.append(f"Forbidden key {key} found at {path}")
            errors.extend(_walk_forbidden_keys(value, f"{path}.{key}"))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            errors.extend(_walk_forbidden_keys(item, f"{path}[{i}]"))
    return errors


def validate_no_visual_blob_leakage(payload: dict | list, path: str = "root") -> list[str]:
    """Recursively check for forbidden raw visual blob keys. Returns list of error messages."""
    return _walk_forbidden_keys(payload, path)


def validate_knowledge_event_collection_integrity(collection: KnowledgeEventCollection) -> list[str]:
    """Validate knowledge event collection: ids, confidence, no forbidden keys."""
    errors: list[str] = []
    seen_ids: set[str] = set()
    for ev in collection.events:
        if not ev.event_id:
            errors.append("KnowledgeEvent missing event_id")
        elif ev.event_id in seen_ids:
            errors.append(f"Duplicate event_id: {ev.event_id}")
        else:
            seen_ids.add(ev.event_id)
        if ev.confidence not in VALID_CONFIDENCE_LABELS:
            errors.append(f"KnowledgeEvent {ev.event_id} has invalid confidence label: {ev.confidence}")
        if ev.confidence_score is not None and not (0.0 <= ev.confidence_score <= 1.0):
            errors.append(f"KnowledgeEvent {ev.event_id} confidence_score out of [0,1]: {ev.confidence_score}")
        errors.extend(validate_no_visual_blob_leakage(ev.metadata, f"events.{ev.event_id}.metadata"))
    return errors


def validate_evidence_index_integrity(index: EvidenceIndex) -> list[str]:
    """Validate evidence index: ids, visual provenance, source_event_ids, no forbidden keys."""
    errors: list[str] = []
    seen_ids: set[str] = set()
    for ref in index.evidence_refs:
        if not ref.evidence_id:
            errors.append("EvidenceRef missing evidence_id")
        elif ref.evidence_id in seen_ids:
            errors.append(f"Duplicate evidence_id: {ref.evidence_id}")
        else:
            seen_ids.add(ref.evidence_id)
        has_visual = bool(ref.frame_ids or ref.raw_visual_event_ids)
        if not has_visual:
            errors.append(f"EvidenceRef {ref.evidence_id} has neither frame_ids nor raw_visual_event_ids")
        if not ref.source_event_ids:
            errors.append(f"EvidenceRef {ref.evidence_id} has no source_event_ids")
        errors.extend(validate_no_visual_blob_leakage(ref.metadata, f"evidence_refs.{ref.evidence_id}.metadata"))
    return errors


def validate_rule_card_collection_integrity(collection: RuleCardCollection) -> list[str]:
    """Validate rule card collection: ids, source_event_ids, confidence, no forbidden keys."""
    errors: list[str] = []
    seen_ids: set[str] = set()
    for rule in collection.rules:
        if not rule.rule_id:
            errors.append("RuleCard missing rule_id")
        elif rule.rule_id in seen_ids:
            errors.append(f"Duplicate rule_id: {rule.rule_id}")
        else:
            seen_ids.add(rule.rule_id)
        if not rule.source_event_ids:
            errors.append(f"RuleCard {rule.rule_id} missing source_event_ids")
        if is_placeholder_text(rule.rule_text):
            errors.append(f"RuleCard {rule.rule_id} has placeholder rule_text")
        if rule.confidence_score is not None and not (0.0 <= rule.confidence_score <= 1.0):
            errors.append(f"RuleCard {rule.rule_id} has invalid confidence_score: {rule.confidence_score}")
        if rule.confidence not in VALID_CONFIDENCE_LABELS:
            errors.append(f"RuleCard {rule.rule_id} has invalid confidence label: {rule.confidence}")
        if rule.visual_summary is not None and len(rule.visual_summary) > MAX_VISUAL_SUMMARY_LENGTH:
            errors.append(f"RuleCard {rule.rule_id} visual_summary exceeds {MAX_VISUAL_SUMMARY_LENGTH} chars")
        errors.extend(validate_no_visual_blob_leakage(rule.metadata, f"rules.{rule.rule_id}.metadata"))
    return errors


def validate_concept_graph_integrity(graph: ConceptGraph) -> list[str]:
    """Validate concept graph: node ids unique, relation source/target exist."""
    errors: list[str] = []
    node_ids = {n.concept_id for n in graph.nodes}
    seen_node_ids: set[str] = set()
    for n in graph.nodes:
        if not n.concept_id:
            errors.append("ConceptNode missing concept_id")
        elif n.concept_id in seen_node_ids:
            errors.append(f"Duplicate concept_id: {n.concept_id}")
        else:
            seen_node_ids.add(n.concept_id)
    for rel in graph.relations:
        if rel.source_id not in node_ids:
            errors.append(f"ConceptRelation {rel.relation_id} source_id not in nodes: {rel.source_id}")
        if rel.target_id not in node_ids:
            errors.append(f"ConceptRelation {rel.relation_id} target_id not in nodes: {rel.target_id}")
    return errors


def validate_ml_manifest_integrity(payload: dict) -> list[str]:
    """Validate ML manifest structure and no forbidden keys."""
    errors: list[str] = []
    if not isinstance(payload, dict):
        errors.append("ML manifest must be a JSON object")
        return errors
    errors.extend(validate_no_visual_blob_leakage(payload, "ml_manifest"))
    return errors


def validate_export_quality(review_markdown: str, rag_markdown: str) -> list[str]:
    """Validate review vs RAG export: both non-empty, not identical, RAG more compact."""
    errors: list[str] = []
    if not (review_markdown or "").strip():
        errors.append("review markdown is empty")
    if not (rag_markdown or "").strip():
        errors.append("rag markdown is empty")
    if (review_markdown or "").strip() == (rag_markdown or "").strip():
        errors.append("review markdown and rag markdown are identical")
    review_lines = len([l for l in (review_markdown or "").splitlines() if l.strip()])
    rag_lines = len([l for l in (rag_markdown or "").splitlines() if l.strip()])
    if rag_lines > review_lines:
        errors.append("rag markdown is not more compact than review markdown")
    return errors


def validate_cross_artifact_references(
    knowledge_events: KnowledgeEventCollection,
    evidence_index: EvidenceIndex,
    rule_cards: RuleCardCollection,
) -> list[str]:
    """Validate that all cross-references between knowledge_events, evidence_index, and rule_cards resolve.

    Returns a list of error messages (empty when all references are consistent).
    """
    errors: list[str] = []
    event_ids = {ev.event_id for ev in knowledge_events.events}
    evidence_ids = {ref.evidence_id for ref in evidence_index.evidence_refs}

    # EvidenceRef.source_event_ids must exist in knowledge_events
    for ref in evidence_index.evidence_refs:
        for eid in ref.source_event_ids:
            if eid not in event_ids:
                errors.append(
                    f"EvidenceRef {ref.evidence_id}: source_event_id {eid!r} not found in knowledge_events"
                )

    # RuleCard.source_event_ids must exist in knowledge_events
    for rule in rule_cards.rules:
        for eid in rule.source_event_ids:
            if eid not in event_ids:
                errors.append(
                    f"RuleCard {rule.rule_id}: source_event_id {eid!r} not found in knowledge_events"
                )

    # RuleCard.evidence_refs must exist in evidence_index
    for rule in rule_cards.rules:
        for ev_id in rule.evidence_refs:
            if ev_id not in evidence_ids:
                errors.append(
                    f"RuleCard {rule.rule_id}: evidence_ref {ev_id!r} not found in evidence_index"
                )

    # RuleCard positive/negative/ambiguous_example_refs must exist in evidence_index
    for rule in rule_cards.rules:
        for ev_id in rule.positive_example_refs:
            if ev_id not in evidence_ids:
                errors.append(
                    f"RuleCard {rule.rule_id}: positive_example_ref {ev_id!r} not found in evidence_index"
                )
        for ev_id in rule.negative_example_refs:
            if ev_id not in evidence_ids:
                errors.append(
                    f"RuleCard {rule.rule_id}: negative_example_ref {ev_id!r} not found in evidence_index"
                )
        for ev_id in rule.ambiguous_example_refs:
            if ev_id not in evidence_ids:
                errors.append(
                    f"RuleCard {rule.rule_id}: ambiguous_example_ref {ev_id!r} not found in evidence_index"
                )

    return errors
