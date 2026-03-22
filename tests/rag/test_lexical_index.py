from __future__ import annotations


def test_exact_concept_query_returns_matching_docs(lexical_index):
    hits = lexical_index.search("stop loss", top_k=5)
    assert hits
    assert any("stop_loss" in doc_id for doc_id, _ in hits)


def test_phrase_query_gets_phrase_boost(lexical_index):
    boosted = lexical_index.search('"technical stop loss"', top_k=3)
    plain = lexical_index.search("technical stop loss", top_k=3)
    assert boosted
    assert boosted[0][1] >= plain[0][1]


def test_alias_boost_works(lexical_index):
    boosted = lexical_index.search("sl", top_k=3, alias_terms=["sl"])
    assert boosted
    assert boosted[0][1] > 0


def test_unit_filter_works(lexical_index):
    hits = lexical_index.search("breakout", top_k=10, unit_types=["concept_relation"])
    assert hits
    assert all("rel:" in doc_id for doc_id, _ in hits)


def test_lesson_filter_works(lexical_index):
    hits = lexical_index.search("breakout", top_k=10, lesson_ids=["lesson_beta"])
    assert hits
