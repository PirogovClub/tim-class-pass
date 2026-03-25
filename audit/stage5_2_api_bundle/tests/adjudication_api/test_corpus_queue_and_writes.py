"""Audit follow-up: corpus-backed queues and write-time corpus validation."""

from __future__ import annotations

import pytest

from pipeline.adjudication.api_errors import AdjudicationApiError
from pipeline.adjudication.api_models import DecisionSubmissionRequest
from pipeline.adjudication.api_service import submit_decision
from pipeline.adjudication.bootstrap import initialize_adjudication_storage
from pipeline.adjudication.corpus_inventory import CorpusTargetIndex
from pipeline.adjudication.enums import DecisionType, ReviewTargetType, ReviewerKind
from pipeline.adjudication.models import NewReviewDecision, NewReviewer
from pipeline.adjudication.queue_service import get_next_queue_item, list_unresolved_queue
from pipeline.adjudication.repository import AdjudicationRepository

from tests.adjudication_api.corpus_index_fixtures import STANDARD_TEST_CORPUS_INDEX


@pytest.fixture
def repo(tmp_path):
    p = tmp_path / "c.db"
    initialize_adjudication_storage(p)
    r = AdjudicationRepository(p)
    r.create_reviewer(NewReviewer(reviewer_id="u1", reviewer_kind=ReviewerKind.HUMAN, display_name="A"))
    return r


def test_queue_includes_corpus_rule_without_adjudication_state(repo) -> None:
    idx = CorpusTargetIndex(
        rule_card_ids=frozenset({"rule:corpus:fresh", "rule:corpus:reviewed"}),
        evidence_link_ids=frozenset(),
        concept_link_ids=frozenset(),
        related_rule_relation_ids=frozenset(),
    )
    repo.append_decision_and_refresh_state(
        NewReviewDecision(
            target_type=ReviewTargetType.RULE_CARD,
            target_id="rule:corpus:reviewed",
            decision_type=DecisionType.NEEDS_REVIEW,
            reviewer_id="u1",
        )
    )
    q = list_unresolved_queue(repo, idx)
    ids = {(i.target_type, i.target_id, i.queue_reason) for i in q.items}
    assert (ReviewTargetType.RULE_CARD, "rule:corpus:fresh", "no_adjudication_state") in ids
    assert any(
        i.target_id == "rule:corpus:reviewed" and i.target_type == ReviewTargetType.RULE_CARD
        for i in q.items
    )


def test_queues_next_returns_never_reviewed_corpus_rule(repo) -> None:
    idx = CorpusTargetIndex(
        rule_card_ids=frozenset({"rule:corpus:next"}),
        evidence_link_ids=frozenset(),
        concept_link_ids=frozenset(),
        related_rule_relation_ids=frozenset(),
    )
    n = get_next_queue_item(repo, "unresolved", ReviewTargetType.RULE_CARD, idx)
    assert n is not None
    assert n.target_id == "rule:corpus:next"
    assert n.queue_reason == "no_adjudication_state"


def test_orphan_state_not_in_queue_when_not_in_inventory(repo) -> None:
    idx = CorpusTargetIndex(
        rule_card_ids=frozenset({"rule:corpus:only"}),
        evidence_link_ids=frozenset(),
        concept_link_ids=frozenset(),
        related_rule_relation_ids=frozenset(),
    )
    repo.append_decision_and_refresh_state(
        NewReviewDecision(
            target_type=ReviewTargetType.RULE_CARD,
            target_id="rule:not:in:inventory",
            decision_type=DecisionType.NEEDS_REVIEW,
            reviewer_id="u1",
        )
    )
    q = list_unresolved_queue(repo, idx)
    assert not any(i.target_id == "rule:not:in:inventory" for i in q.items)
    assert any(i.target_id == "rule:corpus:only" for i in q.items)


def test_submit_rejects_unknown_rule_card(repo) -> None:
    with pytest.raises(AdjudicationApiError) as ei:
        submit_decision(
            repo,
            DecisionSubmissionRequest(
                target_type=ReviewTargetType.RULE_CARD,
                target_id="rule:totally:unknown:xyz",
                decision_type=DecisionType.APPROVE,
                reviewer_id="u1",
            ),
            STANDARD_TEST_CORPUS_INDEX,
        )
    assert ei.value.error_code == "unknown_corpus_target"


