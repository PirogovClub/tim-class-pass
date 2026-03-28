"""Tests for Task 12 concept graph: build_concept_graph, load_rule_cards, save_concept_graph, ConceptGraph."""

from __future__ import annotations

from pathlib import Path

import pytest

from pipeline.schemas import ConceptGraph, RuleCard, RuleCardCollection
from pipeline.component2.concept_graph import (
    build_concept_graph,
    load_rule_cards,
    save_concept_graph,
    CO_OCCURRENCE_THRESHOLD,
)


def _minimal_rule(
    rule_id: str,
    concept: str = "level",
    subconcept: str | None = "level_rating",
    *,
    conditions: list[str] | None = None,
    invalidation: list[str] | None = None,
    exceptions: list[str] | None = None,
    metadata: dict | None = None,
    comparisons: list[str] | None = None,
) -> RuleCard:
    return RuleCard(
        lesson_id="lesson1",
        rule_id=rule_id,
        concept=concept,
        subconcept=subconcept,
        rule_text="A level becomes stronger when price reacts to it multiple times.",
        conditions=conditions or [],
        invalidation=invalidation or [],
        exceptions=exceptions or [],
        comparisons=comparisons or [],
        metadata=metadata or {},
        source_event_ids=[],
    )


def _relation_tuples(graph: ConceptGraph) -> set[tuple[str, str, str]]:
    return {(r.source_id, r.relation_type, r.target_id) for r in graph.relations}


def _node_ids(graph: ConceptGraph) -> set[str]:
    return {n.concept_id for n in graph.nodes}


def _node_types(graph: ConceptGraph) -> dict[str, str]:
    return {n.concept_id: n.type for n in graph.nodes}


def _relation_weight(graph: ConceptGraph, source: str, rtype: str, target: str) -> int | None:
    for r in graph.relations:
        if r.source_id == source and r.relation_type == rtype and r.target_id == target:
            return r.weight
    return None


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
    """Single rule with concept and subconcept; has_subconcept relation (Task 17: no mirrored pair)."""
    coll = RuleCardCollection(
        lesson_id="lesson1",
        rules=[_minimal_rule("r1", concept="level", subconcept="level_rating")],
    )
    graph, _ = build_concept_graph(coll)
    rels = _relation_tuples(graph)
    assert ("level", "has_subconcept", "level_rating") in rels
    assert ("level_rating", "child_of", "level") not in rels


# ----- 3. Sibling related_to -----


def test_sibling_related_relation() -> None:
    """Two rules same concept 'level', subconcepts 'level_recognition' and 'level_rating'.

    Task 17: related_to with empty source_rule_ids is filtered out.
    """
    coll = RuleCardCollection(
        lesson_id="lesson1",
        rules=[
            _minimal_rule("r1", concept="level", subconcept="level_recognition"),
            _minimal_rule("r2", concept="level", subconcept="level_rating"),
        ],
    )
    graph, _ = build_concept_graph(coll)
    rels = _relation_tuples(graph)
    assert ("level_recognition", "related_to", "level_rating") not in rels
    assert ("level_rating", "related_to", "level_recognition") not in rels


# ----- 4. Precedes from source order -----


def test_precedes_relation_filtered_by_provenance() -> None:
    """Task 17: precedes relations are filtered out (no source_rule_ids, not in allowed types)."""
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
    assert ("level_recognition", "precedes", "level_rating") not in rels


# ----- 5. Contrasts_with -----


def test_contrasts_with_filtered_by_provenance() -> None:
    """Task 17: contrasts_with relations are filtered out (empty source_rule_ids, not in allowed types)."""
    coll = RuleCardCollection(
        lesson_id="lesson1",
        rules=[
            _minimal_rule("r1", concept="break", subconcept="break_confirmation"),
            _minimal_rule("r2", concept="break", subconcept="false_breakout"),
        ],
    )
    graph, _ = build_concept_graph(coll)
    rels = _relation_tuples(graph)
    assert ("false_breakout", "contrasts_with", "break_confirmation") not in rels
    assert ("break_confirmation", "contrasts_with", "false_breakout") not in rels


