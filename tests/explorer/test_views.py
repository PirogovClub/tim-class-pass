from __future__ import annotations

from pipeline.explorer.views import (
    build_concept_detail,
    build_concept_lesson_list,
    build_concept_rule_list,
    build_evidence_detail,
    build_lesson_compare_response,
    build_lesson_detail,
    build_related_rules_response,
    build_result_card,
    build_rule_compare_response,
    build_rule_detail,
)


def test_build_result_card_prefers_rule_text_ru(explorer_repo):
    rule_doc = explorer_repo.get_doc("rule:lesson_alpha:rule_stop_loss_1")
    card = build_result_card(rule_doc)
    assert card.snippet == "Технический стоп прячется за откат."


def test_build_result_card_counts_evidence_ids(explorer_repo):
    rule_doc = explorer_repo.get_doc("rule:lesson_alpha:rule_stop_loss_1")
    card = build_result_card(rule_doc)
    assert card.evidence_count == 1


def test_build_detail_views_include_frame_ids(explorer_repo):
    rule_doc = explorer_repo.get_doc("rule:lesson_alpha:rule_stop_loss_1")
    evidence_doc = explorer_repo.get_doc("evidence:lesson_alpha:ev_stop_loss")
    rule_detail = build_rule_detail(
        rule_doc,
        evidence_docs=explorer_repo.get_evidence_docs_for_rule(rule_doc),
        source_events=explorer_repo.get_source_event_docs_for_rule(rule_doc),
        related_rules=explorer_repo.get_related_rule_docs(rule_doc),
    )
    evidence_detail = build_evidence_detail(
        evidence_doc,
        source_rules=explorer_repo.get_source_rule_docs_for_evidence(evidence_doc),
        source_events=explorer_repo.get_source_event_docs_for_evidence(evidence_doc),
    )

    assert rule_detail.frame_ids == ["000011"]
    assert evidence_detail.frame_ids == ["000011"]


def test_build_lesson_detail_counts_units_correctly(explorer_repo):
    lesson_docs = explorer_repo.get_docs_by_lesson("lesson_alpha")
    lesson_detail = build_lesson_detail(
        "lesson_alpha",
        explorer_repo.get_lesson_meta("lesson_alpha"),
        lesson_docs,
    )
    assert lesson_detail.rule_count == 2
    assert lesson_detail.event_count == 2
    assert lesson_detail.evidence_count == 2
    assert lesson_detail.support_basis_counts["transcript_primary"] == 2
    assert lesson_detail.support_basis_counts["transcript_plus_visual"] == 4


def test_build_concept_detail_uses_explicit_totals_for_counts():
    preview_rule = {
        "doc_id": "rule:lesson_alpha:rule_preview",
        "unit_type": "rule_card",
        "lesson_id": "lesson_alpha",
        "title": "Preview rule",
        "rule_text_ru": "Правило-превью.",
        "canonical_concept_ids": ["node:stop_loss"],
    }
    preview_event = {
        "doc_id": "event:lesson_alpha:event_preview",
        "unit_type": "knowledge_event",
        "lesson_id": "lesson_alpha",
        "title": "Preview event",
        "normalized_text_ru": "Событие-превью.",
        "canonical_concept_ids": ["node:stop_loss"],
    }
    detail = build_concept_detail(
        "node:stop_loss",
        aliases=["Stop Loss"],
        neighbors=[],
        top_rules=[preview_rule],
        top_events=[preview_event],
        lessons=["lesson_alpha"],
        evidence_count=3,
        rule_count=12,
        event_count=15,
    )
    assert len(detail.top_rules) == 1
    assert len(detail.top_events) == 1
    assert detail.rule_count == 12
    assert detail.event_count == 15
    assert detail.evidence_count == 3


def test_build_rule_compare_response_collects_summary(explorer_repo):
    first = explorer_repo.get_doc("rule:lesson_alpha:rule_stop_loss_1")
    second = explorer_repo.get_doc("rule:lesson_alpha:rule_accumulation_1")
    compare = build_rule_compare_response(
        [first, second],
        related_context={str(first["doc_id"]): [], str(second["doc_id"]): []},
    )
    assert [item.doc_id for item in compare.rules] == [
        "rule:lesson_alpha:rule_stop_loss_1",
        "rule:lesson_alpha:rule_accumulation_1",
    ]
    assert compare.summary.shared_lessons == ["lesson_alpha"]
    assert any(diff.field == "concept" for diff in compare.summary.differences)


def test_build_lesson_compare_response_reports_shared_and_unique_concepts(explorer_repo):
    lesson_alpha_docs = explorer_repo.get_docs_by_lesson("lesson_alpha")
    lesson_beta_docs = explorer_repo.get_docs_by_lesson("lesson_beta")
    compare = build_lesson_compare_response(
        {
            "lesson_alpha": explorer_repo.get_lesson_meta("lesson_alpha"),
            "lesson_beta": explorer_repo.get_lesson_meta("lesson_beta"),
        },
        {
            "lesson_alpha": lesson_alpha_docs,
            "lesson_beta": lesson_beta_docs,
        },
        overlap={"rule_families": []},
    )
    assert "node:breakout" in compare.shared_concepts
    assert "node:stop_loss" in compare.unique_concepts["lesson_alpha"]


def test_build_related_rules_and_concept_lists_are_stable(explorer_repo):
    related = build_related_rules_response(
        "rule:lesson_alpha:rule_accumulation_1",
        {
            "same_lesson": [explorer_repo.get_doc("rule:lesson_alpha:rule_stop_loss_1")],
        },
    )
    assert related.source_doc_id == "rule:lesson_alpha:rule_accumulation_1"
    assert related.groups["same_lesson"][0].card.doc_id == "rule:lesson_alpha:rule_stop_loss_1"

    concept_rule_list = build_concept_rule_list(
        "node:breakout",
        [
            explorer_repo.get_doc("rule:lesson_alpha:rule_accumulation_1"),
            explorer_repo.get_doc("rule:lesson_beta:rule_false_breakout_1"),
        ],
    )
    assert concept_rule_list.total == 2

    concept_lesson_list = build_concept_lesson_list(
        "node:breakout",
        ["lesson_alpha", "lesson_beta"],
        {
            "lesson_alpha": explorer_repo.get_lesson_meta("lesson_alpha"),
            "lesson_beta": explorer_repo.get_lesson_meta("lesson_beta"),
        },
        {
            "lesson_alpha": explorer_repo.get_docs_by_lesson("lesson_alpha"),
            "lesson_beta": explorer_repo.get_docs_by_lesson("lesson_beta"),
        },
    )
    assert concept_lesson_list.total == 2
