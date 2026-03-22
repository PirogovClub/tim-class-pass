from __future__ import annotations

import json

import pytest

from pipeline.rag.corpus_loader import build_and_persist, load_corpus_and_build_docs


def test_loader_builds_all_unit_types(rag_config):
    store = load_corpus_and_build_docs(rag_config)
    assert store.doc_count == 19
    assert set(store.unit_types()) == {
        "rule_card",
        "knowledge_event",
        "evidence_ref",
        "concept_node",
        "concept_relation",
    }


def test_loader_fails_on_missing_required_file(rag_corpus_root, rag_output_root):
    (rag_corpus_root / "schema_versions.json").unlink()
    with pytest.raises(FileNotFoundError):
        load_corpus_and_build_docs(type("Cfg", (), {"corpus_root": rag_corpus_root, "rag_root": rag_output_root})())


def test_build_and_persist_writes_expected_outputs(rag_config):
    meta = build_and_persist(rag_config)
    assert meta["total_retrieval_docs"] == 19
    assert (rag_config.rag_root / "retrieval_docs_rule_cards.jsonl").exists()
    assert (rag_config.rag_root / "retrieval_docs_knowledge_events.jsonl").exists()
    assert (rag_config.rag_root / "retrieval_docs_evidence_refs.jsonl").exists()
    assert (rag_config.rag_root / "retrieval_docs_concepts.jsonl").exists()
    build_meta = json.loads((rag_config.rag_root / "rag_build_metadata.json").read_text(encoding="utf-8"))
    assert build_meta["corpus_contract_version"] == "0.3.0"
