"""Service-layer read paths (no HTTP)."""

from __future__ import annotations

import pytest

from pipeline.adjudication.api_errors import AdjudicationApiError
from pipeline.adjudication.api_service import (
    get_family_detail,
    get_family_members,
    get_review_history,
    get_review_item,
)
from pipeline.adjudication.bootstrap import initialize_adjudication_storage
from pipeline.adjudication.enums import CanonicalFamilyStatus, DecisionType, ReviewTargetType, ReviewerKind
from pipeline.adjudication.models import NewCanonicalFamily, NewReviewDecision, NewReviewer
from pipeline.adjudication.repository import AdjudicationRepository


@pytest.fixture
def repo(tmp_path):
    p = tmp_path / "a.db"
    initialize_adjudication_storage(p)
    r = AdjudicationRepository(p)
    r.create_reviewer(NewReviewer(reviewer_id="u1", reviewer_kind=ReviewerKind.HUMAN, display_name="A"))
    return r


def test_review_item_rule_empty(repo) -> None:
    item = get_review_item(repo, ReviewTargetType.RULE_CARD, "rule:new:1")
    assert item.target_id == "rule:new:1"
    assert item.latest_decision_type is None


def test_review_history_empty(repo) -> None:
    h = get_review_history(repo, ReviewTargetType.RULE_CARD, "rule:new:1")
    assert h.decisions == []


def test_family_detail_missing(repo) -> None:
    with pytest.raises(AdjudicationApiError) as ei:
        get_family_detail(repo, "missing")
    assert ei.value.status_code == 404
    assert ei.value.error_code == "not_found"


def test_family_members_missing(repo) -> None:
    with pytest.raises(AdjudicationApiError) as ei:
        get_family_members(repo, "missing")
    assert ei.value.status_code == 404


def test_review_item_canonical_family_missing(repo) -> None:
    with pytest.raises(AdjudicationApiError) as ei:
        get_review_item(repo, ReviewTargetType.CANONICAL_RULE_FAMILY, "ghost")
    assert ei.value.status_code == 404


def test_family_round_trip(repo) -> None:
    fam = repo.create_canonical_family(
        NewCanonicalFamily(canonical_title="T", created_by="u1", status=CanonicalFamilyStatus.DRAFT)
    )
    d = get_family_detail(repo, fam.family_id)
    assert d.canonical_title == "T"
    m = get_family_members(repo, fam.family_id)
    assert m.members == []


def test_review_item_family_target(repo) -> None:
    fam = repo.create_canonical_family(
        NewCanonicalFamily(canonical_title="Fam", created_by="u1", status=CanonicalFamilyStatus.DRAFT)
    )
    repo.append_decision_and_refresh_state(
        NewReviewDecision(
            target_type=ReviewTargetType.CANONICAL_RULE_FAMILY,
            target_id=fam.family_id,
            decision_type=DecisionType.NEEDS_REVIEW,
            reviewer_id="u1",
        )
    )
    item = get_review_item(repo, ReviewTargetType.CANONICAL_RULE_FAMILY, fam.family_id)
    assert item.summary == "Fam"
    assert item.latest_decision_type == "needs_review"
