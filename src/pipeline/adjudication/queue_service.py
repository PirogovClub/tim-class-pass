"""Deterministic unresolved queues: corpus inventory + adjudication state overlay (Stage 5.2).

Policy:
- **Inventory** (``CorpusTargetIndex``) lists reviewable ``target_id`` values from the explorer /
  retrieval corpus. Items with **no** row in ``*_reviewed_state`` are still **unresolved**
  (never reviewed) and appear in the queue.
- **State-only rows** whose ``target_id`` is **not** in the inventory are **ignored** (orphan /
  guessed IDs must not surface).
- **Unresolved predicates** (Stage 5.2 state heuristics) plus **tier alignment (5.4):** any
  inventory target whose **materialized tier resolver** returns ``unresolved`` is included even
  when state heuristics alone would skip it (e.g. invalid family link, unsupported evidence).
- **rule_card (state heuristic):** no ``latest_decision_type``, or ``current_status`` in
  {needs_review, ambiguous}, or ``is_ambiguous``, or ``is_deferred``.
- **evidence_link:** ``support_status`` is null or ``unknown`` (including no state row).
- **concept_link:** ``link_status`` is null or ``unknown``.
- **related_rule_relation:** ``relation_status`` is null or ``unknown``.
- **Ordering:** sort key ``(has_ts, last_reviewed_at, target_type, target_id)`` where ``has_ts``
  is ``0`` when ``last_reviewed_at`` is set else ``1``; then ISO timestamp, type, id.
"""

from __future__ import annotations

import sqlite3

from pipeline.adjudication.api_models import QueueItemResponse, QueueListResponse
from pipeline.adjudication.corpus_inventory import CorpusTargetIndex
from pipeline.adjudication.enums import ProposalQueueName, ProposalType, QualityTier, ReviewTargetType
from pipeline.adjudication.models import (
    MaterializedTierRecord,
    ProposalQueueItem,
    ProposalRecord,
    RuleCardReviewedState,
)
from pipeline.adjudication.quality_tier import resolve_tier_for_target
from pipeline.adjudication.repository import AdjudicationRepository


def _sort_key(r: QueueItemResponse) -> tuple[int, str, str, str]:
    null_last = 0 if r.last_reviewed_at else 1
    ts = r.last_reviewed_at or ""
    return (null_last, ts, r.target_type.value, r.target_id)


def _rule_row_unresolved(row: sqlite3.Row) -> bool:
    return bool(
        row["latest_decision_type"] is None
        or row["current_status"] in ("needs_review", "ambiguous")
        or row["is_ambiguous"] == 1
        or row["is_deferred"] == 1
    )


def _rule_queue_reason(row: sqlite3.Row | None, *, no_row: bool) -> str:
    if no_row or row is None:
        return "no_adjudication_state"
    if row["latest_decision_type"] is None:
        return "no_decision"
    if row["is_deferred"]:
        return "deferred"
    if row["is_ambiguous"] or row["current_status"] == "ambiguous":
        return "ambiguous"
    if row["current_status"] == "needs_review":
        return "needs_review"
    return "unresolved"


def _evidence_row_unresolved(row: sqlite3.Row | None) -> bool:
    if row is None:
        return True
    return row["support_status"] is None or row["support_status"] == "unknown"


def _concept_row_unresolved(row: sqlite3.Row | None) -> bool:
    if row is None:
        return True
    return row["link_status"] is None or row["link_status"] == "unknown"


def _relation_row_unresolved(row: sqlite3.Row | None) -> bool:
    if row is None:
        return True
    return row["relation_status"] is None or row["relation_status"] == "unknown"


def _load_rule_states(conn: sqlite3.Connection) -> dict[str, sqlite3.Row]:
    cur = conn.execute(
        """
        SELECT target_id, current_status, latest_decision_type, last_reviewed_at,
               canonical_family_id, is_ambiguous, is_deferred
        FROM rule_card_reviewed_state
        """
    )
    return {str(row["target_id"]): row for row in cur.fetchall()}


def _load_evidence_states(conn: sqlite3.Connection) -> dict[str, sqlite3.Row]:
    cur = conn.execute(
        "SELECT target_id, support_status, last_reviewed_at FROM evidence_link_reviewed_state"
    )
    return {str(row["target_id"]): row for row in cur.fetchall()}


def _load_concept_states(conn: sqlite3.Connection) -> dict[str, sqlite3.Row]:
    cur = conn.execute(
        "SELECT target_id, link_status, last_reviewed_at FROM concept_link_reviewed_state"
    )
    return {str(row["target_id"]): row for row in cur.fetchall()}


