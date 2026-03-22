from __future__ import annotations


def test_merge_deduplicates_by_doc_id(hybrid_retriever):
    result = hybrid_retriever.search("stop loss", top_k=5)
    doc_ids = [hit["doc_id"] for hit in result["top_hits"]]
    assert len(doc_ids) == len(set(doc_ids))


def test_rerank_adds_score_breakdown_and_reasons(hybrid_retriever):
    result = hybrid_retriever.search("false breakout", top_k=3)
    assert result["top_hits"]
    top_hit = result["top_hits"][0]
    assert "score_breakdown" in top_hit
    assert "why_retrieved" in top_hit


def test_intent_detection_sets_evidence_bias(hybrid_retriever):
    result = hybrid_retriever.search("show example of accumulation", top_k=3)
    assert result["detected_unit_bias"] == "evidence"