# ----- 6. Relation dedupe -----


def test_relation_dedupe() -> None:
    """Two rules with same concept and subconcept; exactly one has_subconcept relation (Task 17)."""
    coll = RuleCardCollection(
        lesson_id="lesson1",
        rules=[
            _minimal_rule("r1", concept="level", subconcept="level_rating"),
            _minimal_rule("r2", concept="level", subconcept="level_rating"),
        ],
    )
    graph, _ = build_concept_graph(coll)
    has_sub = [r for r in graph.relations if r.relation_type == "has_subconcept"]
    assert len(has_sub) == 1


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


# ----- 9. Stats block -----


def test_stats_match_node_and_relation_counts() -> None:
    """Graph stats.node_count == len(nodes) and stats.edge_count == len(relations)."""
    coll = RuleCardCollection(
        lesson_id="lesson1",
        rules=[
            _minimal_rule("r1", concept="level", subconcept="level_rating"),
            _minimal_rule("r2", concept="level", subconcept="level_recognition"),
        ],
    )
    graph, _ = build_concept_graph(coll)
    assert graph.stats.node_count == len(graph.nodes)
    assert graph.stats.edge_count == len(graph.relations)
    assert graph.stats.node_count > 0
    assert graph.stats.edge_count > 0


def test_graph_version_present() -> None:
    """Graph has graph_version field."""
    coll = RuleCardCollection(lesson_id="x", rules=[])
    graph, _ = build_concept_graph(coll)
    assert graph.graph_version == "1.0"


# ----- 10. Condition/invalidation/exception nodes -----


def test_condition_nodes_created() -> None:
    """Short condition text creates a 'condition' node."""
    coll = RuleCardCollection(
        lesson_id="lesson1",
        rules=[
            _minimal_rule(
                "r1",
                concept="level",
                subconcept="entry",
                conditions=["entry only after confirmation candle closes above level"],
            ),
        ],
    )
    graph, _ = build_concept_graph(coll)
    types = _node_types(graph)
    condition_nodes = [nid for nid, ntype in types.items() if ntype == "condition"]
    assert len(condition_nodes) == 1
    assert condition_nodes[0].startswith("condition:")


def test_invalidation_nodes_created() -> None:
    """Short invalidation text creates an 'invalidation' node."""
    coll = RuleCardCollection(
        lesson_id="lesson1",
        rules=[
            _minimal_rule(
                "r1",
                concept="level",
                subconcept="breakout",
                invalidation=["invalid if breakout has no volume support"],
            ),
        ],
    )
    graph, _ = build_concept_graph(coll)
    types = _node_types(graph)
    inv_nodes = [nid for nid, ntype in types.items() if ntype == "invalidation"]
    assert len(inv_nodes) == 1


def test_exception_nodes_created() -> None:
    """Short exception text creates an 'exception' node."""
    coll = RuleCardCollection(
        lesson_id="lesson1",
        rules=[
            _minimal_rule(
                "r1",
                concept="level",
                subconcept="breakout",
                exceptions=["exception when gap is filled"],
            ),
        ],
    )
    graph, _ = build_concept_graph(coll)
    types = _node_types(graph)
    exc_nodes = [nid for nid, ntype in types.items() if ntype == "exception"]
    assert len(exc_nodes) == 1


def test_long_condition_not_promoted_to_node() -> None:
    """Conditions longer than MAX_SECONDARY_NODE_LEN are not created as nodes."""
    long_text = "x" * 200
    coll = RuleCardCollection(
        lesson_id="lesson1",
        rules=[
            _minimal_rule("r1", concept="level", subconcept="entry", conditions=[long_text]),
        ],
    )
    graph, _ = build_concept_graph(coll)
    types = _node_types(graph)
    condition_nodes = [nid for nid, ntype in types.items() if ntype == "condition"]
    assert len(condition_nodes) == 0


