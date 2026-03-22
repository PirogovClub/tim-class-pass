"""Tests for transcript-first validation policy changes.

Verifies that:
- Rules with evidence_requirement="none" don't emit no_evidence warnings
- Rules with evidence_requirement="required" and no evidence DO emit warnings
- Provenance validation respects evidence_requirement
- New schema fields are populated on KnowledgeEvent, RuleCard, EvidenceRef
- Confidence scoring is transcript-first
- Real emitted artifacts have non-null support fields (regression)
"""

from __future__ import annotations

import json
from pathlib import Path

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


# ── Regression: real emitted artifacts have populated fields ──────────────

DATA_ROOT = Path(__file__).resolve().parent.parent / "data"

LESSON_DIRS = [
    ("Lesson 2. Levels part 1", "Lesson 2. Levels part 1"),
    ("2025-09-29-sviatoslav-chornyi", "2025-09-29-sviatoslav-chornyi"),
]

_KE_SUPPORT_FIELDS = [
    "support_basis",
    "evidence_requirement",
    "teaching_mode",
    "transcript_support_score",
    "visual_support_score",
    "transcript_support_level",
    "visual_support_level",
]

_RC_SUPPORT_FIELDS = _KE_SUPPORT_FIELDS + [
    "has_visual_evidence",
    "transcript_anchor_count",
    "transcript_repetition_count",
]


def _load_json(path: Path) -> dict | list:
    return json.loads(path.read_text(encoding="utf-8"))


def _skip_if_no_lesson(lesson_dir: Path, artifact: str):
    path = lesson_dir / "output_intermediate" / artifact
    if not path.exists():
        pytest.skip(f"{path} not found (pipeline not yet run)")


class TestRealArtifactSupportFields:
    """Read emitted JSON and assert transcript-first fields are populated."""

    @pytest.mark.parametrize("folder,name", LESSON_DIRS, ids=[d[0][:20] for d in LESSON_DIRS])
    def test_knowledge_events_have_support_fields(self, folder, name):
        lesson_dir = DATA_ROOT / folder
        ke_path = lesson_dir / "output_intermediate" / f"{name}.knowledge_events.json"
        if not ke_path.exists():
            pytest.skip(f"{ke_path} not found")
        data = _load_json(ke_path)
        events = data.get("events", [])
        assert len(events) > 0, "No events in file"
        null_counts = {f: 0 for f in _KE_SUPPORT_FIELDS}
        for ev in events:
            for field in _KE_SUPPORT_FIELDS:
                if ev.get(field) is None:
                    null_counts[field] += 1
        for field, count in null_counts.items():
            assert count == 0, (
                f"{count}/{len(events)} events have null {field} in {name}"
            )

    @pytest.mark.parametrize("folder,name", LESSON_DIRS, ids=[d[0][:20] for d in LESSON_DIRS])
    def test_rule_cards_have_support_fields(self, folder, name):
        lesson_dir = DATA_ROOT / folder
        rc_path = lesson_dir / "output_intermediate" / f"{name}.rule_cards.json"
        if not rc_path.exists():
            pytest.skip(f"{rc_path} not found")
        data = _load_json(rc_path)
        rules = data.get("rules", [])
        assert len(rules) > 0, "No rules in file"
        null_counts = {f: 0 for f in _RC_SUPPORT_FIELDS}
        for r in rules:
            for field in _RC_SUPPORT_FIELDS:
                if r.get(field) is None:
                    null_counts[field] += 1
        for field, count in null_counts.items():
            assert count == 0, (
                f"{count}/{len(rules)} rules have null {field} in {name}"
            )

    @pytest.mark.parametrize("folder,name", LESSON_DIRS, ids=[d[0][:20] for d in LESSON_DIRS])
    def test_evidence_index_has_strength_fields(self, folder, name):
        lesson_dir = DATA_ROOT / folder
        ei_path = lesson_dir / "output_intermediate" / f"{name}.evidence_index.json"
        if not ei_path.exists():
            pytest.skip(f"{ei_path} not found")
        data = _load_json(ei_path)
        refs = data.get("evidence_refs", [])
        if len(refs) == 0:
            pytest.skip("No evidence refs to check")
        null_strength = sum(1 for r in refs if r.get("evidence_strength") is None)
        null_role = sum(1 for r in refs if r.get("evidence_role_detail") is None)
        assert null_strength == 0, (
            f"{null_strength}/{len(refs)} refs have null evidence_strength"
        )
        assert null_role == 0, (
            f"{null_role}/{len(refs)} refs have null evidence_role_detail"
        )

    @pytest.mark.parametrize("folder,name", LESSON_DIRS, ids=[d[0][:20] for d in LESSON_DIRS])
    def test_rule_cards_support_basis_distribution(self, folder, name):
        lesson_dir = DATA_ROOT / folder
        rc_path = lesson_dir / "output_intermediate" / f"{name}.rule_cards.json"
        if not rc_path.exists():
            pytest.skip(f"{rc_path} not found")
        data = _load_json(rc_path)
        rules = data.get("rules", [])
        basis_values = {r.get("support_basis") for r in rules}
        assert None not in basis_values, "Some rules still have null support_basis"
        non_inferred = sum(1 for r in rules if r.get("support_basis") != "inferred")
        assert non_inferred > 0, "All rules are inferred — transcript-first scoring not applied"

    @pytest.mark.parametrize("folder,name", LESSON_DIRS, ids=[d[0][:20] for d in LESSON_DIRS])
    def test_review_markdown_has_support_markers(self, folder, name):
        lesson_dir = DATA_ROOT / folder
        review_path = lesson_dir / "output_review" / f"{name}.review_markdown.md"
        if not review_path.exists():
            pytest.skip(f"{review_path} not found")
        text = review_path.read_text(encoding="utf-8")
        assert "**Support:**" in text, "review.md missing Support: markers"
        assert "support=" in text, "review.md missing support= values"
        assert "mode=" in text, "review.md missing mode= values"
        assert "evidence=" in text, "review.md missing evidence= values"


