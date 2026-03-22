"""Tests for pipeline.component2.support_policy — transcript-first classification."""

from __future__ import annotations

import pytest

from pipeline.component2.support_policy import (
    DEFAULT_EVENT_POLICY,
    classify_evidence_requirement,
    classify_support_basis,
    classify_teaching_mode,
    classify_transcript_support_level,
    classify_visual_support_level,
    should_require_visual_evidence,
)


# ── DEFAULT_EVENT_POLICY table ───────────────────────────────────────────


class TestDefaultEventPolicy:
    def test_all_event_types_present(self):
        expected = {
            "definition", "comparison", "warning", "process_step",
            "algorithm_hint", "rule_statement", "condition", "invalidation",
            "exception", "example", "observation",
        }
        assert set(DEFAULT_EVENT_POLICY.keys()) == expected

    def test_theory_types_require_no_evidence(self):
        assert DEFAULT_EVENT_POLICY["definition"]["evidence_requirement"] == "none"
        assert DEFAULT_EVENT_POLICY["comparison"]["evidence_requirement"] == "none"

    def test_example_requires_evidence(self):
        assert DEFAULT_EVENT_POLICY["example"]["evidence_requirement"] == "required"
        assert DEFAULT_EVENT_POLICY["example"]["teaching_mode"] == "example"


# ── classify_teaching_mode ───────────────────────────────────────────────


class TestClassifyTeachingMode:
    def test_definition_always_theory(self):
        assert classify_teaching_mode("definition", "some text", 5) == "theory"

    def test_comparison_always_theory(self):
        assert classify_teaching_mode("comparison", "text", 0) == "theory"

    def test_example_always_example(self):
        assert classify_teaching_mode("example", "text", 0) == "example"

    def test_rule_statement_with_example_language_and_visuals_is_mixed(self):
        result = classify_teaching_mode(
            "rule_statement", "Смотрим на график", linked_visual_count=2,
        )
        assert result == "mixed"

    def test_rule_statement_plain_text_defaults_to_mixed(self):
        result = classify_teaching_mode("rule_statement", "plain text", 0)
        assert result == "mixed"

    def test_condition_defaults_to_theory(self):
        assert classify_teaching_mode("condition", "text", 0) == "theory"


# ── classify_evidence_requirement ────────────────────────────────────────


class TestClassifyEvidenceRequirement:
    def test_example_mode_requires_evidence(self):
        assert classify_evidence_requirement("example", "example") == "required"

    def test_definition_mode_no_evidence(self):
        assert classify_evidence_requirement("definition", "theory") == "none"

    def test_rule_statement_optional(self):
        result = classify_evidence_requirement("rule_statement", "mixed")
        assert result == "optional"

    def test_unknown_event_type_defaults_optional(self):
        result = classify_evidence_requirement("unknown_type", "theory")
        assert result == "optional"


# ── classify_support_basis ───────────────────────────────────────────────


class TestClassifySupportBasis:
    def test_transcript_primary(self):
        assert classify_support_basis(0.80, 0.10, "theory") == "transcript_primary"

    def test_transcript_plus_visual(self):
        assert classify_support_basis(0.80, 0.50, "mixed") == "transcript_plus_visual"

    def test_visual_primary(self):
        assert classify_support_basis(0.30, 0.80, "example") == "visual_primary"

    def test_inferred(self):
        assert classify_support_basis(0.30, 0.20, "theory") == "inferred"

    def test_edge_thresholds(self):
        assert classify_support_basis(0.60, 0.34, "theory") == "transcript_primary"
        assert classify_support_basis(0.60, 0.35, "theory") == "transcript_plus_visual"


# ── classify_transcript_support_level ────────────────────────────────────


class TestClassifyTranscriptSupportLevel:
    def test_strong(self):
        assert classify_transcript_support_level(0.80) == "strong"

    def test_moderate(self):
        assert classify_transcript_support_level(0.55) == "moderate"

    def test_weak(self):
        assert classify_transcript_support_level(0.30) == "weak"

    def test_boundary_strong(self):
        assert classify_transcript_support_level(0.75) == "strong"

    def test_boundary_moderate(self):
        assert classify_transcript_support_level(0.45) == "moderate"


# ── classify_visual_support_level ────────────────────────────────────────


class TestClassifyVisualSupportLevel:
    def test_none_when_zero(self):
        assert classify_visual_support_level(0.0) == "none"

    def test_illustration(self):
        assert classify_visual_support_level(0.5, "illustration") == "illustration"

    def test_counterexample(self):
        assert classify_visual_support_level(0.5, "counterexample") == "counterexample"
        assert classify_visual_support_level(0.5, "negative_example") == "counterexample"

    def test_ambiguous(self):
        assert classify_visual_support_level(0.5, "ambiguous_example") == "ambiguous"

    def test_strong_example(self):
        assert classify_visual_support_level(0.80) == "strong_example"

    def test_supporting_example(self):
        assert classify_visual_support_level(0.40) == "supporting_example"


# ── should_require_visual_evidence ───────────────────────────────────────


class TestShouldRequireVisualEvidence:
    def test_example_mode_requires(self):
        class _Stub:
            teaching_mode = "example"
            evidence_requirement = "required"
        assert should_require_visual_evidence(_Stub()) is True

    def test_theory_mode_does_not_require(self):
        class _Stub:
            teaching_mode = "theory"
            evidence_requirement = "none"
        assert should_require_visual_evidence(_Stub()) is False

    def test_optional_does_not_require(self):
        class _Stub:
            teaching_mode = "mixed"
            evidence_requirement = "optional"
        assert should_require_visual_evidence(_Stub()) is False
