"""Phase 1 export gates: final exports hard-gated (02-phase1.md)."""

from __future__ import annotations

from pipeline.schemas import (
    EvidenceIndex,
    EvidenceRef,
    KnowledgeEvent,
    KnowledgeEventCollection,
    RuleCard,
    RuleCardCollection,
    validate_evidence_index_for_export,
    validate_knowledge_event_collection_for_export,
    validate_rule_card_collection_for_export,
)
from pipeline.component2.ml_prep import (
    build_ml_manifest,
    enrich_rule_card_for_ml,
)
from pipeline.component2.evidence_linker import (
    VisualEvidenceCandidate,
    infer_example_role,
)


def test_placeholder_rule_removed_before_final_export() -> None:
    """Placeholder rule is filtered out by validate_rule_card_collection_for_export."""
    valid = RuleCard(
        rule_id="r1",
        lesson_id="lesson-1",
        concept="level",
        rule_text="Price must close beyond the level for a valid breakout.",
        source_event_ids=["ke_0"],
    )
    placeholder = RuleCard.model_construct(
        rule_id="r2",
        lesson_id="lesson-1",
        concept="unknown",
        rule_text="No rule text extracted.",
        source_event_ids=[],
    )
    collection = RuleCardCollection(
        schema_version="1.0",
        lesson_id="lesson-1",
        rules=[valid, placeholder],
    )
    valid_collection, debug_rows = validate_rule_card_collection_for_export(collection)
    assert len(valid_collection.rules) == 1
    assert valid_collection.rules[0].rule_id == "r1"
    assert len(debug_rows) == 1
    assert debug_rows[0]["entity_id"] == "r2"
    assert "reason_rejected" in debug_rows[0]


def test_ml_enrichment_no_guidance_for_invalid_rule() -> None:
    """Invalid rule gets no labeling_guidance, no candidate_features, no ML example refs."""
    invalid_rule = RuleCard.model_construct(
        rule_id="r1",
        lesson_id="lesson-1",
        concept="unknown",
        rule_text="No rule text extracted.",
        source_event_ids=[],
    )
    result = enrich_rule_card_for_ml(invalid_rule, [])
    assert result.labeling_guidance is None
    assert result.candidate_features == []
    assert result.positive_example_refs == []
    assert result.negative_example_refs == []
    assert result.ambiguous_example_refs == []


def test_ml_manifest_skips_invalid_rules() -> None:
    """build_ml_manifest omits invalid rules from manifest['rules']."""
    invalid_rule = RuleCard.model_construct(
        rule_id="r1",
        lesson_id="lesson-1",
        concept="unknown",
        rule_text="No rule text extracted.",
        source_event_ids=[],
    )
    collection = RuleCardCollection(
        schema_version="1.0",
        lesson_id="lesson-1",
        rules=[invalid_rule],
    )
    evidence_index = EvidenceIndex(schema_version="1.0", lesson_id="lesson-1", evidence_refs=[])
    manifest, debug_rows = build_ml_manifest(
        lesson_id="lesson-1",
        rule_cards=collection,
        evidence_index=evidence_index,
    )
    assert len(manifest["rules"]) == 0
    assert any(d.get("skipped_from_manifest") for d in debug_rows)


def test_false_breakout_not_auto_counterexample() -> None:
    """Visual with 'false breakout' and rule_statement link is not labeled counterexample."""
    candidate = VisualEvidenceCandidate(
        candidate_id="ev1",
        lesson_id="lesson-1",
        chunk_index=0,
        timestamp_start=0.0,
        timestamp_end=60.0,
        compact_visual_summary="Example of false breakout: price breaks level then reverses.",
        concept_hints=["false_breakout"],
        visual_events=[],
    )
    linked = [
        KnowledgeEvent.model_construct(
            event_id="ke1",
            lesson_id="lesson-1",
            event_type="rule_statement",
            raw_text="False breakout when price fails to hold beyond level.",
            normalized_text="False breakout when price fails to hold beyond level.",
        ),
    ]
    role = infer_example_role(candidate, linked)
    assert role != "counterexample"
    assert role == "positive_example"


def test_post_ml_validation_catches_bad_rules() -> None:
    """Export validation helper quarantines invalid rule from enriched collection."""
    invalid_rule = RuleCard.model_construct(
        rule_id="r1",
        lesson_id="lesson-1",
        concept="",
        rule_text="No rule text extracted.",
        source_event_ids=[],
    )
    collection = RuleCardCollection(
        schema_version="1.0",
        lesson_id="lesson-1",
        rules=[invalid_rule],
    )
    valid_collection, debug_rows = validate_rule_card_collection_for_export(collection)
    assert len(valid_collection.rules) == 0
    assert len(debug_rows) == 1
    assert debug_rows[0]["entity_id"] == "r1"


# ----- Knowledge/evidence export validators (03-phase1) -----


def test_final_evidence_export_rejects_empty_source_event_ids() -> None:
    index = EvidenceIndex(
        lesson_id="lesson1",
        evidence_refs=[
            EvidenceRef(
                lesson_id="lesson1",
                evidence_id="ev1",
                frame_ids=["001"],
                linked_rule_ids=["r1"],
                source_event_ids=[],
            )
        ],
    )

    valid_index, debug_rows = validate_evidence_index_for_export(index)
    assert len(valid_index.evidence_refs) == 0
    assert len(debug_rows) == 1
    assert "source_event_ids" in " ".join(debug_rows[0]["reason_rejected"])


def test_final_evidence_export_rejects_empty_linked_rule_ids() -> None:
    index = EvidenceIndex(
        lesson_id="lesson1",
        evidence_refs=[
            EvidenceRef(
                lesson_id="lesson1",
                evidence_id="ev1",
                frame_ids=["001"],
                source_event_ids=["ke1"],
                linked_rule_ids=[],
            )
        ],
    )

    valid_index, debug_rows = validate_evidence_index_for_export(index)
    assert len(valid_index.evidence_refs) == 0
    assert len(debug_rows) == 1
    assert "linked_rule_ids" in " ".join(debug_rows[0]["reason_rejected"])


def test_final_knowledge_export_rejects_placeholder_event() -> None:
    bad_event = KnowledgeEvent.model_construct(
        lesson_id="lesson1",
        event_id="ke1",
        event_type="rule_statement",
        raw_text="No rule text extracted.",
        normalized_text="No rule text extracted.",
        metadata={"chunk_index": 0},
    )

    collection = KnowledgeEventCollection(
        lesson_id="lesson1",
        events=[bad_event],
    )

    valid_collection, debug_rows = validate_knowledge_event_collection_for_export(collection)
    assert len(valid_collection.events) == 0
    assert len(debug_rows) == 1


def test_final_knowledge_export_allows_empty_source_event_ids_when_event_is_otherwise_valid() -> None:
    """Valid knowledge event with empty source_event_ids is still allowed by export validation (05-phase1)."""
    event = KnowledgeEvent(
        lesson_id="lesson1",
        event_id="ke1",
        event_type="rule_statement",
        raw_text="A valid rule statement.",
        normalized_text="A valid rule statement.",
        source_event_ids=[],
        metadata={"chunk_index": 0},
        timestamp_start="00:01",
        timestamp_end="00:10",
    )

    collection = KnowledgeEventCollection(
        lesson_id="lesson1",
        events=[event],
    )

    valid_collection, debug_rows = validate_knowledge_event_collection_for_export(collection)

    assert len(valid_collection.events) == 1
    assert valid_collection.events[0].event_id == "ke1"
    assert debug_rows == []
