from __future__ import annotations

import random
from pathlib import Path

from pipeline.contracts.lesson_registry import load_registry_v1, save_registry_v1
from pipeline.corpus.corpus_builder import build_corpus
from pipeline.corpus.corpus_validation import corpus_output_fingerprints


def test_ids_and_outputs_are_deterministic(
    corpus_input_root: Path,
    lesson_registry_path: Path,
    tmp_path: Path,
) -> None:
    out1 = tmp_path / "out1"
    out2 = tmp_path / "out2"
    build_corpus(corpus_input_root, out1, strict=False, lesson_registry_path=lesson_registry_path)
    build_corpus(corpus_input_root, out2, strict=False, lesson_registry_path=lesson_registry_path)
    assert corpus_output_fingerprints(out1) == corpus_output_fingerprints(out2)


def test_outputs_invariant_to_registry_lesson_order(
    corpus_input_root: Path,
    lesson_registry_path: Path,
    tmp_path: Path,
) -> None:
    out_ordered = tmp_path / "out_ordered"
    out_shuffled = tmp_path / "out_shuffled"
    doc = load_registry_v1(lesson_registry_path)
    shuffled = list(doc.lessons)
    random.Random(42).shuffle(shuffled)
    doc.lessons = shuffled
    shuf_path = tmp_path / "lesson_registry_shuffled.json"
    save_registry_v1(doc, shuf_path)

    build_corpus(corpus_input_root, out_ordered, strict=False, lesson_registry_path=lesson_registry_path)
    build_corpus(corpus_input_root, out_shuffled, strict=False, lesson_registry_path=shuf_path)
    assert corpus_output_fingerprints(out_ordered) == corpus_output_fingerprints(out_shuffled)