def _load_relation_states(conn: sqlite3.Connection) -> dict[str, sqlite3.Row]:
    cur = conn.execute(
        "SELECT target_id, relation_status, last_reviewed_at FROM related_rule_relation_reviewed_state"
    )
    return {str(row["target_id"]): row for row in cur.fetchall()}


def _collect_rule_items(
    states: dict[str, sqlite3.Row],
    inventory_ids: frozenset[str],
) -> list[QueueItemResponse]:
    items: list[QueueItemResponse] = []
    for target_id in sorted(inventory_ids):
        row = states.get(target_id)
        no_row = row is None
        if no_row:
            items.append(
                QueueItemResponse(
                    target_type=ReviewTargetType.RULE_CARD,
                    target_id=target_id,
                    queue_reason=_rule_queue_reason(None, no_row=True),
                )
            )
        elif _rule_row_unresolved(row):
            items.append(
                QueueItemResponse(
                    target_type=ReviewTargetType.RULE_CARD,
                    target_id=target_id,
                    current_status=row["current_status"],
                    latest_decision_type=row["latest_decision_type"],
                    last_reviewed_at=row["last_reviewed_at"],
                    canonical_family_id=row["canonical_family_id"],
                    queue_reason=_rule_queue_reason(row, no_row=False),
                )
            )
    return items


def _collect_evidence_items(
    states: dict[str, sqlite3.Row],
    inventory_ids: frozenset[str],
) -> list[QueueItemResponse]:
    items: list[QueueItemResponse] = []
    for target_id in sorted(inventory_ids):
        row = states.get(target_id)
        if not _evidence_row_unresolved(row):
            continue
        items.append(
            QueueItemResponse(
                target_type=ReviewTargetType.EVIDENCE_LINK,
                target_id=target_id,
                latest_decision_type=None,
                last_reviewed_at=row["last_reviewed_at"] if row else None,
                support_status=row["support_status"] if row else None,
                queue_reason="no_adjudication_state" if row is None else "unknown_support",
            )
        )
    return items


def _collect_concept_items(
    states: dict[str, sqlite3.Row],
    inventory_ids: frozenset[str],
) -> list[QueueItemResponse]:
    items: list[QueueItemResponse] = []
    for target_id in sorted(inventory_ids):
        row = states.get(target_id)
        if not _concept_row_unresolved(row):
            continue
        items.append(
            QueueItemResponse(
                target_type=ReviewTargetType.CONCEPT_LINK,
                target_id=target_id,
                last_reviewed_at=row["last_reviewed_at"] if row else None,
                link_status=row["link_status"] if row else None,
                queue_reason="no_adjudication_state" if row is None else "unknown_link",
            )
        )
    return items


def _collect_relation_items(
    states: dict[str, sqlite3.Row],
    inventory_ids: frozenset[str],
) -> list[QueueItemResponse]:
    items: list[QueueItemResponse] = []
    for target_id in sorted(inventory_ids):
        row = states.get(target_id)
        if not _relation_row_unresolved(row):
            continue
        items.append(
            QueueItemResponse(
                target_type=ReviewTargetType.RELATED_RULE_RELATION,
                target_id=target_id,
                last_reviewed_at=row["last_reviewed_at"] if row else None,
                relation_status=row["relation_status"] if row else None,
                queue_reason="no_adjudication_state" if row is None else "unknown_relation",
            )
        )
    return items


def _tier_unresolved_queue_reason(rec: MaterializedTierRecord) -> str:
    if rec.blocker_codes:
        return rec.blocker_codes[0]
    return "tier_unresolved"


