from __future__ import annotations

import json
from pathlib import Path

from pipeline.corpus.corpus_builder import build_corpus


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def test_builder_creates_required_outputs(
    corpus_input_root: Path,
    corpus_output_root: Path,
    lesson_registry_path: Path,
) -> None:
    summary = build_corpus(
        input_root=corpus_input_root,
        output_root=corpus_output_root,
        strict=False,
        lesson_registry_path=lesson_registry_path,
    )
    assert summary["lessons"] == 2
    for name in (
        "corpus_rule_cards.jsonl",
        "corpus_knowledge_events.jsonl",
        "corpus_evidence_index.jsonl",
        "corpus_concept_graph.json",
    ):
        assert (corpus_output_root / name).is_file()


def test_builder_merges_multiple_lessons(
    corpus_input_root: Path,
    corpus_output_root: Path,
    lesson_registry_path: Path,
) -> None:
    build_corpus(corpus_input_root, corpus_output_root, strict=False, lesson_registry_path=lesson_registry_path)
    rules = _read_jsonl(corpus_output_root / "corpus_rule_cards.jsonl")
    lessons = {r["lesson_id"] for r in rules}
    assert lessons == {"lesson_minimal", "lesson_multi_concept"}


def test_invalid_registry_lessons_are_skipped(
    corpus_input_root: Path,
    corpus_output_root: Path,
    lesson_registry_path: Path,
    tmp_path: Path,
) -> None:
    from pipeline.contracts.lesson_registry import load_registry_v1, save_registry_v1

    doc = load_registry_v1(lesson_registry_path)
    doc.lessons[0].status = "invalid"
    tampered = tmp_path / "tampered_registry.json"
    save_registry_v1(doc, tampered)
    summary = build_corpus(corpus_input_root, corpus_output_root, strict=False, lesson_registry_path=tampered)
    assert summary["lessons"] == 1
    assert doc.lessons[0].lesson_id in summary["skipped_registry_lessons"]


def test_failed_validation_registry_lessons_are_skipped(
    corpus_input_root: Path,
    corpus_output_root: Path,
    lesson_registry_path: Path,
    tmp_path: Path,
) -> None:
    from pipeline.contracts.lesson_registry import load_registry_v1, save_registry_v1

    doc = load_registry_v1(lesson_registry_path)
    doc.lessons[0].validation_status = "failed"
    tampered = tmp_path / "failed_validation_registry.json"
    save_registry_v1(doc, tampered)
    summary = build_corpus(corpus_input_root, corpus_output_root, strict=False, lesson_registry_path=tampered)
    assert summary["lessons"] == 1
    assert doc.lessons[0].lesson_id in summary["skipped_registry_lessons"]
