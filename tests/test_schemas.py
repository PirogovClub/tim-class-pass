"""Tests for the canonical pipeline schemas (Task 2)."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from pipeline.schemas import (
    EvidenceRef,
    KnowledgeEvent,
    LessonKnowledgeBundle,
    RuleCard,
)


def test_valid_knowledge_event() -> None:
    """Construct a valid KnowledgeEvent and ensure serialization works."""
    event = KnowledgeEvent(
        lesson_id="lesson-1",
        event_id="ev-1",
        event_type="rule_statement",
        raw_text="Price breaks above the level.",
        normalized_text="Price breaks above the level.",
    )
    out = event.model_dump_json()
    assert out
    data = json.loads(out)
    assert data["event_id"] == "ev-1"
    assert data["event_type"] == "rule_statement"
    assert data["raw_text"] == "Price breaks above the level."
    assert data["normalized_text"] == "Price breaks above the level."
    assert data["lesson_id"] == "lesson-1"
    # Round-trip
    event2 = KnowledgeEvent.model_validate_json(out)
    assert event2.event_id == event.event_id
    assert event2.raw_text == event.raw_text


def test_blank_text_rejected() -> None:
    """Blank raw_text or normalized_text should fail."""
    with pytest.raises(ValidationError):
        KnowledgeEvent(
            lesson_id="lesson-1",
            event_id="ev-1",
            event_type="rule_statement",
            raw_text="",
            normalized_text="Price breaks above the level.",
        )
    with pytest.raises(ValidationError):
        KnowledgeEvent(
            lesson_id="lesson-1",
            event_id="ev-1",
            event_type="rule_statement",
            raw_text="Price breaks above the level.",
            normalized_text="   ",
        )


def test_valid_rule_card() -> None:
    """Construct a minimal valid RuleCard and assert serialization."""
    card = RuleCard(
        lesson_id="lesson-1",
        rule_id="rule-1",
        concept="level",
        rule_text="A level is a horizontal support or resistance.",
    )
    out = card.model_dump_json()
    assert out
    data = json.loads(out)
    assert data["rule_id"] == "rule-1"
    assert data["concept"] == "level"
    assert data["rule_text"] == "A level is a horizontal support or resistance."
    assert data["lesson_id"] == "lesson-1"
    assert data["conditions"] == []
    assert data["evidence_refs"] == []


def test_rule_card_requires_concept_and_rule_text() -> None:
    """Blank concept or rule_text should fail."""
    with pytest.raises(ValidationError):
        RuleCard(
            lesson_id="lesson-1",
            rule_id="rule-1",
            concept="",
            rule_text="Some rule.",
        )
    with pytest.raises(ValidationError):
        RuleCard(
            lesson_id="lesson-1",
            rule_id="rule-1",
            concept="level",
            rule_text="  \t ",
        )


def test_confidence_score_bounds() -> None:
    """confidence_score must be in [0.0, 1.0]; 1.2 and -0.1 should fail."""
    with pytest.raises(ValidationError):
        KnowledgeEvent(
            lesson_id="lesson-1",
            event_id="ev-1",
            event_type="rule_statement",
            raw_text="Text.",
            normalized_text="Text.",
            confidence_score=1.2,
        )
    with pytest.raises(ValidationError):
        KnowledgeEvent(
            lesson_id="lesson-1",
            event_id="ev-1",
            event_type="rule_statement",
            raw_text="Text.",
            normalized_text="Text.",
            confidence_score=-0.1,
        )
    # In-bounds is ok
    event = KnowledgeEvent(
        lesson_id="lesson-1",
        event_id="ev-1",
        event_type="rule_statement",
        raw_text="Text.",
        normalized_text="Text.",
        confidence_score=0.9,
    )
    assert event.confidence_score == 0.9


def test_unknown_field_rejected() -> None:
    """Passing an extra keyword should raise ValidationError (extra='forbid')."""
    with pytest.raises(ValidationError):
        KnowledgeEvent(
            lesson_id="lesson-1",
            event_id="ev-1",
            event_type="rule_statement",
            raw_text="Text.",
            normalized_text="Text.",
            unknown_field=1,
        )


def test_valid_evidence_ref() -> None:
    """Build EvidenceRef with empty lists; assert JSON has [] not null."""
    ref = EvidenceRef(
        lesson_id="lesson-1",
        evidence_id="evid-1",
    )
    out = ref.model_dump_json()
    assert out
    data = json.loads(out)
    assert data["evidence_id"] == "evid-1"
    assert data["frame_ids"] == []
    assert data["screenshot_paths"] == []
    assert data["linked_rule_ids"] == []
    assert data["raw_visual_event_ids"] == []
    # List fields must be [] not null (no None lists)
    assert data["frame_ids"] is not None
    assert data["screenshot_paths"] is not None


def test_bundle_serialization() -> None:
    """Build LessonKnowledgeBundle with one event, one evidence ref, one rule card."""
    event = KnowledgeEvent(
        lesson_id="L1",
        event_id="e1",
        event_type="definition",
        raw_text="Level is support or resistance.",
        normalized_text="Level is support or resistance.",
    )
    evidence = EvidenceRef(
        lesson_id="L1",
        evidence_id="ev1",
    )
    rule = RuleCard(
        lesson_id="L1",
        rule_id="r1",
        concept="level",
        rule_text="Trade in the direction of the break.",
    )
    bundle = LessonKnowledgeBundle(
        lesson_id="L1",
        knowledge_events=[event],
        evidence_index=[evidence],
        rule_cards=[rule],
    )
    out = bundle.model_dump_json()
    assert out
    data = json.loads(out)
    assert data["schema_version"] == "1.0"
    assert data["lesson_id"] == "L1"
    assert len(data["knowledge_events"]) == 1
    assert data["knowledge_events"][0]["event_id"] == "e1"
    assert len(data["evidence_index"]) == 1
    assert data["evidence_index"][0]["evidence_id"] == "ev1"
    assert len(data["rule_cards"]) == 1
    assert data["rule_cards"][0]["rule_id"] == "r1"