class TestCorpusMetadataSupportCounts:
    """Verify corpus_metadata.json has non-zero transcript-first counts."""

    CORPUS_PATH = Path(__file__).resolve().parent.parent / "output_corpus" / "corpus_metadata.json"

    def test_corpus_metadata_has_support_basis_counts(self):
        if not self.CORPUS_PATH.exists():
            pytest.skip("corpus_metadata.json not found")
        meta = _load_json(self.CORPUS_PATH)
        assert "transcript_primary_rules" in meta
        assert "transcript_plus_visual_rules" in meta
        assert "inferred_rules" in meta

    def test_corpus_metadata_not_all_inferred(self):
        if not self.CORPUS_PATH.exists():
            pytest.skip("corpus_metadata.json not found")
        meta = _load_json(self.CORPUS_PATH)
        total_non_inferred = (
            meta.get("transcript_primary_rules", 0)
            + meta.get("transcript_plus_visual_rules", 0)
            + meta.get("visual_primary_rules", 0)
        )
        assert total_non_inferred > 0, (
            f"All rules are inferred (transcript_primary={meta.get('transcript_primary_rules')}, "
            f"transcript_plus_visual={meta.get('transcript_plus_visual_rules')})"
        )

    def test_corpus_validation_uses_optional_category(self):
        vr_path = self.CORPUS_PATH.parent / "validation_report.json"
        if not vr_path.exists():
            pytest.skip("validation_report.json not found")
        report = _load_json(vr_path)
        warnings = report.get("warnings", [])
        categories = {w.get("category") for w in warnings}
        assert "no_evidence_optional" in categories or len(warnings) == 0, (
            "Expected no_evidence_optional warnings; got categories: " + str(categories)
        )
