from __future__ import annotations

from pipeline.rag.query_intents import (
    INTENT_CONCEPT_COMPARISON,
    INTENT_CROSS_LESSON_CONFLICT,
    INTENT_EXAMPLE_LOOKUP,
    INTENT_SUPPORT_POLICY,
    INTENT_TIMEFRAME,
    analyze_query_intents,
    unit_bias_from_intents,
)


def test_example_phrasing_triggers_example_lookup():
    sig = analyze_query_intents("show an example of accumulation on the chart")
    assert INTENT_EXAMPLE_LOOKUP in sig.detected_intents
    assert sig.prefers_examples
    assert unit_bias_from_intents(sig) == "evidence"


def test_comparison_phrasing_triggers_concept_comparison():
    sig = analyze_query_intents("difference between technical stop and regular stop")
    assert INTENT_CONCEPT_COMPARISON in sig.detected_intents


def test_transcript_only_support_policy_prefers_transcript_signal():
    sig = analyze_query_intents("which rules are confirmed only from transcript")
    assert INTENT_SUPPORT_POLICY in sig.detected_intents
    assert sig.prefers_transcript_only


def test_visual_evidence_support_policy_sets_visual_preference():
    sig = analyze_query_intents("which examples require visual proof")
    assert INTENT_SUPPORT_POLICY in sig.detected_intents
    assert sig.prefers_visual_evidence


def test_stoploss_example_query_detects_stoploss():
    sig = analyze_query_intents("Пример постановки стоп-лосса")
    assert INTENT_EXAMPLE_LOOKUP in sig.detected_intents
    assert sig.prefers_examples
    assert sig.mentions_stoploss
    assert unit_bias_from_intents(sig) == "evidence"


def test_timeframe_markers():
    sig = analyze_query_intents("rules for trading on higher timeframe and daily level")
    assert INTENT_TIMEFRAME in sig.detected_intents


def test_timeframe_action_query_prefers_actionable_rules():
    sig = analyze_query_intents("Как определить дневной уровень?")
    assert INTENT_TIMEFRAME in sig.detected_intents
    assert sig.mentions_timeframe
    assert sig.prefers_actionable_rules
    assert unit_bias_from_intents(sig) == "rule"


def test_multi_timeframe_rules_query_prefers_actionable_rules():
    sig = analyze_query_intents("Правила торговли на разных таймфреймах")
    assert INTENT_TIMEFRAME in sig.detected_intents
    assert sig.mentions_timeframe
    assert sig.prefers_actionable_rules
    assert sig.prefers_explicit_rules
    assert unit_bias_from_intents(sig) == "rule"


def test_cross_lesson_timeframe_query_stays_concept_biased():
    sig = analyze_query_intents("Какие правила связаны с анализом таймфреймов?")
    assert INTENT_TIMEFRAME in sig.detected_intents
    assert INTENT_CROSS_LESSON_CONFLICT in sig.detected_intents
    assert sig.prefers_actionable_rules
    assert unit_bias_from_intents(sig) == "concept"
