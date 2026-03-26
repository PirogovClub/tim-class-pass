from __future__ import annotations

import json
from pathlib import Path

from pipeline.corpus.corpus_builder import build_corpus


def test_contract_example_shapes(
    corpus_input_root: Path,
    corpus_output_root: Path,
    lesson_registry_path: Path,
) -> None:
    build_corpus(corpus_input_root, corpus_output_root, strict=False, lesson_registry_path=lesson_registry_path)

    graph = json.loads((corpus_output_root / "corpus_concept_graph.json").read_text(encoding="utf-8"))
    assert graph["lesson_id"] == "corpus"
    assert "nodes" in graph and isinstance(graph["nodes"], list)
    assert "relations" in graph and isinstance(graph["relations"], list)

    for name in (
        "corpus_rule_cards.jsonl",
        "corpus_knowledge_events.jsonl",
        "corpus_evidence_index.jsonl",
    ):
        lines = [x for x in (corpus_output_root / name).read_text(encoding="utf-8").splitlines() if x.strip()]
        assert lines
