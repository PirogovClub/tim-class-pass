"""Integration tests for Stage 5.4 audit fixes (recompute, corpus validation, family refresh, queue)."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from pipeline.adjudication.api_errors import AdjudicationApiError, adjudication_api_error_handler
from pipeline.adjudication.api_routes import adjudication_router, init_adjudication
from pipeline.adjudication.bootstrap import initialize_adjudication_storage
from pipeline.adjudication.enums import (
    CanonicalFamilyStatus,
    DecisionType,
    QualityTier,
    ReviewTargetType,
    ReviewerKind,
)
from pipeline.adjudication.models import NewCanonicalFamily, NewReviewDecision, NewReviewer
from pipeline.adjudication.queue_service import list_unresolved_queue
from pipeline.adjudication.repository import AdjudicationRepository

from tests.adjudication_api.corpus_index_fixtures import STANDARD_TEST_CORPUS_INDEX


def _inventory_total() -> int:
    idx = STANDARD_TEST_CORPUS_INDEX
    return (
        len(idx.rule_card_ids)
        + len(idx.evidence_link_ids)
        + len(idx.concept_link_ids)
        + len(idx.related_rule_relation_ids)
    )


@pytest.fixture
def tier_audit_client(tmp_path) -> TestClient:
    db = tmp_path / "tier_audit.sqlite"
    init_adjudication(db, None, corpus_index=STANDARD_TEST_CORPUS_INDEX)
    repo = AdjudicationRepository(db)
    repo.create_reviewer(NewReviewer(reviewer_id="u1", reviewer_kind=ReviewerKind.HUMAN, display_name="A"))
    app = FastAPI()
    app.add_exception_handler(AdjudicationApiError, adjudication_api_error_handler)
    app.include_router(adjudication_router)
    return TestClient(app)


@pytest.fixture
def repo(tmp_path):
    p = tmp_path / "tier.sqlite"
    initialize_adjudication_storage(p)
    r = AdjudicationRepository(p)
    r.create_reviewer(NewReviewer(reviewer_id="u1", reviewer_kind=ReviewerKind.HUMAN, display_name="A"))
    return r


def test_get_tier_unknown_corpus_target_returns_404(tier_audit_client: TestClient) -> None:
    r = tier_audit_client.get(
        "/adjudication/tier",
        params={"target_type": "rule_card", "target_id": "rule:does_not_exist_in_inventory"},
    )
    assert r.status_code == 404
    assert r.json()["error_code"] == "unknown_corpus_target"


def test_post_recompute_all_matches_inventory(tier_audit_client: TestClient) -> None:
    pr = tier_audit_client.post("/adjudication/tiers/recompute-all")
    assert pr.status_code == 200
    body = pr.json()
    assert body["total"] == _inventory_total()
    cr = tier_audit_client.get("/adjudication/tiers/counts")
    assert cr.status_code == 200
    totals = cr.json()["totals_by_tier"]
    assert sum(totals.values()) == _inventory_total()


def test_recompute_idempotent(repo: AdjudicationRepository) -> None:
    repo.recompute_all_materialized_tiers(STANDARD_TEST_CORPUS_INDEX)
    repo.recompute_all_materialized_tiers(STANDARD_TEST_CORPUS_INDEX)
    t1 = repo.get_materialized_tier(ReviewTargetType.RULE_CARD, "rule:http:1")
    assert t1 is not None
    t2 = repo.get_materialized_tier(ReviewTargetType.RULE_CARD, "rule:http:1")
    assert t1.tier == t2.tier


def test_tier_row_updates_after_decision(tier_audit_client: TestClient) -> None:
    tier_audit_client.post("/adjudication/tiers/recompute-all")
    r0 = tier_audit_client.get(
        "/adjudication/tier", params={"target_type": "rule_card", "target_id": "rule:w:1"}
    )
    assert r0.json()["tier"] == "unresolved"
    pr = tier_audit_client.post(
        "/adjudication/decision",
        json={
            "target_type": "rule_card",
            "target_id": "rule:w:1",
            "decision_type": "approve",
            "reviewer_id": "u1",
        },
    )
    assert pr.status_code == 200
    r1 = tier_audit_client.get(
        "/adjudication/tier", params={"target_type": "rule_card", "target_id": "rule:w:1"}
    )
    assert r1.json()["tier"] == "gold"


def test_duplicate_silver_not_promotable_via_api(tier_audit_client: TestClient) -> None:
    tier_audit_client.post(
        "/adjudication/decision",
        json={
            "target_type": "rule_card",
            "target_id": "rule:dup:1",
            "decision_type": "duplicate_of",
            "reviewer_id": "u1",
            "related_target_id": "rule:b:1",
        },
    )
    r = tier_audit_client.get(
        "/adjudication/tier", params={"target_type": "rule_card", "target_id": "rule:dup:1"}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["tier"] == "silver"
    assert body["is_promotable_to_gold"] is False


def test_family_approve_refreshes_linked_rule_tier(repo: AdjudicationRepository) -> None:
    fam = repo.create_canonical_family(
        NewCanonicalFamily(
            canonical_title="Fam",
            created_by="u1",
            status=CanonicalFamilyStatus.DRAFT,
        )
    )
    repo.append_decision_and_refresh_state(
        NewReviewDecision(
            target_type=ReviewTargetType.RULE_CARD,
            target_id="rule:w:1",
            decision_type=DecisionType.MERGE_INTO,
            reviewer_id="u1",
            related_target_id=fam.family_id,
        )
    )
    t0 = repo.get_materialized_tier(ReviewTargetType.RULE_CARD, "rule:w:1")
    assert t0 is not None
    assert t0.tier == QualityTier.UNRESOLVED
    assert "family_not_active" in t0.blocker_codes

    repo.append_decision_and_refresh_state(
        NewReviewDecision(
            target_type=ReviewTargetType.CANONICAL_RULE_FAMILY,
            target_id=fam.family_id,
            decision_type=DecisionType.APPROVE,
            reviewer_id="u1",
        )
    )
    t1 = repo.get_materialized_tier(ReviewTargetType.RULE_CARD, "rule:w:1")
    assert t1 is not None
    assert t1.tier == QualityTier.SILVER


def test_queue_includes_tier_only_unresolved_evidence(repo: AdjudicationRepository) -> None:
    repo.recompute_all_materialized_tiers(STANDARD_TEST_CORPUS_INDEX)
    repo.append_decision_and_refresh_state(
        NewReviewDecision(
            target_type=ReviewTargetType.EVIDENCE_LINK,
            target_id="ev:1",
            decision_type=DecisionType.EVIDENCE_UNSUPPORTED,
            reviewer_id="u1",
        )
    )
    q = list_unresolved_queue(repo, STANDARD_TEST_CORPUS_INDEX)
    ev_items = [i for i in q.items if i.target_type == ReviewTargetType.EVIDENCE_LINK and i.target_id == "ev:1"]
    assert len(ev_items) == 1
    assert ev_items[0].queue_reason == "unsupported_state"
