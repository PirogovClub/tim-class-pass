"""Integration tests for pipeline stage boundaries and full structured pipeline smoke."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from conftest import FIXTURES_ROOT, GOLDEN_ROOT, load_json
from pipeline.contracts import PipelinePaths
from pipeline.schemas import (
    ConceptGraph,
    EvidenceIndex,
    KnowledgeEventCollection,
    RuleCardCollection,
)
from pipeline.validation import (
    validate_concept_graph_integrity,
    validate_cross_artifact_references,
    validate_evidence_index_integrity,
    validate_no_visual_blob_leakage,
    validate_rule_card_collection_integrity,
)
from pipeline.component2 import evidence_linker
from pipeline.component2 import rule_reducer
from pipeline.component2 import concept_graph
from pipeline.component2 import ml_prep
from pipeline.component2 import exporters
from pipeline.invalidation_filter import load_dense_analysis


# ----- Step 3 → Step 4 -----


def test_step3_to_step4_integration(
    lesson_minimal_root: Path,
    temp_video_root: Path,
) -> None:
    """Build evidence index from knowledge_events, chunks, dense_analysis; validate integrity and cross-refs."""
    lesson_id = "lesson_minimal"
    ke_path = lesson_minimal_root / "knowledge_events.json"
    chunks_path = lesson_minimal_root / "chunks.json"
    dense_path = lesson_minimal_root / "dense_analysis.json"
    rule_cards_path = lesson_minimal_root / "rule_cards.json"

    collection = KnowledgeEventCollection.model_validate_json(
        ke_path.read_text(encoding="utf-8")
    )
    chunks = evidence_linker.load_chunks_json(chunks_path)
    dense_analysis = load_dense_analysis(dense_path) if dense_path.exists() else None

    evidence_index, _ = evidence_linker.build_evidence_index(
        lesson_id,
        knowledge_events=collection.events,
        chunks=chunks,
        dense_analysis=dense_analysis,
    )

    assert evidence_index.evidence_refs, "EvidenceIndex should have evidence_refs"
    errors = validate_evidence_index_integrity(evidence_index)
    assert not errors, f"Evidence index integrity: {errors}"

    # Cross-refs: evidence_index vs knowledge_events only (skip rule_cards: fixture
    # rule_cards point to fixture evidence IDs, not this newly built evidence_index)
    empty_rules = RuleCardCollection(
        schema_version="1.0", lesson_id=lesson_id, rules=[]
    )
    cross_errors = validate_cross_artifact_references(
        collection, evidence_index, empty_rules
    )
    assert not cross_errors, f"Cross-artifact references (knowledge↔evidence): {cross_errors}"


# ----- Step 4 → Step 5 -----


def test_step4_to_step5_integration(lesson_minimal_root: Path) -> None:
    """Build rule cards from knowledge_events + evidence_index; assert rules and source_event_ids."""
    ke_path = lesson_minimal_root / "knowledge_events.json"
    ei_path = lesson_minimal_root / "evidence_index.json"

    knowledge_collection = rule_reducer.load_knowledge_events(ke_path)
    evidence_index = rule_reducer.load_evidence_index(ei_path)

    rule_cards, _ = rule_reducer.build_rule_cards(
        knowledge_collection,
        evidence_index,
    )

    assert rule_cards.rules, "RuleCardCollection.rules should be non-empty"
    for rule in rule_cards.rules:
        assert rule.source_event_ids, (
            f"RuleCard {rule.rule_id} must have source_event_ids"
        )


# ----- Rule cards → Concept graph -----


def test_rule_cards_to_concept_graph_integration(lesson_minimal_root: Path) -> None:
    """Build concept graph from rule_cards; assert nodes/relations and validate_concept_graph_integrity."""
    rc_path = lesson_minimal_root / "rule_cards.json"
    rule_cards = RuleCardCollection.model_validate_json(
        rc_path.read_text(encoding="utf-8")
    )

    graph, _ = concept_graph.build_concept_graph(rule_cards)

    assert graph.nodes, "Concept graph should have nodes"
    assert graph.relations is not None, "Concept graph should have relations"
    errors = validate_concept_graph_integrity(graph)
    assert not errors, f"Concept graph integrity: {errors}"


# ----- Rule cards → ML prep -----


def test_rule_cards_to_ml_prep_integration(lesson_minimal_root: Path) -> None:
    """Enrich rule cards for ML and build ML manifest; assert enriched rules and manifest."""
    rc_path = lesson_minimal_root / "rule_cards.json"
    ei_path = lesson_minimal_root / "evidence_index.json"

    rule_cards = RuleCardCollection.model_validate_json(
        rc_path.read_text(encoding="utf-8")
    )
    evidence_index = EvidenceIndex.model_validate_json(
        ei_path.read_text(encoding="utf-8")
    )

    enriched = ml_prep.enrich_rule_card_collection_for_ml(rule_cards, evidence_index)
    assert enriched.rules, "Enriched collection should have rules"
    manifest, debug_rows = ml_prep.build_ml_manifest(
        rule_cards.lesson_id, rule_cards, evidence_index
    )
    assert "lesson_id" in manifest
    assert "rules" in manifest
    assert "examples" in manifest
    assert isinstance(manifest["rules"], list)
    assert isinstance(manifest["examples"], list)


# ----- Rule cards → Exporters -----


def test_rule_cards_to_exporters_integration(
    lesson_minimal_root: Path,
    tmp_path: Path,
) -> None:
    """Export review and RAG markdown (deterministic); assert non-empty output."""
    rule_cards_path = lesson_minimal_root / "rule_cards.json"
    evidence_index_path = lesson_minimal_root / "evidence_index.json"
    knowledge_events_path = lesson_minimal_root / "knowledge_events.json"
    review_out = tmp_path / "review.md"
    rag_out = tmp_path / "rag.md"

    review_md, _ = exporters.export_review_markdown(
        lesson_id="lesson_minimal",
        lesson_title="Lesson minimal",
        rule_cards_path=rule_cards_path,
        evidence_index_path=evidence_index_path,
        knowledge_events_path=knowledge_events_path,
        output_path=review_out,
        use_llm=False,
    )
    assert (review_md or "").strip(), "Review markdown should be non-empty"
    assert review_out.exists()
    assert review_out.read_text(encoding="utf-8").strip()

    rag_md, _ = exporters.export_rag_markdown(
        lesson_id="lesson_minimal",
        lesson_title="Lesson minimal",
        rule_cards_path=rule_cards_path,
        evidence_index_path=evidence_index_path,
        knowledge_events_path=knowledge_events_path,
        output_path=rag_out,
        use_llm=False,
    )
    assert (rag_md or "").strip(), "RAG markdown should be non-empty"
    assert rag_out.exists()
    assert rag_out.read_text(encoding="utf-8").strip()


# ----- Full structured pipeline smoke -----


def test_full_structured_pipeline_smoke(
    lesson_minimal_root: Path,
    temp_video_root: Path,
) -> None:
    """Copy fixtures to temp layout, run pipeline from knowledge+evidence to exports; validate all artifacts."""
    lesson_name = "lesson_minimal"
    paths = PipelinePaths(video_root=temp_video_root)
    paths.ensure_output_dirs()

    # Copy fixture files into temp layout
    intermediate = paths.output_intermediate_dir
    shutil.copy(
        lesson_minimal_root / "chunks.json",
        intermediate / f"{lesson_name}.chunks.json",
    )
    shutil.copy(
        lesson_minimal_root / "knowledge_events.json",
        intermediate / f"{lesson_name}.knowledge_events.json",
    )
    shutil.copy(
        lesson_minimal_root / "evidence_index.json",
        intermediate / f"{lesson_name}.evidence_index.json",
    )
    shutil.copy(
        lesson_minimal_root / "rule_cards.json",
        intermediate / f"{lesson_name}.rule_cards.json",
    )
    dense_src = lesson_minimal_root / "dense_analysis.json"
    if dense_src.exists():
        shutil.copy(dense_src, temp_video_root / "dense_analysis.json")

    # Load from temp paths
    knowledge_collection = rule_reducer.load_knowledge_events(
        paths.knowledge_events_path(lesson_name)
    )
    evidence_index = rule_reducer.load_evidence_index(
        paths.evidence_index_path(lesson_name)
    )

    # Build rule cards, concept graph, ML prep
    rule_cards, _ = rule_reducer.build_rule_cards(
        knowledge_collection,
        evidence_index,
    )
    rule_cards.save_json(paths.rule_cards_path(lesson_name))

    graph, _ = concept_graph.build_concept_graph(rule_cards)
    concept_graph.save_concept_graph(graph, paths.concept_graph_path(lesson_name))

    enriched = ml_prep.enrich_rule_card_collection_for_ml(rule_cards, evidence_index)
    manifest, _ = ml_prep.build_ml_manifest(
        lesson_id=lesson_name,
        rule_cards=enriched,
        evidence_index=evidence_index,
    )
    paths.ml_manifest_path(lesson_name).parent.mkdir(parents=True, exist_ok=True)
    paths.ml_manifest_path(lesson_name).write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    # Export markdown
    exporters.export_review_markdown(
        lesson_id=lesson_name,
        lesson_title=knowledge_collection.lesson_id,
        rule_cards_path=paths.rule_cards_path(lesson_name),
        evidence_index_path=paths.evidence_index_path(lesson_name),
        knowledge_events_path=paths.knowledge_events_path(lesson_name),
        concept_graph_path=paths.concept_graph_path(lesson_name),
        output_path=paths.review_markdown_path(lesson_name),
        use_llm=False,
    )
    exporters.export_rag_markdown(
        lesson_id=lesson_name,
        lesson_title=knowledge_collection.lesson_id,
        rule_cards_path=paths.rule_cards_path(lesson_name),
        evidence_index_path=paths.evidence_index_path(lesson_name),
        knowledge_events_path=paths.knowledge_events_path(lesson_name),
        output_path=paths.rag_ready_export_path(lesson_name),
        use_llm=False,
    )

    # Assert expected paths exist
    assert paths.knowledge_events_path(lesson_name).exists()
    assert paths.evidence_index_path(lesson_name).exists()
    assert paths.rule_cards_path(lesson_name).exists()
    assert paths.concept_graph_path(lesson_name).exists()
    assert paths.ml_manifest_path(lesson_name).exists()
    assert paths.review_markdown_path(lesson_name).exists()
    assert paths.rag_ready_export_path(lesson_name).exists()

    # Validate JSONs with Pydantic
    KnowledgeEventCollection.model_validate_json(
        paths.knowledge_events_path(lesson_name).read_text(encoding="utf-8")
    )
    EvidenceIndex.model_validate_json(
        paths.evidence_index_path(lesson_name).read_text(encoding="utf-8")
    )
    RuleCardCollection.model_validate_json(
        paths.rule_cards_path(lesson_name).read_text(encoding="utf-8")
    )
    ConceptGraph.model_validate_json(
        paths.concept_graph_path(lesson_name).read_text(encoding="utf-8")
    )

    # Cross-artifact and blob leakage
    ke = KnowledgeEventCollection.model_validate_json(
        paths.knowledge_events_path(lesson_name).read_text(encoding="utf-8")
    )
    ei = EvidenceIndex.model_validate_json(
        paths.evidence_index_path(lesson_name).read_text(encoding="utf-8")
    )
    rc = RuleCardCollection.model_validate_json(
        paths.rule_cards_path(lesson_name).read_text(encoding="utf-8")
    )
    cross_errors = validate_cross_artifact_references(ke, ei, rc)
    assert not cross_errors, f"Cross-artifact references: {cross_errors}"

    assert not validate_no_visual_blob_leakage(
        ke.model_dump(), "knowledge_events"
    ), "No visual blob leakage in knowledge_events"
    assert not validate_no_visual_blob_leakage(
        ei.model_dump(), "evidence_index"
    ), "No visual blob leakage in evidence_index"
    assert not validate_no_visual_blob_leakage(
        rc.model_dump(), "rule_cards"
    ), "No visual blob leakage in rule_cards"
