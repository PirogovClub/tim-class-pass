"""Tests for pipeline artifact invariants using validation.py and fixture data."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import load_json
from pipeline.schemas import (
    EvidenceIndex,
    KnowledgeEventCollection,
    RuleCardCollection,
)
from pipeline.validation import (
    MAX_VISUAL_SUMMARY_LENGTH,
    VALID_CONFIDENCE_LABELS,
    validate_export_quality,
    validate_no_visual_blob_leakage,
)

# Fixture root: conftest's FIXTURES_ROOT or Path relative to this file
TESTS_DIR = Path(__file__).resolve().parent
FIXTURES_LESSON_MINIMAL = TESTS_DIR / "fixtures" / "lesson_minimal"
FIXTURES_LESSON_MULTI = TESTS_DIR / "fixtures" / "lesson_multi_concept"


def _load_lesson_minimal_root(lesson_minimal_root: Path | None) -> Path:
    """Use pytest fixture path if provided, else fallback to fixtures/lesson_minimal."""
    if lesson_minimal_root is not None:
        return lesson_minimal_root
    return FIXTURES_LESSON_MINIMAL


# ----- Knowledge events -----


def test_every_knowledge_event_has_event_id(lesson_minimal_root: Path) -> None:
    """Load knowledge_events.json as KnowledgeEventCollection; assert every event has event_id."""
    root = _load_lesson_minimal_root(lesson_minimal_root)
    path = root / "knowledge_events.json"
    collection = KnowledgeEventCollection.model_validate_json(path.read_text(encoding="utf-8"))
    for ev in collection.events:
        assert ev.event_id, f"KnowledgeEvent missing event_id: {ev}"


def test_every_knowledge_event_has_phase1_provenance_fields(lesson_minimal_root: Path) -> None:
    """KnowledgeEvent provenance in Phase 1 is event_id + lesson_id + chunk_index + timestamps, not source_event_ids."""
    root = _load_lesson_minimal_root(lesson_minimal_root)
    path = root / "knowledge_events.json"
    collection = KnowledgeEventCollection.model_validate_json(path.read_text(encoding="utf-8"))

    for ev in collection.events:
        assert ev.event_id, f"KnowledgeEvent missing event_id: {ev}"
        assert ev.lesson_id, f"KnowledgeEvent {ev.event_id} missing lesson_id"
        assert (ev.metadata or {}).get("chunk_index") is not None, (
            f"KnowledgeEvent {ev.event_id} missing metadata.chunk_index"
        )
        assert ev.timestamp_start, f"KnowledgeEvent {ev.event_id} missing timestamp_start"
        assert ev.timestamp_end, f"KnowledgeEvent {ev.event_id} missing timestamp_end"
        assert ev.normalized_text, f"KnowledgeEvent {ev.event_id} missing normalized_text"


def test_every_evidence_ref_has_evidence_id(lesson_minimal_root: Path) -> None:
    """Load evidence_index.json; assert every evidence_ref has evidence_id."""
    root = _load_lesson_minimal_root(lesson_minimal_root)
    path = root / "evidence_index.json"
    index = EvidenceIndex.model_validate_json(path.read_text(encoding="utf-8"))
    for ref in index.evidence_refs:
        assert ref.evidence_id, f"EvidenceRef missing evidence_id: {ref}"


def test_every_rule_card_has_rule_id(lesson_minimal_root: Path) -> None:
    """Load rule_cards.json; assert every rule has rule_id."""
    root = _load_lesson_minimal_root(lesson_minimal_root)
    path = root / "rule_cards.json"
    collection = RuleCardCollection.model_validate_json(path.read_text(encoding="utf-8"))
    for rule in collection.rules:
        assert rule.rule_id, f"RuleCard missing rule_id: {rule}"


def test_every_rule_card_has_source_event_ids(lesson_minimal_root: Path) -> None:
    """Load rule_cards; assert every rule has non-empty source_event_ids."""
    root = _load_lesson_minimal_root(lesson_minimal_root)
    path = root / "rule_cards.json"
    collection = RuleCardCollection.model_validate_json(path.read_text(encoding="utf-8"))
    for rule in collection.rules:
        assert rule.source_event_ids, (
            f"RuleCard {rule.rule_id} has no source_event_ids"
        )


def test_every_evidence_ref_has_visual_provenance(lesson_minimal_root: Path) -> None:
    """Load evidence_index; assert every ref has frame_ids or raw_visual_event_ids."""
    root = _load_lesson_minimal_root(lesson_minimal_root)
    path = root / "evidence_index.json"
    index = EvidenceIndex.model_validate_json(path.read_text(encoding="utf-8"))
    for ref in index.evidence_refs:
        has_visual = bool(ref.frame_ids or ref.raw_visual_event_ids)
        assert has_visual, (
            f"EvidenceRef {ref.evidence_id} has neither frame_ids nor raw_visual_event_ids"
        )


def test_every_evidence_ref_has_source_event_ids(lesson_minimal_root: Path) -> None:
    """Load evidence_index; assert every ref has source_event_ids."""
    root = _load_lesson_minimal_root(lesson_minimal_root)
    path = root / "evidence_index.json"
    index = EvidenceIndex.model_validate_json(path.read_text(encoding="utf-8"))
    for ref in index.evidence_refs:
        assert ref.source_event_ids, (
            f"EvidenceRef {ref.evidence_id} has no source_event_ids"
        )


def test_confidence_fields_valid(lesson_minimal_root: Path) -> None:
    """For knowledge_events and rule_cards, assert confidence in (low, medium, high) and confidence_score in [0,1] if present."""
    root = _load_lesson_minimal_root(lesson_minimal_root)
    # Knowledge events
    ke_path = root / "knowledge_events.json"
    ke_coll = KnowledgeEventCollection.model_validate_json(ke_path.read_text(encoding="utf-8"))
    for ev in ke_coll.events:
        assert ev.confidence in VALID_CONFIDENCE_LABELS, (
            f"KnowledgeEvent {ev.event_id} invalid confidence: {ev.confidence}"
        )
        if ev.confidence_score is not None:
            assert 0.0 <= ev.confidence_score <= 1.0, (
                f"KnowledgeEvent {ev.event_id} confidence_score out of [0,1]: {ev.confidence_score}"
            )
    # Rule cards
    rc_path = root / "rule_cards.json"
    rc_coll = RuleCardCollection.model_validate_json(rc_path.read_text(encoding="utf-8"))
    for rule in rc_coll.rules:
        assert rule.confidence in VALID_CONFIDENCE_LABELS, (
            f"RuleCard {rule.rule_id} invalid confidence: {rule.confidence}"
        )
        if rule.confidence_score is not None:
            assert 0.0 <= rule.confidence_score <= 1.0, (
                f"RuleCard {rule.rule_id} confidence_score out of [0,1]: {rule.confidence_score}"
            )


def test_no_visual_blob_leakage_in_structured_outputs(lesson_minimal_root: Path) -> None:
    """Load knowledge_events, evidence_index, rule_cards; run validate_no_visual_blob_leakage on each; assert no errors."""
    root = _load_lesson_minimal_root(lesson_minimal_root)
    ke_errors = validate_no_visual_blob_leakage(
        load_json(root / "knowledge_events.json"), "knowledge_events"
    )
    assert not ke_errors, f"Knowledge events blob leakage: {ke_errors}"
    ei_errors = validate_no_visual_blob_leakage(
        load_json(root / "evidence_index.json"), "evidence_index"
    )
    assert not ei_errors, f"Evidence index blob leakage: {ei_errors}"
    rc_errors = validate_no_visual_blob_leakage(
        load_json(root / "rule_cards.json"), "rule_cards"
    )
    assert not rc_errors, f"Rule cards blob leakage: {rc_errors}"


def test_visual_summaries_compact(lesson_minimal_root: Path) -> None:
    """Load rule_cards; assert every rule.visual_summary has len <= MAX_VISUAL_SUMMARY_LENGTH if present."""
    root = _load_lesson_minimal_root(lesson_minimal_root)
    path = root / "rule_cards.json"
    collection = RuleCardCollection.model_validate_json(path.read_text(encoding="utf-8"))
    for rule in collection.rules:
        if rule.visual_summary is not None:
            assert len(rule.visual_summary) <= MAX_VISUAL_SUMMARY_LENGTH, (
                f"RuleCard {rule.rule_id} visual_summary length {len(rule.visual_summary)} > {MAX_VISUAL_SUMMARY_LENGTH}"
            )


def test_export_outputs_distinct(
    lesson_minimal_root: Path, tmp_path: Path
) -> None:
    """Call exporters to produce review_md and rag_md from fixture, then validate_export_quality; assert no errors."""
    from pipeline.component2.exporters import export_rag_markdown, export_review_markdown

    root = _load_lesson_minimal_root(lesson_minimal_root)
    rule_cards_path = root / "rule_cards.json"
    evidence_index_path = root / "evidence_index.json"
    knowledge_events_path = root / "knowledge_events.json"
    review_out = tmp_path / "review.md"
    rag_out = tmp_path / "rag.md"

    review_md, _ = export_review_markdown(
        lesson_id="lesson_minimal",
        lesson_title="Lesson minimal",
        rule_cards_path=rule_cards_path,
        evidence_index_path=evidence_index_path,
        knowledge_events_path=knowledge_events_path,
        output_path=review_out,
        use_llm=False,
    )
    rag_md, _ = export_rag_markdown(
        lesson_id="lesson_minimal",
        lesson_title="Lesson minimal",
        rule_cards_path=rule_cards_path,
        evidence_index_path=evidence_index_path,
        knowledge_events_path=knowledge_events_path,
        output_path=rag_out,
        use_llm=False,
    )
    errors = validate_export_quality(review_md, rag_md)
    assert not errors, f"Export quality: {errors}"
