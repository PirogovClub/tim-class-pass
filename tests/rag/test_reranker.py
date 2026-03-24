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


def test_transcript_policy_signal_prefers_transcript_primary():
    transcript_primary = RerankerCandidate(
        "doc:transcript",
        {
            "doc_id": "doc:transcript",
            "unit_type": "rule_card",
            "canonical_concept_ids": ["node:stop_loss"],
            "alias_terms": [],
            "support_basis": "transcript_primary",
            "teaching_mode": "theory",
            "confidence_score": 0.7,
            "evidence_ids": [],
            "timestamps": [{"start": "00:01", "end": "00:02"}],
            "provenance": {"section": "A"},
            "lesson_id": "lesson_alpha",
        },
    )
    visual = RerankerCandidate(
        "doc:visual",
        {
            "doc_id": "doc:visual",
            "unit_type": "knowledge_event",
            "canonical_concept_ids": ["node:stop_loss"],
            "alias_terms": [],
            "support_basis": "transcript_plus_visual",
            "teaching_mode": "mixed",
            "confidence_score": 0.95,
            "evidence_ids": ["e1"],
            "timestamps": [{"start": "00:01", "end": "00:02"}],
            "provenance": {"section": "A"},
            "lesson_id": "lesson_alpha",
        },
    )
    transcript_primary.lexical_score = 0.7
    transcript_primary.vector_score = 0.7
    visual.lexical_score = 1.0
    visual.vector_score = 1.0

    ranked = rerank(
        [visual, transcript_primary],
        query_concept_ids={"node:stop_loss"},
        query_alias_terms=set(),
        boosted_rule_ids=set(),
        detected_intents={"support_policy"},
        intent_signals={"prefers_transcript_only": True},
    )
    assert ranked[0].doc_id == "doc:transcript"
    assert ranked[0].signals["intent_transcript_policy_signal"] > 0
    assert ranked[1].signals["intent_transcript_policy_signal"] < 0


def test_timeframe_actionable_prefers_rule_over_generic_relation():
    relation = RerankerCandidate(
        "rel:timeframe",
        {
            "doc_id": "rel:timeframe",
            "unit_type": "concept_relation",
            "canonical_concept_ids": ["node:uroven"],
            "alias_terms": [],
            "title": "Уровень -> Уровень лимитного игрока",
            "text": "Общее отношение про уровень.",
            "short_text": "Общее отношение про уровень.",
            "keywords": ["уровень"],
            "support_basis": None,
            "teaching_mode": None,
            "confidence_score": 0.4,
            "evidence_ids": [],
            "timestamps": [],
            "provenance": {},
            "lesson_id": "corpus",
        },
    )
    rule = RerankerCandidate(
        "rule:timeframe",
        {
            "doc_id": "rule:timeframe",
            "unit_type": "rule_card",
            "canonical_concept_ids": ["node:analiz_taymfreymov"],
            "alias_terms": ["старшие таймфреймы", "дневной уровень"],
            "title": "Старшие таймфреймы и дневной уровень",
            "text": "Старайтесь брать уровни, которые приходят со старших таймфреймов.",
            "short_text": "Старайтесь брать уровни, которые приходят со старших таймфреймов.",
            "keywords": ["старшие таймфреймы", "дневной уровень"],
            "support_basis": "transcript_primary",
            "teaching_mode": "theory",
            "confidence_score": 0.85,
            "evidence_ids": [],
            "timestamps": [{"start": "00:20", "end": "00:24"}],
            "provenance": {"section": "Timeframes"},
            "lesson_id": "lesson_alpha",
        },
    )
    relation.lexical_score = 1.0
    relation.vector_score = 1.0
    rule.lexical_score = 0.75
    rule.vector_score = 0.85

    ranked = rerank(
        [relation, rule],
        query_concept_ids={"node:analiz_taymfreymov", "node:uroven"},
        query_alias_terms={"дневной уровень", "старшие таймфреймы"},
        boosted_rule_ids=set(),
        detected_intents={"timeframe_lookup"},
        intent_signals={"mentions_timeframe": True, "prefers_actionable_rules": True},
    )
    assert ranked[0].doc_id == "rule:timeframe"
    assert ranked[0].signals["intent_timeframe_boost"] > ranked[1].signals["intent_timeframe_boost"]
    assert ranked[0].signals["intent_concept_priority_signal"] > ranked[1].signals["intent_concept_priority_signal"]


