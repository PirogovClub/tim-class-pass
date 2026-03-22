from __future__ import annotations

import pytest

from pipeline.rag.contracts import CorpusInputManifest, REQUIRED_CORPUS_FILES


def test_manifest_loads_all_required_files(rag_corpus_root):
    manifest = CorpusInputManifest.from_root(rag_corpus_root)
    assert set(manifest.files) == set(REQUIRED_CORPUS_FILES)


def test_manifest_fails_fast_on_missing_file(rag_corpus_root):
    (rag_corpus_root / "concept_rule_map.json").unlink()
    with pytest.raises(FileNotFoundError):
        CorpusInputManifest.from_root(rag_corpus_root)
