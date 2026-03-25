from __future__ import annotations

from pipeline.explorer.views import build_concept_detail, build_lesson_detail, build_result_card


def test_build_result_card_prefers_rule_text_ru(explorer_repo):
    rule_doc = explorer_repo.get_doc("rule:lesson_alpha:rule_stop_loss_1")
    card = build_result_card(rule_doc)
    assert card.snippet == "Технический стоп прячется за откат."


def test_build_result_card_counts_evidence_ids(explorer_repo):
    rule_doc = explorer_repo.get_doc("rule:lesson_alpha:rule_stop_loss_1")
    card = build_result_card(rule_doc)
    assert card.evidence_count == 1


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
