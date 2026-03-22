from __future__ import annotations

from pipeline.rag.reranker import RerankerCandidate, rerank


def test_reranker_exposes_all_key_signals():
    exact = RerankerCandidate(
        "rule:1",
        {
            "doc_id": "rule:1",
            "unit_type": "evidence_ref",
            "canonical_concept_ids": ["node:accumulation"],
            "alias_terms": ["накопление"],
            "support_basis": "transcript_plus_visual",
            "teaching_mode": "example",
            "confidence_score": 0.9,
            "evidence_ids": ["e1"],
            "timestamps": [{"start": "00:10", "end": "00:12"}],
            "provenance": {"section": "Examples"},
            "lesson_id": "lesson_alpha",
        },
    )
    exact.lexical_score = 3.0
    exact.vector_score = 0.9

    weak = RerankerCandidate(
        "rule:2",
        {
            "doc_id": "rule:2",
            "unit_type": "knowledge_event",
            "canonical_concept_ids": [],
            "alias_terms": [],
            "support_basis": "inferred",
            "teaching_mode": "theory",
            "confidence_score": 0.3,
            "evidence_ids": [],
            "timestamps": [],
            "provenance": {},
            "lesson_id": "lesson_alpha",
        },
    )
    weak.lexical_score = 1.0
    weak.vector_score = 0.2

    ranked = rerank(
        [exact, weak],
        query_concept_ids={"node:accumulation"},
        query_alias_terms={"накопление"},
        boosted_rule_ids=set(),
        unit_type_weights={"evidence_ref": 1.2, "knowledge_event": 0.9},
        detected_unit_bias="evidence",
        query_preferences={"prefers_examples": True, "prefers_theory": False},
    )
    assert ranked[0].doc_id == "rule:1"
    assert "unit_type_relevance" in ranked[0].signals
    assert "teaching_mode_relevance" in ranked[0].signals
    assert "groundedness" in ranked[0].signals


def test_diversity_bonus_is_present():
    first = RerankerCandidate("doc:1", {"doc_id": "doc:1", "unit_type": "rule_card", "canonical_concept_ids": [], "alias_terms": [], "support_basis": "transcript_primary", "teaching_mode": "theory", "confidence_score": 0.8, "evidence_ids": ["e1"], "timestamps": [{"start": "00:01", "end": "00:02"}], "provenance": {"section": "A"}, "lesson_id": "lesson_alpha"})
    second = RerankerCandidate("doc:2", {"doc_id": "doc:2", "unit_type": "rule_card", "canonical_concept_ids": [], "alias_terms": [], "support_basis": "transcript_primary", "teaching_mode": "theory", "confidence_score": 0.8, "evidence_ids": ["e2"], "timestamps": [{"start": "00:03", "end": "00:04"}], "provenance": {"section": "B"}, "lesson_id": "lesson_beta"})
    first.lexical_score = second.lexical_score = 1.0
    first.vector_score = second.vector_score = 1.0
    ranked = rerank([first, second], set(), set(), set())
    assert "lesson_diversity_bonus" in ranked[0].signals