def test_stoploss_example_prefers_evidence_ref():
    event = RerankerCandidate(
        "event:stop",
        {
            "doc_id": "event:stop",
            "unit_type": "knowledge_event",
            "canonical_concept_ids": ["node:stop_loss"],
            "alias_terms": ["стоп-лосс"],
            "title": "Пояснение по стоп-лоссу",
            "text": "Сначала объяснение про постановку стопа.",
            "short_text": "Сначала объяснение про постановку стопа.",
            "support_basis": "transcript_primary",
            "teaching_mode": "example",
            "confidence_score": 0.9,
            "evidence_ids": ["e1"],
            "timestamps": [{"start": "00:10", "end": "00:14"}],
            "provenance": {"section": "Stops"},
            "lesson_id": "lesson_alpha",
        },
    )
    evidence = RerankerCandidate(
        "evidence:stop",
        {
            "doc_id": "evidence:stop",
            "unit_type": "evidence_ref",
            "canonical_concept_ids": ["node:stop_loss"],
            "alias_terms": ["постановка стоп-лосса"],
            "title": "Пример постановки стоп-лосса",
            "text": "График показывает постановку стоп-лосса за откат.",
            "short_text": "График показывает постановку стоп-лосса за откат.",
            "support_basis": "transcript_plus_visual",
            "teaching_mode": "example",
            "confidence_score": 0.85,
            "evidence_ids": ["evidence:stop"],
            "timestamps": [{"start": "00:10", "end": "00:14"}],
            "provenance": {"section": "Stops"},
            "lesson_id": "lesson_alpha",
            "example_role": "illustration",
        },
    )
    event.lexical_score = 1.0
    event.vector_score = 1.0
    evidence.lexical_score = 0.82
    evidence.vector_score = 0.9

    ranked = rerank(
        [event, evidence],
        query_concept_ids={"node:stop_loss"},
        query_alias_terms={"постановка стоп-лосса", "стоп-лосс"},
        boosted_rule_ids=set(),
        detected_intents={"example_lookup"},
        intent_signals={"mentions_stoploss": True},
        query_preferences={"prefers_examples": True},
    )
    assert ranked[0].doc_id == "evidence:stop"
    assert ranked[0].signals["intent_evidence_priority_boost"] > 0
    assert ranked[0].signals["intent_concept_priority_signal"] > ranked[1].signals["intent_concept_priority_signal"]


def test_explicit_rule_timeframe_query_prefers_rule_card_top1():
    event = RerankerCandidate(
        "event:rules",
        {
            "doc_id": "event:rules",
            "unit_type": "knowledge_event",
            "canonical_concept_ids": ["node:analiz_taymfreymov"],
            "alias_terms": ["разные таймфреймы"],
            "title": "Разные таймфреймы в работе",
            "text": "Сначала смотрим старшие таймфреймы, потом локальный.",
            "short_text": "Сначала смотрим старшие таймфреймы, потом локальный.",
            "keywords": ["разные таймфреймы", "старшие таймфреймы"],
            "support_basis": "transcript_primary",
            "teaching_mode": "theory",
            "confidence_score": 0.92,
            "evidence_ids": [],
            "timestamps": [{"start": "00:20", "end": "00:24"}],
            "provenance": {"section": "Timeframes"},
            "lesson_id": "lesson_alpha",
        },
    )
    rule = RerankerCandidate(
        "rule:rules",
        {
            "doc_id": "rule:rules",
            "unit_type": "rule_card",
            "canonical_concept_ids": ["node:analiz_taymfreymov"],
            "alias_terms": ["разные таймфреймы"],
            "title": "Правила торговли на разных таймфреймах",
            "text": "Правила торговли на разных таймфреймах начинаются со старшего контекста.",
            "short_text": "Правила торговли на разных таймфреймах начинаются со старшего контекста.",
            "keywords": ["разные таймфреймы", "старшие таймфреймы"],
            "support_basis": "transcript_primary",
            "teaching_mode": "theory",
            "confidence_score": 0.84,
            "evidence_ids": [],
            "timestamps": [{"start": "00:21", "end": "00:25"}],
            "provenance": {"section": "Timeframes"},
            "lesson_id": "lesson_alpha",
        },
    )
    event.lexical_score = 1.0
    event.vector_score = 1.0
    rule.lexical_score = 0.88
    rule.vector_score = 0.92

    ranked = rerank(
        [event, rule],
        query_concept_ids={"node:analiz_taymfreymov"},
        query_alias_terms={"разные таймфреймы"},
        boosted_rule_ids=set(),
        detected_intents={"timeframe_lookup"},
        intent_signals={
            "mentions_timeframe": True,
            "prefers_actionable_rules": True,
            "prefers_explicit_rules": True,
        },
    )
    assert ranked[0].doc_id == "rule:rules"
    assert ranked[0].signals["intent_concept_priority_signal"] > ranked[1].signals["intent_concept_priority_signal"]


def test_concept_priority_signal_prefers_relation_for_cross_lesson_queries():
    relation = RerankerCandidate(
        "rel:1",
        {
            "doc_id": "rel:1",
            "unit_type": "concept_relation",
            "canonical_concept_ids": ["node:breakout", "node:stop_loss"],
            "alias_terms": [],
            "support_basis": None,
            "teaching_mode": None,
            "confidence_score": 0.2,
            "evidence_ids": [],
            "timestamps": [],
            "provenance": {},
            "metadata": {"source_lessons": ["lesson_alpha", "lesson_beta"]},
            "lesson_id": "corpus",
        },
    )
    event = RerankerCandidate(
        "event:1",
        {
            "doc_id": "event:1",
            "unit_type": "knowledge_event",
            "canonical_concept_ids": ["node:breakout"],
            "alias_terms": [],
            "support_basis": "transcript_plus_visual",
            "teaching_mode": "mixed",
            "confidence_score": 0.95,
            "evidence_ids": ["e1"],
            "timestamps": [{"start": "00:01", "end": "00:02"}],
            "provenance": {"section": "A"},
            "lesson_id": "lesson_alpha",
        },
    )
    relation.lexical_score = 0.8
    relation.vector_score = 0.7
    event.lexical_score = 1.0
    event.vector_score = 1.0

    ranked = rerank(
        [event, relation],
        query_concept_ids={"node:breakout", "node:stop_loss"},
        query_alias_terms=set(),
        boosted_rule_ids=set(),
        detected_intents={"cross_lesson_conflict_lookup"},
        intent_signals={"mentions_cross_lesson": True},
    )
    assert ranked[0].doc_id == "rel:1"
    assert ranked[0].signals["intent_concept_priority_signal"] > ranked[1].signals["intent_concept_priority_signal"]
