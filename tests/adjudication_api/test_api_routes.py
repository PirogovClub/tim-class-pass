"""HTTP-level tests for adjudication routes."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from pipeline.adjudication.api_errors import AdjudicationApiError, adjudication_api_error_handler
from pipeline.adjudication.api_routes import adjudication_router, init_adjudication
from pipeline.adjudication.enums import DecisionType, ReviewTargetType, ReviewerKind
from pipeline.adjudication.models import NewReviewDecision, NewReviewer
from pipeline.adjudication.repository import AdjudicationRepository

from tests.adjudication_api.corpus_index_fixtures import STANDARD_TEST_CORPUS_INDEX


@pytest.fixture
def client_with_reviewer(tmp_path) -> TestClient:
    db = tmp_path / "x.sqlite"
    init_adjudication(db, None, corpus_index=STANDARD_TEST_CORPUS_INDEX)
    repo = AdjudicationRepository(db)
    repo.create_reviewer(NewReviewer(reviewer_id="u1", reviewer_kind=ReviewerKind.HUMAN, display_name="A"))
    app = FastAPI()
    app.add_exception_handler(AdjudicationApiError, adjudication_api_error_handler)
    app.include_router(adjudication_router)
    return TestClient(app)


def test_review_item_ok(client_with_reviewer) -> None:
    r = client_with_reviewer.get(
        "/adjudication/review-item",
        params={"target_type": "rule_card", "target_id": "rule:http:1"},
    )
    assert r.status_code == 200
    assert r.json()["target_id"] == "rule:http:1"


def test_review_history_ok(client_with_reviewer) -> None:
    r = client_with_reviewer.get(
        "/adjudication/review-history",
        params={"target_type": "rule_card", "target_id": "rule:http:1"},
    )
    assert r.status_code == 200
    assert r.json()["decisions"] == []


def test_family_404(client_with_reviewer) -> None:
    r = client_with_reviewer.get("/adjudication/families/missing-id")
    assert r.status_code == 404
    assert r.json()["error_code"] == "not_found"


def test_family_members_404(client_with_reviewer) -> None:
    r = client_with_reviewer.get("/adjudication/families/missing-id/members")
    assert r.status_code == 404


def test_review_bundle_ok(client_with_reviewer, tmp_path) -> None:
    db = tmp_path / "x.sqlite"
    repo = AdjudicationRepository(db)
    repo.append_decision_and_refresh_state(
        NewReviewDecision(
            target_type=ReviewTargetType.RULE_CARD,
            target_id="rule:b:1",
            decision_type=DecisionType.NEEDS_REVIEW,
            reviewer_id="u1",
        )
    )
    r = client_with_reviewer.get(
        "/adjudication/review-bundle",
        params={"target_type": "rule_card", "target_id": "rule:b:1"},
    )
    assert r.status_code == 200
    assert len(r.json()["history"]) == 1


def test_decision_post_ok(client_with_reviewer) -> None:
    r = client_with_reviewer.post(
        "/adjudication/decision",
        json={
            "target_type": "rule_card",
            "target_id": "rule:post:1",
            "decision_type": "approve",
            "reviewer_id": "u1",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["decision_id"]
    assert body["updated_state"]["latest_decision_type"] == "approve"


def test_decision_unknown_reviewer(client_with_reviewer) -> None:
    r = client_with_reviewer.post(
        "/adjudication/decision",
        json={
            "target_type": "rule_card",
            "target_id": "rule:post:2",
            "decision_type": "approve",
            "reviewer_id": "nobody",
        },
    )
    assert r.status_code == 404
    assert r.json()["error_code"] == "unknown_reviewer"


def test_decision_invalid_pair(client_with_reviewer) -> None:
    r = client_with_reviewer.post(
        "/adjudication/decision",
        json={
            "target_type": "evidence_link",
            "target_id": "ev:1",
            "decision_type": "duplicate_of",
            "reviewer_id": "u1",
            "related_target_id": "rule:x",
        },
    )
    assert r.status_code == 400
    assert r.json()["error_code"] == "invalid_target_decision_pair"


def test_queues_unresolved(client_with_reviewer, tmp_path) -> None:
    db = tmp_path / "x.sqlite"
    repo = AdjudicationRepository(db)
    repo.append_decision_and_refresh_state(
        NewReviewDecision(
            target_type=ReviewTargetType.RULE_CARD,
            target_id="rule:qq:1",
            decision_type=DecisionType.NEEDS_REVIEW,
            reviewer_id="u1",
        )
    )
    r = client_with_reviewer.get("/adjudication/queues/unresolved")
    assert r.status_code == 200
    assert r.json()["total"] >= 1


def test_queues_next(client_with_reviewer, tmp_path) -> None:
    db = tmp_path / "x.sqlite"
    repo = AdjudicationRepository(db)
    repo.append_decision_and_refresh_state(
        NewReviewDecision(
            target_type=ReviewTargetType.RULE_CARD,
            target_id="rule:qn:1",
            decision_type=DecisionType.DEFER,
            reviewer_id="u1",
        )
    )
    r = client_with_reviewer.get(
        "/adjudication/queues/next",
        params={"queue": "unresolved", "target_type": "rule_card"},
    )
    assert r.status_code == 200
    assert r.json()["target_id"] == "rule:qn:1"


def test_bad_target_type_query(client_with_reviewer) -> None:
    r = client_with_reviewer.get(
        "/adjudication/review-item",
        params={"target_type": "not_real", "target_id": "x"},
    )
    assert r.status_code == 400
    assert r.json()["error_code"] == "validation_error"


def test_malformed_json_decision(client_with_reviewer) -> None:
    r = client_with_reviewer.post(
        "/adjudication/decision",
        content="not-json",
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 422


def test_decision_missing_related_duplicate_of(client_with_reviewer) -> None:
    r = client_with_reviewer.post(
        "/adjudication/decision",
        json={
            "target_type": "rule_card",
            "target_id": "rule:dup:1",
            "decision_type": "duplicate_of",
            "reviewer_id": "u1",
        },
    )
    assert r.status_code == 422
    assert r.json()["error_code"] == "validation_error"
