"""Optional: build ``CorpusTargetIndex`` from a real explorer repository (local build artifacts)."""

from __future__ import annotations

from pathlib import Path

import pytest

from pipeline.adjudication.corpus_inventory import CorpusTargetIndex
from pipeline.explorer.loader import ExplorerRepository

_ROOT = Path(__file__).resolve().parents[2]
_RAG = _ROOT / "output_rag" / "retrieval_docs_all.jsonl"
_CORPUS = _ROOT / "output_corpus"


@pytest.mark.skipif(not _RAG.is_file() or not (_CORPUS / "corpus_metadata.json").is_file(), reason="no local rag/corpus build")
def test_from_explorer_repository_loads_rule_cards() -> None:
    repo = ExplorerRepository.from_paths(_RAG.parent, _CORPUS)
    idx = CorpusTargetIndex.from_explorer_repository(repo)
    assert len(idx.rule_card_ids) > 0
    sample = next(iter(sorted(idx.rule_card_ids)))
    assert sample.startswith("rule:")
