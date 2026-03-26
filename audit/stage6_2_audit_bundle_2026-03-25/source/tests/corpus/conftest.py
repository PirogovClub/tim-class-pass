from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from pipeline.contracts.lesson_registry import build_registry_v1, save_registry_v1


def _materialize_lesson(root: Path, fixture_name: str) -> None:
    lesson = root / fixture_name / "output_intermediate"
    lesson.mkdir(parents=True, exist_ok=True)
    fixture = Path(__file__).resolve().parents[1] / "fixtures" / fixture_name
    for stem, suffix in (
        ("knowledge_events", ".knowledge_events.json"),
        ("rule_cards", ".rule_cards.json"),
        ("evidence_index", ".evidence_index.json"),
        ("concept_graph", ".concept_graph.json"),
    ):
        shutil.copy(fixture / f"{stem}.json", lesson / f"{fixture_name}{suffix}")


@pytest.fixture
def corpus_input_root(tmp_path: Path) -> Path:
    root = tmp_path / "corpus_input"
    _materialize_lesson(root, "lesson_minimal")
    _materialize_lesson(root, "lesson_multi_concept")
    return root


@pytest.fixture
def lesson_registry_path(corpus_input_root: Path, tmp_path: Path) -> Path:
    doc = build_registry_v1(corpus_input_root, validate=True, strict_validation=True)
    path = tmp_path / "lesson_registry.json"
    save_registry_v1(doc, path)
    return path


@pytest.fixture
def corpus_output_root(tmp_path: Path) -> Path:
    return tmp_path / "corpus_output"
