"""Stage 5.7 metrics service and HTTP routes."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from pipeline.adjudication.api_errors import AdjudicationApiError, adjudication_api_error_handler
from pipeline.adjudication.api_routes import adjudication_router, init_adjudication
from pipeline.adjudication.enums import (
    CanonicalFamilyStatus,
    DecisionType,
    ProposalStatus,
    ProposalType,
    ReviewTargetType,
    ReviewerKind,
)
from pipeline.adjudication.metrics_enums import ThroughputWindow
from pipeline.adjudication.metrics_service import (
    build_corpus_curation_summary,
    build_coverage_lessons,
    build_flags_distribution,
    build_proposal_usefulness,
    build_queue_health_metrics,
    build_throughput_metrics,
)
from pipeline.adjudication.models import (
    NewCanonicalFamily,
    NewReviewer,
    NewReviewDecision,
    ProposalRecord,
)
from pipeline.adjudication.proposal_policy import DEFAULT_GENERATOR_VERSION
from pipeline.adjudication.repository import AdjudicationRepository
from pipeline.adjudication.time_utils import utc_now_iso

from tests.adjudication_api.corpus_index_fixtures import STANDARD_TEST_CORPUS_INDEX


class _FakeExplorerRepo:
    def __init__(self, docs: list[dict]) -> None:
        self._docs = docs

    def get_all_docs(self) -> list[dict]:
        return self._docs


class _FakeExplorer:
    def __init__(self, docs: list[dict]) -> None:
        self._repo = _FakeExplorerRepo(docs)


@pytest.fixture
def metrics_client(tmp_path) -> TestClient:
    db = tmp_path / "metrics.sqlite"
    init_adjudication(db, explorer=None, corpus_index=STANDARD_TEST_CORPUS_INDEX)
    repo = AdjudicationRepository(db)
    repo.create_reviewer(NewReviewer(reviewer_id="u1", reviewer_kind=ReviewerKind.HUMAN, display_name="A"))
    app = FastAPI()
    app.add_exception_handler(AdjudicationApiError, adjudication_api_error_handler)
    app.include_router(adjudication_router)
    return TestClient(app)


@pytest.fixture
def metrics_repo(tmp_path) -> AdjudicationRepository:
    db = tmp_path / "metrics_repo.sqlite"
    init_adjudication(db, explorer=None, corpus_index=STANDARD_TEST_CORPUS_INDEX)
    repo = AdjudicationRepository(db)
    repo.create_reviewer(NewReviewer(reviewer_id="u1", reviewer_kind=ReviewerKind.HUMAN, display_name="A"))
    return repo


def test_summary_counts_unresolved_and_tiers(metrics_repo: AdjudicationRepository) -> None:
    s = build_corpus_curation_summary(metrics_repo, STANDARD_TEST_CORPUS_INDEX)
    assert s.total_supported_review_targets == len(STANDARD_TEST_CORPUS_INDEX.rule_card_ids) + len(
        STANDARD_TEST_CORPUS_INDEX.evidence_link_ids
    ) + len(STANDARD_TEST_CORPUS_INDEX.concept_link_ids) + len(
        STANDARD_TEST_CORPUS_INDEX.related_rule_relation_ids
    )
    assert s.unresolved_count > 0
    assert s.gold_count == 0
    assert s.merge_decision_count == 0


def test_summary_after_approve_gold(metrics_repo: AdjudicationRepository) -> None:
    metrics_repo.append_decision_and_refresh_state(
        NewReviewDecision(
            target_type=ReviewTargetType.RULE_CARD,
            target_id="rule:w:1",
            decision_type=DecisionType.APPROVE,
            reviewer_id="u1",
        ),
    )
    s = build_corpus_curation_summary(metrics_repo, STANDARD_TEST_CORPUS_INDEX)
    assert s.gold_count >= 1


def test_summary_rejected_and_merge(metrics_repo: AdjudicationRepository) -> None:
    metrics_repo.append_decision_and_refresh_state(
        NewReviewDecision(
            target_type=ReviewTargetType.RULE_CARD,
            target_id="rule:b:1",
            decision_type=DecisionType.REJECT,
            reviewer_id="u1",
        ),
    )
    fam = metrics_repo.create_canonical_family(
        NewCanonicalFamily(canonical_title="F", created_by="u1", status=CanonicalFamilyStatus.DRAFT)
    )
    metrics_repo.append_decision_and_refresh_state(
        NewReviewDecision(
            target_type=ReviewTargetType.RULE_CARD,
            target_id="rule:w:9",
            decision_type=DecisionType.MERGE_INTO,
            reviewer_id="u1",
            related_target_id=fam.family_id,
        ),
    )
    s = build_corpus_curation_summary(metrics_repo, STANDARD_TEST_CORPUS_INDEX)
    assert s.rejected_count >= 1
    assert s.merge_decision_count >= 1


def test_queue_health_matches_unresolved(metrics_repo: AdjudicationRepository) -> None:
    s = build_corpus_curation_summary(metrics_repo, STANDARD_TEST_CORPUS_INDEX)
    q = build_queue_health_metrics(metrics_repo, STANDARD_TEST_CORPUS_INDEX)
    assert q.unresolved_queue_size == s.unresolved_count
    assert isinstance(q.proposal_queue_open_counts, list)


def test_proposal_usefulness_counts(metrics_repo: AdjudicationRepository) -> None:
    now = utc_now_iso()
    metrics_repo.upsert_proposal(
        ProposalRecord(
            proposal_id="p1",
            proposal_type=ProposalType.MERGE_CANDIDATE,
            source_target_type=ReviewTargetType.RULE_CARD,
            source_target_id="rule:http:1",
            related_target_type=ReviewTargetType.RULE_CARD,
            related_target_id="rule:b:1",
            proposal_status=ProposalStatus.NEW,
            score=0.5,
            rationale_summary="r",
            adjudication_snapshot_json="{}",
            tier_snapshot_json="{}",
            queue_priority=0.5,
            dedupe_key="k1",
            generator_version=DEFAULT_GENERATOR_VERSION,
            created_at=now,
            updated_at=now,
            last_generated_at=now,
        )
    )
    metrics_repo.upsert_proposal(
        ProposalRecord(
            proposal_id="p2",
            proposal_type=ProposalType.DUPLICATE_CANDIDATE,
            source_target_type=ReviewTargetType.RULE_CARD,
            source_target_id="rule:a:1",
            proposal_status=ProposalStatus.NEW,
            score=0.6,
            rationale_summary="r2",
            adjudication_snapshot_json="{}",
            tier_snapshot_json="{}",
            queue_priority=0.6,
            dedupe_key="k2",
            generator_version=DEFAULT_GENERATOR_VERSION,
            created_at=now,
            updated_at=now,
            last_generated_at=now,
        )
    )
    # Fresh inserts always normalize to NEW in ``upsert_proposal``; mark terminal state directly.
    with metrics_repo.connect() as conn:
        conn.execute(
            """
            UPDATE adjudication_proposal
            SET proposal_status = ?, accepted_decision_id = ?, updated_at = ?
            WHERE proposal_id = ?
            """,
            (ProposalStatus.ACCEPTED.value, "d1", now, "p2"),
        )
    p = build_proposal_usefulness(metrics_repo)
    assert p.total_proposals == 2
    assert p.open_proposals == 1
    assert p.accepted_proposals == 1
    assert p.acceptance_rate_all == 0.5
    assert p.acceptance_rate_closed == 1.0


def test_throughput_window_filter(metrics_repo: AdjudicationRepository) -> None:
    metrics_repo.append_decision(
        NewReviewDecision(
            target_type=ReviewTargetType.RULE_CARD,
            target_id="rule:q:1",
            decision_type=DecisionType.APPROVE,
            reviewer_id="u1",
        ),
    )
    t = build_throughput_metrics(metrics_repo, ThroughputWindow.DAYS_30)
    assert t.decision_count >= 1
    assert any(r.decision_type == "approve" for r in t.by_decision_type)
    assert any(r.reviewer_id == "u1" for r in t.by_reviewer_id)

    old_id = metrics_repo.append_decision(
        NewReviewDecision(
            target_type=ReviewTargetType.RULE_CARD,
            target_id="rule:q:z",
            decision_type=DecisionType.REJECT,
            reviewer_id="u1",
        ),
    ).decision_id
    ancient = "2000-01-01T00:00:00+00:00"
    with metrics_repo.connect() as conn:
        conn.execute(
            "UPDATE review_decisions SET created_at = ? WHERE decision_id = ?",
            (ancient, old_id),
        )
    t7 = build_throughput_metrics(metrics_repo, ThroughputWindow.DAYS_7)
    assert t7.decision_count >= 1
    types_7 = {r.decision_type for r in t7.by_decision_type}
    assert "reject" not in types_7


def test_coverage_lessons_with_explorer(metrics_repo: AdjudicationRepository) -> None:
    docs = [
        {
            "doc_id": "rule:w:1",
            "unit_type": "rule_card",
            "lesson_id": "L-test",
            "canonical_concept_ids": ["c1"],
        },
        {
            "doc_id": "ev:1",
            "unit_type": "evidence_ref",
            "lesson_id": "L-test",
            "canonical_concept_ids": ["c1"],
        },
    ]
    ex = _FakeExplorer(docs)
    metrics_repo.append_decision_and_refresh_state(
        NewReviewDecision(
            target_type=ReviewTargetType.RULE_CARD,
            target_id="rule:w:1",
            decision_type=DecisionType.APPROVE,
            reviewer_id="u1",
        ),
    )
    cov = build_coverage_lessons(metrics_repo, STANDARD_TEST_CORPUS_INDEX, ex)
    assert cov.explorer_available is True
    by_id = {b.bucket_id: b for b in cov.buckets}
    assert "L-test" in by_id
    assert by_id["L-test"].total_targets >= 1
    assert by_id["L-test"].reviewed_not_unresolved >= 1
    assert by_id["L-test"].coverage_ratio is not None


def test_coverage_without_explorer_empty_buckets(metrics_repo: AdjudicationRepository) -> None:
    cov = build_coverage_lessons(metrics_repo, STANDARD_TEST_CORPUS_INDEX, None)
    assert cov.explorer_available is False
    assert cov.buckets == []


def test_flags_summary(metrics_repo: AdjudicationRepository) -> None:
    metrics_repo.append_decision_and_refresh_state(
        NewReviewDecision(
            target_type=ReviewTargetType.RULE_CARD,
            target_id="rule:x:1",
            decision_type=DecisionType.AMBIGUOUS,
            reviewer_id="u1",
        ),
    )
    f = build_flags_distribution(metrics_repo, STANDARD_TEST_CORPUS_INDEX, None)
    assert f.summary.ambiguity_rule_cards >= 1


def test_http_metrics_shapes(metrics_client: TestClient) -> None:
    r = metrics_client.get("/adjudication/metrics/summary")
    assert r.status_code == 200
    body = r.json()
    assert "gold_count" in body
    assert "unresolved_count" in body

    r2 = metrics_client.get("/adjudication/metrics/queues")
    assert r2.status_code == 200

    r3 = metrics_client.get("/adjudication/metrics/proposals")
    assert r3.status_code == 200

    r4 = metrics_client.get("/adjudication/metrics/throughput", params={"window": "7d"})
    assert r4.status_code == 200

    r5 = metrics_client.get("/adjudication/metrics/coverage/lessons")
    assert r5.status_code == 200
    assert r5.json()["explorer_available"] is False

    r6 = metrics_client.get("/adjudication/metrics/flags")
    assert r6.status_code == 200


def test_http_throughput_bad_window(metrics_client: TestClient) -> None:
    r = metrics_client.get("/adjudication/metrics/throughput", params={"window": "1y"})
    assert r.status_code == 400
