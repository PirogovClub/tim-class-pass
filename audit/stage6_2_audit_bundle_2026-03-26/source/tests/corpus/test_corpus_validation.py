from __future__ import annotations

import json
from pathlib import Path

from pipeline.corpus.corpus_builder import build_corpus
from pipeline.corpus.corpus_validation import validate_corpus_outputs


def test_validator_passes_good_corpus(
    corpus_input_root: Path,
    corpus_output_root: Path,
    lesson_registry_path: Path,
) -> None:
    build_corpus(corpus_input_root, corpus_output_root, strict=False, lesson_registry_path=lesson_registry_path)
    result = validate_corpus_outputs(corpus_output_root, lesson_registry_path=lesson_registry_path)
    assert result.status == "passed"


def test_validator_fails_missing_event_reference(
    corpus_input_root: Path,
    corpus_output_root: Path,
    lesson_registry_path: Path,
) -> None:
    build_corpus(corpus_input_root, corpus_output_root, strict=False, lesson_registry_path=lesson_registry_path)
    path = corpus_output_root / "corpus_rule_cards.jsonl"
    rows = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
    rows[0]["source_event_ids"] = ["event:missing:unknown"]
    path.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in rows) + "\n", encoding="utf-8")
    result = validate_corpus_outputs(corpus_output_root, lesson_registry_path=lesson_registry_path)
    assert result.status == "failed"
    assert any("missing event" in e["message"] for e in result.errors)


def test_validator_fails_duplicate_corpus_ids(
    corpus_input_root: Path,
    corpus_output_root: Path,
    lesson_registry_path: Path,
) -> None:
    build_corpus(corpus_input_root, corpus_output_root, strict=False, lesson_registry_path=lesson_registry_path)
    path = corpus_output_root / "corpus_evidence_index.jsonl"
    rows = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
    rows[1]["global_id"] = rows[0]["global_id"]
    path.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in rows) + "\n", encoding="utf-8")
    result = validate_corpus_outputs(corpus_output_root, lesson_registry_path=lesson_registry_path)
    assert result.status == "failed"
    assert any(e["category"] == "duplicate_id" for e in result.errors)
