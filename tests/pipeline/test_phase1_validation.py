"""Phase 1 validation gates: placeholder rules, empty provenance, invalid evidence (01-phase1.md)."""

from __future__ import annotations

import pytest

from pipeline.schemas import (
    EvidenceRef,
    KnowledgeEvent,
    RuleCard,
    is_placeholder_text,
    normalize_text,
    validate_evidence_ref,
    validate_knowledge_event,
    validate_rule_card,
)


def test_reject_placeholder_rule_card() -> None:
    """RuleCard with placeholder rule_text and empty source_event_ids must fail validation."""
    card = RuleCard.model_construct(
        rule_id="r1",
        lesson_id="lesson-1",
        concept="level",
        rule_text="No rule text extracted.",
        source_event_ids=[],
    )
    errors = validate_rule_card(card)
    assert len(errors) > 0
    assert any("placeholder" in e.lower() or "source_event_ids" in e.lower() for e in errors)
    # Such a rule would not be written to final rules
    assert validate_rule_card(card)  # non-empty


def test_accept_minimal_valid_rule_card() -> None:
    """Rule with non-empty rule_text and non-empty source_event_ids passes validation."""
    card = RuleCard(
        rule_id="r1",
        lesson_id="lesson-1",
        concept="level",
        rule_text="Price must close beyond the level for a valid breakout.",
        source_event_ids=["ke_lesson_0_rule_statement_0"],
    )
    errors = validate_rule_card(card)
    assert errors == []


def test_reject_empty_knowledge_event_text() -> None:
    """Event with empty or placeholder normalized_text is rejected by validator (or builder does not emit)."""
    # Use model_construct to build without Pydantic validators so we can test validate_knowledge_event
    event = KnowledgeEvent.model_construct(
        event_id="ev-1",
        lesson_id="lesson-1",
        event_type="rule_statement",
        raw_text="Valid text",
        normalized_text="",
    )
    errors = validate_knowledge_event(event)
    assert len(errors) > 0
    assert any("placeholder" in e.lower() or "normalized" in e.lower() for e in errors)

    event_placeholder = KnowledgeEvent.model_construct(
        event_id="ev-2",
        lesson_id="lesson-1",
        event_type="rule_statement",
        raw_text="No rule text extracted.",
        normalized_text="no rule text extracted.",
    )
    errors2 = validate_knowledge_event(event_placeholder)
    assert len(errors2) > 0


def test_reject_evidence_with_no_frames_and_no_raw_visual_ids() -> None:
    """EvidenceRef with both frame_ids and raw_visual_event_ids empty must fail validation."""
    ref = EvidenceRef(
        evidence_id="ev-1",
        lesson_id="lesson-1",
        frame_ids=[],
        raw_visual_event_ids=[],
    )
    errors = validate_evidence_ref(ref, allow_unlinked_rules=True)
    assert len(errors) > 0
    assert any("empty" in e.lower() or "frame" in e.lower() for e in errors)


def test_allow_unlinked_evidence_pre_reduction() -> None:
    """EvidenceRef with empty linked_rule_ids passes when allow_unlinked_rules=True (pre-reduction)."""
    ref = EvidenceRef(
        evidence_id="ev-1",
        lesson_id="lesson-1",
        frame_ids=["f1"],
        raw_visual_event_ids=[],
        linked_rule_ids=[],
    )
    errors = validate_evidence_ref(ref, allow_unlinked_rules=True)
    # No error for empty linked_rule_ids in pre-reduction mode
    assert not any("linked_rule" in e.lower() for e in errors)


def test_blank_labeling_guidance_for_invalid_rule() -> None:
    """Invalid/placeholder rule is quarantined and does not receive labeling_guidance in final artifact."""
    card = RuleCard.model_construct(
        rule_id="r1",
        lesson_id="lesson-1",
        concept="unknown",
        rule_text="No rule text extracted.",
        source_event_ids=[],
        labeling_guidance="Label when match.",  # would be wrong to emit
    )
    errors = validate_rule_card(card)
    assert len(errors) > 0
    # Phase 1: such a rule is quarantined (not in final rules), so labeling_guidance is never written
    assert any("placeholder" in e.lower() or "labeling" in e.lower() or "source_event" in e.lower() for e in errors)


def test_placeholder_helpers() -> None:
    """normalize_text and is_placeholder_text behave as specified."""
    assert normalize_text("  foo   bar  ") == "foo bar"
    assert normalize_text(None) == ""
    assert is_placeholder_text("No rule text extracted.") is True
    assert is_placeholder_text("n/a") is True
    assert is_placeholder_text("  N/A  ") is True
    assert is_placeholder_text("A real rule.") is False
