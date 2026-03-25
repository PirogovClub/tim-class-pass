"""Unit tests for adjudication enums and Pydantic models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from pipeline.adjudication.enums import DecisionType, ReviewTargetType, ReviewerKind
from pipeline.adjudication.models import NewReviewDecision, ReviewDecision


def test_review_target_type_values() -> None:
    assert ReviewTargetType.RULE_CARD.value == "rule_card"
    assert ReviewTargetType.CANONICAL_RULE_FAMILY.value == "canonical_rule_family"
    assert len(ReviewTargetType) == 5


def test_decision_type_distinct_values() -> None:
    assert DecisionType.EVIDENCE_STRONG.value == "evidence_strong"
    assert DecisionType.CONCEPT_INVALID.value == "concept_invalid"
    assert DecisionType.RELATION_VALID.value == "relation_valid"


def test_review_decision_requires_related_for_duplicate_of() -> None:
    with pytest.raises(ValidationError):
        ReviewDecision(
            decision_id="d1",
            target_type=ReviewTargetType.RULE_CARD,
            target_id="rule:a:1",
            decision_type=DecisionType.DUPLICATE_OF,
            reviewer_id="u1",
            created_at="2020-01-01T00:00:00+00:00",
            related_target_id=None,
        )


def test_review_decision_allows_duplicate_of_with_related() -> None:
    d = ReviewDecision(
        decision_id="d1",
        target_type=ReviewTargetType.RULE_CARD,
        target_id="rule:a:1",
        decision_type=DecisionType.DUPLICATE_OF,
        reviewer_id="u1",
        created_at="2020-01-01T00:00:00+00:00",
        related_target_id="rule:a:2",
    )
    assert d.related_target_id == "rule:a:2"


def test_new_review_decision_merge_into_requires_related() -> None:
    with pytest.raises(ValidationError):
        NewReviewDecision(
            target_type=ReviewTargetType.RULE_CARD,
            target_id="rule:a:1",
            decision_type=DecisionType.MERGE_INTO,
            reviewer_id="u1",
        )


def test_invalid_decision_type_string_rejected() -> None:
    with pytest.raises(ValueError):
        DecisionType("not_a_real_type")
