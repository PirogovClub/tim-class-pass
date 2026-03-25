"""Repository tests for adjudication_proposal (Stage 5.5)."""

from __future__ import annotations

import json

import pytest

from pipeline.adjudication.bootstrap import initialize_adjudication_storage
from pipeline.adjudication.enums import DecisionType, ProposalStatus, ProposalType, ReviewTargetType
from pipeline.adjudication.enums import ReviewerKind
from pipeline.adjudication.models import NewReviewDecision, NewReviewer, ProposalRecord
from pipeline.adjudication.corpus_inventory import CorpusTargetIndex
from pipeline.adjudication.proposal_policy import DEFAULT_GENERATOR_VERSION
from pipeline.adjudication.repository import (
    STALE_AFTER_DECISION_REASON,
    STALE_NOT_IN_INVENTORY_REASON,
    AdjudicationRepository,
)
from pipeline.adjudication.time_utils import utc_now_iso


def _sample_record(dedupe: str, pid: str) -> ProposalRecord:
    now = utc_now_iso()
    return ProposalRecord(
        proposal_id=pid,
        proposal_type=ProposalType.MERGE_CANDIDATE,
        source_target_type=ReviewTargetType.RULE_CARD,
        source_target_id="a",
        related_target_type=ReviewTargetType.RULE_CARD,
        related_target_id="b",
        proposal_status=ProposalStatus.NEW,
        score=0.75,
        rationale_summary="test",
        adjudication_snapshot_json=json.dumps({"k": 1}),
        tier_snapshot_json=json.dumps({"k": 2}),
        queue_priority=0.9,
        dedupe_key=dedupe,
        generator_version=DEFAULT_GENERATOR_VERSION,
        created_at=now,
        updated_at=now,
        last_generated_at=now,
    )


@pytest.fixture
def repo(tmp_path):
    p = tmp_path / "pr.sqlite"
    initialize_adjudication_storage(p)
    return AdjudicationRepository(p)


def test_proposal_upsert_created(repo: AdjudicationRepository) -> None:
    rec = _sample_record("merge|rule_card|a|rule_card|b", "10000000-0000-0000-0000-000000000001")
    out, kind = repo.upsert_proposal(rec)
    assert kind == "created"
    got = repo.get_proposal_by_dedupe_key(rec.dedupe_key)
    assert got is not None
    assert got.score == 0.75


def test_proposal_refresh_updates_score(repo: AdjudicationRepository) -> None:
    rec = _sample_record("merge|rule_card|x|rule_card|y", "10000000-0000-0000-0000-000000000002")
    repo.upsert_proposal(rec)
    rec2 = rec.model_copy(update={"score": 0.81, "rationale_summary": "updated"})
    out, kind = repo.upsert_proposal(rec2)
    assert kind == "refreshed"
    assert out.score == 0.81


def test_dismissed_not_overwritten_on_upsert(repo: AdjudicationRepository) -> None:
    rec = _sample_record("dup|rule_card|p|rule_card|q", "10000000-0000-0000-0000-000000000003")
    repo.upsert_proposal(rec)
    p = repo.get_proposal_by_dedupe_key(rec.dedupe_key)
    assert p is not None
    repo.mark_proposal_dismissed(p.proposal_id, "no")
    rec2 = rec.model_copy(update={"score": 0.99})
    out, kind = repo.upsert_proposal(rec2)
    assert kind == "unchanged"
    assert out.proposal_status == ProposalStatus.DISMISSED


def test_mark_missing_stale(repo: AdjudicationRepository) -> None:
    r1 = _sample_record("k1", "10000000-0000-0000-0000-000000000011")
    r2 = _sample_record("k2", "10000000-0000-0000-0000-000000000012")
    repo.upsert_proposal(r1)
    repo.upsert_proposal(r2)
    n = repo.mark_missing_generated_proposals_stale(DEFAULT_GENERATOR_VERSION, {"k1"})
    assert n >= 1
    left = repo.get_proposal_by_dedupe_key("k2")
    assert left is not None
    assert left.proposal_status == ProposalStatus.STALE


def test_list_open_proposals_by_queue_filters_status(repo: AdjudicationRepository) -> None:
    rec = _sample_record(
        "duplicate|rule_card|m|rule_card|n", "10000000-0000-0000-0000-000000000021"
    )
    rec = rec.model_copy(update={"proposal_type": ProposalType.DUPLICATE_CANDIDATE})
    repo.upsert_proposal(rec)
    rows = repo.list_open_proposals_by_queue("high_confidence_duplicates", limit=10)
    assert len(rows) == 1
    rows_m = repo.list_open_proposals_by_queue("merge_candidates", limit=10)
    assert len(rows_m) == 0


@pytest.fixture
def repo_with_reviewer(repo: AdjudicationRepository) -> AdjudicationRepository:
    repo.create_reviewer(NewReviewer(reviewer_id="u1", reviewer_kind=ReviewerKind.HUMAN, display_name="A"))
    return repo


