"""Task 17: Tests for rule compatibility, ML safety, and Russian *_ru backfill."""

from __future__ import annotations

import pytest

from pipeline.component2.rule_compat import (
    are_directions_conflicting,
    infer_rule_direction,
    is_evidence_safe_for_ml,
    is_positive_example_compatible,
)
from pipeline.schemas import (
    EvidenceRef,
    KnowledgeEvent,
    RuleCard,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rule_dict(rule_id: str, rule_text: str, **kw) -> dict:
    return {"rule_id": rule_id, "rule_text": rule_text, **kw}


# ---------------------------------------------------------------------------
# Test 1 — Contradictory positive example is blocked
# ---------------------------------------------------------------------------


class TestContradictoryPositiveBlocked:
    def test_bullish_bearish_conflict(self):
        bullish = _rule_dict("r1", "Цена выше уровня — покупка")
        bearish = _rule_dict("r2", "Цена ниже уровня — продажа")
        evidence = {
            "evidence_id": "e1",
            "linked_rule_ids": ["r1", "r2"],
            "example_role": "positive_example",
        }
        rbi = {"r1": bullish, "r2": bearish}

        assert not is_positive_example_compatible(bullish, evidence, rbi)
        assert not is_positive_example_compatible(bearish, evidence, rbi)

    def test_single_rule_always_compatible(self):
        rule = _rule_dict("r1", "Some generic rule text")
        evidence = {
            "evidence_id": "e1",
            "linked_rule_ids": ["r1"],
            "example_role": "positive_example",
        }
        assert is_positive_example_compatible(rule, evidence, {"r1": rule})

    def test_same_direction_allowed(self):
        r1 = _rule_dict("r1", "Отскок вверх от уровня")
        r2 = _rule_dict("r2", "Рост цены выше уровня")
        evidence = {
            "evidence_id": "e1",
            "linked_rule_ids": ["r1", "r2"],
            "example_role": "positive_example",
        }
        rbi = {"r1": r1, "r2": r2}
        assert is_positive_example_compatible(r1, evidence, rbi)

    def test_breakout_up_vs_down_blocked(self):
        r1 = _rule_dict("r1", "пробой вверх через уровень")
        r2 = _rule_dict("r2", "пробой вниз через уровень")
        evidence = {
            "evidence_id": "e1",
            "linked_rule_ids": ["r1", "r2"],
        }
        rbi = {"r1": r1, "r2": r2}
        assert not is_positive_example_compatible(r1, evidence, rbi)

    def test_unknown_multi_rule_blocked(self):
        r1 = _rule_dict("r1", "generic rule")
        r2 = _rule_dict("r2", "another rule")
        evidence = {
            "evidence_id": "e1",
            "linked_rule_ids": ["r1", "r2"],
        }
        rbi = {"r1": r1, "r2": r2}
        assert not is_positive_example_compatible(r1, evidence, rbi)


# ---------------------------------------------------------------------------
# Test 2 — ML safety conservative under ambiguity
# ---------------------------------------------------------------------------


class TestMLSafetyConservative:
    def test_conflicting_directions_unsafe(self):
        r1 = _rule_dict("r1", "Покупка выше уровня")
        r2 = _rule_dict("r2", "Продажа ниже уровня")
        evidence = {
            "evidence_id": "e1",
            "linked_rule_ids": ["r1", "r2"],
            "source_event_ids": ["ke1"],
        }
        rbi = {"r1": r1, "r2": r2}
        assert not is_evidence_safe_for_ml(evidence, rbi)

    def test_unknown_multi_rule_unsafe(self):
        r1 = _rule_dict("r1", "some text")
        r2 = _rule_dict("r2", "other text")
        evidence = {
            "evidence_id": "e1",
            "linked_rule_ids": ["r1", "r2"],
        }
        rbi = {"r1": r1, "r2": r2}
        assert not is_evidence_safe_for_ml(evidence, rbi)

    def test_single_rule_safe(self):
        r1 = _rule_dict("r1", "Some neutral rule")
        evidence = {
            "evidence_id": "e1",
            "linked_rule_ids": ["r1"],
        }
        assert is_evidence_safe_for_ml(evidence, {"r1": r1})

    def test_no_linked_rules_unsafe(self):
        evidence = {"evidence_id": "e1", "linked_rule_ids": []}
        assert not is_evidence_safe_for_ml(evidence, {})

    def test_compatible_multi_rule_safe(self):
        r1 = _rule_dict("r1", "Покупка выше уровня")
        r2 = _rule_dict("r2", "Лонг при росте")
        evidence = {
            "evidence_id": "e1",
            "linked_rule_ids": ["r1", "r2"],
        }
        rbi = {"r1": r1, "r2": r2}
        assert is_evidence_safe_for_ml(evidence, rbi)


# ---------------------------------------------------------------------------
# Test — infer_rule_direction
# ---------------------------------------------------------------------------


class TestInferRuleDirection:
    def test_bullish(self):
        assert infer_rule_direction({"rule_text": "Цена выше уровня"}) == "bullish_above"

    def test_bearish(self):
        assert infer_rule_direction({"rule_text": "Цена ниже уровня"}) == "bearish_below"

    def test_breakout_up(self):
        assert infer_rule_direction({"rule_text": "пробой вверх"}) == "breakout_up"

    def test_breakout_down(self):
        assert infer_rule_direction({"rule_text": "пробой вниз"}) == "breakout_down"

    def test_reversal_up(self):
        assert infer_rule_direction({"rule_text": "бычий разворот"}) == "reversal_up"

    def test_reversal_down(self):
        assert infer_rule_direction({"rule_text": "медвежий разворот"}) == "reversal_down"

    def test_neutral(self):
        assert infer_rule_direction({"rule_text": "консолидация"}) == "neutral"

    def test_unknown(self):
        assert infer_rule_direction({"rule_text": "уровень"}) == "unknown"

    def test_empty(self):
        assert infer_rule_direction({}) == "unknown"


# ---------------------------------------------------------------------------
# Test — are_directions_conflicting
# ---------------------------------------------------------------------------


class TestAreDirectionsConflicting:
    def test_same_not_conflicting(self):
        assert not are_directions_conflicting("bullish_above", "bullish_above")

    def test_bullish_bearish_conflicting(self):
        assert are_directions_conflicting("bullish_above", "bearish_below")

    def test_unknown_always_conflicting(self):
        assert are_directions_conflicting("bullish_above", "unknown")
        assert are_directions_conflicting("unknown", "bearish_below")

    def test_neutral_not_conflicting_with_itself(self):
        assert not are_directions_conflicting("neutral", "neutral")


# ---------------------------------------------------------------------------
# Test 3 — Russian *_ru backfill
# ---------------------------------------------------------------------------


class TestRussianBackfill:
    def test_knowledge_event_ru_fields(self):
        ke = KnowledgeEvent(
            event_id="ke1",
            lesson_id="test",
            event_type="rule_statement",
            raw_text="Уровень важен",
            normalized_text="уровень важен",
            concept="уровень",
            subconcept="оценка уровня",
            source_language="ru",
            normalized_text_ru="уровень важен",
            concept_label_ru="уровень",
            subconcept_label_ru="оценка уровня",
        )
        assert ke.normalized_text_ru == "уровень важен"
        assert ke.concept_label_ru == "уровень"
        assert ke.subconcept_label_ru == "оценка уровня"

    def test_knowledge_event_ru_fields_default_none(self):
        ke = KnowledgeEvent(
            event_id="ke1",
            lesson_id="test",
            event_type="rule_statement",
            raw_text="test",
            normalized_text="test",
        )
        assert ke.normalized_text_ru is None
        assert ke.concept_label_ru is None
        assert ke.subconcept_label_ru is None

    def test_rule_card_ru_fields(self):
        rc = RuleCard(
            rule_id="r1",
            lesson_id="test",
            concept="уровень",
            subconcept="оценка",
            rule_text="Правило по уровню",
            source_language="ru",
            rule_text_ru="Правило по уровню",
            concept_label_ru="уровень",
            subconcept_label_ru="оценка",
        )
        assert rc.rule_text_ru == "Правило по уровню"
        assert rc.concept_label_ru == "уровень"
        assert rc.subconcept_label_ru == "оценка"

    def test_rule_card_ru_fields_default_none(self):
        rc = RuleCard(
            rule_id="r1",
            lesson_id="test",
            concept="c",
            rule_text="r",
        )
        assert rc.rule_text_ru is None
        assert rc.concept_label_ru is None
        assert rc.subconcept_label_ru is None

    def test_evidence_ref_summary_ru(self):
        er = EvidenceRef(
            evidence_id="e1",
            lesson_id="test",
            compact_visual_summary="График с уровнями",
            source_language="ru",
            summary_primary="График с уровнями",
            summary_language="ru",
            summary_ru="График с уровнями",
        )
        assert er.summary_ru == "График с уровнями"
        assert er.summary_primary == "График с уровнями"
        assert er.summary_language == "ru"
        assert er.summary_en is None

    def test_evidence_ref_summary_ru_default_none(self):
        er = EvidenceRef(evidence_id="e1", lesson_id="test")
        assert er.summary_ru is None
        assert er.summary_en is None
        assert er.summary_primary is None
        assert er.summary_language is None


# ---------------------------------------------------------------------------
# Task 18 — Language-aware summary fields
# ---------------------------------------------------------------------------


class TestLanguageAwareSummary:
    def test_russian_summary_goes_to_summary_ru(self):
        from pipeline.component2.evidence_linker import detect_summary_language

        text = "График с уровнями поддержки"
        lang = detect_summary_language(text)
        assert lang == "ru"
        er = EvidenceRef(
            evidence_id="e1",
            lesson_id="test",
            compact_visual_summary=text,
            summary_primary=text,
            summary_language=lang,
            summary_ru=text if lang == "ru" else None,
            summary_en=text if lang == "en" else None,
        )
        assert er.summary_primary == text
        assert er.summary_language == "ru"
        assert er.summary_ru == text
        assert er.summary_en is None

    def test_english_summary_does_not_go_to_summary_ru(self):
        from pipeline.component2.evidence_linker import detect_summary_language

        text = "Chart showing support levels with price reactions"
        lang = detect_summary_language(text)
        assert lang == "en"
        er = EvidenceRef(
            evidence_id="e1",
            lesson_id="test",
            compact_visual_summary=text,
            summary_primary=text,
            summary_language=lang,
            summary_ru=text if lang == "ru" else None,
            summary_en=text if lang == "en" else None,
        )
        assert er.summary_primary == text
        assert er.summary_language == "en"
        assert er.summary_en == text
        assert er.summary_ru is None

    def test_legacy_compact_visual_summary_preserved(self):
        original = "Instructor visible on the left"
        er = EvidenceRef(
            evidence_id="e1",
            lesson_id="test",
            compact_visual_summary=original,
            summary_primary=original,
            summary_language="en",
            summary_en=original,
        )
        assert er.compact_visual_summary == original

    def test_ambiguous_empty_summary_stays_safe(self):
        from pipeline.component2.evidence_linker import detect_summary_language

        assert detect_summary_language(None) is None
        assert detect_summary_language("") is None
        assert detect_summary_language("123 456") is None

        er = EvidenceRef(
            evidence_id="e1",
            lesson_id="test",
            compact_visual_summary="123",
            summary_primary="123",
            summary_language=None,
        )
        assert er.summary_ru is None
        assert er.summary_en is None

    def test_detect_summary_language_mixed(self):
        from pipeline.component2.evidence_linker import detect_summary_language

        assert detect_summary_language("Slide with title 'Уровень'") == "en"
        assert detect_summary_language("Уровень поддержки level") == "ru"
