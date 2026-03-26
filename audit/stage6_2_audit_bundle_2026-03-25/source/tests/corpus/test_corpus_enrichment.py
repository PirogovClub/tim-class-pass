from __future__ import annotations

import json
from pathlib import Path

from pipeline.corpus.corpus_builder import build_corpus


def test_enrichment_outputs_exist_and_are_nonempty(
    corpus_input_root: Path,
    corpus_output_root: Path,
    lesson_registry_path: Path,
) -> None:
    build_corpus(corpus_input_root, corpus_output_root, strict=False, lesson_registry_path=lesson_registry_path)
    for name in (
        "concept_frequencies.json",
        "concept_rule_map.json",
        "concept_overlap_report.json",
        "concept_alias_registry.json",
        "rule_family_index.json",
    ):
        assert (corpus_output_root / name).is_file()

    freqs = json.loads((corpus_output_root / "concept_frequencies.json").read_text(encoding="utf-8"))
    assert isinstance(freqs, dict)
    assert freqs  # at least one concept

    crm = json.loads((corpus_output_root / "concept_rule_map.json").read_text(encoding="utf-8"))
    assert isinstance(crm, dict)
    assert any(v for v in crm.values())
