from __future__ import annotations

import json
from pathlib import Path

from pipeline.contracts.corpus_validator import (
    validate_corpus,
    validate_intermediate_dir,
    validate_lesson_record_v1,
    validate_registry_v1,
)
from pipeline.contracts.lesson_registry import build_registry_v1
from pipeline.corpus.lesson_registry import discover_lessons

from tests.contracts.conftest import materialize_lesson_corpus


def test_validator_passes_good_lesson(corpus_lesson_minimal: Path) -> None:
    lessons = discover_lessons(corpus_lesson_minimal)
    assert len(lessons) == 1
    out = validate_lesson_record_v1(lessons[0], strict=True)
    assert out.passed


def test_validate_corpus_report(corpus_lesson_minimal: Path) -> None:
    lessons = discover_lessons(corpus_lesson_minimal)
    rep = validate_corpus(lessons, strict=True)
    assert rep["overall_status"] == "passed"
    assert rep["passed_count"] == 1


def test_fails_when_rule_cards_missing(tmp_path: Path) -> None:
    root = materialize_lesson_corpus(tmp_path, "lesson_minimal")
    inter = root / "lesson_minimal" / "output_intermediate"
    for p in inter.glob("*.rule_cards.json"):
        p.unlink()
    lessons = discover_lessons(root)
    out = validate_lesson_record_v1(lessons[0], strict=True)
    assert not out.passed
    assert any("rule_cards" in e["message"] or "artifact" in e["category"] for e in out.errors)


def test_fails_when_rule_lacks_lesson_id(
    corpus_lesson_minimal: Path,
    corpus_lesson_minimal_paths: dict[str, Path],
) -> None:
    p = corpus_lesson_minimal_paths["rule_cards"]
    data = json.loads(p.read_text(encoding="utf-8"))
    del data["rules"][0]["lesson_id"]
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")
    lessons = discover_lessons(corpus_lesson_minimal)
    out = validate_lesson_record_v1(lessons[0], strict=True)
    assert not out.passed
    assert any("lesson_id" in e["message"] for e in out.errors)


def test_fails_when_rule_lacks_source_event_ids_key(tmp_path: Path, corpus_lesson_minimal_paths: dict) -> None:
    p = corpus_lesson_minimal_paths["rule_cards"]
    data = json.loads(p.read_text(encoding="utf-8"))
    del data["rules"][0]["source_event_ids"]
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")
    lessons = discover_lessons(tmp_path / "corpus")
    out = validate_lesson_record_v1(lessons[0], strict=True)
    assert not out.passed
    assert any("source_event_ids" in e["message"] for e in out.errors)


def test_fails_when_rule_lacks_evidence_refs_key(
    corpus_lesson_minimal: Path,
    corpus_lesson_minimal_paths: dict[str, Path],
) -> None:
    p = corpus_lesson_minimal_paths["rule_cards"]
    data = json.loads(p.read_text(encoding="utf-8"))
    del data["rules"][0]["evidence_refs"]
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")
    lessons = discover_lessons(corpus_lesson_minimal)
    out = validate_lesson_record_v1(lessons[0], strict=True)
    assert not out.passed
    assert any("evidence_refs" in e["message"] for e in out.errors)


def test_detects_bad_event_ref(
    corpus_lesson_minimal: Path,
    corpus_lesson_minimal_paths: dict[str, Path],
) -> None:
    p = corpus_lesson_minimal_paths["rule_cards"]
    data = json.loads(p.read_text(encoding="utf-8"))
    data["rules"][0]["source_event_ids"] = ["missing_event"]
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")
    lessons = discover_lessons(corpus_lesson_minimal)
    out = validate_lesson_record_v1(lessons[0], strict=False)
    assert out.passed
    assert any("unknown event_id" in w["message"] for w in out.warnings)


def test_validate_intermediate_dir_helper(tmp_path: Path) -> None:
    root = materialize_lesson_corpus(tmp_path, "lesson_minimal")
    inter = root / "lesson_minimal" / "output_intermediate"
    out = validate_intermediate_dir(inter, "lesson_minimal", strict=True)
    assert out.passed


def test_validate_registry_matches_disk(corpus_lesson_minimal: Path) -> None:
    doc = build_registry_v1(corpus_lesson_minimal, validate=True, strict_validation=True)
    rep = validate_registry_v1(doc, corpus_lesson_minimal, strict=True)
    assert rep["registry_validation_status"] == "passed"
    assert rep["issues"] == []