def test_submit_rejects_unknown_evidence_link(repo) -> None:
    with pytest.raises(AdjudicationApiError) as ei:
        submit_decision(
            repo,
            DecisionSubmissionRequest(
                target_type=ReviewTargetType.EVIDENCE_LINK,
                target_id="ev:does:not:exist",
                decision_type=DecisionType.EVIDENCE_STRONG,
                reviewer_id="u1",
            ),
            STANDARD_TEST_CORPUS_INDEX,
        )
    assert ei.value.error_code == "unknown_corpus_target"


def test_submit_rejects_unknown_concept_link(repo) -> None:
    with pytest.raises(AdjudicationApiError) as ei:
        submit_decision(
            repo,
            DecisionSubmissionRequest(
                target_type=ReviewTargetType.CONCEPT_LINK,
                target_id="rel:node:fake:rel:node:nope",
                decision_type=DecisionType.CONCEPT_VALID,
                reviewer_id="u1",
            ),
            STANDARD_TEST_CORPUS_INDEX,
        )
    assert ei.value.error_code == "unknown_corpus_target"


def test_submit_rejects_unknown_related_rule_relation(repo) -> None:
    with pytest.raises(AdjudicationApiError) as ei:
        submit_decision(
            repo,
            DecisionSubmissionRequest(
                target_type=ReviewTargetType.RELATED_RULE_RELATION,
                target_id="rel:rule:x:r1:fake:rule:x:r9",
                decision_type=DecisionType.RELATION_VALID,
                reviewer_id="u1",
            ),
            STANDARD_TEST_CORPUS_INDEX,
        )
    assert ei.value.error_code == "unknown_corpus_target"


def test_submit_accepts_inventory_concept_link(repo) -> None:
    out = submit_decision(
        repo,
        DecisionSubmissionRequest(
            target_type=ReviewTargetType.CONCEPT_LINK,
            target_id="rel:node:concept_link_test:relates_to:node:other",
            decision_type=DecisionType.CONCEPT_VALID,
            reviewer_id="u1",
        ),
        STANDARD_TEST_CORPUS_INDEX,
    )
    assert out.updated_state.link_status == "valid"


def test_submit_accepts_inventory_related_rule_relation(repo) -> None:
    out = submit_decision(
        repo,
        DecisionSubmissionRequest(
            target_type=ReviewTargetType.RELATED_RULE_RELATION,
            target_id="rel:rule:lesson_a:r1:relates_to:rule:lesson_a:r2",
            decision_type=DecisionType.RELATION_VALID,
            reviewer_id="u1",
        ),
        STANDARD_TEST_CORPUS_INDEX,
    )
    assert out.updated_state.relation_status == "valid"


def test_duplicate_of_rejects_unknown_related_rule(repo) -> None:
    with pytest.raises(AdjudicationApiError) as ei:
        submit_decision(
            repo,
            DecisionSubmissionRequest(
                target_type=ReviewTargetType.RULE_CARD,
                target_id="rule:w:1",
                decision_type=DecisionType.DUPLICATE_OF,
                reviewer_id="u1",
                related_target_id="rule:no:such:duplicate:peer",
            ),
            STANDARD_TEST_CORPUS_INDEX,
        )
    assert ei.value.error_code == "unknown_corpus_target"
    assert ei.value.details is not None
    assert ei.value.details.get("field") == "related_target_id"


def test_family_target_still_rejects_unknown_family_without_corpus(repo) -> None:
    with pytest.raises(AdjudicationApiError) as ei:
        submit_decision(
            repo,
            DecisionSubmissionRequest(
                target_type=ReviewTargetType.CANONICAL_RULE_FAMILY,
                target_id="not-a-family",
                decision_type=DecisionType.APPROVE,
                reviewer_id="u1",
            ),
            None,
        )
    assert ei.value.error_code == "unknown_family"
