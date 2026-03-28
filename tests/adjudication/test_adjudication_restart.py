"""Mandatory durability: close DB and reopen repository."""

from __future__ import annotations

from pipeline.adjudication.bootstrap import initialize_adjudication_storage
from pipeline.adjudication.enums import (
    DecisionType,
    MembershipRole,
    ReviewTargetType,
    ReviewerKind,
)
from pipeline.adjudication.models import (
    NewCanonicalFamily,
    NewMembership,
    NewReviewer,
    NewReviewDecision,
)
from pipeline.adjudication.repository import AdjudicationRepository


def test_restart_reloads_history_and_state(tmp_path) -> None:
    db_path = tmp_path / "adj.db"
    initialize_adjudication_storage(db_path)

    repo = AdjudicationRepository(db_path)
    repo.create_reviewer(
        NewReviewer(reviewer_id="u1", reviewer_kind=ReviewerKind.HUMAN, display_name="T")
    )
    fam = repo.create_canonical_family(NewCanonicalFamily(canonical_title="F", created_by="u1"))
    repo.add_rule_to_family(
        NewMembership(
            family_id=fam.family_id,
            rule_id="rule:l:a",
            membership_role=MembershipRole.DUPLICATE,
            added_by_decision_id=None,
        )
    )
    d = repo.append_decision_and_refresh_state(
        NewReviewDecision(
            target_type=ReviewTargetType.RULE_CARD,
            target_id="rule:l:x",
            decision_type=DecisionType.DUPLICATE_OF,
            reviewer_id="u1",
            related_target_id="rule:l:a",
        )
    )

    del repo

    repo2 = AdjudicationRepository(db_path)
    hist = repo2.get_decisions_for_target(ReviewTargetType.RULE_CARD, "rule:l:x")
    assert len(hist) == 1
    assert hist[0].decision_id == d.decision_id
    st = repo2.get_rule_card_state("rule:l:x")
    assert st is not None
    assert st.is_duplicate is True
    members = repo2.list_family_members(fam.family_id)
    assert len(members) == 1
