"""Tests for Task 7 exporters: load, context, deterministic render, save."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from pipeline.schemas import (
    EvidenceIndex,
    EvidenceRef,
    KnowledgeEventCollection,
    RuleCard,
    RuleCardCollection,
)
from pipeline.component2.exporters import (
    build_export_context,
    clean_markdown_text,
    dedupe_preserve_order,
    ensure_parent_dir,
    export_rag_markdown,
    export_review_markdown,
    format_bullet_block,
    format_compact_text_list,
    group_rule_cards_for_export,
    load_evidence_index,
    load_knowledge_events,
    load_rule_cards,
    render_rag_markdown,
    render_rag_markdown_deterministic,
    render_review_markdown,
    render_review_markdown_deterministic,
    save_export_debug,
    save_rag_markdown,
    save_review_markdown,
    sort_rule_cards,
    write_export_manifest,
    ExportContext,
)


# ----- Fixtures -----


def _minimal_rule(rule_id: str, concept: str = "Level", subconcept: str | None = None) -> RuleCard:
    return RuleCard(
        lesson_id="lesson2",
        rule_id=rule_id,
        concept=concept,
        subconcept=subconcept,
        rule_text="A level becomes stronger when price reacts to it multiple times.",
        conditions=["Reactions occur near the same price zone."],
        invalidation=["A single isolated touch is not enough."],
        exceptions=[],
        comparisons=[],
        algorithm_notes=["Count reaction frequency."],
        visual_summary="Annotated chart showing repeated reactions.",
        evidence_refs=["evid_lesson2_3_0"],
        confidence="high",
        confidence_score=0.88,
        source_event_ids=["ke_lesson2_4_rule_statement_0"],
    )


def _minimal_evidence(evidence_id: str) -> EvidenceRef:
    return EvidenceRef(
        lesson_id="lesson2",
        evidence_id=evidence_id,
        compact_visual_summary="Repeated reactions around one price zone.",
        linked_rule_ids=["rule-1"],
    )


@pytest.fixture
def rule_cards_path(tmp_path: Path) -> Path:
    coll = RuleCardCollection(
        lesson_id="lesson2",
        rules=[
            _minimal_rule("rule-1", "Level", "level_rating"),
            _minimal_rule("rule-2", "Level", "level_rating"),
            _minimal_rule("rule-3", "Other"),
        ],
    )
    p = tmp_path / "rule_cards.json"
    p.write_text(coll.model_dump_json(indent=2), encoding="utf-8")
    return p


@pytest.fixture
def evidence_index_path(tmp_path: Path) -> Path:
    idx = EvidenceIndex(
        lesson_id="lesson2",
        lesson_title="Lesson 2. Levels part 1",
        evidence_refs=[_minimal_evidence("evid_lesson2_3_0")],
    )
    p = tmp_path / "evidence_index.json"
    p.write_text(idx.model_dump_json(indent=2), encoding="utf-8")
    return p


# ----- Load and context -----


def test_load_rule_cards(rule_cards_path: Path) -> None:
    coll = load_rule_cards(rule_cards_path)
    assert coll.lesson_id == "lesson2"
    assert len(coll.rules) == 3
    assert coll.rules[0].rule_id == "rule-1"


def test_load_evidence_index(evidence_index_path: Path) -> None:
    idx = load_evidence_index(evidence_index_path)
    assert idx.lesson_id == "lesson2"
    assert len(idx.evidence_refs) == 1
    assert idx.evidence_refs[0].evidence_id == "evid_lesson2_3_0"


def test_load_knowledge_events_missing(tmp_path: Path) -> None:
    assert load_knowledge_events(tmp_path / "nonexistent.json") is None


def test_load_knowledge_events_present(tmp_path: Path) -> None:
    from pipeline.schemas import KnowledgeEvent, KnowledgeEventCollection

    coll = KnowledgeEventCollection(
        lesson_id="lesson2",
        events=[
            KnowledgeEvent(
                lesson_id="lesson2",
                event_id="ke-1",
                event_type="rule_statement",
                raw_text="A level.",
                normalized_text="A level.",
            ),
        ],
    )
    p = tmp_path / "knowledge_events.json"
    p.write_text(coll.model_dump_json(indent=2), encoding="utf-8")
    loaded = load_knowledge_events(p)
    assert loaded is not None
    assert len(loaded.events) == 1
    assert loaded.events[0].event_id == "ke-1"


def test_build_export_context(rule_cards_path: Path, evidence_index_path: Path) -> None:
    rule_cards = load_rule_cards(rule_cards_path)
    evidence_index = load_evidence_index(evidence_index_path)
    ctx = build_export_context(rule_cards, evidence_index, lesson_title="Custom Title")
    assert ctx.lesson_id == "lesson2"
    assert ctx.lesson_title == "Custom Title"
    assert len(ctx.rule_cards) == 3
    assert len(ctx.evidence_refs) == 1
    assert ctx.rules_by_id["rule-1"].concept == "Level"
    assert ctx.evidence_by_id["evid_lesson2_3_0"].evidence_id == "evid_lesson2_3_0"


# ----- Grouping and sorting -----


def test_group_rule_cards_for_export() -> None:
    rules = [
        _minimal_rule("r1", "Level"),
        _minimal_rule("r2", "Level"),
        _minimal_rule("r3", "Order"),
        _minimal_rule("r4", "Unclassified"),
    ]
    groups = group_rule_cards_for_export(rules)
    assert "Level" in groups
    assert "Order" in groups
    assert "Unclassified" in groups
    assert len(groups["Level"]) == 2
    assert len(groups["Unclassified"]) == 1


def test_sort_rule_cards_deterministic() -> None:
    rules = [
        _minimal_rule("r2", "A"),
        _minimal_rule("r1", "A"),
        _minimal_rule("r3", "B"),
    ]
    sorted_r = sort_rule_cards(rules)
    ids = [r.rule_id for r in sorted_r]
    assert ids == ["r1", "r2", "r3"]


# ----- Helpers -----


def test_format_bullet_block() -> None:
    out = format_bullet_block("Conditions", ["One", "Two"])
    assert "**Conditions**" in out
    assert "- One" in out
    assert "- Two" in out
    assert format_bullet_block("Empty", []) == ""


def test_dedupe_preserve_order() -> None:
    assert dedupe_preserve_order(["a", "b", "a", "c", "b"]) == ["a", "b", "c"]


def test_clean_markdown_text() -> None:
    assert clean_markdown_text("  foo   bar  ") == "foo bar"


# ----- Deterministic review render -----


def test_render_review_markdown_deterministic_includes_structure() -> None:
    rule_cards = RuleCardCollection(
        lesson_id="lesson2",
        rules=[_minimal_rule("rule-1", "Level", "level_rating")],
    )
    evidence_index = EvidenceIndex(
        lesson_id="lesson2",
        evidence_refs=[_minimal_evidence("evid_lesson2_3_0")],
    )
    ctx = build_export_context(rule_cards, evidence_index, lesson_title="Levels")
    md = render_review_markdown_deterministic(ctx)
    assert "# Lesson: Levels" in md
    assert "## Concept: Level" in md
    assert "### Rule:" in md
    assert "A level becomes stronger" in md
    assert "**Conditions**" in md
    assert "Reactions occur near" in md
    assert "**Invalidation**" in md
    assert "**Visual evidence**" in md
    assert "evid_lesson2_3_0" in md
    assert "ke_lesson2_4_rule_statement_0" in md


def test_review_empty_sections_omitted() -> None:
    rule = RuleCard(
        lesson_id="l",
        rule_id="r1",
        concept="X",
        rule_text="Only rule text.",
        conditions=[],
        invalidation=[],
        exceptions=[],
        comparisons=[],
        algorithm_notes=[],
    )
    rule_cards = RuleCardCollection(lesson_id="l", rules=[rule])
    evidence_index = EvidenceIndex(lesson_id="l", evidence_refs=[])
    ctx = build_export_context(rule_cards, evidence_index)
    md = render_review_markdown_deterministic(ctx)
    assert "Only rule text." in md
    assert "**Exceptions**" not in md
    assert "**Comparisons**" not in md
    assert "**Algorithm notes**" not in md


# ----- Deterministic RAG render -----


def test_render_rag_markdown_deterministic_compact() -> None:
    rule_cards = RuleCardCollection(
        lesson_id="lesson2",
        rules=[_minimal_rule("rule-1", "Level")],
    )
    evidence_index = EvidenceIndex(
        lesson_id="lesson2",
        evidence_refs=[_minimal_evidence("evid_1")],
    )
    ctx = build_export_context(rule_cards, evidence_index, lesson_title="Levels")
    md = render_rag_markdown_deterministic(ctx)
    assert "# Lesson: Levels" in md
    assert "## Level" in md
    assert "Rule: A level becomes stronger" in md
    assert "Conditions:" in md or "**Conditions**" in md
    assert "Source events:" not in md
    assert "Evidence refs:" not in md


# ----- Render without LLM -----


def test_render_review_markdown_deterministic_returns_empty_usage() -> None:
    rule_cards = RuleCardCollection(lesson_id="l", rules=[_minimal_rule("r1", "C")])
    evidence_index = EvidenceIndex(lesson_id="l", evidence_refs=[])
    ctx = build_export_context(rule_cards, evidence_index)
    md, usage = render_review_markdown(ctx, use_llm=False)
    assert md
    assert usage == []


def test_render_rag_markdown_deterministic_returns_empty_usage() -> None:
    rule_cards = RuleCardCollection(lesson_id="l", rules=[_minimal_rule("r1", "C")])
    evidence_index = EvidenceIndex(lesson_id="l", evidence_refs=[])
    ctx = build_export_context(rule_cards, evidence_index)
    md, usage = render_rag_markdown(ctx, use_llm=False)
    assert md
    assert usage == []


# ----- Save and ensure_parent_dir -----


def test_ensure_parent_dir_and_save_review_markdown(tmp_path: Path) -> None:
    out = tmp_path / "sub" / "review.md"
    assert not out.parent.exists()
    save_review_markdown("# Hello", out)
    assert out.parent.exists()
    assert out.read_text(encoding="utf-8") == "# Hello"


def test_save_rag_markdown(tmp_path: Path) -> None:
    out = tmp_path / "rag.md"
    save_rag_markdown("# RAG", out)
    assert out.read_text(encoding="utf-8") == "# RAG"


def test_save_export_debug(tmp_path: Path) -> None:
    out = tmp_path / "debug.json"
    save_export_debug([{"a": 1}, {"b": 2}], out)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data == [{"a": 1}, {"b": 2}]


def test_write_export_manifest(tmp_path: Path) -> None:
    out = tmp_path / "manifest.json"
    write_export_manifest(
        {
            "lesson_id": "lesson2",
            "review_markdown_path": "out/review.md",
            "rag_markdown_path": "out/rag.md",
            "used_llm_review_render": False,
            "used_llm_rag_render": False,
            "rule_count": 3,
            "evidence_count": 1,
        },
        out,
    )
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["lesson_id"] == "lesson2"
    assert data["rule_count"] == 3


# ----- Export orchestration -----


def test_export_review_markdown_writes_file(
    rule_cards_path: Path,
    evidence_index_path: Path,
    tmp_path: Path,
) -> None:
    out = tmp_path / "out" / "lesson2.review_markdown.md"
    md, usage = export_review_markdown(
        lesson_id="lesson2",
        lesson_title="Levels",
        rule_cards_path=rule_cards_path,
        evidence_index_path=evidence_index_path,
        output_path=out,
        use_llm=False,
    )
    assert out.exists()
    assert "# Lesson: Levels" in md
    assert usage == []


def test_export_rag_markdown_writes_file(
    rule_cards_path: Path,
    evidence_index_path: Path,
    tmp_path: Path,
) -> None:
    out = tmp_path / "out" / "lesson2.rag_ready.md"
    md, usage = export_rag_markdown(
        lesson_id="lesson2",
        lesson_title="Levels",
        rule_cards_path=rule_cards_path,
        evidence_index_path=evidence_index_path,
        output_path=out,
        use_llm=False,
    )
    assert out.exists()
    assert "Lesson" in md
    assert usage == []


def test_export_review_markdown_with_missing_knowledge_events(
    rule_cards_path: Path,
    evidence_index_path: Path,
    tmp_path: Path,
) -> None:
    out = tmp_path / "review.md"
    md, _ = export_review_markdown(
        lesson_id="lesson2",
        lesson_title="Levels",
        rule_cards_path=rule_cards_path,
        evidence_index_path=evidence_index_path,
        knowledge_events_path=tmp_path / "missing_ke.json",
        output_path=out,
        use_llm=False,
    )
    assert out.exists()
    assert md


def test_llm_render_receives_structured_inputs_only() -> None:
    """When use_llm=True, process_rule_cards_markdown_render is called with only structured inputs (no raw chunks)."""
    rule_cards = RuleCardCollection(lesson_id="L", rules=[_minimal_rule("r1", "C")])
    evidence_index = EvidenceIndex(lesson_id="L", evidence_refs=[_minimal_evidence("e1")])
    ctx = build_export_context(rule_cards, evidence_index, lesson_title="Title")
    with patch(
        "pipeline.component2.llm_processor.process_rule_cards_markdown_render",
        return_value=(MagicMock(markdown="# LLM output"), [{"tokens": 1}]),
    ) as mock_render:
        md, usage = render_review_markdown(ctx, use_llm=True)
    assert md == "# LLM output"
    assert usage == [{"tokens": 1}]
    mock_render.assert_called_once()
    call_kw = mock_render.call_args[1]
    assert call_kw["lesson_id"] == "L"
    assert call_kw["lesson_title"] == "Title"
    assert call_kw["render_mode"] == "review"
    assert len(call_kw["rule_cards"]) == 1
    assert len(call_kw["evidence_refs"]) == 1
    # Must not pass raw chunk/transcript keys
    for bad in ("chunks", "transcript", "raw_chunks", "transcript_lines"):
        assert bad not in call_kw


def test_deterministic_export_does_not_require_raw_chunks() -> None:
    """Deterministic render uses only ExportContext (rule_cards + evidence); no chunk/transcript input."""
    rule_cards = RuleCardCollection(lesson_id="lesson2", rules=[_minimal_rule("r1", "Level")])
    evidence_index = EvidenceIndex(
        lesson_id="lesson2",
        lesson_title="Levels",
        evidence_refs=[_minimal_evidence("ev1")],
    )
    ctx = build_export_context(rule_cards, evidence_index)
    md = render_review_markdown_deterministic(ctx)
    assert "# Lesson:" in md
    assert "Level" in md
    # ExportContext has no transcript/chunk fields; this test documents that we never pass them
    assert not hasattr(ctx, "chunks")
    assert not hasattr(ctx, "transcript_lines")
