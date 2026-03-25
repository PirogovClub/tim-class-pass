"""DTO validation for adjudication API."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from pipeline.adjudication.api_models import DecisionSubmissionRequest, NextQueueItemRequest
from pipeline.adjudication.enums import DecisionType, ReviewTargetType


def test_valid_decision_request() -> None:
    r = DecisionSubmissionRequest(
        target_type=ReviewTargetType.RULE_CARD,
        target_id="rule:a:1",
        decision_type=DecisionType.APPROVE,
        reviewer_id="u1",
    )
    assert r.target_id == "rule:a:1"


def test_decision_request_invalid_target_type_string() -> None:
    with pytest.raises(ValidationError):
        DecisionSubmissionRequest(
            target_type="not_an_enum",  # type: ignore[arg-type]
            target_id="x",
            decision_type=DecisionType.APPROVE,
            reviewer_id="u1",
        )


def test_next_queue_request_defaults() -> None:
    n = NextQueueItemRequest()
    assert n.queue == "unresolved"


def test_malformed_decision_missing_reviewer() -> None:
    with pytest.raises(ValidationError):
        DecisionSubmissionRequest(
            target_type=ReviewTargetType.RULE_CARD,
            target_id="r1",
            decision_type=DecisionType.NEEDS_REVIEW,
            reviewer_id="",
        )
