from __future__ import annotations

import pytest

from pipeline.adjudication.bootstrap import initialize_adjudication_storage
from pipeline.adjudication.corpus_inventory import CorpusTargetIndex
from pipeline.adjudication.enums import DecisionType, ReviewTargetType, ReviewerKind
from pipeline.adjudication.models import NewReviewDecision, NewReviewer
from pipeline.adjudication.queue_service import (
    get_next_queue_item,
    list_queue_by_target,
    list_unresolved_queue,
)
from pipeline.adjudication.repository import AdjudicationRepository


@pytest.fixture
def repo(tmp_path):
    p = tmp_path / "a.db"
    initialize_adjudication_storage(p)
    r = AdjudicationRepository(p)
    r.create_reviewer(NewReviewer(reviewer_id="u1", reviewer_kind=ReviewerKind.HUMAN, display_name="A"))
    return r


def test_unresolved_deterministic_order(repo) -> None:
    idx = CorpusTargetIndex(
        rule_card_ids=frozenset({"rule:q:a", "rule:q:b"}),
        evidence_link_ids=frozenset(),
        concept_link_ids=frozenset(),
        related_rule_relation_ids=frozenset(),
    )
    repo.append_decision_and_refresh_state(
        NewReviewDecision(
            target_type=ReviewTargetType.RULE_CARD,
            target_id="rule:q:b",
            decision_type=DecisionType.NEEDS_REVIEW,
            reviewer_id="u1",
        )
    )
    repo.append_decision_and_refresh_state(
        NewReviewDecision(
            target_type=ReviewTargetType.RULE_CARD,
            target_id="rule:q:a",
            decision_type=DecisionType.NEEDS_REVIEW,
            reviewer_id="u1",
        )
    )
    q1 = list_unresolved_queue(repo, idx)
    q2 = list_unresolved_queue(repo, idx)
    assert q1.total == q2.total
    assert [i.target_id for i in q1.items] == [i.target_id for i in q2.items]
    rule_ids = {i.target_id for i in q1.items if i.target_type == ReviewTargetType.RULE_CARD}
    assert rule_ids == {"rule:q:a", "rule:q:b"}


def test_by_target_filter(repo) -> None:
    idx = CorpusTargetIndex(
        rule_card_ids=frozenset({"rule:q:1"}),
        evidence_link_ids=frozenset({"ev:q:1"}),
        concept_link_ids=frozenset(),
        related_rule_relation_ids=frozenset(),
    )
    repo.append_decision_and_refresh_state(
        NewReviewDecision(
            target_type=ReviewTargetType.RULE_CARD,
            target_id="rule:q:1",
            decision_type=DecisionType.DEFER,
            reviewer_id="u1",
        )
    )
    repo.append_decision_and_refresh_state(
        NewReviewDecision(
            target_type=ReviewTargetType.EVIDENCE_LINK,
            target_id="ev:q:1",
            decision_type=DecisionType.EVIDENCE_PARTIAL,
            reviewer_id="u1",
        )
    )
    by_rule = list_queue_by_target(repo, ReviewTargetType.RULE_CARD, idx)
    assert all(i.target_type == ReviewTargetType.RULE_CARD for i in by_rule.items)


def test_next_first_item(repo) -> None:
    idx = CorpusTargetIndex(
        rule_card_ids=frozenset({"rule:q:z"}),
        evidence_link_ids=frozenset(),
        concept_link_ids=frozenset(),
        related_rule_relation_ids=frozenset(),
    )
    repo.append_decision_and_refresh_state(
        NewReviewDecision(
            target_type=ReviewTargetType.RULE_CARD,
            target_id="rule:q:z",
            decision_type=DecisionType.DEFER,
            reviewer_id="u1",
        )
    )
    n = get_next_queue_item(repo, "unresolved", None, idx)
    assert n is not None
    assert n.target_id == "rule:q:z"


def test_next_filtered(repo) -> None:
    idx = CorpusTargetIndex(
        rule_card_ids=frozenset({"rule:q:only"}),
        evidence_link_ids=frozenset(),
        concept_link_ids=frozenset(),
        related_rule_relation_ids=frozenset(),
    )
    repo.append_decision_and_refresh_state(
        NewReviewDecision(
            target_type=ReviewTargetType.RULE_CARD,
            target_id="rule:q:only",
            decision_type=DecisionType.AMBIGUOUS,
            reviewer_id="u1",
        )
    )
    n = get_next_queue_item(repo, "unresolved", ReviewTargetType.EVIDENCE_LINK, idx)
    assert n is None


def test_empty_queue_stable(repo) -> None:
    empty = CorpusTargetIndex.empty()
    q = list_unresolved_queue(repo, empty)
    assert q.total == 0
    assert q.items == []
