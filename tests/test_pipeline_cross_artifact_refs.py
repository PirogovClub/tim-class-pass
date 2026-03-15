"""Tests for cross-artifact reference validation (evidence ↔ events ↔ rules)."""

from __future__ import annotations

from pathlib import Path

import pytest

from pipeline.schemas import (
    EvidenceIndex,
    EvidenceRef,
    KnowledgeEvent,
    KnowledgeEventCollection,
    RuleCard,
    RuleCardCollection,
)
from pipeline.validation import validate_cross_artifact_references

FIXTURES_MINIMAL = Path(__file__).parent / "fixtures" / "lesson_minimal"


def _load_knowledge_events(root: Path) -> KnowledgeEventCollection:
    path = root / "knowledge_events.json"
    return KnowledgeEventCollection.model_validate_json(path.read_text(encoding="utf-8"))


def _load_evidence_index(root: Path) -> EvidenceIndex:
    path = root / "evidence_index.json"
    return EvidenceIndex.model_validate_json(path.read_text(encoding="utf-8"))


def _load_rule_cards(root: Path) -> RuleCardCollection:
    path = root / "rule_cards.json"
    return RuleCardCollection.model_validate_json(path.read_text(encoding="utf-8"))


# --- Validator returns empty when consistent ---


def test_cross_artifact_references_validator_consistent_returns_empty(
    lesson_minimal_root: Path,
) -> None:
    """When knowledge_events, evidence_index, and rule_cards are consistent, validator returns no errors."""
    knowledge_events = _load_knowledge_events(lesson_minimal_root)
    evidence_index = _load_evidence_index(lesson_minimal_root)
    rule_cards = _load_rule_cards(lesson_minimal_root)
    errors = validate_cross_artifact_references(
        knowledge_events, evidence_index, rule_cards
    )
    assert errors == []


def test_knowledge_event_source_event_ids_are_not_required_for_cross_artifact_integrity() -> None:
    """Events can be roots; evidence and rules point to them. Empty KnowledgeEvent.source_event_ids is valid (05-phase1)."""
    knowledge_events = KnowledgeEventCollection(
        schema_version="1.0",
        lesson_id="test",
        events=[
            KnowledgeEvent(
                event_id="e1",
                lesson_id="test",
                event_type="rule_statement",
                raw_text="A rule.",
                normalized_text="A rule.",
                source_event_ids=[],
                metadata={"chunk_index": 0},
                timestamp_start="00:01",
                timestamp_end="00:05",
            ),
        ],
    )
    evidence_index = EvidenceIndex(
        schema_version="1.0",
        lesson_id="test",
        evidence_refs=[
            EvidenceRef(
                evidence_id="ev1",
                lesson_id="test",
                source_event_ids=["e1"],
                linked_rule_ids=["r1"],
                frame_ids=["f1"],
            ),
        ],
    )
    rule_cards = RuleCardCollection(
        schema_version="1.0",
        lesson_id="test",
        rules=[
            RuleCard(
                rule_id="r1",
                lesson_id="test",
                concept="level",
                rule_text="Valid rule.",
                source_event_ids=["e1"],
                evidence_refs=["ev1"],
            ),
        ],
    )

    errors = validate_cross_artifact_references(
        knowledge_events, evidence_index, rule_cards
    )
    assert errors == []


# --- Evidence source_event_ids resolve to knowledge_events ---


def test_evidence_source_events_resolve(lesson_minimal_root: Path) -> None:
    """Every EvidenceRef.source_event_ids id exists in knowledge_events.events."""
    knowledge_events = _load_knowledge_events(lesson_minimal_root)
    evidence_index = _load_evidence_index(lesson_minimal_root)
    event_ids = {ev.event_id for ev in knowledge_events.events}
    for ref in evidence_index.evidence_refs:
        for eid in ref.source_event_ids:
            assert eid in event_ids, f"EvidenceRef {ref.evidence_id}: source_event_id {eid!r} not in knowledge_events"


# --- Rule source_event_ids resolve to knowledge_events ---


def test_rule_source_events_resolve(lesson_minimal_root: Path) -> None:
    """Every RuleCard.source_event_ids id exists in knowledge_events.events."""
    knowledge_events = _load_knowledge_events(lesson_minimal_root)
    rule_cards = _load_rule_cards(lesson_minimal_root)
    event_ids = {ev.event_id for ev in knowledge_events.events}
    for rule in rule_cards.rules:
        for eid in rule.source_event_ids:
            assert eid in event_ids, f"RuleCard {rule.rule_id}: source_event_id {eid!r} not in knowledge_events"


# --- Rule evidence_refs resolve to evidence_index ---


def test_rule_evidence_refs_resolve(lesson_minimal_root: Path) -> None:
    """Every RuleCard.evidence_refs id exists in evidence_index.evidence_refs."""
    evidence_index = _load_evidence_index(lesson_minimal_root)
    rule_cards = _load_rule_cards(lesson_minimal_root)
    evidence_ids = {ref.evidence_id for ref in evidence_index.evidence_refs}
    for rule in rule_cards.rules:
        for ev_id in rule.evidence_refs:
            assert ev_id in evidence_ids, f"RuleCard {rule.rule_id}: evidence_ref {ev_id!r} not in evidence_index"


# --- ML example refs resolve to evidence_index ---


def test_ml_example_refs_resolve(lesson_minimal_root: Path) -> None:
    """Every positive/negative/ambiguous_example_refs id exists in evidence_index.evidence_refs."""
    evidence_index = _load_evidence_index(lesson_minimal_root)
    rule_cards = _load_rule_cards(lesson_minimal_root)
    evidence_ids = {ref.evidence_id for ref in evidence_index.evidence_refs}
    for rule in rule_cards.rules:
        for ev_id in rule.positive_example_refs:
            assert ev_id in evidence_ids
        for ev_id in rule.negative_example_refs:
            assert ev_id in evidence_ids
        for ev_id in rule.ambiguous_example_refs:
            assert ev_id in evidence_ids


# --- Validator rejects broken refs ---


def test_cross_artifact_references_validator_rejects_broken_refs() -> None:
    """Validator returns errors when a rule references a non-existent source event."""
    knowledge_events = KnowledgeEventCollection(
        schema_version="1.0",
        lesson_id="test",
        events=[
            KnowledgeEvent(
                event_id="e1",
                lesson_id="test",
                event_type="rule_statement",
                raw_text="A rule.",
                normalized_text="A rule.",
                source_event_ids=[],
            ),
        ],
    )
    evidence_index = EvidenceIndex(
        schema_version="1.0",
        lesson_id="test",
        evidence_refs=[
            EvidenceRef(
                evidence_id="ev1",
                lesson_id="test",
                source_event_ids=["e1"],
            ),
        ],
    )
    rule_cards = RuleCardCollection(
        schema_version="1.0",
        lesson_id="test",
        rules=[
            RuleCard(
                rule_id="r1",
                lesson_id="test",
                concept="test",
                rule_text="Rule text.",
                source_event_ids=["e99"],  # e99 does not exist
            ),
        ],
    )
    errors = validate_cross_artifact_references(
        knowledge_events, evidence_index, rule_cards
    )
    assert len(errors) > 0
    assert any("e99" in err and "source_event_id" in err for err in errors)
