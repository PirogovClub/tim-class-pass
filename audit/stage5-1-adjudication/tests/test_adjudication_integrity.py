"""Post–1st-audit integrity: reviewer, family, and decision/target allow-list."""

from __future__ import annotations

import pytest

from pipeline.adjudication.bootstrap import initialize_adjudication_storage
from pipeline.adjudication.enums import (
    CanonicalFamilyStatus,
    DecisionType,
    MembershipRole,
    ReviewTargetType,
    ReviewerKind,
)
from pipeline.adjudication.errors import (
    FamilyNotFoundError,
    InvalidDecisionForTargetError,
    ReviewerNotFoundError,
)
from pipeline.adjudication.models import (
    NewCanonicalFamily,
    NewMembership,
    NewReviewDecision,
    NewReviewer,
)
from pipeline.adjudication.repository import AdjudicationRepository


@pytest.fixture
def db_path(tmp_path):
    p = tmp_path / "adj.db"
    initialize_adjudication_storage(p)
    return p


@pytest.fixture
def repo_and_reviewer(db_path):
    repo = AdjudicationRepository(db_path)
    repo.create_reviewer(
        NewReviewer(reviewer_id="u1", reviewer_kind=ReviewerKind.HUMAN, display_name="T")
    )
    return repo


def test_append_decision_rejects_unknown_reviewer(db_path) -> None:
    repo = AdjudicationRepository(db_path)
    with pytest.raises(ReviewerNotFoundError) as ei:
        repo.append_decision(
            NewReviewDecision(
                target_type=ReviewTargetType.RULE_CARD,
                target_id="rule:l:1",
                decision_type=DecisionType.NEEDS_REVIEW,
                reviewer_id="nobody",
            )
        )
    assert ei.value.reviewer_id == "nobody"


def test_append_decision_and_refresh_rejects_unknown_reviewer(repo_and_reviewer, db_path) -> None:
    repo = repo_and_reviewer
    with pytest.raises(ReviewerNotFoundError):
        repo.append_decision_and_refresh_state(
            NewReviewDecision(
                target_type=ReviewTargetType.RULE_CARD,
                target_id="rule:l:1",
                decision_type=DecisionType.NEEDS_REVIEW,
                reviewer_id="ghost",
            )
        )


def test_merge_into_rejects_missing_family(repo_and_reviewer) -> None:
    repo = repo_and_reviewer
    with pytest.raises(FamilyNotFoundError) as ei:
        repo.append_decision_and_refresh_state(
            NewReviewDecision(
                target_type=ReviewTargetType.RULE_CARD,
                target_id="rule:l:1",
                decision_type=DecisionType.MERGE_INTO,
                reviewer_id="u1",
                related_target_id="nonexistent-family-id",
            )
        )
    assert ei.value.family_id == "nonexistent-family-id"


def test_append_merge_into_without_refresh_rejects_missing_family(repo_and_reviewer) -> None:
    repo = repo_and_reviewer
    with pytest.raises(FamilyNotFoundError):
        repo.append_decision(
            NewReviewDecision(
                target_type=ReviewTargetType.RULE_CARD,
                target_id="rule:l:1",
                decision_type=DecisionType.MERGE_INTO,
                reviewer_id="u1",
                related_target_id="missing-fam",
            )
        )


def test_add_rule_to_family_rejects_missing_family(repo_and_reviewer) -> None:
    repo = repo_and_reviewer
    with pytest.raises(FamilyNotFoundError):
        repo.add_rule_to_family(
            NewMembership(
                family_id="no-such-family",
                rule_id="rule:l:1",
                membership_role=MembershipRole.MEMBER,
            )
        )


def test_invalid_target_decision_combo_rejected(repo_and_reviewer) -> None:
    repo = repo_and_reviewer
    with pytest.raises(InvalidDecisionForTargetError) as ei:
        repo.append_decision_and_refresh_state(
            NewReviewDecision(
                target_type=ReviewTargetType.EVIDENCE_LINK,
                target_id="ev:1",
                decision_type=DecisionType.DUPLICATE_OF,
                reviewer_id="u1",
                related_target_id="rule:l:other",
            )
        )
    assert ei.value.target_type == ReviewTargetType.EVIDENCE_LINK
    assert ei.value.decision_type == DecisionType.DUPLICATE_OF


def test_append_decision_rejects_missing_family_as_target(repo_and_reviewer) -> None:
    repo = repo_and_reviewer
    with pytest.raises(FamilyNotFoundError) as ei:
        repo.append_decision(
            NewReviewDecision(
                target_type=ReviewTargetType.CANONICAL_RULE_FAMILY,
                target_id="no-such-family-row",
                decision_type=DecisionType.APPROVE,
                reviewer_id="u1",
            )
        )
    assert ei.value.family_id == "no-such-family-row"


def test_append_decision_and_refresh_rejects_missing_family_as_target(repo_and_reviewer) -> None:
    repo = repo_and_reviewer
    with pytest.raises(FamilyNotFoundError):
        repo.append_decision_and_refresh_state(
            NewReviewDecision(
                target_type=ReviewTargetType.CANONICAL_RULE_FAMILY,
                target_id="ghost-family-id",
                decision_type=DecisionType.NEEDS_REVIEW,
                reviewer_id="u1",
            )
        )


def test_valid_combos_still_succeed(repo_and_reviewer) -> None:
    repo = repo_and_reviewer
    repo.append_decision_and_refresh_state(
        NewReviewDecision(
            target_type=ReviewTargetType.RULE_CARD,
            target_id="rule:l:1",
            decision_type=DecisionType.APPROVE,
            reviewer_id="u1",
        )
    )
    repo.append_decision_and_refresh_state(
        NewReviewDecision(
            target_type=ReviewTargetType.EVIDENCE_LINK,
            target_id="ev:1",
            decision_type=DecisionType.EVIDENCE_PARTIAL,
            reviewer_id="u1",
        )
    )
    repo.append_decision_and_refresh_state(
        NewReviewDecision(
            target_type=ReviewTargetType.CONCEPT_LINK,
            target_id="cl:1",
            decision_type=DecisionType.CONCEPT_VALID,
            reviewer_id="u1",
        )
    )
    repo.append_decision_and_refresh_state(
        NewReviewDecision(
            target_type=ReviewTargetType.RELATED_RULE_RELATION,
            target_id="rel:a:t:b",
            decision_type=DecisionType.RELATION_VALID,
            reviewer_id="u1",
        )
    )
    fam = repo.create_canonical_family(
        NewCanonicalFamily(canonical_title="F", created_by="u1", status=CanonicalFamilyStatus.DRAFT)
    )
    repo.append_decision_and_refresh_state(
        NewReviewDecision(
            target_type=ReviewTargetType.CANONICAL_RULE_FAMILY,
            target_id=fam.family_id,
            decision_type=DecisionType.APPROVE,
            reviewer_id="u1",
        )
    )
