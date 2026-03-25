"""Mapping from domain integrity errors to API errors (Stage 5.2)."""

from __future__ import annotations

from pipeline.adjudication.api_errors import ErrorCode, map_integrity_error
from pipeline.adjudication.enums import DecisionType, ReviewTargetType
from pipeline.adjudication.errors import (
    FamilyNotFoundError,
    InvalidDecisionForTargetError,
    ReviewerNotFoundError,
)


def test_map_reviewer_not_found() -> None:
    e = ReviewerNotFoundError(reviewer_id="missing")
    api = map_integrity_error(e)
    assert api.error_code == ErrorCode.UNKNOWN_REVIEWER.value
    assert api.status_code == 404
    assert api.details == {"reviewer_id": "missing"}


def test_map_family_not_found() -> None:
    e = FamilyNotFoundError(family_id="fam-1")
    api = map_integrity_error(e)
    assert api.error_code == ErrorCode.UNKNOWN_FAMILY.value
    assert api.status_code == 404


def test_map_invalid_decision_for_target() -> None:
    e = InvalidDecisionForTargetError(
        target_type=ReviewTargetType.RULE_CARD,
        decision_type=DecisionType.RELATION_VALID,
    )
    api = map_integrity_error(e)
    assert api.error_code == ErrorCode.INVALID_TARGET_DECISION_PAIR.value
    assert api.status_code == 400
    assert api.details == {
        "target_type": "rule_card",
        "decision_type": "relation_valid",
    }