# ----- 11. has_condition / has_invalidation / has_exception edges -----


def test_has_condition_edge() -> None:
    """Condition node linked to owning subconcept via has_condition."""
    coll = RuleCardCollection(
        lesson_id="lesson1",
        rules=[
            _minimal_rule(
                "r1",
                concept="level",
                subconcept="entry",
                conditions=["entry only after confirmation"],
            ),
        ],
    )
    graph, _ = build_concept_graph(coll)
    rels = _relation_tuples(graph)
    has_cond = [r for r in rels if r[1] == "has_condition"]
    assert len(has_cond) == 1
    assert has_cond[0][0] == "entry"


def test_has_invalidation_edge() -> None:
    """Invalidation node linked via has_invalidation."""
    coll = RuleCardCollection(
        lesson_id="lesson1",
        rules=[
            _minimal_rule(
                "r1",
                concept="level",
                subconcept="breakout",
                invalidation=["invalid if no volume"],
            ),
        ],
    )
    graph, _ = build_concept_graph(coll)
    rels = _relation_tuples(graph)
    has_inv = [r for r in rels if r[1] == "has_invalidation"]
    assert len(has_inv) == 1
    assert has_inv[0][0] == "breakout"


def test_has_exception_edge() -> None:
    """Exception node linked via has_exception."""
    coll = RuleCardCollection(
        lesson_id="lesson1",
        rules=[
            _minimal_rule(
                "r1",
                concept="level",
                subconcept="breakout",
                exceptions=["except during gap fill"],
            ),
        ],
    )
    graph, _ = build_concept_graph(coll)
    rels = _relation_tuples(graph)
    has_exc = [r for r in rels if r[1] == "has_exception"]
    assert len(has_exc) == 1
    assert has_exc[0][0] == "breakout"


# ----- 12. co_occurs_with edges -----


def test_co_occurs_with_above_threshold() -> None:
    """Concept+subconcept pair appearing in >= CO_OCCURRENCE_THRESHOLD rules creates co_occurs_with edge."""
    rules = [
        _minimal_rule(f"r{i}", concept="level", subconcept="rating")
        for i in range(CO_OCCURRENCE_THRESHOLD)
    ]
    coll = RuleCardCollection(lesson_id="lesson1", rules=rules)
    graph, _ = build_concept_graph(coll)
    rels = _relation_tuples(graph)
    assert ("level", "co_occurs_with", "rating") in rels or (
        "rating", "co_occurs_with", "level"
    ) in rels


def test_co_occurs_with_below_threshold_not_created() -> None:
    """Pair appearing in only 1 rule does not produce co_occurs_with (threshold is 2)."""
    coll = RuleCardCollection(
        lesson_id="lesson1",
        rules=[_minimal_rule("r1", concept="level", subconcept="rating")],
    )
    graph, _ = build_concept_graph(coll)
    rels = _relation_tuples(graph)
    co = [r for r in rels if r[1] == "co_occurs_with"]
    assert len(co) == 0


# ----- 13. Integer weights -----


def test_edge_weights_are_integers() -> None:
    """All relation weights must be ints >= 1."""
    coll = RuleCardCollection(
        lesson_id="lesson1",
        rules=[
            _minimal_rule("r1", concept="level", subconcept="rating"),
            _minimal_rule("r2", concept="level", subconcept="rating"),
        ],
    )
    graph, _ = build_concept_graph(coll)
    for rel in graph.relations:
        assert isinstance(rel.weight, int)
        assert rel.weight >= 1


def test_dedupe_merges_weights() -> None:
    """Two rules with same concept/subconcept; has_subconcept weight == 2 after dedupe (Task 17)."""
    coll = RuleCardCollection(
        lesson_id="lesson1",
        rules=[
            _minimal_rule("r1", concept="level", subconcept="rating"),
            _minimal_rule("r2", concept="level", subconcept="rating"),
        ],
    )
    graph, _ = build_concept_graph(coll)
    w = _relation_weight(graph, "level", "has_subconcept", "rating")
    assert w == 2


