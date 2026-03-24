from __future__ import annotations

from pipeline.rag.answer_builder import build_answer


def test_example_intent_prefers_evidence_snippets_in_summary():
    retrieval = {
        "query": "show example",
        "normalized_query": "show example",
        "detected_unit_bias": "evidence",
        "detected_intents": ["example_lookup"],
        "intent_signals": {"prefers_visual_evidence": False, "prefers_transcript_only": False},
        "expansion": {"canonical_concept_ids": []},
        "top_hits": [
            {
                "doc_id": "ev:1",
                "unit_type": "evidence_ref",
                "text_snippet": "EV SNIP",
                "timestamps": [{"start": "0:10"}],
                "evidence_ids": ["e1"],
            },
            {
                "doc_id": "rule:1",
                "unit_type": "rule_card",
                "text_snippet": "RULE SNIP",
                "timestamps": [],
                "evidence_ids": [],
            },
        ],
        "facets": {},
        "hit_count": 2,
    }
    out = build_answer(retrieval, return_summary=True)
    assert "EV SNIP" in (out["summary"]["answer_text"] or "")
    assert "RULE SNIP" not in (out["summary"]["answer_text"] or "")


def test_comparison_intent_prefers_concept_snippets():
    retrieval = {
        "query": "difference a vs b",
        "normalized_query": "difference a vs b",
        "detected_unit_bias": "concept",
        "detected_intents": ["concept_comparison"],
        "intent_signals": {},
        "expansion": {"canonical_concept_ids": ["node:a"]},
        "top_hits": [
            {
                "doc_id": "rel:1",
                "unit_type": "concept_relation",
                "text_snippet": "REL SNIP",
                "timestamps": [],
                "evidence_ids": [],
            },
            {
                "doc_id": "rule:1",
                "unit_type": "rule_card",
                "text_snippet": "RULE SNIP",
                "timestamps": [],
                "evidence_ids": [],
            },
        ],
        "facets": {},
        "hit_count": 2,
    }
    out = build_answer(retrieval, return_summary=True)
    text = out["summary"]["answer_text"] or ""
    assert "REL SNIP" in text
    assert "RULE SNIP" not in text


def test_query_analysis_includes_intent_fields():
    retrieval = {
        "query": "q",
        "normalized_query": "q",
        "detected_unit_bias": "mixed",
        "detected_intents": ["lesson_coverage"],
        "intent_signals": {"mentions_cross_lesson": True},
        "expansion": {"canonical_concept_ids": []},
        "top_hits": [],
        "facets": {},
        "hit_count": 0,
    }
    out = build_answer(retrieval, return_summary=False)
    qa = out["query_analysis"]
    assert qa["detected_intents"] == ["lesson_coverage"]
    assert qa["intent_signals"]["mentions_cross_lesson"] is True
    assert qa["intent_signals"]["prefers_actionable_rules"] is False
