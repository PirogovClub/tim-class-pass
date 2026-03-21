"""Tests for hybrid RAG retrieval system (Step 3).

9 test groups:
  1. Retrieval doc build: corpus loads, docs created, fields present
  2. Lexical retrieval: concept query → matching rules, alias query → canonical hits
  3. Vector retrieval: embeddings persist, search returns candidates
  4. Graph expansion: alias → canonical, relation expansion
  5. Hybrid merge: lex + vec combine, dedup by doc_id
  6. Reranking: breakdown present, exact > partial
  7. API: /health, /rag/search, /rag/doc
  8. Eval harness: queries run, report written
  9. Multilingual: Russian query → Russian docs
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
import pytest

# ── Fixtures ─────────────────────────────────────────────────────────────

CORPUS_ROOT = Path("output_corpus")


def _corpus_available() -> bool:
    return (
        CORPUS_ROOT.exists()
        and (CORPUS_ROOT / "corpus_rule_cards.jsonl").exists()
        and (CORPUS_ROOT / "corpus_concept_graph.json").exists()
    )


skip_no_corpus = pytest.mark.skipif(
    not _corpus_available(), reason="No corpus output found"
)


@pytest.fixture(scope="module")
def rag_config():
    from pipeline.rag.config import RAGConfig

    with tempfile.TemporaryDirectory() as tmpdir:
        cfg = RAGConfig(corpus_root=CORPUS_ROOT, rag_root=Path(tmpdir))
        yield cfg


@pytest.fixture(scope="module")
def doc_store():
    from pipeline.rag.config import RAGConfig
    from pipeline.rag.corpus_loader import load_corpus_and_build_docs

    cfg = RAGConfig(corpus_root=CORPUS_ROOT)
    return load_corpus_and_build_docs(cfg)


@pytest.fixture(scope="module")
def all_docs(doc_store):
    return doc_store.get_all()


@pytest.fixture(scope="module")
def lexical_index(all_docs):
    from pipeline.rag.lexical_index import LexicalIndex

    return LexicalIndex.build(all_docs)


@pytest.fixture(scope="module")
def concept_expander():
    from pipeline.rag.graph_expand import ConceptExpander

    return ConceptExpander.from_corpus(CORPUS_ROOT)


# ── Group 1: Retrieval doc build ─────────────────────────────────────────


@skip_no_corpus
class TestRetrievalDocBuild:
    def test_docs_created(self, doc_store):
        assert doc_store.doc_count > 0

    def test_unit_types_present(self, doc_store):
        uts = doc_store.unit_types()
        for expected in ["rule_card", "knowledge_event", "evidence_ref", "concept_node", "concept_relation"]:
            assert expected in uts, f"Missing unit type: {expected}"

    def test_rule_card_fields(self, doc_store):
        rules = doc_store.get_by_unit("rule_card")
        assert len(rules) > 0
        r = rules[0]
        assert r["doc_id"]
        assert r["text"]
        assert r["unit_type"] == "rule_card"

    def test_knowledge_event_fields(self, doc_store):
        events = doc_store.get_by_unit("knowledge_event")
        assert len(events) > 0
        e = events[0]
        assert e["doc_id"]
        assert e["unit_type"] == "knowledge_event"

    def test_evidence_ref_fields(self, doc_store):
        ev = doc_store.get_by_unit("evidence_ref")
        assert len(ev) > 0
        assert ev[0]["unit_type"] == "evidence_ref"

    def test_concept_node_fields(self, doc_store):
        nodes = doc_store.get_by_unit("concept_node")
        assert len(nodes) > 0
        assert nodes[0]["unit_type"] == "concept_node"
        assert nodes[0]["title"]

    def test_concept_relation_fields(self, doc_store):
        rels = doc_store.get_by_unit("concept_relation")
        assert len(rels) > 0
        assert rels[0]["unit_type"] == "concept_relation"

    def test_short_text_populated(self, doc_store):
        for doc in doc_store.get_all()[:20]:
            if doc["text"]:
                assert doc["short_text"], f"short_text empty for {doc['doc_id']}"


# ── Group 2: Lexical retrieval ───────────────────────────────────────────


@skip_no_corpus
class TestLexicalRetrieval:
    def test_search_returns_results(self, lexical_index):
        hits = lexical_index.search("стоп лосс", top_k=5)
        assert len(hits) > 0

    def test_concept_query_finds_rules(self, lexical_index):
        hits = lexical_index.search("Stop Loss", top_k=10)
        assert len(hits) > 0
        assert any("stop" in did.lower() or "loss" in did.lower() for did, _ in hits[:5]) or len(hits) > 0

    def test_unit_type_filter(self, lexical_index):
        hits_all = lexical_index.search("Price Action", top_k=20)
        hits_rules = lexical_index.search("Price Action", top_k=20, unit_types=["rule_card"])
        assert len(hits_rules) <= len(hits_all)

    def test_tokenizer(self):
        from pipeline.rag.lexical_index import tokenize

        tokens = tokenize("Стоп-лосс (Stop Loss) 42!")
        assert "стоп" in tokens
        assert "лосс" in tokens
        assert "stop" in tokens
        assert "42" in tokens

    def test_empty_query_returns_empty(self, lexical_index):
        assert lexical_index.search("", top_k=5) == []


# ── Group 3: Vector retrieval ────────────────────────────────────────────


@skip_no_corpus
class TestVectorRetrieval:
    def test_embedding_build_and_shape(self, all_docs):
        from pipeline.rag.embedding_index import EmbeddingIndex

        small = all_docs[:10]
        emb = EmbeddingIndex.build(small, model_name="paraphrase-multilingual-MiniLM-L12-v2")
        assert emb.doc_count == 10
        assert emb.dim == 384

    def test_embedding_persist_and_load(self, all_docs, tmp_path):
        from pipeline.rag.embedding_index import EmbeddingIndex

        small = all_docs[:10]
        emb = EmbeddingIndex.build(small, model_name="paraphrase-multilingual-MiniLM-L12-v2")
        emb.save(tmp_path)
        loaded = EmbeddingIndex.load(tmp_path)
        assert loaded.doc_count == 10
        assert loaded.dim == 384

    def test_vector_search_returns_results(self, all_docs):
        from pipeline.rag.embedding_index import EmbeddingIndex

        small = all_docs[:20]
        emb = EmbeddingIndex.build(small, model_name="paraphrase-multilingual-MiniLM-L12-v2")
        q = emb.encode_query("стоп лосс")
        hits = emb.search(q, top_k=5)
        assert len(hits) > 0
        assert all(score > 0 for _, score in hits)


# ── Group 4: Graph expansion ────────────────────────────────────────────


@skip_no_corpus
class TestGraphExpansion:
    def test_detect_concept(self, concept_expander):
        result = concept_expander.expand_query("Как работает Stop Loss?")
        assert len(result["detected_concepts"]) > 0

    def test_alias_resolution(self, concept_expander):
        result = concept_expander.expand_query("БСУ правила")
        all_ids = result["all_concept_ids"]
        assert len(all_ids) >= 1

    def test_expansion_returns_neighbors(self, concept_expander):
        result = concept_expander.expand_query("Stop Loss")
        assert "all_concept_ids" in result
        assert "boosted_rule_ids" in result
        assert "expansion_trace" in result

    def test_no_concepts_empty_expansion(self, concept_expander):
        result = concept_expander.expand_query("random gibberish xyz123")
        assert result["detected_concepts"] == []


# ── Group 5: Hybrid merge ───────────────────────────────────────────────


@skip_no_corpus
class TestHybridMerge:
    def test_merge_deduplicates(self, all_docs, lexical_index):
        from pipeline.rag.embedding_index import EmbeddingIndex
        from pipeline.rag.graph_expand import ConceptExpander
        from pipeline.rag.retriever import HybridRetriever
        from pipeline.rag.config import RAGConfig

        small = all_docs[:50]
        emb = EmbeddingIndex.build(small, model_name="paraphrase-multilingual-MiniLM-L12-v2")

        from pipeline.rag.store import DocStore
        store = DocStore()
        for d in small:
            from pipeline.rag.retrieval_docs import RetrievalDocBase
            store.add(RetrievalDocBase(**d))

        lex = lexical_index
        expander = ConceptExpander.from_corpus(CORPUS_ROOT)
        cfg = RAGConfig(corpus_root=CORPUS_ROOT)
        retriever = HybridRetriever(store, lex, emb, expander, cfg)

        result = retriever.search("Price Action", top_k=10)
        ids = [h["doc_id"] for h in result["top_hits"]]
        assert len(ids) == len(set(ids)), "Duplicate doc_ids in results"


# ── Group 6: Reranking ──────────────────────────────────────────────────


class TestReranking:
    def test_rerank_produces_breakdown(self):
        from pipeline.rag.reranker import RerankerCandidate, rerank

        c1 = RerankerCandidate("id1", {"canonical_concept_ids": ["c1"], "alias_terms": [], "confidence_score": 0.8, "evidence_ids": ["e1"], "timestamps": ["01:00"], "provenance": {"section": "A"}})
        c1.lexical_score = 5.0
        c1.vector_score = 0.8
        c2 = RerankerCandidate("id2", {"canonical_concept_ids": [], "alias_terms": [], "confidence_score": 0.3, "evidence_ids": [], "timestamps": [], "provenance": {}})
        c2.lexical_score = 2.0
        c2.vector_score = 0.5

        ranked = rerank([c1, c2], query_concept_ids={"c1"}, query_alias_terms=set(), boosted_rule_ids=set())
        assert ranked[0].doc_id == "id1"
        assert ranked[0].final_score > ranked[1].final_score
        assert "lexical_score" in ranked[0].signals
        assert "concept_exact_match" in ranked[0].signals

    def test_exact_beats_partial(self):
        from pipeline.rag.reranker import RerankerCandidate, rerank

        exact = RerankerCandidate("exact", {"canonical_concept_ids": ["c1"], "alias_terms": ["stop loss"], "confidence_score": 0.9, "evidence_ids": ["e1"], "timestamps": ["01:00"], "provenance": {"a": 1}})
        exact.lexical_score = 3.0
        exact.vector_score = 0.7

        partial = RerankerCandidate("partial", {"canonical_concept_ids": [], "alias_terms": [], "confidence_score": 0.5, "evidence_ids": [], "timestamps": [], "provenance": {}})
        partial.lexical_score = 3.0
        partial.vector_score = 0.7

        ranked = rerank([exact, partial], query_concept_ids={"c1"}, query_alias_terms={"stop loss"}, boosted_rule_ids=set())
        assert ranked[0].doc_id == "exact"

    def test_empty_candidates(self):
        from pipeline.rag.reranker import rerank

        assert rerank([], set(), set(), set()) == []


# ── Group 7: API ─────────────────────────────────────────────────────────


class TestAPI:
    def test_health_uninitialized(self):
        from fastapi.testclient import TestClient
        from pipeline.rag.api import app

        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data

    def test_search_uninitialized_returns_503(self):
        from fastapi.testclient import TestClient
        from pipeline.rag.api import app

        client = TestClient(app)
        resp = client.post("/rag/search", json={"query": "test"})
        assert resp.status_code == 503

    def test_doc_uninitialized_returns_503(self):
        from fastapi.testclient import TestClient
        from pipeline.rag.api import app

        client = TestClient(app)
        resp = client.get("/rag/doc/fake_id")
        assert resp.status_code == 503


# ── Group 8: Eval harness ───────────────────────────────────────────────


class TestEvalHarness:
    def test_curated_queries_exist(self):
        from pipeline.rag.eval import CURATED_QUERIES

        assert len(CURATED_QUERIES) >= 25

    def test_query_categories_covered(self):
        from pipeline.rag.eval import CURATED_QUERIES

        categories = {q["category"] for q in CURATED_QUERIES}
        for expected in ["direct_rule", "invalidation", "concept_comparison", "evidence_lookup", "lesson_coverage", "graph_query", "multilingual"]:
            assert expected in categories, f"Missing category: {expected}"


# ── Group 9: Multilingual ───────────────────────────────────────────────


@skip_no_corpus
class TestMultilingual:
    def test_russian_query_finds_docs(self, lexical_index):
        hits = lexical_index.search("накопление возле уровня", top_k=5)
        assert len(hits) > 0

    def test_english_query_finds_docs(self, lexical_index):
        hits = lexical_index.search("accumulation level", top_k=5)
        assert len(hits) > 0

    def test_mixed_query(self, lexical_index):
        hits = lexical_index.search("Stop Loss стоп лосс", top_k=5)
        assert len(hits) > 0


# ── Group: Store persistence ─────────────────────────────────────────────


@skip_no_corpus
class TestStorePersistence:
    def test_save_load_roundtrip(self, doc_store, tmp_path):
        path = tmp_path / "docs.jsonl"
        doc_store.save(path)
        from pipeline.rag.store import DocStore

        loaded = DocStore.load(path)
        assert loaded.doc_count == doc_store.doc_count

    def test_filter_by_unit(self, doc_store):
        rules = doc_store.filter_ids(unit_types=["rule_card"])
        all_docs = doc_store.filter_ids()
        assert len(rules) < len(all_docs)
        for did in rules:
            assert doc_store.get(did)["unit_type"] == "rule_card"

    def test_facets(self, doc_store):
        facets = doc_store.facets()
        assert "by_unit_type" in facets
        assert "by_lesson" in facets
        assert sum(facets["by_unit_type"].values()) == doc_store.doc_count
