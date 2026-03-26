from __future__ import annotations

from pathlib import Path

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
