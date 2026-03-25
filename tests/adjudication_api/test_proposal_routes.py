"""HTTP tests for Stage 5.5 proposal API routes."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from pipeline.adjudication.api_errors import AdjudicationApiError, adjudication_api_error_handler
from pipeline.adjudication.api_routes import adjudication_router, init_adjudication
from pipeline.adjudication.bootstrap import initialize_adjudication_storage
from pipeline.adjudication.corpus_inventory import CorpusTargetIndex
from pipeline.adjudication.enums import ProposalStatus, ProposalType, ReviewTargetType, ReviewerKind, QualityTier
from pipeline.adjudication.models import NewReviewDecision, NewReviewer, ProposalRecord
from pipeline.adjudication.proposal_policy import DEFAULT_GENERATOR_VERSION
from pipeline.adjudication.repository import AdjudicationRepository
from pipeline.adjudication.time_utils import utc_now_iso

from pipeline.explorer.contracts import BrowserResultCard, RuleDetailResponse

from tests.adjudication_api.corpus_index_fixtures import STANDARD_TEST_CORPUS_INDEX


def _stub_rule_detail(doc_id: str) -> RuleDetailResponse:
    ev = [
        BrowserResultCard(doc_id="e1", unit_type="evidence_ref", title="e1"),
        BrowserResultCard(doc_id="e2", unit_type="evidence_ref", title="e2"),
    ]
    se = [BrowserResultCard(doc_id="s1", unit_type="knowledge_event", title="s1")]
    return RuleDetailResponse(
        doc_id=doc_id,
        lesson_id="L1",
        lesson_slug=None,
        title="T",
        concept="risk",
        subconcept="stop",
        rule_text="stop loss protects capital in volatile markets",
        rule_text_ru="",
        evidence_refs=ev,
        source_events=se,
    )


class _StubExplorer:
    def get_rule_detail(self, doc_id: str) -> RuleDetailResponse:
        return _stub_rule_detail(doc_id)


@pytest.fixture
def prop_client(tmp_path) -> TestClient:
    db = tmp_path / "prop_api.sqlite"
    init_adjudication(db, explorer=None, corpus_index=STANDARD_TEST_CORPUS_INDEX)
    r = AdjudicationRepository(db)
    r.create_reviewer(NewReviewer(reviewer_id="u1", reviewer_kind=ReviewerKind.HUMAN, display_name="A"))
    app = FastAPI()
    app.add_exception_handler(AdjudicationApiError, adjudication_api_error_handler)
    app.include_router(adjudication_router)
    return TestClient(app)


def test_proposals_generate_503_without_explorer(prop_client: TestClient) -> None:
    r = prop_client.post("/adjudication/proposals/generate", json={})
    assert r.status_code == 503


def test_proposals_list_empty(prop_client: TestClient) -> None:
    r = prop_client.get("/adjudication/proposals")
    assert r.status_code == 200
    assert r.json()["items"] == []


def test_proposal_detail_404(prop_client: TestClient) -> None:
    r = prop_client.get("/adjudication/proposals/does-not-exist")
    assert r.status_code == 404
    assert r.json()["error_code"] == "proposal_not_found"


def test_dismiss_proposal(prop_client: TestClient, tmp_path) -> None:
    db = tmp_path / "d.sqlite"
    initialize_adjudication_storage(db)
    repo = AdjudicationRepository(db)
    now = utc_now_iso()
    rec = ProposalRecord(
        proposal_id="pid-1",
        proposal_type=ProposalType.MERGE_CANDIDATE,
        source_target_type=ReviewTargetType.RULE_CARD,
        source_target_id="rule:http:1",
        related_target_type=ReviewTargetType.RULE_CARD,
        related_target_id="rule:b:1",
        proposal_status=__import__("pipeline.adjudication.enums", fromlist=["ProposalStatus"]).ProposalStatus.NEW,
        score=0.7,
        rationale_summary="x",
        adjudication_snapshot_json="{}",
        tier_snapshot_json="{}",
        queue_priority=0.8,
        dedupe_key="merge|rule_card|a|rule_card|b",
        generator_version=DEFAULT_GENERATOR_VERSION,
        created_at=now,
        updated_at=now,
        last_generated_at=now,
    )
    repo.upsert_proposal(rec)
    init_adjudication(db, explorer=None, corpus_index=STANDARD_TEST_CORPUS_INDEX)
    app = FastAPI()
    app.add_exception_handler(AdjudicationApiError, adjudication_api_error_handler)
    app.include_router(adjudication_router)
    client = TestClient(app)
    dr = client.post("/adjudication/proposals/pid-1/dismiss", json={"note": "nope"})
    assert dr.status_code == 200
    assert dr.json()["proposal_status"] == "dismissed"


def test_decision_with_proposal_id_marks_accepted(prop_client: TestClient, tmp_path) -> None:
    db = tmp_path / "acc.sqlite"
    initialize_adjudication_storage(db)
    repo = AdjudicationRepository(db)
    repo.create_reviewer(NewReviewer(reviewer_id="u1", reviewer_kind=ReviewerKind.HUMAN, display_name="A"))
    now = utc_now_iso()
    rec = ProposalRecord(
        proposal_id="prop-acc-1",
        proposal_type=ProposalType.DUPLICATE_CANDIDATE,
        source_target_type=ReviewTargetType.RULE_CARD,
        source_target_id="rule:w:1",
        related_target_type=ReviewTargetType.RULE_CARD,
        related_target_id="rule:b:1",
        proposal_status=ProposalStatus.NEW,
        score=0.9,
        rationale_summary="x",
        adjudication_snapshot_json="{}",
        tier_snapshot_json="{}",
        queue_priority=1.0,
        dedupe_key="duplicate|rule_card|rule:b:1|rule_card|rule:w:1",
        generator_version=DEFAULT_GENERATOR_VERSION,
        created_at=now,
        updated_at=now,
        last_generated_at=now,
    )
    repo.upsert_proposal(rec)
    init_adjudication(db, explorer=None, corpus_index=STANDARD_TEST_CORPUS_INDEX)
    app = FastAPI()
    app.add_exception_handler(AdjudicationApiError, adjudication_api_error_handler)
    app.include_router(adjudication_router)
    client = TestClient(app)
    pr = client.post(
        "/adjudication/decision",
        json={
            "target_type": "rule_card",
            "target_id": "rule:w:1",
            "decision_type": "duplicate_of",
            "reviewer_id": "u1",
            "related_target_id": "rule:b:1",
            "proposal_id": "prop-acc-1",
        },
    )
    assert pr.status_code == 200
    p2 = repo.get_proposal("prop-acc-1")
    assert p2 is not None
    assert p2.proposal_status == ProposalStatus.ACCEPTED
    assert p2.accepted_decision_id == pr.json()["decision_id"]


def test_proposals_list_filter_by_type(prop_client: TestClient, tmp_path) -> None:
    db = tmp_path / "listf.sqlite"
    initialize_adjudication_storage(db)
    repo = AdjudicationRepository(db)
    repo.create_reviewer(
        NewReviewer(reviewer_id="u1", reviewer_kind=ReviewerKind.HUMAN, display_name="A")
    )
    now = utc_now_iso()
    m = ProposalRecord(
        proposal_id="plist-m",
        proposal_type=ProposalType.MERGE_CANDIDATE,
        source_target_type=ReviewTargetType.RULE_CARD,
        source_target_id="rule:a:1",
        related_target_type=ReviewTargetType.RULE_CARD,
        related_target_id="rule:b:1",
        proposal_status=ProposalStatus.NEW,
        score=0.7,
        rationale_summary="m",
        adjudication_snapshot_json="{}",
        tier_snapshot_json="{}",
        queue_priority=0.8,
        dedupe_key="merge|rule_card|rule:a:1|rule_card|rule:b:1",
        generator_version=DEFAULT_GENERATOR_VERSION,
        created_at=now,
        updated_at=now,
        last_generated_at=now,
    )
    d = ProposalRecord(
        proposal_id="plist-d",
        proposal_type=ProposalType.DUPLICATE_CANDIDATE,
        source_target_type=ReviewTargetType.RULE_CARD,
        source_target_id="rule:http:1",
        related_target_type=ReviewTargetType.RULE_CARD,
        related_target_id="rule:post:1",
        proposal_status=ProposalStatus.NEW,
        score=0.9,
        rationale_summary="d",
        adjudication_snapshot_json="{}",
        tier_snapshot_json="{}",
        queue_priority=1.0,
        dedupe_key="duplicate|rule_card|rule:http:1|rule_card|rule:post:1",
        generator_version=DEFAULT_GENERATOR_VERSION,
        created_at=now,
        updated_at=now,
        last_generated_at=now,
    )
    repo.upsert_proposal(m)
    repo.upsert_proposal(d)
    init_adjudication(db, explorer=None, corpus_index=STANDARD_TEST_CORPUS_INDEX)
    app = FastAPI()
    app.add_exception_handler(AdjudicationApiError, adjudication_api_error_handler)
    app.include_router(adjudication_router)
    client = TestClient(app)
    r = client.get("/adjudication/proposals", params={"proposal_type": "merge_candidate"})
    assert r.status_code == 200
    body = r.json()
    ids = {x["proposal_id"] for x in body["items"]}
    assert ids == {"plist-m"}
    assert body["total"] == 1


def test_proposal_detail_includes_snapshots(prop_client: TestClient, tmp_path) -> None:
    db = tmp_path / "det.sqlite"
    initialize_adjudication_storage(db)
    repo = AdjudicationRepository(db)
    now = utc_now_iso()
    snap = '{"tier": "unresolved"}'
    rec = ProposalRecord(
        proposal_id="pdet-1",
        proposal_type=ProposalType.MERGE_CANDIDATE,
        source_target_type=ReviewTargetType.RULE_CARD,
        source_target_id="rule:w:1",
        related_target_type=ReviewTargetType.RULE_CARD,
        related_target_id="rule:b:1",
        proposal_status=ProposalStatus.NEW,
        score=0.72,
        rationale_summary="r",
        adjudication_snapshot_json='{"state": "x"}',
        tier_snapshot_json=snap,
        queue_priority=0.85,
        dedupe_key="merge|rule_card|rule:b:1|rule_card|rule:w:1",
        generator_version=DEFAULT_GENERATOR_VERSION,
        created_at=now,
        updated_at=now,
        last_generated_at=now,
    )
    repo.upsert_proposal(rec)
    init_adjudication(db, explorer=None, corpus_index=STANDARD_TEST_CORPUS_INDEX)
    app = FastAPI()
    app.add_exception_handler(AdjudicationApiError, adjudication_api_error_handler)
    app.include_router(adjudication_router)
    client = TestClient(app)
    r = client.get("/adjudication/proposals/pdet-1")
    assert r.status_code == 200
    body = r.json()
    assert body["proposal"]["adjudication_snapshot_json"] == '{"state": "x"}'
    assert body["proposal"]["tier_snapshot_json"] == snap
    assert "source_item" in body


def test_proposals_generate_200_with_explorer(tmp_path) -> None:
    db = tmp_path / "gen_ok.sqlite"
    initialize_adjudication_storage(db)
    mini = CorpusTargetIndex(
        rule_card_ids=frozenset({"r1", "r2", "r3", "r4"}),
        evidence_link_ids=frozenset(),
        concept_link_ids=frozenset(),
        related_rule_relation_ids=frozenset(),
    )
    init_adjudication(db, explorer=_StubExplorer(), corpus_index=mini)
    app = FastAPI()
    app.add_exception_handler(AdjudicationApiError, adjudication_api_error_handler)
    app.include_router(adjudication_router)
    client = TestClient(app)
    r = client.post("/adjudication/proposals/generate", json={})
    assert r.status_code == 200
    j = r.json()
    assert j["generator_version"]
    assert j["created"] + j["refreshed"] >= 1


def test_proposals_list_total_independent_of_page_size(tmp_path) -> None:
    db = tmp_path / "tot.sqlite"
    initialize_adjudication_storage(db)
    repo = AdjudicationRepository(db)
    now = utc_now_iso()
    for i in range(3):
        repo.upsert_proposal(
            ProposalRecord(
                proposal_id=f"tot-{i}",
                proposal_type=ProposalType.MERGE_CANDIDATE,
                source_target_type=ReviewTargetType.RULE_CARD,
                source_target_id=f"rule:t{i}:1",
                related_target_type=ReviewTargetType.RULE_CARD,
                related_target_id="rule:t:other",
                proposal_status=ProposalStatus.NEW,
                score=0.7,
                rationale_summary="x",
                adjudication_snapshot_json="{}",
                tier_snapshot_json="{}",
                queue_priority=0.8,
                dedupe_key=f"merge|rule_card|rule:t{i}:1|rule_card|rule:t:other",
                generator_version=DEFAULT_GENERATOR_VERSION,
                created_at=now,
                updated_at=now,
                last_generated_at=now,
            )
        )
    init_adjudication(db, explorer=None, corpus_index=STANDARD_TEST_CORPUS_INDEX)
    app = FastAPI()
    app.add_exception_handler(AdjudicationApiError, adjudication_api_error_handler)
    app.include_router(adjudication_router)
    client = TestClient(app)
    r = client.get("/adjudication/proposals", params={"limit": 1, "offset": 0})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 3
    assert len(body["items"]) == 1


def _upsert_materialized_tier(repo: AdjudicationRepository, target_id: str, tier: str) -> None:
    now = utc_now_iso()
    with repo.connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO materialized_tier_state (
                target_type, target_id, tier, tier_reasons_json, blocker_codes_json,
                is_eligible, is_promotable_to_gold, resolved_at, policy_version
            ) VALUES (?, ?, ?, '[]', '[]', 0, 0, ?, 'audit')
            """,
            (ReviewTargetType.RULE_CARD.value, target_id, tier, now),
        )


