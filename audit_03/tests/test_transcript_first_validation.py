"""Tests for transcript-first validation policy changes.

Verifies that:
- Rules with evidence_requirement="none" don't emit no_evidence warnings
- Rules with evidence_requirement="required" and no evidence DO emit warnings
- Provenance validation respects evidence_requirement
- New schema fields are populated on KnowledgeEvent, RuleCard, EvidenceRef
- Confidence scoring is transcript-first
"""

from __future__ import annotations

import pytest

from pipeline.schemas import (
    EvidenceRef,
    KnowledgeEvent,
    RuleCard,
    validate_rule_card,
)
from pipeline.component2.provenance import validate_rule_card_provenance
from pipeline.component2.knowledge_builder import (
    score_event_confidence,
    score_transcript_support,
    score_visual_support,
    AdaptedChunk,
    extraction_result_to_knowledge_events,
    ChunkExtractionResult,
    ExtractedStatement,
)
from pipeline.component2.rule_reducer import (
    score_rule_candidate_confidence,
    RuleCandidate,
)
from pipeline.component2.evidence_linker import (
    classify_evidence_strength,
    classify_evidence_role_detail,
    VisualEvidenceCandidate,
)


# ── Helper factories ─────────────────────────────────────────────────────


def _make_rule(**overrides) -> RuleCard:
    defaults = dict(
        rule_id="test_rule_1",
        lesson_id="lesson_1",
        concept="level",
        rule_text="Price reacts from the level.",
        source_event_ids=["ke_1"],
        evidence_refs=[],
        confidence="high",
        confidence_score=0.85,
    )
    defaults.update(overrides)
    return RuleCard(**defaults)


def _make_event(**overrides) -> KnowledgeEvent:
    defaults = dict(
        event_id="ke_1",
        lesson_id="lesson_1",
        event_type="rule_statement",
        raw_text="Цена реагирует от уровня.",
        normalized_text="Цена реагирует от уровня.",
        metadata={"chunk_index": 0},
    )
    defaults.update(overrides)
    return KnowledgeEvent(**defaults)


def _make_chunk(**overrides) -> AdaptedChunk:
    defaults = dict(
        chunk_index=0,
        lesson_id="lesson_1",
        lesson_title="Test Lesson",
        section=None,
        subsection=None,
        start_time_seconds=0.0,
        end_time_seconds=60.0,
        transcript_lines=[
            {"text": "Цена реагирует от уровня.", "start_seconds": 0.0, "end_seconds": 5.0},
            {"text": "Уровень подтверждается реакциями.", "start_seconds": 5.0, "end_seconds": 10.0},
        ],
    )
    defaults.update(overrides)
    return AdaptedChunk(**defaults)


# ── Schema fields exist ──────────────────────────────────────────────────


class TestSchemaFieldsExist:
    def test_knowledge_event_has_support_fields(self):
        ke = _make_event(
            support_basis="transcript_primary",
            evidence_requirement="none",
            teaching_mode="theory",
            transcript_support_level="strong",
            visual_support_level="none",
            transcript_support_score=0.85,
            visual_support_score=0.0,
        )
        assert ke.support_basis == "transcript_primary"
        assert ke.evidence_requirement == "none"
        assert ke.teaching_mode == "theory"

    def test_rule_card_has_support_fields(self):
        rc = _make_rule(
            support_basis="transcript_plus_visual",
            evidence_requirement="optional",
            teaching_mode="mixed",
            has_visual_evidence=True,
            transcript_anchor_count=3,
            transcript_repetition_count=1,
        )
        assert rc.support_basis == "transcript_plus_visual"
        assert rc.has_visual_evidence is True
        assert rc.transcript_anchor_count == 3

    def test_evidence_ref_has_strength_fields(self):
        ref = EvidenceRef(
            evidence_id="ev_1",
            lesson_id="lesson_1",
            evidence_strength="moderate",
            evidence_role_detail="illustrates_rule",
        )
        assert ref.evidence_strength == "moderate"
        assert ref.evidence_role_detail == "illustrates_rule"


# ── Validation policy: evidence_requirement-based ────────────────────────


class TestValidationPolicy:
    def test_rule_no_evidence_no_warning_when_requirement_none(self):
        rc = _make_rule(
            evidence_refs=[],
            visual_summary="Some visual text",
            evidence_requirement="none",
        )
        errors = validate_rule_card(rc)
        assert not any("evidence_refs empty" in e for e in errors)

    def test_rule_no_evidence_warning_when_visual_summary_and_requirement_optional(self):
        rc = _make_rule(
            evidence_refs=[],
            visual_summary="Some visual text",
            evidence_requirement="optional",
        )
        errors = validate_rule_card(rc)
        assert any("visual_summary present but evidence_refs empty" in e for e in errors)

    def test_provenance_no_warning_visual_summary_when_requirement_none(self):
        rc = _make_rule(
            evidence_refs=[],
            visual_summary="Some visual text",
            evidence_requirement="none",
        )
        warnings = validate_rule_card_provenance(rc)
        assert "visual_summary present but evidence_refs missing" not in warnings


