"""Tests that the pipeline and individual stages handle degraded input without crashing."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pipeline.component2 import evidence_linker
from pipeline.component2 import knowledge_builder
from pipeline.component2 import ml_prep
from pipeline.component2 import rule_reducer
from pipeline.invalidation_filter import load_dense_analysis
from pipeline.schemas import (
    EvidenceIndex,
    EvidenceRef,
    KnowledgeEvent,
    KnowledgeEventCollection,
    RuleCard,
    RuleCardCollection,
)


# ----- test_sparse_transcript_pipeline_survives -----


def test_sparse_transcript_pipeline_survives(lesson_edge_sparse_root: Path) -> None:
    """Load lesson_edge_sparse chunks and dense_analysis; build knowledge_events from minimal
    extraction, then build_evidence_index, then build_rule_cards. Assert no exception;
    outputs may be minimal (few or zero events/rules).
    """
    chunks_path = lesson_edge_sparse_root / "chunks.json"
    dense_path = lesson_edge_sparse_root / "dense_analysis.json"
    lesson_id = "lesson_edge_sparse"

    chunks = evidence_linker.load_chunks_json(chunks_path)

    dense_analysis = load_dense_analysis(dense_path) if dense_path.exists() else None

    adapted = knowledge_builder.adapt_chunks(chunks, lesson_id=lesson_id)
    # One minimal ChunkExtractionResult per chunk (no statements => no events)
    extraction_results = [knowledge_builder.ChunkExtractionResult() for _ in adapted]

    collection, _ = knowledge_builder.build_knowledge_events_from_extraction_results(
        adapted,
        extraction_results,
        lesson_id=lesson_id,
    )
    knowledge_events = list(collection.events)

    evidence_index, _ = evidence_linker.build_evidence_index(
        lesson_id,
        knowledge_events=knowledge_events,
        chunks=chunks,
        dense_analysis=dense_analysis,
    )

    rule_cards, _ = rule_reducer.build_rule_cards(collection, evidence_index)
    # Pipeline completed; outputs may be minimal
    assert rule_cards.lesson_id == lesson_id
    assert isinstance(rule_cards.rules, list)


# ----- test_weak_visuals_pipeline_survives -----


def test_weak_visuals_pipeline_survives(lesson_minimal_root: Path) -> None:
    """Use chunks with strong transcript but few/empty visual_events. Run evidence_linker
    and rule_reducer. Assert pipeline completes without crash; evidence may be sparse.
    """
    lesson_id = "lesson_weak_visuals"
    # In-memory chunks: one chunk with transcript, empty or minimal visual_events
    chunks = [
        {
            "chunk_index": 0,
            "start_time_seconds": 0.0,
            "end_time_seconds": 30.0,
            "transcript_lines": [
                {"start_seconds": 0.0, "end_seconds": 5.0, "text": "A level is a price zone where the market reacted."},
                {"start_seconds": 5.0, "end_seconds": 10.0, "text": "The more reactions, the stronger the level."},
            ],
            "visual_events": [],
            "metadata": {},
        }
    ]
    # Knowledge events from “strong” transcript (minimal in-memory)
    events = [
        KnowledgeEvent(
            event_id="ke_weak_0_rule_statement_0",
            lesson_id=lesson_id,
            event_type="rule_statement",
            raw_text="A level is a price zone where the market reacted.",
            normalized_text="A level is a price zone where the market reacted.",
            concept="level",
            subconcept=None,
            source_event_ids=[],
            timestamp_start="00:00",
            timestamp_end="00:30",
            evidence_refs=[],
            confidence="high",
            confidence_score=0.8,
            ambiguity_notes=[],
            metadata={"chunk_index": 0},
        ),
    ]
    collection = KnowledgeEventCollection(
        schema_version="1.0",
        lesson_id=lesson_id,
        events=events,
    )

    evidence_index, _ = evidence_linker.build_evidence_index(
        lesson_id,
        knowledge_events=collection.events,
        chunks=chunks,
        dense_analysis=None,
    )
    rule_cards, _ = rule_reducer.build_rule_cards(collection, evidence_index)
    assert rule_cards.lesson_id == lesson_id
    assert isinstance(rule_cards.rules, list)


# ----- test_ambiguous_examples_do_not_become_positive -----


def test_ambiguous_examples_do_not_become_positive() -> None:
    """Use in-memory rule_cards with ambiguous_example_refs and evidence with
    example_role=ambiguous_example. After enrich_rule_card_collection_for_ml,
    assert ambiguous refs remain in ambiguous_example_refs and are not in positive_example_refs.
    """
    lesson_id = "lesson_ambiguous"
    amb_evidence_id = "ev_ambiguous_001"
    pos_evidence_id = "ev_positive_001"

    evidence_refs = [
        EvidenceRef(
            evidence_id=amb_evidence_id,
            lesson_id=lesson_id,
            frame_ids=["000010"],
            example_role="ambiguous_example",
            source_event_ids=[],
        ),
        EvidenceRef(
            evidence_id=pos_evidence_id,
            lesson_id=lesson_id,
            frame_ids=["000020"],
            example_role="positive_example",
            source_event_ids=[],
        ),
    ]
    evidence_index = EvidenceIndex(
        schema_version="1.0",
        lesson_id=lesson_id,
        evidence_refs=evidence_refs,
    )

    rule = RuleCard(
        rule_id="rule_ambiguous_0",
        lesson_id=lesson_id,
        concept="level",
        subconcept=None,
        rule_text="A level is a price zone where the market reacted.",
        evidence_refs=[amb_evidence_id, pos_evidence_id],
        positive_example_refs=[],
        negative_example_refs=[],
        ambiguous_example_refs=[amb_evidence_id],
    )
    rules = RuleCardCollection(
        schema_version="1.0",
        lesson_id=lesson_id,
        rules=[rule],
    )

    enriched = ml_prep.enrich_rule_card_collection_for_ml(rules, evidence_index)
    assert len(enriched.rules) == 1
    r = enriched.rules[0]
    assert amb_evidence_id in (r.ambiguous_example_refs or []), "ambiguous ref must stay in ambiguous_example_refs"
    assert amb_evidence_id not in (r.positive_example_refs or []), "ambiguous ref must not be forced into positive_example_refs"
    assert pos_evidence_id in (r.positive_example_refs or []), "positive ref should remain in positive_example_refs"


# ----- test_missing_concepts_do_not_crash_pipeline -----


def test_missing_concepts_do_not_crash_pipeline() -> None:
    """Use in-memory KnowledgeEventCollection with some events having concept=None.
    Run build_rule_cards with minimal evidence_index. Assert no crash; concept graph or rules may be smaller.
    """
    lesson_id = "lesson_missing_concepts"
    events = [
        KnowledgeEvent(
            event_id="ke_mc_0_rule_0",
            lesson_id=lesson_id,
            event_type="rule_statement",
            raw_text="Price often reacts at levels.",
            normalized_text="Price often reacts at levels.",
            concept="level",
            subconcept=None,
            source_event_ids=[],
            timestamp_start="00:00",
            timestamp_end="00:20",
            evidence_refs=[],
            confidence="medium",
            confidence_score=0.6,
            ambiguity_notes=[],
            metadata={"chunk_index": 0},
        ),
        KnowledgeEvent(
            event_id="ke_mc_0_rule_1",
            lesson_id=lesson_id,
            event_type="rule_statement",
            raw_text="Sometimes the market ignores the level.",
            normalized_text="Sometimes the market ignores the level.",
            concept=None,
            subconcept=None,
            source_event_ids=[],
            timestamp_start="00:20",
            timestamp_end="00:40",
            evidence_refs=[],
            confidence="low",
            confidence_score=0.4,
            ambiguity_notes=[],
            metadata={"chunk_index": 0},
        ),
    ]
    collection = KnowledgeEventCollection(
        schema_version="1.0",
        lesson_id=lesson_id,
        events=events,
    )
    evidence_index = EvidenceIndex(
        schema_version="1.0",
        lesson_id=lesson_id,
        evidence_refs=[],
    )

    rule_cards, _ = rule_reducer.build_rule_cards(collection, evidence_index)
    assert rule_cards.lesson_id == lesson_id
    assert isinstance(rule_cards.rules, list)
    # Events with concept=None become rules with concept "unknown" via rule_reducer
    for card in rule_cards.rules:
        assert card.concept and card.concept.strip(), "RuleCard must have non-blank concept"
