from __future__ import annotations

import json
from pathlib import Path

from pipeline.contracts.lesson_registry import build_registry_v1, load_registry_v1, save_registry_v1
from pipeline.contracts.registry_models import LessonRegistryFileV1


def test_build_registry_creates_document(corpus_lesson_minimal: Path) -> None:
    doc = build_registry_v1(corpus_lesson_minimal, validate=True, strict_validation=True)
    assert isinstance(doc, LessonRegistryFileV1)
    assert doc.lessons
    entry = doc.lessons[0]
    assert entry.lesson_id == "lesson_minimal"
    assert entry.artifacts.knowledge_events_path
    assert entry.artifacts.rule_cards_path
    assert entry.artifacts.evidence_index_path
    assert entry.artifacts.concept_graph_path
    assert entry.validation_status == "passed"
    assert entry.record_counts["knowledge_events"] >= 1


def test_registry_roundtrip(tmp_path: Path, corpus_lesson_minimal: Path) -> None:
    doc = build_registry_v1(corpus_lesson_minimal, validate=True, strict_validation=True)
    path = tmp_path / "lesson_registry.json"
    save_registry_v1(doc, path)
    loaded = load_registry_v1(path)
    assert loaded.lesson_contract_version == doc.lesson_contract_version
    assert len(loaded.lessons) == len(doc.lessons)


def test_registry_paths_resolve(corpus_lesson_minimal: Path) -> None:
    doc = build_registry_v1(corpus_lesson_minimal, validate=True, strict_validation=True)
    root = corpus_lesson_minimal
    e = doc.lessons[0]
    assert (root / e.artifacts.knowledge_events_path).is_file()
    assert (root / e.artifacts.concept_graph_path).is_file()


def test_registry_counts_match_disk(tmp_path: Path, corpus_lesson_minimal: Path) -> None:
    doc = build_registry_v1(corpus_lesson_minimal, validate=True, strict_validation=True)
    path = tmp_path / "lesson_registry.json"
    save_registry_v1(doc, path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    ke = json.loads((corpus_lesson_minimal / raw["lessons"][0]["artifacts"]["knowledge_events_path"]).read_text())
    assert raw["lessons"][0]["record_counts"]["knowledge_events"] == len(ke["events"])
