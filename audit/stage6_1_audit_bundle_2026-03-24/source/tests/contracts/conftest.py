"""Shared helpers for contract v1 tests."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest


def materialize_lesson_corpus(tmp_path: Path, fixture_name: str) -> Path:
    """Lay out tests/fixtures/<fixture_name> under corpus/<id>/output_intermediate/*.suffix.json."""
    root = tmp_path / "corpus"
    lesson = root / fixture_name
    inter = lesson / "output_intermediate"
    inter.mkdir(parents=True)
    fix = Path(__file__).resolve().parent.parent / "fixtures" / fixture_name
    mapping = (
        ("knowledge_events", ".knowledge_events.json"),
        ("rule_cards", ".rule_cards.json"),
        ("evidence_index", ".evidence_index.json"),
        ("concept_graph", ".concept_graph.json"),
    )
    for stem, suffix in mapping:
        src = fix / f"{stem}.json"
        shutil.copy(src, inter / f"{fixture_name}{suffix}")
    return root


@pytest.fixture
def corpus_lesson_minimal(tmp_path: Path) -> Path:
    return materialize_lesson_corpus(tmp_path, "lesson_minimal")


@pytest.fixture
def corpus_lesson_minimal_paths(corpus_lesson_minimal: Path) -> dict[str, Path]:
    inter = corpus_lesson_minimal / "lesson_minimal" / "output_intermediate"
    return {
        "rule_cards": next(inter.glob("*.rule_cards.json")),
        "knowledge_events": next(inter.glob("*.knowledge_events.json")),
    }
