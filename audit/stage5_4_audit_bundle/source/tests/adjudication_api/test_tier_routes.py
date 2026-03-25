"""HTTP tests for Stage 5.4 tier endpoints."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from pipeline.adjudication.api_errors import AdjudicationApiError, adjudication_api_error_handler
from pipeline.adjudication.api_routes import adjudication_router, init_adjudication
from pipeline.adjudication.enums import ReviewerKind
from pipeline.adjudication.models import NewReviewer
from pipeline.adjudication.repository import AdjudicationRepository

from tests.adjudication_api.corpus_index_fixtures import STANDARD_TEST_CORPUS_INDEX


@pytest.fixture
def client_with_reviewer(tmp_path) -> TestClient:
    db = tmp_path / "tier.sqlite"
    init_adjudication(db, None, corpus_index=STANDARD_TEST_CORPUS_INDEX)
    repo = AdjudicationRepository(db)
    repo.create_reviewer(NewReviewer(reviewer_id="u1", reviewer_kind=ReviewerKind.HUMAN, display_name="A"))
    app = FastAPI()
    app.add_exception_handler(AdjudicationApiError, adjudication_api_error_handler)
    app.include_router(adjudication_router)
    return TestClient(app)


def test_tier_unresolved_without_decision(client_with_reviewer: TestClient) -> None:
    r = client_with_reviewer.get(
        "/adjudication/tier",
        params={"target_type": "rule_card", "target_id": "rule:http:1"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["tier"] == "unresolved"
    assert "no_adjudication_state" in body["blocker_codes"]


def test_tier_gold_after_approve(client_with_reviewer: TestClient) -> None:
    rid = "rule:w:1"
    pr = client_with_reviewer.post(
        "/adjudication/decision",
        json={
            "target_type": "rule_card",
            "target_id": rid,
            "decision_type": "approve",
            "reviewer_id": "u1",
        },
    )
    assert pr.status_code == 200, pr.text
    r = client_with_reviewer.get(
        "/adjudication/tier",
        params={"target_type": "rule_card", "target_id": rid},
    )
    assert r.status_code == 200
    assert r.json()["tier"] == "gold"
    assert r.json()["is_eligible_for_downstream_use"] is True


def test_tiers_counts(client_with_reviewer: TestClient) -> None:
    r = client_with_reviewer.get("/adjudication/tiers/counts")
    assert r.status_code == 200
    data = r.json()
    assert "by_target_type" in data
    assert "totals_by_tier" in data


def test_tiers_by_tier_filter(client_with_reviewer: TestClient) -> None:
    client_with_reviewer.post(
        "/adjudication/decision",
        json={
            "target_type": "rule_card",
            "target_id": "rule:b:1",
            "decision_type": "approve",
            "reviewer_id": "u1",
        },
    )
    r = client_with_reviewer.get(
        "/adjudication/tiers/by-tier",
        params={"tier": "gold", "target_type": "rule_card"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["tier"] == "gold"
    assert any(i["target_id"] == "rule:b:1" for i in body["items"])


def test_tier_bad_target_type(client_with_reviewer: TestClient) -> None:
    r = client_with_reviewer.get(
        "/adjudication/tier",
        params={"target_type": "canonical_rule_family", "target_id": "fam-1"},
    )
    assert r.status_code == 400