def _collect_tier_only_unresolved(
    repo: AdjudicationRepository,
    corpus_index: CorpusTargetIndex,
    already: list[QueueItemResponse],
    rule_s: dict[str, sqlite3.Row],
    ev_s: dict[str, sqlite3.Row],
    co_s: dict[str, sqlite3.Row],
    rel_s: dict[str, sqlite3.Row],
) -> list[QueueItemResponse]:
    """Targets in corpus inventory with tier ``unresolved`` not already in ``already``."""
    keys = {(i.target_type.value, i.target_id) for i in already}
    extra: list[QueueItemResponse] = []

    for tid in sorted(corpus_index.rule_card_ids):
        if ("rule_card", tid) in keys:
            continue
        rec = resolve_tier_for_target(repo, ReviewTargetType.RULE_CARD, tid)
        if rec.tier != QualityTier.UNRESOLVED:
            continue
        row = rule_s.get(tid)
        extra.append(
            QueueItemResponse(
                target_type=ReviewTargetType.RULE_CARD,
                target_id=tid,
                current_status=row["current_status"] if row else None,
                latest_decision_type=row["latest_decision_type"] if row else None,
                last_reviewed_at=row["last_reviewed_at"] if row else None,
                canonical_family_id=row["canonical_family_id"] if row else None,
                queue_reason=_tier_unresolved_queue_reason(rec),
            )
        )

    for tid in sorted(corpus_index.evidence_link_ids):
        if ("evidence_link", tid) in keys:
            continue
        rec = resolve_tier_for_target(repo, ReviewTargetType.EVIDENCE_LINK, tid)
        if rec.tier != QualityTier.UNRESOLVED:
            continue
        row = ev_s.get(tid)
        extra.append(
            QueueItemResponse(
                target_type=ReviewTargetType.EVIDENCE_LINK,
                target_id=tid,
                last_reviewed_at=row["last_reviewed_at"] if row else None,
                support_status=row["support_status"] if row else None,
                queue_reason=_tier_unresolved_queue_reason(rec),
            )
        )

    for tid in sorted(corpus_index.concept_link_ids):
        if ("concept_link", tid) in keys:
            continue
        rec = resolve_tier_for_target(repo, ReviewTargetType.CONCEPT_LINK, tid)
        if rec.tier != QualityTier.UNRESOLVED:
            continue
        row = co_s.get(tid)
        extra.append(
            QueueItemResponse(
                target_type=ReviewTargetType.CONCEPT_LINK,
                target_id=tid,
                last_reviewed_at=row["last_reviewed_at"] if row else None,
                link_status=row["link_status"] if row else None,
                queue_reason=_tier_unresolved_queue_reason(rec),
            )
        )

    for tid in sorted(corpus_index.related_rule_relation_ids):
        if ("related_rule_relation", tid) in keys:
            continue
        rec = resolve_tier_for_target(repo, ReviewTargetType.RELATED_RULE_RELATION, tid)
        if rec.tier != QualityTier.UNRESOLVED:
            continue
        row = rel_s.get(tid)
        extra.append(
            QueueItemResponse(
                target_type=ReviewTargetType.RELATED_RULE_RELATION,
                target_id=tid,
                last_reviewed_at=row["last_reviewed_at"] if row else None,
                relation_status=row["relation_status"] if row else None,
                queue_reason=_tier_unresolved_queue_reason(rec),
            )
        )

    return extra


def _apply_quality_tiers(
    repo: AdjudicationRepository, items: list[QueueItemResponse]
) -> list[QueueItemResponse]:
    if not items:
        return items
    with repo.connect() as conn:
        cur = conn.execute(
            "SELECT target_type, target_id, tier FROM materialized_tier_state"
        )
        m = {(str(r["target_type"]), str(r["target_id"])): r["tier"] for r in cur.fetchall()}
    out: list[QueueItemResponse] = []
    for it in items:
        tr = m.get((it.target_type.value, it.target_id))
        out.append(it.model_copy(update={"quality_tier": tr}) if tr is not None else it)
    return out


def _collect_unresolved(
    repo: AdjudicationRepository,
    corpus_index: CorpusTargetIndex,
) -> list[QueueItemResponse]:
    with repo.connect() as conn:
        rule_s = _load_rule_states(conn)
        ev_s = _load_evidence_states(conn)
        co_s = _load_concept_states(conn)
        rel_s = _load_relation_states(conn)

    items: list[QueueItemResponse] = []
    items.extend(_collect_rule_items(rule_s, corpus_index.rule_card_ids))
    items.extend(_collect_evidence_items(ev_s, corpus_index.evidence_link_ids))
    items.extend(_collect_concept_items(co_s, corpus_index.concept_link_ids))
    items.extend(_collect_relation_items(rel_s, corpus_index.related_rule_relation_ids))
    items.extend(
        _collect_tier_only_unresolved(repo, corpus_index, items, rule_s, ev_s, co_s, rel_s)
    )
    items.sort(key=_sort_key)
    return _apply_quality_tiers(repo, items)


def list_unresolved_queue(
    repo: AdjudicationRepository,
    corpus_index: CorpusTargetIndex,
) -> QueueListResponse:
    items = _collect_unresolved(repo, corpus_index)
    return QueueListResponse(queue="unresolved", items=items, total=len(items))


def list_queue_by_target(
    repo: AdjudicationRepository,
    target_type: ReviewTargetType,
    corpus_index: CorpusTargetIndex,
) -> QueueListResponse:
    items = [i for i in _collect_unresolved(repo, corpus_index) if i.target_type == target_type]
    return QueueListResponse(queue="unresolved", items=items, total=len(items))


PROPOSAL_QUEUE_NAMES = frozenset(
    {
        ProposalQueueName.HIGH_CONFIDENCE_DUPLICATES.value,
        ProposalQueueName.MERGE_CANDIDATES.value,
        ProposalQueueName.CANONICAL_FAMILY_CANDIDATES.value,
    }
)


