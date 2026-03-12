"""Regression tests: fixture counts vs golden expectations and exporter output structure."""

from __future__ import annotations

from pathlib import Path

import pytest

from conftest import GOLDEN_ROOT, load_json
from pipeline.component2.exporters import export_rag_markdown, export_review_markdown
from pipeline.schemas import (
    EvidenceIndex,
    KnowledgeEventCollection,
    RuleCardCollection,
)


def _load_fixture_artifacts(root: Path):
    """Load knowledge_events, evidence_index, rule_cards from a fixture root with Pydantic."""
    events_path = root / "knowledge_events.json"
    events = (
        KnowledgeEventCollection.model_validate_json(events_path.read_text(encoding="utf-8"))
        if events_path.exists()
        else None
    )
    evidence_index = EvidenceIndex.model_validate_json(
        (root / "evidence_index.json").read_text(encoding="utf-8")
    )
    rule_cards = RuleCardCollection.model_validate_json(
        (root / "rule_cards.json").read_text(encoding="utf-8")
    )
    return events, evidence_index, rule_cards


def test_lesson_minimal_regression_counts(
    lesson_minimal_root: Path,
) -> None:
    """Assert lesson_minimal fixture meets golden min counts and concept/rule-id constraints."""
    events_coll, evidence_index, rule_cards = _load_fixture_artifacts(lesson_minimal_root)
    golden = load_json(GOLDEN_ROOT / "lesson_minimal_expected.json")

    events = events_coll.events if events_coll else []
    evidence_refs = evidence_index.evidence_refs
    rules = rule_cards.rules

    assert len(events) >= golden["min_knowledge_events"]
    assert len(evidence_refs) >= golden["min_evidence_refs"]
    assert len(rules) >= golden["min_rule_cards"]

    required_concepts = golden["required_concepts"]
    concepts_in_rules = {r.concept for r in rules if r.concept}
    for concept in required_concepts:
        assert concept in concepts_in_rules, f"required concept {concept!r} not in any rule"

    required_rule_prefixes = golden["required_rule_prefixes"]
    for rule in rules:
        assert any(
            rule.rule_id.startswith(prefix) for prefix in required_rule_prefixes
        ), f"rule_id {rule.rule_id!r} does not start with any of {required_rule_prefixes}"


def test_lesson_multi_concept_regression_counts(
    lesson_multi_concept_root: Path,
) -> None:
    """Assert lesson_multi_concept fixture meets golden min counts and concept/rule-id constraints."""
    events_coll, evidence_index, rule_cards = _load_fixture_artifacts(lesson_multi_concept_root)
    golden = load_json(GOLDEN_ROOT / "lesson_multi_concept_expected.json")

    events = events_coll.events if events_coll else []
    evidence_refs = evidence_index.evidence_refs
    rules = rule_cards.rules

    assert len(events) >= golden["min_knowledge_events"]
    assert len(evidence_refs) >= golden["min_evidence_refs"]
    assert len(rules) >= golden["min_rule_cards"]

    required_concepts = golden["required_concepts"]
    concepts_in_rules = {r.concept for r in rules if r.concept}
    for concept in required_concepts:
        assert concept in concepts_in_rules, f"required concept {concept!r} not in any rule"

    required_rule_prefixes = golden["required_rule_prefixes"]
    for rule in rules:
        assert any(
            rule.rule_id.startswith(prefix) for prefix in required_rule_prefixes
        ), f"rule_id {rule.rule_id!r} does not start with any of {required_rule_prefixes}"


def test_exporter_output_structure_regression(
    lesson_minimal_root: Path,
    tmp_path: Path,
) -> None:
    """Run exporters from lesson_minimal to tmp_path; assert RAG line cap and structural elements."""
    golden = load_json(GOLDEN_ROOT / "lesson_minimal_expected.json")
    max_rag_lines = golden["max_rag_markdown_lines"]

    rule_cards_path = lesson_minimal_root / "rule_cards.json"
    evidence_index_path = lesson_minimal_root / "evidence_index.json"
    knowledge_events_path = lesson_minimal_root / "knowledge_events.json"
    review_path = tmp_path / "review.md"
    rag_path = tmp_path / "rag.md"

    export_review_markdown(
        lesson_id="lesson_minimal",
        lesson_title="Lesson minimal",
        rule_cards_path=rule_cards_path,
        evidence_index_path=evidence_index_path,
        knowledge_events_path=knowledge_events_path,
        output_path=review_path,
        use_llm=False,
    )
    export_rag_markdown(
        lesson_id="lesson_minimal",
        lesson_title="Lesson minimal",
        rule_cards_path=rule_cards_path,
        evidence_index_path=evidence_index_path,
        knowledge_events_path=knowledge_events_path,
        output_path=rag_path,
        use_llm=False,
    )

    review_md = review_path.read_text(encoding="utf-8")
    rag_md = rag_path.read_text(encoding="utf-8")

    rag_non_empty_lines = [line for line in rag_md.splitlines() if line.strip()]
    assert len(rag_non_empty_lines) <= max_rag_lines, (
        f"RAG markdown has {len(rag_non_empty_lines)} non-empty lines, "
        f"golden max is {max_rag_lines}"
    )

    has_review_structure = (
        "## " in review_md or "### " in review_md or "rule" in review_md.lower() or "level" in review_md.lower()
    )
    assert has_review_structure, (
        "Review markdown should contain structural elements (headers ##/###, or 'rule'/'level')"
    )

    has_rag_structure = (
        "## " in rag_md or "### " in rag_md or "rule" in rag_md.lower() or "level" in rag_md.lower()
    )
    assert has_rag_structure, (
        "RAG markdown should contain structural elements (headers ##/###, or 'rule'/'level')"
    )
