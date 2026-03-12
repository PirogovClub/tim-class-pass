"""Tests for Task 12 concept graph: build_concept_graph, load_rule_cards, save_concept_graph, ConceptGraph."""

from __future__ import annotations

from pathlib import Path

import pytest

from pipeline.schemas import ConceptGraph, RuleCard, RuleCardCollection
from pipeline.component2.concept_graph import (
    build_concept_graph,
    load_rule_cards,
    save_concept_graph,
)


def _minimal_rule(
    rule_id: str,
    concept: str = "level",
    subconcept: str | None = "level_rating",
    *,
    metadata: dict | None = None,
    comparisons: list[str] | None = None,
) -> RuleCard:
    return RuleCard(
        lesson_id="lesson1",
        rule_id=rule_id,
        concept=concept,
        subconcept=subconcept,
        rule_text="A level becomes stronger when price reacts to it multiple times.",
        conditions=[],
        invalidation=[],
        comparisons=comparisons or [],
        metadata=metadata or {},
        source_event_ids=[],
    )


def _relation_tuples(graph: ConceptGraph) -> set[tuple[str, str, str]]:
    return {(r.source_id, r.relation_type, r.target_id) for r in graph.relations}


def _node_ids(graph: ConceptGraph) -> set[str]:
    return {n.concept_id for n in graph.nodes}


# ----- 1. Concept and subconcept nodes -----


def test_create_concept_and_subconcept_nodes() -> None:
    """RuleCardCollection with one rule concept='level', subconcept='level_rating'; graph has nodes level and level_rating."""
    coll = RuleCardCollection(
        lesson_id="lesson1",
        rules=[_minimal_rule("r1", concept="level", subconcept="level_rating")],
    )
    graph, _ = build_concept_graph(coll)
    ids = _node_ids(graph)
    assert "level" in ids
    assert "level_rating" in ids


# ----- 2. Parent/child relation -----


def test_parent_child_relation() -> None:
    """Single rule with concept and subconcept; relations contain parent_of and child_of."""
    coll = RuleCardCollection(
        lesson_id="lesson1",
        rules=[_minimal_rule("r1", concept="level", subconcept="level_rating")],
    )
    graph, _ = build_concept_graph(coll)
    rels = _relation_tuples(graph)
    assert ("level", "parent_of", "level_rating") in rels
    assert ("level_rating", "child_of", "level") in rels


# ----- 3. Sibling related_to -----


def test_sibling_related_relation() -> None:
    """Two rules same concept 'level', subconcepts 'level_recognition' and 'level_rating'; related_to in both directions."""
    coll = RuleCardCollection(
        lesson_id="lesson1",
        rules=[
            _minimal_rule("r1", concept="level", subconcept="level_recognition"),
            _minimal_rule("r2", concept="level", subconcept="level_rating"),
        ],
    )
    graph, _ = build_concept_graph(coll)
    rels = _relation_tuples(graph)
    assert ("level_recognition", "related_to", "level_rating") in rels
    assert ("level_rating", "related_to", "level_recognition") in rels


# ----- 4. Precedes from source order -----


def test_precedes_relation_from_source_order() -> None:
    """Two rules same concept, different subconcepts, source_chunk_indexes [1] and [5]; first precedes second."""
    coll = RuleCardCollection(
        lesson_id="lesson1",
        rules=[
            _minimal_rule(
                "r1",
                concept="level",
                subconcept="level_recognition",
                metadata={"source_chunk_indexes": [1]},
            ),
            _minimal_rule(
                "r2",
                concept="level",
                subconcept="level_rating",
                metadata={"source_chunk_indexes": [5]},
            ),
        ],
    )
    graph, _ = build_concept_graph(coll)
    rels = _relation_tuples(graph)
    assert ("level_recognition", "precedes", "level_rating") in rels


# ----- 5. Contrasts_with -----


def test_contrasts_with_relation() -> None:
    """Two rules with subconcepts false_breakout and break_confirmation (name pair); contrasts_with in one direction."""
    coll = RuleCardCollection(
        lesson_id="lesson1",
        rules=[
            _minimal_rule("r1", concept="break", subconcept="break_confirmation"),
            _minimal_rule("r2", concept="break", subconcept="false_breakout"),
        ],
    )
    graph, _ = build_concept_graph(coll)
    rels = _relation_tuples(graph)
    assert ("false_breakout", "contrasts_with", "break_confirmation") in rels or (
        "break_confirmation",
        "contrasts_with",
        "false_breakout",
    ) in rels


# ----- 6. Relation dedupe -----


def test_relation_dedupe() -> None:
    """Two rules with same concept and subconcept; exactly one parent_of (and one child_of) relation."""
    coll = RuleCardCollection(
        lesson_id="lesson1",
        rules=[
            _minimal_rule("r1", concept="level", subconcept="level_rating"),
            _minimal_rule("r2", concept="level", subconcept="level_rating"),
        ],
    )
    graph, _ = build_concept_graph(coll)
    parent_of = [r for r in graph.relations if r.relation_type == "parent_of"]
    child_of = [r for r in graph.relations if r.relation_type == "child_of"]
    assert len(parent_of) == 1
    assert len(child_of) == 1


# ----- 7. Graph serialization -----


def test_graph_serialization() -> None:
    """build_concept_graph then ConceptGraph.model_validate_json(graph.model_dump_json()); lesson_id and node count match."""
    coll = RuleCardCollection(
        lesson_id="lesson1",
        rules=[_minimal_rule("r1", concept="level", subconcept="level_rating")],
    )
    graph, _ = build_concept_graph(coll)
    json_str = graph.model_dump_json()
    parsed = ConceptGraph.model_validate_json(json_str)
    assert parsed.lesson_id == graph.lesson_id
    assert len(parsed.nodes) == len(graph.nodes)


# ----- 8. Feature flag: empty rules -> empty graph (unit); full flag-off is integration -----


def test_empty_rules_produce_empty_graph_and_serializes() -> None:
    """With empty RuleCardCollection, build_concept_graph returns graph with lesson_id, no nodes, no relations; it serializes.
    Full 'enable_concept_graph=False' pipeline behavior is covered by integration tests."""
    coll = RuleCardCollection(lesson_id="x", rules=[])
    graph, _ = build_concept_graph(coll)
    assert graph.lesson_id == "x"
    assert graph.nodes == []
    assert graph.relations == []
    json_str = graph.model_dump_json()
    parsed = ConceptGraph.model_validate_json(json_str)
    assert parsed.lesson_id == "x"
    assert len(parsed.nodes) == 0
    assert len(parsed.relations) == 0


def test_save_concept_graph_writes_file(tmp_path: Path) -> None:
    """save_concept_graph writes JSON to path; empty graph round-trips."""
    coll = RuleCardCollection(lesson_id="x", rules=[])
    graph, _ = build_concept_graph(coll)
    out = tmp_path / "concept_graph.json"
    save_concept_graph(graph, out)
    assert out.exists()
    content = out.read_text(encoding="utf-8")
    parsed = ConceptGraph.model_validate_json(content)
    assert parsed.lesson_id == graph.lesson_id
    assert len(parsed.nodes) == len(graph.nodes)