def _queue_hint_for_proposal_type(pt: ProposalType) -> str:
    return {
        ProposalType.DUPLICATE_CANDIDATE: ProposalQueueName.HIGH_CONFIDENCE_DUPLICATES.value,
        ProposalType.MERGE_CANDIDATE: ProposalQueueName.MERGE_CANDIDATES.value,
        ProposalType.CANONICAL_FAMILY_CANDIDATE: ProposalQueueName.CANONICAL_FAMILY_CANDIDATES.value,
    }[pt]


def _proposal_source_context(
    repo: AdjudicationRepository, proposal: ProposalRecord
) -> tuple[RuleCardReviewedState | None, str | None]:
    st_row = None
    if proposal.source_target_type == ReviewTargetType.RULE_CARD:
        st_row = repo.get_rule_card_state(proposal.source_target_id)
    tier_rec = repo.get_materialized_tier(
        proposal.source_target_type, proposal.source_target_id
    )
    qt = tier_rec.tier.value if tier_rec else None
    return st_row, qt


def build_proposal_queue_item(
    repo: AdjudicationRepository, proposal: ProposalRecord
) -> ProposalQueueItem:
    st_row, qt = _proposal_source_context(repo, proposal)
    return ProposalQueueItem(
        proposal_id=proposal.proposal_id,
        proposal_type=proposal.proposal_type,
        source_target_type=proposal.source_target_type,
        source_target_id=proposal.source_target_id,
        related_target_type=proposal.related_target_type,
        related_target_id=proposal.related_target_id,
        score=proposal.score,
        queue_priority=proposal.queue_priority,
        rationale_summary=proposal.rationale_summary,
        current_tier=qt,
        current_status=st_row.current_status.value if st_row and st_row.current_status else None,
        created_at=proposal.created_at,
        updated_at=proposal.updated_at,
    )


def proposal_record_to_queue_item(
    repo: AdjudicationRepository, proposal: ProposalRecord
) -> QueueItemResponse:
    st_row, qt = _proposal_source_context(repo, proposal)
    summary = proposal.rationale_summary[:200] if proposal.rationale_summary else None
    return QueueItemResponse(
        target_type=proposal.source_target_type,
        target_id=proposal.source_target_id,
        current_status=st_row.current_status.value if st_row and st_row.current_status else None,
        latest_decision_type=(
            st_row.latest_decision_type.value if st_row and st_row.latest_decision_type else None
        ),
        last_reviewed_at=st_row.last_reviewed_at if st_row else None,
        canonical_family_id=st_row.canonical_family_id if st_row else None,
        queue_reason=_queue_hint_for_proposal_type(proposal.proposal_type),
        summary=summary,
        quality_tier=qt,
        proposal_id=proposal.proposal_id,
        proposal_type=proposal.proposal_type.value,
        related_target_type=(
            proposal.related_target_type.value if proposal.related_target_type else None
        ),
        related_target_id=proposal.related_target_id,
        proposal_score=proposal.score,
        proposal_queue_priority=proposal.queue_priority,
        proposal_rationale_summary=proposal.rationale_summary,
        proposal_updated_at=proposal.updated_at,
    )


def list_proposal_queue(
    repo: AdjudicationRepository,
    queue_name: str,
    *,
    limit: int = 500,
    offset: int = 0,
    source_target_type: ReviewTargetType | None = None,
    quality_tier: str | None = None,
) -> QueueListResponse:
    total = repo.count_open_proposals_by_queue(
        queue_name,
        source_target_type=source_target_type,
        quality_tier=quality_tier,
    )
    rows = repo.list_open_proposals_by_queue(
        queue_name,
        limit,
        offset,
        source_target_type=source_target_type,
        quality_tier=quality_tier,
    )
    items = [proposal_record_to_queue_item(repo, r) for r in rows]
    return QueueListResponse(queue=queue_name, items=items, total=total)


def get_next_queue_item(
    repo: AdjudicationRepository,
    queue_name: str,
    target_type: ReviewTargetType | None,
    corpus_index: CorpusTargetIndex,
    *,
    quality_tier: str | None = None,
) -> QueueItemResponse | None:
    if queue_name in PROPOSAL_QUEUE_NAMES:
        rows = repo.list_open_proposals_by_queue(
            queue_name,
            limit=1,
            offset=0,
            source_target_type=target_type,
            quality_tier=quality_tier,
        )
        if not rows:
            return None
        return proposal_record_to_queue_item(repo, rows[0])
    if queue_name != "unresolved":
        return None
    items = _collect_unresolved(repo, corpus_index)
    if target_type is not None:
        items = [i for i in items if i.target_type == target_type]
    return items[0] if items else None
