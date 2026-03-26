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
    assert "example_lookup" in (result.get("detected_intents") or [])


def test_russian_example_query_prefers_evidence_top_slot(hybrid_retriever):
    result = hybrid_retriever.search("Покажи пример накопления на графике", top_k=5)
    assert result["top_hits"]
    assert result["top_hits"][0]["unit_type"] == "evidence_ref"
    assert "example_lookup" in (result.get("detected_intents") or [])


def test_visual_support_policy_query_surfaces_evidence_in_top3(hybrid_retriever):
    result = hybrid_retriever.search(
        "Какие примеры требуют визуальных доказательств?",
        top_k=5,
    )
    top3_types = [h["unit_type"] for h in result["top_hits"][:3]]
    assert "evidence_ref" in top3_types
    assert "support_policy" in (result.get("detected_intents") or [])


def test_transcript_only_query_prefers_transcript_primary_hits(hybrid_retriever):
    result = hybrid_retriever.search("Какие правила подтверждаются только по transcript?", top_k=5)
    assert result["top_hits"]
    top_hit = result["top_hits"][0]
    assert (top_hit["resolved_doc"].get("support_basis") == "transcript_primary")
    assert "support_policy" in (result.get("detected_intents") or [])
