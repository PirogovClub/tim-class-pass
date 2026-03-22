from __future__ import annotations

import json

from pipeline.rag.retrieval_docs import ConceptNodeDoc, EvidenceRefDoc, KnowledgeEventDoc, RuleCardDoc


def _first_jsonl_row(path):
    return json.loads(path.read_text(encoding="utf-8").splitlines()[0])


def test_rule_card_transform_preserves_links_and_support(rag_corpus_root):
    raw = _first_jsonl_row(rag_corpus_root / "corpus_rule_cards.jsonl")
    doc = RuleCardDoc.from_corpus(raw)
    assert doc.doc_id == raw["global_id"]
    assert doc.evidence_ids == raw["evidence_refs"]
    assert doc.source_event_ids == raw["source_event_ids"]
    assert doc.support_basis == raw["support_basis"]
    assert doc.evidence_requirement == raw["evidence_requirement"]
    assert doc.teaching_mode == raw["teaching_mode"]


def test_knowledge_event_transform_preserves_timestamps(rag_corpus_root):
    raw = _first_jsonl_row(rag_corpus_root / "corpus_knowledge_events.jsonl")
    doc = KnowledgeEventDoc.from_corpus(raw)
    assert doc.timestamps == [{"start": raw["timestamp_start"], "end": raw["timestamp_end"]}]
    assert doc.source_event_ids == raw["source_event_ids"]
    assert doc.evidence_ids == raw["evidence_refs"]


def test_evidence_ref_transform_preserves_screenshot_and_rules(rag_corpus_root):
    raw = _first_jsonl_row(rag_corpus_root / "corpus_evidence_index.jsonl")
    doc = EvidenceRefDoc.from_corpus(raw)
    assert doc.source_rule_ids == raw["linked_rule_ids"]
    assert doc.metadata["screenshot_paths"] == raw["screenshot_paths"]
    assert doc.metadata["evidence_strength"] == raw["evidence_strength"]


def test_concept_transform_preserves_aliases(rag_corpus_root):
    graph = json.loads((rag_corpus_root / "corpus_concept_graph.json").read_text(encoding="utf-8"))
    node = graph["nodes"][0]
    doc = ConceptNodeDoc.from_corpus(node, {"node:accumulation": {"rule_count": 1, "event_count": 1, "lesson_count": 1}})
    assert doc.doc_id == node["global_id"]
    assert doc.aliases == node["aliases"]
    assert doc.alias_terms == node["aliases"]
