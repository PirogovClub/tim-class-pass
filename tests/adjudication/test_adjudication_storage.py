"""Schema, repository append-only behavior, and materialized state upserts."""

from __future__ import annotations

import sqlite3

import pytest

from pipeline.adjudication.bootstrap import initialize_adjudication_storage
from pipeline.adjudication.enums import (
    CanonicalFamilyStatus,
    DecisionType,
    EvidenceSupportStatus,
    MembershipRole,
    ReviewTargetType,
    ReviewerKind,
    RuleCardCoarseStatus,
)
from pipeline.adjudication.models import (
    NewCanonicalFamily,
    NewMembership,
    NewReviewer,
    NewReviewDecision,
)
from pipeline.adjudication.repository import REQUIRED_TABLES, AdjudicationRepository


@pytest.fixture
def db_path(tmp_path):
    p = tmp_path / "adj.db"
    initialize_adjudication_storage(p)
    return p


def test_schema_bootstrap_all_tables(db_path) -> None:
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        names = {row[0] for row in cur.fetchall()}
        for t in REQUIRED_TABLES:
            assert t in names
    finally:
        conn.close()


def test_initialize_idempotent(db_path) -> None:
    initialize_adjudication_storage(db_path)
    initialize_adjudication_storage(db_path)
    test_schema_bootstrap_all_tables(db_path)


def test_append_two_decisions_same_target_preserved(db_path) -> None:
    repo = AdjudicationRepository(db_path)
    repo.create_reviewer(
        NewReviewer(reviewer_id="u1", reviewer_kind=ReviewerKind.HUMAN, display_name="T")
    )
    r1 = repo.append_decision(
        NewReviewDecision(
            target_type=ReviewTargetType.RULE_CARD,
            target_id="rule:l:r1",
            decision_type=DecisionType.NEEDS_REVIEW,
            reviewer_id="u1",
        )
    )
    r2 = repo.append_decision(
        NewReviewDecision(
            target_type=ReviewTargetType.RULE_CARD,
            target_id="rule:l:r1",
            decision_type=DecisionType.AMBIGUOUS,
            reviewer_id="u1",
        )
    )
    hist = repo.get_decisions_for_target(ReviewTargetType.RULE_CARD, "rule:l:r1")
    assert len(hist) == 2
    assert {h.decision_id for h in hist} == {r1.decision_id, r2.decision_id}


def test_rule_state_resolution_needs_review_then_duplicate(db_path) -> None:
    repo = AdjudicationRepository(db_path)
    repo.create_reviewer(
        NewReviewer(reviewer_id="u1", reviewer_kind=ReviewerKind.HUMAN, display_name="T")
    )
    repo.append_decision_and_refresh_state(
        NewReviewDecision(
            target_type=ReviewTargetType.RULE_CARD,
            target_id="rule:l:r1",
            decision_type=DecisionType.NEEDS_REVIEW,
            reviewer_id="u1",
        )
    )
    repo.append_decision_and_refresh_state(
        NewReviewDecision(
            target_type=ReviewTargetType.RULE_CARD,
            target_id="rule:l:r1",
            decision_type=DecisionType.DUPLICATE_OF,
            reviewer_id="u1",
            related_target_id="rule:l:r2",
        )
    )
    st = repo.get_rule_card_state("rule:l:r1")
    assert st is not None
    assert st.is_duplicate is True
    assert st.duplicate_of_rule_id == "rule:l:r2"
    assert st.latest_decision_type == DecisionType.DUPLICATE_OF


def test_evidence_partial_then_strong_state(db_path) -> None:
    repo = AdjudicationRepository(db_path)
    repo.create_reviewer(
        NewReviewer(reviewer_id="u1", reviewer_kind=ReviewerKind.HUMAN, display_name="T")
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
            target_type=ReviewTargetType.EVIDENCE_LINK,
            target_id="ev:1",
            decision_type=DecisionType.EVIDENCE_STRONG,
            reviewer_id="u1",
        )
    )
    st = repo.get_evidence_link_state("ev:1")
    assert st is not None
    assert st.support_status == EvidenceSupportStatus.STRONG


