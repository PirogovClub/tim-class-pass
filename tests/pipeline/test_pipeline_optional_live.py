"""
Optional live-provider tests: run only with pytest -m live_provider.
Skip when required API keys (OPENAI_API_KEY or GEMINI_API_KEY) are not set.
Focus on provider wiring and schema parsing, not business logic.
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
import sys

import pytest

# Repository root (this file lives under tests/pipeline/)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

pytestmark = pytest.mark.live_provider


def _has_provider_credentials() -> bool:
    """True if at least one supported provider has an API key set."""
    openai_key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    gemini_key = (os.environ.get("GEMINI_API_KEY") or "").strip()
    return bool(openai_key or gemini_key)


def _skip_if_no_credentials() -> None:
    if not _has_provider_credentials():
        pytest.skip("No provider credentials (set OPENAI_API_KEY or GEMINI_API_KEY)")


@pytest.fixture
def lesson_minimal_chunks_path() -> Path:
    from tests.conftest import FIXTURES_ROOT
    return FIXTURES_ROOT / "lesson_minimal" / "chunks.json"


def test_live_provider_extraction_optional(lesson_minimal_chunks_path: Path) -> None:
    """
    If credentials not set, skip. Otherwise call real knowledge extraction for one chunk
    and validate that the response parses to ChunkExtractionResult.
    """
    _skip_if_no_credentials()

    from pipeline.component2.knowledge_builder import (
        AdaptedChunk,
        ChunkExtractionResult,
        adapt_chunk,
        load_chunks_json,
    )
    from pipeline.component2.llm_processor import process_chunk_knowledge_extract

    chunks_data = load_chunks_json(lesson_minimal_chunks_path)
    assert chunks_data, "Fixture chunks.json should not be empty"
    raw = chunks_data[0]
    chunk = adapt_chunk(raw, lesson_id="lesson_minimal", lesson_title="Minimal")
    assert isinstance(chunk, AdaptedChunk)

    result, usage = asyncio.run(
        process_chunk_knowledge_extract(chunk, provider=None, model=None)
    )
    assert isinstance(result, ChunkExtractionResult)
    # Schema has these buckets; we only care that parsing succeeded
    assert hasattr(result, "definitions") and isinstance(result.definitions, list)
    assert hasattr(result, "rule_statements") and isinstance(result.rule_statements, list)
    assert isinstance(usage, list)


def test_live_provider_markdown_render_optional() -> None:
    """
    If credentials not set, skip. Otherwise call real markdown render with minimal input;
    assert no exception and output is non-empty string.
    """
    _skip_if_no_credentials()

    from pipeline.schemas import EvidenceRef, RuleCard
    from pipeline.component2.llm_processor import process_rule_cards_markdown_render

    lesson_id = "test_live"
    rule_cards = [
        RuleCard(
            lesson_id=lesson_id,
            rule_id="r1",
            concept="Test",
            rule_text="Sample rule for live markdown test.",
        )
    ]
    evidence_refs = [
        EvidenceRef(lesson_id=lesson_id, evidence_id="e1"),
    ]

    result, usage = process_rule_cards_markdown_render(
        lesson_id=lesson_id,
        lesson_title="Live test",
        rule_cards=rule_cards,
        evidence_refs=evidence_refs,
        render_mode="review",
    )
    assert result is not None
    assert hasattr(result, "markdown")
    assert isinstance(result.markdown, str)
    assert result.markdown.strip(), "Markdown output should be non-empty"
    assert isinstance(usage, list)