def _merge_prop(
    pid: str,
    dedupe: str,
    src: str,
    rel: str,
    now: str,
) -> ProposalRecord:
    return ProposalRecord(
        proposal_id=pid,
        proposal_type=ProposalType.MERGE_CANDIDATE,
        source_target_type=ReviewTargetType.RULE_CARD,
        source_target_id=src,
        related_target_type=ReviewTargetType.RULE_CARD,
        related_target_id=rel,
        proposal_status=ProposalStatus.NEW,
        score=0.75,
        rationale_summary="x",
        adjudication_snapshot_json="{}",
        tier_snapshot_json="{}",
        queue_priority=0.85,
        dedupe_key=dedupe,
        generator_version=DEFAULT_GENERATOR_VERSION,
        created_at=now,
        updated_at=now,
        last_generated_at=now,
    )


def test_queues_proposals_total_and_pagination(tmp_path) -> None:
    db = tmp_path / "qpag.sqlite"
    initialize_adjudication_storage(db)
    repo = AdjudicationRepository(db)
    now = utc_now_iso()
    for i in range(5):
        a, b = f"rule:pag:{i}a", f"rule:pag:{i}b"
        low, high = sorted((a, b))
        repo.upsert_proposal(
            _merge_prop(
                f"qp-{i}",
                f"merge|rule_card|{low}|rule_card|{high}",
                low,
                high,
                now,
            )
        )
    init_adjudication(db, explorer=None, corpus_index=STANDARD_TEST_CORPUS_INDEX)
    app = FastAPI()
    app.add_exception_handler(AdjudicationApiError, adjudication_api_error_handler)
    app.include_router(adjudication_router)
    client = TestClient(app)
    r = client.get(
        "/adjudication/queues/proposals",
        params={"queue": "merge_candidates", "limit": 2, "offset": 0},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 5
    assert len(body["items"]) == 2


def test_queues_proposals_total_respects_queue_type(tmp_path) -> None:
    db = tmp_path / "qmix.sqlite"
    initialize_adjudication_storage(db)
    repo = AdjudicationRepository(db)
    now = utc_now_iso()
    for i in range(2):
        a, b = f"rule:dup:{i}a", f"rule:dup:{i}b"
        low, high = sorted((a, b))
        repo.upsert_proposal(
            ProposalRecord(
                proposal_id=f"d{i}",
                proposal_type=ProposalType.DUPLICATE_CANDIDATE,
                source_target_type=ReviewTargetType.RULE_CARD,
                source_target_id=low,
                related_target_type=ReviewTargetType.RULE_CARD,
                related_target_id=high,
                proposal_status=ProposalStatus.NEW,
                score=0.9,
                rationale_summary="d",
                adjudication_snapshot_json="{}",
                tier_snapshot_json="{}",
                queue_priority=1.0,
                dedupe_key=f"duplicate|rule_card|{low}|rule_card|{high}",
                generator_version=DEFAULT_GENERATOR_VERSION,
                created_at=now,
                updated_at=now,
                last_generated_at=now,
            )
        )
    for i in range(3):
        a, b = f"rule:m:{i}a", f"rule:m:{i}b"
        low, high = sorted((a, b))
        repo.upsert_proposal(
            _merge_prop(
                f"m{i}",
                f"merge|rule_card|{low}|rule_card|{high}",
                low,
                high,
                now,
            )
        )
    init_adjudication(db, explorer=None, corpus_index=STANDARD_TEST_CORPUS_INDEX)
    app = FastAPI()
    app.add_exception_handler(AdjudicationApiError, adjudication_api_error_handler)
    app.include_router(adjudication_router)
    client = TestClient(app)
    mr = client.get("/adjudication/queues/proposals", params={"queue": "merge_candidates"})
    assert mr.status_code == 200
    assert mr.json()["total"] == 3
    dr = client.get("/adjudication/queues/proposals", params={"queue": "high_confidence_duplicates"})
    assert dr.status_code == 200
    assert dr.json()["total"] == 2


def test_queues_proposals_quality_tier_filter_counts(tmp_path) -> None:
    db = tmp_path / "qtier.sqlite"
    initialize_adjudication_storage(db)
    repo = AdjudicationRepository(db)
    now = utc_now_iso()
    _upsert_materialized_tier(repo, "rule:http:1", QualityTier.SILVER.value)
    _upsert_materialized_tier(repo, "rule:a:1", QualityTier.BRONZE.value)
    repo.upsert_proposal(
        _merge_prop(
            "qt1",
            "merge|rule_card|rule:http:1|rule_card|rule:post:1",
            "rule:http:1",
            "rule:post:1",
            now,
        )
    )
    repo.upsert_proposal(
        _merge_prop(
            "qt2",
            "merge|rule_card|rule:a:1|rule_card|rule:b:1",
            "rule:a:1",
            "rule:b:1",
            now,
        )
    )
    init_adjudication(db, explorer=None, corpus_index=STANDARD_TEST_CORPUS_INDEX)
    app = FastAPI()
    app.add_exception_handler(AdjudicationApiError, adjudication_api_error_handler)
    app.include_router(adjudication_router)
    client = TestClient(app)
    r = client.get(
        "/adjudication/queues/proposals",
        params={"queue": "merge_candidates", "quality_tier": "silver"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["proposal_id"] == "qt1"