def test_append_refresh_keeps_full_history(db_path) -> None:
    repo = AdjudicationRepository(db_path)
    repo.create_reviewer(
        NewReviewer(reviewer_id="u1", reviewer_kind=ReviewerKind.HUMAN, display_name="T")
    )
    repo.append_decision_and_refresh_state(
        NewReviewDecision(
            target_type=ReviewTargetType.RULE_CARD,
            target_id="rule:l:r9",
            decision_type=DecisionType.NEEDS_REVIEW,
            reviewer_id="u1",
        )
    )
    repo.append_decision_and_refresh_state(
        NewReviewDecision(
            target_type=ReviewTargetType.RULE_CARD,
            target_id="rule:l:r9",
            decision_type=DecisionType.APPROVE,
            reviewer_id="u1",
        )
    )
    hist = repo.get_decisions_for_target(ReviewTargetType.RULE_CARD, "rule:l:r9")
    assert len(hist) == 2
    st = repo.get_rule_card_state("rule:l:r9")
    assert st is not None
    assert st.current_status == RuleCardCoarseStatus.APPROVED


def test_canonical_family_persistence_reload(db_path) -> None:
    repo = AdjudicationRepository(db_path)
    repo.create_reviewer(
        NewReviewer(reviewer_id="u1", reviewer_kind=ReviewerKind.HUMAN, display_name="T")
    )
    fam = repo.create_canonical_family(
        NewCanonicalFamily(
            canonical_title="Stop loss",
            created_by="u1",
            status=CanonicalFamilyStatus.DRAFT,
        )
    )
    repo.add_rule_to_family(
        NewMembership(
            family_id=fam.family_id,
            rule_id="rule:l:canon",
            membership_role=MembershipRole.CANONICAL,
        )
    )
    repo2 = AdjudicationRepository(db_path)
    loaded = repo2.get_family(fam.family_id)
    assert loaded is not None
    assert loaded.canonical_title == "Stop loss"
    members = repo2.list_family_members(fam.family_id)
    assert len(members) == 1
    assert members[0].rule_id == "rule:l:canon"


def test_canonical_family_id_persists_after_approve_post_merge(db_path) -> None:
    """Membership row keeps family linkage when latest decision is not merge_into."""
    repo = AdjudicationRepository(db_path)
    repo.create_reviewer(
        NewReviewer(reviewer_id="u1", reviewer_kind=ReviewerKind.HUMAN, display_name="T")
    )
    fam = repo.create_canonical_family(
        NewCanonicalFamily(canonical_title="Fam", created_by="u1")
    )
    repo.append_decision_and_refresh_state(
        NewReviewDecision(
            target_type=ReviewTargetType.RULE_CARD,
            target_id="rule:l:child",
            decision_type=DecisionType.MERGE_INTO,
            reviewer_id="u1",
            related_target_id=fam.family_id,
        )
    )
    repo.append_decision_and_refresh_state(
        NewReviewDecision(
            target_type=ReviewTargetType.RULE_CARD,
            target_id="rule:l:child",
            decision_type=DecisionType.APPROVE,
            reviewer_id="u1",
        )
    )
    st = repo.get_rule_card_state("rule:l:child")
    assert st is not None
    assert st.canonical_family_id == fam.family_id
    assert st.current_status == RuleCardCoarseStatus.APPROVED


def test_merge_into_creates_membership_and_state(db_path) -> None:
    repo = AdjudicationRepository(db_path)
    repo.create_reviewer(
        NewReviewer(reviewer_id="u1", reviewer_kind=ReviewerKind.HUMAN, display_name="T")
    )
    fam = repo.create_canonical_family(
        NewCanonicalFamily(canonical_title="Fam", created_by="u1")
    )
    repo.append_decision_and_refresh_state(
        NewReviewDecision(
            target_type=ReviewTargetType.RULE_CARD,
            target_id="rule:l:child",
            decision_type=DecisionType.MERGE_INTO,
            reviewer_id="u1",
            related_target_id=fam.family_id,
        )
    )
    members = repo.list_family_members(fam.family_id)
    assert any(m.rule_id == "rule:l:child" for m in members)
    st = repo.get_rule_card_state("rule:l:child")
    assert st is not None
    assert st.canonical_family_id == fam.family_id
