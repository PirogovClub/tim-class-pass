from __future__ import annotations

import pytest

from pipeline.adjudication.bootstrap import initialize_adjudication_storage
from pipeline.adjudication.bundle_service import get_review_bundle
from pipeline.adjudication.enums import (
    CanonicalFamilyStatus,
    DecisionType,
    ReviewTargetType,
    ReviewerKind,
)
from pipeline.adjudication.models import NewCanonicalFamily, NewReviewDecision, NewReviewer
from pipeline.adjudication.repository import AdjudicationRepository


@pytest.fixture
def repo(tmp_path):
    p = tmp_path / "a.db"
    initialize_adjudication_storage(p)
    r = AdjudicationRepository(p)
    r.create_reviewer(NewReviewer(reviewer_id="u1", reviewer_kind=ReviewerKind.HUMAN, display_name="A"))
    return r


def test_bundle_rule_no_family(repo) -> None:
    repo.append_decision_and_refresh_state(
        NewReviewDecision(
            target_type=ReviewTargetType.RULE_CARD,
            target_id="rule:x:1",
            decision_type=DecisionType.NEEDS_REVIEW,
            reviewer_id="u1",
        )
    )
    b = get_review_bundle(repo, ReviewTargetType.RULE_CARD, "rule:x:1", explorer=None)
    assert b.target_id == "rule:x:1"
    assert len(b.history) == 1
    assert b.family is None
    assert b.optional_context == {}
    assert b.quality_tier is not None
    assert b.quality_tier.tier == "unresolved"


def test_bundle_rule_with_family(repo) -> None:
    fam = repo.create_canonical_family(
        NewCanonicalFamily(canonical_title="F", created_by="u1", status=CanonicalFamilyStatus.DRAFT)
    )
    repo.append_decision_and_refresh_state(
        NewReviewDecision(
            target_type=ReviewTargetType.RULE_CARD,
            target_id="rule:x:2",
            decision_type=DecisionType.MERGE_INTO,
            reviewer_id="u1",
            related_target_id=fam.family_id,
        )
    )
    b = get_review_bundle(repo, ReviewTargetType.RULE_CARD, "rule:x:2", explorer=None)
    assert b.family is not None
    assert b.family.family_id == fam.family_id
    assert b.family.member_count is not None
    assert len(b.history) >= 1


def test_bundle_optional_context_absent_without_explorer(repo) -> None:
    b = get_review_bundle(repo, ReviewTargetType.RULE_CARD, "rule:z:9", explorer=None)
    assert b.optional_context == {}
