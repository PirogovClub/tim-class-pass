"""Task 14 export quality tests: review/RAG markdown structure, distinctness, no transcript replay, visual spam.

Uses fixtures from tests/fixtures/lesson_minimal (rule_cards, evidence_index). Calls
export_review_markdown and export_rag_markdown (deterministic, no LLM), then
validate_export_quality and validate_markdown_visual_compaction. Does NOT replace
test_exporters.py, which tests the exporter module internals.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pipeline import validation
from pipeline.component2.exporters import export_review_markdown, export_rag_markdown
from pipeline.component2.visual_compaction import validate_markdown_visual_compaction


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def lesson_minimal_rule_cards_path(lesson_minimal_root: Path) -> Path:
    return lesson_minimal_root / "rule_cards.json"


@pytest.fixture
def lesson_minimal_evidence_index_path(lesson_minimal_root: Path) -> Path:
    return lesson_minimal_root / "evidence_index.json"


@pytest.fixture
def lesson_minimal_knowledge_events_path(lesson_minimal_root: Path) -> Path:
    return lesson_minimal_root / "knowledge_events.json"


@pytest.fixture
def exported_review_markdown(
    lesson_minimal_root: Path,
    lesson_minimal_rule_cards_path: Path,
    lesson_minimal_evidence_index_path: Path,
    lesson_minimal_knowledge_events_path: Path,
    tmp_path: Path,
) -> str:
    """Produce review markdown from lesson_minimal fixtures (deterministic, no LLM)."""
    output_path = tmp_path / "review.md"
    md, _ = export_review_markdown(
        lesson_id="lesson_minimal",
        lesson_title="Lesson minimal",
        rule_cards_path=lesson_minimal_rule_cards_path,
        evidence_index_path=lesson_minimal_evidence_index_path,
        knowledge_events_path=lesson_minimal_knowledge_events_path,
        output_path=output_path,
        use_llm=False,
    )
    return md


@pytest.fixture
def exported_rag_markdown(
    lesson_minimal_root: Path,
    lesson_minimal_rule_cards_path: Path,
    lesson_minimal_evidence_index_path: Path,
    lesson_minimal_knowledge_events_path: Path,
    tmp_path: Path,
) -> str:
    """Produce RAG markdown from lesson_minimal fixtures (deterministic, no LLM)."""
    output_path = tmp_path / "rag.md"
    md, _ = export_rag_markdown(
        lesson_id="lesson_minimal",
        lesson_title="Lesson minimal",
        rule_cards_path=lesson_minimal_rule_cards_path,
        evidence_index_path=lesson_minimal_evidence_index_path,
        knowledge_events_path=lesson_minimal_knowledge_events_path,
        output_path=output_path,
        use_llm=False,
    )
    return md


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_review_markdown_structure(exported_review_markdown: str) -> None:
    """Review markdown has concept/rule structure (headers, rule, level) and optional provenance."""
    md = exported_review_markdown
    assert md, "review markdown must not be empty"
    # Concept/rule structure: headers or "rule" or "level" (concept from fixture)
    has_structure = (
        "## " in md or "### " in md or "Concept" in md or "rule" in md.lower() or "level" in md.lower()
    )
    assert has_structure, "review markdown should contain concept/rule structure (headers, rule, or level)"
    # Optional provenance: source_event_ids or similar may appear in compact provenance
    # No strict requirement; structure check above is sufficient


def test_rag_markdown_compact(
    exported_review_markdown: str,
    exported_rag_markdown: str,
) -> None:
    """RAG markdown is more compact than review, or validate_export_quality passes."""
    review_md = exported_review_markdown
    rag_md = exported_rag_markdown
    errors = validation.validate_export_quality(review_md, rag_md)
    assert not errors, f"validate_export_quality should pass: {errors}"
    review_lines = len([l for l in review_md.splitlines() if l.strip()])
    rag_lines = len([l for l in rag_md.splitlines() if l.strip()])
    assert rag_lines <= review_lines, "RAG should have fewer or equal non-empty lines than review"


def test_export_outputs_distinct(
    exported_review_markdown: str,
    exported_rag_markdown: str,
) -> None:
    """validate_export_quality(review_md, rag_md) returns no errors."""
    errors = validation.validate_export_quality(
        exported_review_markdown,
        exported_rag_markdown,
    )
    assert errors == [], f"Expected no export quality errors, got: {errors}"


def test_no_transcript_replay_in_markdown(
    exported_review_markdown: str,
    exported_rag_markdown: str,
) -> None:
    """Final markdown does not contain raw chunk transcript markers or long verbatim replay."""
    # Structural markers that would indicate raw transcript/chunk leakage
    replay_markers = [
        "chunk_index",
        "transcript_lines",
        "start_time_seconds",
        "end_time_seconds",
    ]
    for md in (exported_review_markdown, exported_rag_markdown):
        for marker in replay_markers:
            assert marker not in md, f"Markdown should not contain transcript/chunk marker: {marker!r}"
    # Content should be rule-centric (rule/concept framing), not raw narration
    for md in (exported_review_markdown, exported_rag_markdown):
        assert "Rule" in md or "rule" in md or "Concept" in md or "## " in md, (
            "Markdown should be rule-centric (Rule/Concept/headers)"
        )


def test_markdown_passes_visual_spam_validator(
    exported_review_markdown: str,
    exported_rag_markdown: str,
) -> None:
    """validate_markdown_visual_compaction on review and RAG returns empty or acceptably small flagged list."""
    review_flagged = validate_markdown_visual_compaction(exported_review_markdown)
    rag_flagged = validate_markdown_visual_compaction(exported_rag_markdown)
    assert len(review_flagged) <= 2, (
        f"Review markdown should have at most 2 visual spam lines, got {len(review_flagged)}: {review_flagged}"
    )
    assert len(rag_flagged) <= 2, (
        f"RAG markdown should have at most 2 visual spam lines, got {len(rag_flagged)}: {rag_flagged}"
    )