# ----- 14. source_rule_ids on nodes and relations -----


def test_nodes_have_source_rule_ids() -> None:
    """Concept and subconcept nodes track which rules reference them."""
    coll = RuleCardCollection(
        lesson_id="lesson1",
        rules=[
            _minimal_rule("r1", concept="level", subconcept="rating"),
            _minimal_rule("r2", concept="level", subconcept="recognition"),
        ],
    )
    graph, _ = build_concept_graph(coll)
    level_node = next(n for n in graph.nodes if n.concept_id == "level")
    assert "r1" in level_node.source_rule_ids
    assert "r2" in level_node.source_rule_ids


def test_relations_have_source_rule_ids() -> None:
    """has_subconcept relation tracks contributing rule_ids (Task 17)."""
    coll = RuleCardCollection(
        lesson_id="lesson1",
        rules=[
            _minimal_rule("r1", concept="level", subconcept="rating"),
            _minimal_rule("r2", concept="level", subconcept="rating"),
        ],
    )
    graph, _ = build_concept_graph(coll)
    has_sub = [r for r in graph.relations if r.relation_type == "has_subconcept"]
    assert len(has_sub) == 1
    assert "r1" in has_sub[0].source_rule_ids
    assert "r2" in has_sub[0].source_rule_ids


# ----- 15. No markdown dependency (structural test) -----


def test_graph_built_from_structured_json_only() -> None:
    """build_concept_graph takes RuleCardCollection (structured JSON), not markdown text."""
    coll = RuleCardCollection(
        lesson_id="lesson1",
        rules=[_minimal_rule("r1", concept="level", subconcept="rating")],
    )
    graph, debug = build_concept_graph(coll)
    assert isinstance(graph, ConceptGraph)
    assert isinstance(debug, list)


# ----- Task 17: Provenance-backed relations -----


def test_all_relations_have_provenance() -> None:
    """Task 17: every emitted relation must have non-empty source_rule_ids."""
    coll = RuleCardCollection(
        lesson_id="lesson1",
        rules=[
            _minimal_rule("r1", concept="level", subconcept="level_recognition"),
            _minimal_rule("r2", concept="level", subconcept="level_rating"),
        ],
    )
    graph, _ = build_concept_graph(coll)
    for rel in graph.relations:
        assert rel.source_rule_ids, f"Relation {rel.relation_id} has empty source_rule_ids"


def test_no_mirrored_structural_duplicates() -> None:
    """Task 17: if A has_subconcept B exists, reverse child_of/parent_of is absent."""
    coll = RuleCardCollection(
        lesson_id="lesson1",
        rules=[_minimal_rule("r1", concept="level", subconcept="rating")],
    )
    graph, _ = build_concept_graph(coll)
    rels = _relation_tuples(graph)
    assert ("level", "has_subconcept", "rating") in rels
    assert ("rating", "child_of", "level") not in rels
    assert ("rating", "parent_of", "level") not in rels


def test_only_allowed_relation_types() -> None:
    """Task 17: all relation types must be in the allowed set."""
    allowed = {"has_subconcept", "has_condition", "has_invalidation", "has_exception", "co_occurs_with"}
    coll = RuleCardCollection(
        lesson_id="lesson1",
        rules=[
            _minimal_rule("r1", concept="level", subconcept="recognition",
                          metadata={"source_chunk_indexes": [1]}),
            _minimal_rule("r2", concept="level", subconcept="rating",
                          metadata={"source_chunk_indexes": [5]}),
        ],
    )
    graph, _ = build_concept_graph(coll)
    for rel in graph.relations:
        assert rel.relation_type in allowed, f"Unexpected relation type: {rel.relation_type}"