# ── Transcript support scoring ───────────────────────────────────────────


class TestTranscriptSupportScoring:
    def test_line_confidence_gives_high_score(self):
        score = score_transcript_support(
            anchor_density=1.0,
            anchor_line_count=2,
            timestamp_confidence="line",
            text="Цена реагирует от уровня.",
        )
        assert score >= 0.70

    def test_chunk_confidence_gives_lower_score(self):
        score = score_transcript_support(
            anchor_density=0.0,
            anchor_line_count=0,
            timestamp_confidence="chunk",
            text="Short.",
        )
        assert score < 0.35

    def test_longer_text_boosts_score(self):
        short = score_transcript_support(0.5, 1, "span", "Short")
        long = score_transcript_support(
            0.5, 1, "span",
            "This is a much longer text that should give a higher boost."
        )
        assert long > short


# ── Confidence scoring is transcript-first ───────────────────────────────


class TestConfidenceScoringTranscriptFirst:
    def test_high_transcript_score_lifts_confidence(self):
        chunk = _make_chunk()
        _, score_high = score_event_confidence(
            "Цена реагирует от уровня.", "rule_statement",
            "level", [], chunk, transcript_support_score=0.90,
        )
        _, score_low = score_event_confidence(
            "Цена реагирует от уровня.", "rule_statement",
            "level", [], chunk, transcript_support_score=0.20,
        )
        assert score_high > score_low

    def test_rule_candidate_confidence_transcript_first(self):
        cand = RuleCandidate(
            candidate_id="test",
            lesson_id="lesson_1",
            concept="level",
            subconcept=None,
            title_hint=None,
            primary_events=[_make_event()],
        )
        _, score_high = score_rule_candidate_confidence(
            cand, transcript_support_score=0.90,
        )
        _, score_low = score_rule_candidate_confidence(
            cand, transcript_support_score=0.20,
        )
        assert score_high > score_low


# ── Evidence strength and role detail ────────────────────────────────────


class TestEvidenceClassifiers:
    def _make_visual_candidate(self, summary: str = "") -> VisualEvidenceCandidate:
        return VisualEvidenceCandidate(
            candidate_id="vc_1",
            lesson_id="lesson_1",
            chunk_index=0,
            timestamp_start=0.0,
            timestamp_end=10.0,
            compact_visual_summary=summary,
        )

    def test_classify_evidence_strength_weak(self):
        vc = self._make_visual_candidate("intro slide")
        assert classify_evidence_strength(vc, []) == "weak"

    def test_classify_evidence_strength_strong(self):
        vc = self._make_visual_candidate("annotated chart with level and candles")
        evts = [_make_event(), _make_event(event_id="ke_2")]
        assert classify_evidence_strength(vc, evts) == "strong"

    def test_classify_evidence_strength_moderate(self):
        vc = self._make_visual_candidate("annotated chart")
        evts = [_make_event(), _make_event(event_id="ke_2")]
        assert classify_evidence_strength(vc, evts) == "moderate"

    def test_classify_evidence_role_detail_illustrates(self):
        vc = self._make_visual_candidate("chart with level")
        evts = [_make_event(event_type="rule_statement")]
        result = classify_evidence_role_detail("illustration", vc, evts)
        assert result == "illustrates_rule"

    def test_classify_evidence_role_detail_counterexample(self):
        vc = self._make_visual_candidate("failed breakout")
        evts = [_make_event(event_type="invalidation")]
        result = classify_evidence_role_detail("counterexample", vc, evts)
        assert result == "shows_counterexample"


# ── KnowledgeEvent populates new fields ──────────────────────────────────


class TestKnowledgeEventNewFields:
    def test_extraction_populates_support_fields(self):
        chunk = _make_chunk()
        extraction = ChunkExtractionResult(
            rule_statements=[
                ExtractedStatement(
                    text="Цена реагирует от уровня.",
                    concept="level",
                    source_line_indices=[0, 1],
                ),
            ]
        )
        events, _ = extraction_result_to_knowledge_events(extraction, chunk)
        assert len(events) == 1
        ke = events[0]
        assert ke.support_basis is not None
        assert ke.evidence_requirement is not None
        assert ke.teaching_mode is not None
        assert ke.transcript_support_score is not None
        assert ke.visual_support_score is not None
        assert ke.transcript_support_level is not None
        assert ke.visual_support_level is not None

    def test_theory_event_gets_transcript_primary(self):
        chunk = _make_chunk(visual_events=[])
        extraction = ChunkExtractionResult(
            definitions=[
                ExtractedStatement(
                    text="Уровень — это зона, от которой цена реагирует.",
                    concept="level",
                    source_line_indices=[0, 1],
                ),
            ]
        )
        events, _ = extraction_result_to_knowledge_events(extraction, chunk)
        assert len(events) == 1
        ke = events[0]
        assert ke.teaching_mode == "theory"
        assert ke.evidence_requirement == "none"
        assert ke.visual_support_score == 0.0
