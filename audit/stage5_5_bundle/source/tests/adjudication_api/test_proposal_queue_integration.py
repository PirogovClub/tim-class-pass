"""Proposal-backed queue ordering and ProposalQueueItem builder (Stage 5.5)."""

from __future__ import annotations

import json

from pipeline.adjudication.bootstrap import initialize_adjudication_storage
from pipeline.adjudication.enums import ProposalStatus, ProposalType, ReviewTargetType
from pipeline.adjudication.models import ProposalRecord
from pipeline.adjudication.proposal_policy import DEFAULT_GENERATOR_VERSION
from pipeline.adjudication.queue_service import build_proposal_queue_item, list_proposal_queue
from pipeline.adjudication.repository import AdjudicationRepository
from pipeline.adjudication.time_utils import utc_now_iso


def _merge_record(
    *,
    proposal_id: str,
    dedupe_key: str,
    source_id: str,
    related_id: str,
    queue_priority: float,
    score: float,
    now: str,
) -> ProposalRecord:
    return ProposalRecord(
        proposal_id=proposal_id,
        proposal_type=ProposalType.MERGE_CANDIDATE,
        source_target_type=ReviewTargetType.RULE_CARD,
        source_target_id=source_id,
        related_target_type=ReviewTargetType.RULE_CARD,
        related_target_id=related_id,
        proposal_status=ProposalStatus.NEW,
        score=score,
        rationale_summary="test",
        adjudication_snapshot_json=json.dumps({"k": proposal_id}),
        tier_snapshot_json="{}",
        queue_priority=queue_priority,
        dedupe_key=dedupe_key,
        generator_version=DEFAULT_GENERATOR_VERSION,
        created_at=now,
        updated_at=now,
        last_generated_at=now,
    )


def test_list_proposal_queue_sorted_by_priority_then_score(tmp_path) -> None:
    db = tmp_path / "pq.sqlite"
    initialize_adjudication_storage(db)
    repo = AdjudicationRepository(db)
    now = utc_now_iso()
    records = [
        _merge_record(
            proposal_id="p-low",
            dedupe_key="merge|rule_card|rule:a:1|rule_card|rule:q:1",
            source_id="rule:a:1",
            related_id="rule:q:1",
            queue_priority=0.4,
            score=0.8,
            now=now,
        ),
        _merge_record(
            proposal_id="p-high",
            dedupe_key="merge|rule_card|rule:b:1|rule_card|rule:q:1",
            source_id="rule:b:1",
            related_id="rule:q:1",
            queue_priority=0.95,
            score=0.75,
            now=now,
        ),
        _merge_record(
            proposal_id="p-mid",
            dedupe_key="merge|rule_card|rule:http:1|rule_card|rule:q:1",
            source_id="rule:http:1",
            related_id="rule:q:1",
            queue_priority=0.7,
            score=0.9,
            now=now,
        ),
    ]
    for r in records:
        repo.upsert_proposal(r)
    out = list_proposal_queue(repo, "merge_candidates", limit=10, offset=0)
    ids = [it.proposal_id for it in out.items]
    assert ids == ["p-high", "p-mid", "p-low"]


def test_build_proposal_queue_item_fields(tmp_path) -> None:
    db = tmp_path / "pqi.sqlite"
    initialize_adjudication_storage(db)
    repo = AdjudicationRepository(db)
    now = utc_now_iso()
    rec = _merge_record(
        proposal_id="p-one",
        dedupe_key="merge|rule_card|rule:w:1|rule_card|rule:b:1",
        source_id="rule:w:1",
        related_id="rule:b:1",
        queue_priority=0.5,
        score=0.77,
        now=now,
    )
    repo.upsert_proposal(rec)
    item = build_proposal_queue_item(repo, rec)
    assert item.proposal_id == "p-one"
    assert item.proposal_type == ProposalType.MERGE_CANDIDATE
    assert item.source_target_id == "rule:w:1"
    assert item.related_target_id == "rule:b:1"
    assert item.score == 0.77
    assert item.queue_priority == 0.5
    assert item.created_at == now
    assert item.updated_at == now
