from __future__ import annotations


def test_russian_query_retrieves_docs(hybrid_retriever):
    result = hybrid_retriever.search("стоп лосс", top_k=3)
    assert result["top_hits"]


def test_alias_query_resolves_canonical_concept(concept_expander):
    result = concept_expander.expand_query("sl")
    assert "node:stop_loss" in result.canonical_concept_ids
