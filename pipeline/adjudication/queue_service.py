"""Deterministic unresolved queues: corpus inventory + adjudication state overlay (Stage 5.2).

Policy:
- **Inventory** (``CorpusTargetIndex``) lists reviewable ``target_id`` values from the explorer /
  retrieval corpus. Items with **no** row in ``*_reviewed_state`` are still **unresolved**
  (never reviewed) and appear in the queue.
- **State-only rows** whose ``target_id`` is **not** in the inventory are **ignored** (orphan /
  guessed IDs must not surface).
- **Unresolved predicates** (unchanged):
  - **rule_card:** no ``latest_decision_type``, or ``current_status`` in {needs_review, ambiguous},
    or ``is_ambiguous``, or ``is_deferred``.
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
from pipeline.adjudication.enums import ReviewTargetType
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
    items.sort(key=_sort_key)
    return items


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


def get_next_queue_item(
    repo: AdjudicationRepository,
    queue_name: str,
    target_type: ReviewTargetType | None,
    corpus_index: CorpusTargetIndex,
) -> QueueItemResponse | None:
    if queue_name != "unresolved":
        return None
    items = _collect_unresolved(repo, corpus_index)
    if target_type is not None:
        items = [i for i in items if i.target_type == target_type]
    return items[0] if items else None
