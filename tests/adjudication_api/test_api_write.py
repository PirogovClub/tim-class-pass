from __future__ import annotations

import pytest

from pipeline.adjudication.api_errors import AdjudicationApiError
from pipeline.adjudication.api_models import DecisionSubmissionRequest
from pipeline.adjudication.api_service import submit_decision
from pipeline.adjudication.bootstrap import initialize_adjudication_storage
from pipeline.adjudication.enums import (
    CanonicalFamilyStatus,
    DecisionType,
    ReviewTargetType,
    ReviewerKind,
)
from pipeline.adjudication.models import NewCanonicalFamily, NewReviewer
from pipeline.adjudication.repository import AdjudicationRepository

from tests.adjudication_api.corpus_index_fixtures import STANDARD_TEST_CORPUS_INDEX


@pytest.fixture
def repo(tmp_path):
    p = tmp_path / "a.db"
    initialize_adjudication_storage(p)
    r = AdjudicationRepository(p)
    r.create_reviewer(NewReviewer(reviewer_id="u1", reviewer_kind=ReviewerKind.HUMAN, display_name="A"))
    return r


def test_submit_valid(repo) -> None:
    req = DecisionSubmissionRequest(
        target_type=ReviewTargetType.RULE_CARD,
        target_id="rule:w:1",
        decision_type=DecisionType.APPROVE,
        reviewer_id="u1",
    )
    out = submit_decision(repo, req, STANDARD_TEST_CORPUS_INDEX)
    assert out.success
    assert out.updated_state.latest_decision_type == "approve"


def test_submit_unknown_reviewer(repo) -> None:
    with pytest.raises(AdjudicationApiError) as ei:
        submit_decision(
            repo,
            DecisionSubmissionRequest(
                target_type=ReviewTargetType.RULE_CARD,
                target_id="rule:w:1",
                decision_type=DecisionType.APPROVE,
                reviewer_id="ghost",
            ),
            STANDARD_TEST_CORPUS_INDEX,
        )
    assert ei.value.error_code == "unknown_reviewer"


def test_submit_invalid_pair(repo) -> None:
    with pytest.raises(AdjudicationApiError) as ei:
        submit_decision(
            repo,
            DecisionSubmissionRequest(
                target_type=ReviewTargetType.EVIDENCE_LINK,
                target_id="ev:1",
                decision_type=DecisionType.DUPLICATE_OF,
                reviewer_id="u1",
                related_target_id="rule:x",
            ),
            STANDARD_TEST_CORPUS_INDEX,
        )
    assert ei.value.error_code == "invalid_target_decision_pair"


def test_submit_missing_family_merge(repo) -> None:
    with pytest.raises(AdjudicationApiError) as ei:
        submit_decision(
            repo,
            DecisionSubmissionRequest(
                target_type=ReviewTargetType.RULE_CARD,
                target_id="rule:w:1",
                decision_type=DecisionType.MERGE_INTO,
                reviewer_id="u1",
                related_target_id="no-family",
            ),
            STANDARD_TEST_CORPUS_INDEX,
        )
    assert ei.value.error_code == "unknown_family"


def test_submit_family_target_missing_family(repo) -> None:
    with pytest.raises(AdjudicationApiError) as ei:
        submit_decision(
            repo,
            DecisionSubmissionRequest(
                target_type=ReviewTargetType.CANONICAL_RULE_FAMILY,
                target_id="nope",
                decision_type=DecisionType.APPROVE,
                reviewer_id="u1",
            ),
            None,
        )
    assert ei.value.error_code == "unknown_family"


def test_submit_merge_family_linkage_summary(repo) -> None:
    fam = repo.create_canonical_family(
        NewCanonicalFamily(canonical_title="F", created_by="u1", status=CanonicalFamilyStatus.DRAFT)
    )
    out = submit_decision(
        repo,
        DecisionSubmissionRequest(
            target_type=ReviewTargetType.RULE_CARD,
            target_id="rule:w:9",
            decision_type=DecisionType.MERGE_INTO,
            reviewer_id="u1",
            related_target_id=fam.family_id,
        ),
        STANDARD_TEST_CORPUS_INDEX,
    )
    assert out.family_linkage_summary is not None
    assert out.family_linkage_summary["merge_into_family_id"] == fam.family_id