def test_append_decision_marks_touching_proposals_stale(repo_with_reviewer: AdjudicationRepository) -> None:
    p_touch = _sample_record("merge|rule_card|rule:w:1|rule_card|rule:b:1", "pid-touch-1")
    p_touch = p_touch.model_copy(
        update={
            "source_target_id": "rule:w:1",
            "related_target_id": "rule:b:1",
        }
    )
    p_other = _sample_record("merge|rule_card|rule:z:9|rule_card|rule:q:1", "pid-other-1")
    p_other = p_other.model_copy(
        update={
            "source_target_id": "rule:z:9",
            "related_target_id": "rule:q:1",
            "dedupe_key": "merge|rule_card|rule:q:1|rule_card|rule:z:9",
        }
    )
    repo_with_reviewer.upsert_proposal(p_touch)
    repo_with_reviewer.upsert_proposal(p_other)
    repo_with_reviewer.append_decision_and_refresh_state(
        NewReviewDecision(
            target_type=ReviewTargetType.RULE_CARD,
            target_id="rule:w:1",
            decision_type=DecisionType.APPROVE,
            reviewer_id="u1",
        )
    )
    t = repo_with_reviewer.get_proposal("pid-touch-1")
    o = repo_with_reviewer.get_proposal("pid-other-1")
    assert t is not None and t.proposal_status == ProposalStatus.STALE
    assert t.stale_reason == STALE_AFTER_DECISION_REASON
    assert o is not None and o.proposal_status == ProposalStatus.NEW


def test_mark_inventory_stale_for_rule_not_in_corpus(repo: AdjudicationRepository) -> None:
    now = utc_now_iso()
    ghost = _sample_record("merge|rule_card|ghost|rule_card|z", "pid-ghost")
    ghost = ghost.model_copy(
        update={
            "source_target_id": "rule:ghost:1",
            "related_target_id": "rule:z:9",
            "dedupe_key": "merge|rule_card|rule:ghost:1|rule_card|rule:z:9",
        }
    )
    repo.upsert_proposal(ghost)
    idx = CorpusTargetIndex(
        rule_card_ids=frozenset({"rule:z:9"}),
        evidence_link_ids=frozenset(),
        concept_link_ids=frozenset(),
        related_rule_relation_ids=frozenset(),
    )
    n = repo.mark_new_proposals_stale_when_missing_from_inventory(idx)
    assert n >= 1
    g = repo.get_proposal("pid-ghost")
    assert g is not None
    assert g.proposal_status == ProposalStatus.STALE
    assert g.stale_reason == STALE_NOT_IN_INVENTORY_REASON


def test_count_proposals_matches_list_filters(repo: AdjudicationRepository) -> None:
    for i in range(3):
        sid, rid = f"src{i}", f"rel{i}"
        dk = f"merge|rule_card|{min(sid, rid)}|rule_card|{max(sid, rid)}"
        r = _sample_record(dk, f"10000000-0000-0000-0000-0000000000{i:02d}")
        r = r.model_copy(update={"source_target_id": sid, "related_target_id": rid})
        repo.upsert_proposal(r)
    assert repo.count_proposals(proposal_status=ProposalStatus.NEW) == 3
    rows = repo.list_proposals(proposal_status=ProposalStatus.NEW, limit=1, offset=0)
    assert len(rows) == 1


def test_append_decision_stale_excludes_accepted_proposal_id(repo_with_reviewer: AdjudicationRepository) -> None:
    p_keep = _sample_record("merge|rule_card|rule:w:1|rule_card|rule:b:1", "pid-keep")
    p_keep = p_keep.model_copy(
        update={"source_target_id": "rule:w:1", "related_target_id": "rule:b:1"}
    )
    p_drop = _sample_record("merge|rule_card|rule:w:1|rule_card|rule:http:1", "pid-drop")
    p_drop = p_drop.model_copy(
        update={
            "source_target_id": "rule:w:1",
            "related_target_id": "rule:http:1",
            "dedupe_key": "merge|rule_card|rule:http:1|rule_card|rule:w:1",
        }
    )
    repo_with_reviewer.upsert_proposal(p_keep)
    repo_with_reviewer.upsert_proposal(p_drop)
    repo_with_reviewer.append_decision_and_refresh_state(
        NewReviewDecision(
            target_type=ReviewTargetType.RULE_CARD,
            target_id="rule:w:1",
            decision_type=DecisionType.APPROVE,
            reviewer_id="u1",
            proposal_id="pid-keep",
        )
    )
    keep = repo_with_reviewer.get_proposal("pid-keep")
    drop = repo_with_reviewer.get_proposal("pid-drop")
    assert keep is not None and keep.proposal_status == ProposalStatus.NEW
    assert drop is not None and drop.proposal_status == ProposalStatus.STALE
