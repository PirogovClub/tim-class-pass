"""Read-only Stage 5.7 metrics over adjudication state and corpus inventory."""

from __future__ import annotations

import statistics
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from pipeline.adjudication.corpus_inventory import CorpusTargetIndex
from pipeline.adjudication.enums import (
    ConceptLinkStatus,
    DecisionType,
    EvidenceSupportStatus,
    ProposalStatus,
    ProposalType,
    QualityTier,
    RelationStatus,
    ReviewTargetType,
    RuleCardCoarseStatus,
)
from pipeline.adjudication.metrics_enums import ThroughputWindow
from pipeline.adjudication.metrics_models import (
    CorpusCurationSummaryResponse,
    CoverageBucketRow,
    CoverageConceptsResponse,
    CoverageLessonsResponse,
    FlagDistributionRow,
    FlagsDistributionResponse,
    FlagsSummaryBlock,
    ProposalQueueSizeRow,
    ProposalTypeMetricsRow,
    ProposalUsefulnessResponse,
    QueueHealthResponse,
    ReviewerThroughputRow,
    ThroughputBreakdownRow,
    ThroughputResponse,
)
from pipeline.adjudication.queue_service import PROPOSAL_QUEUE_NAMES, list_unresolved_queue
from pipeline.adjudication.repository import AdjudicationRepository
from pipeline.adjudication.time_utils import utc_now_iso


def _parse_iso_ts(ts: str) -> datetime:
    s = (ts or "").strip()
    if not s:
        return datetime.min.replace(tzinfo=timezone.utc)
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _window_delta(w: ThroughputWindow) -> timedelta:
    if w == ThroughputWindow.DAYS_7:
        return timedelta(days=7)
    return timedelta(days=30)


def _explorer_doc_map(explorer: Any | None) -> dict[str, dict[str, Any]] | None:
    if explorer is None:
        return None
    repo = getattr(explorer, "_repo", None)
    if repo is None or not hasattr(repo, "get_all_docs"):
        return None
    out: dict[str, dict[str, Any]] = {}
    for doc in repo.get_all_docs():
        did = str(doc.get("doc_id") or "").strip()
        if did:
            out[did] = doc
    return out


def _lesson_and_concept_from_doc(doc: dict[str, Any] | None) -> tuple[str, str]:
    if not doc:
        return ("unknown_doc", "unknown")
    lesson = str(doc.get("lesson_id") or "").strip() or "unknown"
    cids = doc.get("canonical_concept_ids") or []
    if cids:
        concept = str(cids[0])
    else:
        concept = str(doc.get("concept") or "").strip() or "unknown"
    return (lesson, concept)


def _inventory_tier_counts(repo: AdjudicationRepository, index: CorpusTargetIndex) -> dict[str, int]:
    out: dict[str, int] = defaultdict(int)
    with repo.connect() as conn:
        cur = conn.execute("SELECT target_type, target_id, tier FROM materialized_tier_state")
        for r in cur.fetchall():
            tt = ReviewTargetType(r["target_type"])
            if index.contains(tt, r["target_id"]):
                out[str(r["tier"])] += 1
    return dict(out)


def _is_not_unresolved(
    repo: AdjudicationRepository, target_type: ReviewTargetType, target_id: str
) -> bool:
    rec = repo.get_materialized_tier(target_type, target_id)
    if rec is None:
        return False
    return rec.tier != QualityTier.UNRESOLVED


def _sql_count_ids(
    repo: AdjudicationRepository,
    *,
    table: str,
    id_column: str,
    ids: frozenset[str],
    where_sql: str,
    where_args: tuple[Any, ...],
) -> int:
    if not ids:
        return 0
    placeholders = ",".join("?" * len(ids))
    sql = f"SELECT COUNT(*) AS c FROM {table} WHERE {id_column} IN ({placeholders}) AND ({where_sql})"
    with repo.connect() as conn:
        row = conn.execute(sql, (*ids,) + where_args).fetchone()
    return int(row["c"])


def build_corpus_curation_summary(
    repo: AdjudicationRepository, index: CorpusTargetIndex
) -> CorpusCurationSummaryResponse:
    computed_at = utc_now_iso()
    tiers = _inventory_tier_counts(repo, index)
    uq = list_unresolved_queue(repo, index)

    rejected = _sql_count_ids(
        repo,
        table="rule_card_reviewed_state",
        id_column="target_id",
        ids=index.rule_card_ids,
        where_sql="current_status = ?",
        where_args=(RuleCardCoarseStatus.REJECTED.value,),
    )
    unsupported_rules = _sql_count_ids(
        repo,
        table="rule_card_reviewed_state",
        id_column="target_id",
        ids=index.rule_card_ids,
        where_sql="is_unsupported = 1 OR current_status = ?",
        where_args=(RuleCardCoarseStatus.UNSUPPORTED.value,),
    )
    unsupported_evidence = _sql_count_ids(
        repo,
        table="evidence_link_reviewed_state",
        id_column="target_id",
        ids=index.evidence_link_ids,
        where_sql="support_status = ?",
        where_args=(EvidenceSupportStatus.UNSUPPORTED.value,),
    )

    with repo.connect() as conn:
        fam_row = conn.execute("SELECT COUNT(*) AS c FROM canonical_rule_families").fetchone()
        merge_row = conn.execute(
            "SELECT COUNT(*) AS c FROM review_decisions WHERE decision_type = ?",
            (DecisionType.MERGE_INTO.value,),
        ).fetchone()

    total_inv = (
        len(index.rule_card_ids)
        + len(index.evidence_link_ids)
        + len(index.concept_link_ids)
        + len(index.related_rule_relation_ids)
    )

    return CorpusCurationSummaryResponse(
        computed_at=computed_at,
        total_supported_review_targets=total_inv,
        unresolved_count=uq.total,
        gold_count=int(tiers.get(QualityTier.GOLD.value, 0)),
        silver_count=int(tiers.get(QualityTier.SILVER.value, 0)),
        bronze_count=int(tiers.get(QualityTier.BRONZE.value, 0)),
        tier_unresolved_count=int(tiers.get(QualityTier.UNRESOLVED.value, 0)),
        rejected_count=rejected,
        unsupported_count=unsupported_rules + unsupported_evidence,
        canonical_family_count=int(fam_row["c"]),
        merge_decision_count=int(merge_row["c"]),
    )


def build_queue_health_metrics(
    repo: AdjudicationRepository, index: CorpusTargetIndex
) -> QueueHealthResponse:
    computed_at = utc_now_iso()
    uq = list_unresolved_queue(repo, index)
    by_tt = Counter(i.target_type.value for i in uq.items)
    by_tier = Counter((i.quality_tier or "none") for i in uq.items)

    deferred = _sql_count_ids(
        repo,
        table="rule_card_reviewed_state",
        id_column="target_id",
        ids=index.rule_card_ids,
        where_sql="is_deferred = 1",
        where_args=(),
    )

    pq_sizes: list[ProposalQueueSizeRow] = []
    for qn in sorted(PROPOSAL_QUEUE_NAMES):
        c = repo.count_open_proposals_by_queue(qn)
        pq_sizes.append(ProposalQueueSizeRow(queue_name=qn, open_count=c))

    oldest_ts: str | None = None
    for i in uq.items:
        if i.last_reviewed_at:
            if oldest_ts is None or i.last_reviewed_at < oldest_ts:
                oldest_ts = i.last_reviewed_at

    age_sec: float | None = None
    if oldest_ts:
        delta = _parse_iso_ts(computed_at) - _parse_iso_ts(oldest_ts)
        age_sec = max(0.0, delta.total_seconds())

    return QueueHealthResponse(
        computed_at=computed_at,
        unresolved_queue_size=uq.total,
        deferred_rule_cards=deferred,
        proposal_queue_open_counts=pq_sizes,
        unresolved_by_target_type=dict(sorted(by_tt.items())),
        unresolved_backlog_by_tier=dict(sorted(by_tier.items())),
        oldest_unresolved_last_reviewed_at=oldest_ts,
        oldest_unresolved_age_seconds=age_sec,
    )


def _terminal_statuses() -> frozenset[ProposalStatus]:
    return frozenset(
        {
            ProposalStatus.ACCEPTED,
            ProposalStatus.DISMISSED,
            ProposalStatus.STALE,
            ProposalStatus.SUPERSEDED,
        }
    )


def _proposal_rows_by_type_status(
    repo: AdjudicationRepository,
) -> dict[tuple[str, str], int]:
    out: dict[tuple[str, str], int] = defaultdict(int)
    with repo.connect() as conn:
        cur = conn.execute(
            """
            SELECT proposal_type, proposal_status, COUNT(*) AS c
            FROM adjudication_proposal
            GROUP BY proposal_type, proposal_status
            """
        )
        for r in cur.fetchall():
            out[(r["proposal_type"], r["proposal_status"])] = int(r["c"])
    return dict(out)


def _median_disposition_seconds(repo: AdjudicationRepository) -> float | None:
    deltas: list[float] = []
    terminal = {s.value for s in _terminal_statuses()}
    with repo.connect() as conn:
        cur = conn.execute(
            """
            SELECT created_at, updated_at, proposal_status
            FROM adjudication_proposal
            """
        )
        for r in cur.fetchall():
            if r["proposal_status"] not in terminal:
                continue
            try:
                c0 = _parse_iso_ts(r["created_at"])
                c1 = _parse_iso_ts(r["updated_at"])
                deltas.append(max(0.0, (c1 - c0).total_seconds()))
            except (TypeError, ValueError, OSError):
                continue
    if not deltas:
        return None
    return float(statistics.median(deltas))


def build_proposal_usefulness(repo: AdjudicationRepository) -> ProposalUsefulnessResponse:
    computed_at = utc_now_iso()
    cells = _proposal_rows_by_type_status(repo)
    total = sum(cells.values())

    def _sum_status(st: ProposalStatus) -> int:
        return sum(c for (__, ps), c in cells.items() if ps == st.value)

    open_c = _sum_status(ProposalStatus.NEW)
    acc = _sum_status(ProposalStatus.ACCEPTED)
    dis = _sum_status(ProposalStatus.DISMISSED)
    stl = _sum_status(ProposalStatus.STALE)
    sup = _sum_status(ProposalStatus.SUPERSEDED)
    terminal = acc + dis + stl + sup
    stale_total = stl + sup

    def _rate(num: int, den: int) -> float | None:
        if den <= 0:
            return None
        return round(num / den, 6)

    by_type: list[ProposalTypeMetricsRow] = []
    for ptype in ProposalType:
        t_total = sum(c for (pt, ps), c in cells.items() if pt == ptype.value)
        t_open = sum(c for (pt, ps), c in cells.items() if pt == ptype.value and ps == ProposalStatus.NEW.value)
        t_acc = sum(c for (pt, ps), c in cells.items() if pt == ptype.value and ps == ProposalStatus.ACCEPTED.value)
        t_dis = sum(c for (pt, ps), c in cells.items() if pt == ptype.value and ps == ProposalStatus.DISMISSED.value)
        t_stl = sum(c for (pt, ps), c in cells.items() if pt == ptype.value and ps == ProposalStatus.STALE.value)
        t_sup = sum(c for (pt, ps), c in cells.items() if pt == ptype.value and ps == ProposalStatus.SUPERSEDED.value)
        t_term = t_acc + t_dis + t_stl + t_sup
        by_type.append(
            ProposalTypeMetricsRow(
                proposal_type=ptype.value,
                total=t_total,
                open=t_open,
                accepted=t_acc,
                dismissed=t_dis,
                stale=t_stl,
                superseded=t_sup,
                terminal=t_term,
                acceptance_rate_closed=_rate(t_acc, t_term),
                acceptance_rate_all=_rate(t_acc, t_total),
            )
        )

    return ProposalUsefulnessResponse(
        computed_at=computed_at,
        total_proposals=total,
        open_proposals=open_c,
        accepted_proposals=acc,
        dismissed_proposals=dis,
        stale_proposals=stl,
        superseded_proposals=sup,
        stale_total=stale_total,
        terminal_proposals=terminal,
        acceptance_rate_closed=_rate(acc, terminal),
        acceptance_rate_all=_rate(acc, total),
        median_seconds_to_disposition=_median_disposition_seconds(repo),
        by_proposal_type=by_type,
    )


def build_throughput_metrics(
    repo: AdjudicationRepository, window: ThroughputWindow
) -> ThroughputResponse:
    computed_at = utc_now_iso()
    now = _parse_iso_ts(computed_at)
    start = now - _window_delta(window)
    window_start = start.isoformat()

    by_dt: Counter[str] = Counter()
    by_rev: Counter[str] = Counter()
    total = 0
    with repo.connect() as conn:
        cur = conn.execute(
            "SELECT decision_type, reviewer_id, created_at FROM review_decisions"
        )
        for r in cur.fetchall():
            try:
                ts = _parse_iso_ts(r["created_at"])
            except (TypeError, ValueError, OSError):
                continue
            if ts < start:
                continue
            total += 1
            by_dt[r["decision_type"]] += 1
            by_rev[r["reviewer_id"]] += 1

    return ThroughputResponse(
        computed_at=computed_at,
        window=window.value,
        window_start_utc=window_start,
        decision_count=total,
        by_decision_type=[
            ThroughputBreakdownRow(decision_type=k, count=v)
            for k, v in sorted(by_dt.items(), key=lambda kv: (-kv[1], kv[0]))
        ],
        by_reviewer_id=[
            ReviewerThroughputRow(reviewer_id=k, count=v)
            for k, v in sorted(by_rev.items(), key=lambda kv: (-kv[1], kv[0]))
        ],
    )


def _iter_inventory_targets(
    index: CorpusTargetIndex,
) -> list[tuple[ReviewTargetType, str]]:
    pairs: list[tuple[ReviewTargetType, str]] = []
    for rid in sorted(index.rule_card_ids):
        pairs.append((ReviewTargetType.RULE_CARD, rid))
    for eid in sorted(index.evidence_link_ids):
        pairs.append((ReviewTargetType.EVIDENCE_LINK, eid))
    for cid in sorted(index.concept_link_ids):
        pairs.append((ReviewTargetType.CONCEPT_LINK, cid))
    for rid in sorted(index.related_rule_relation_ids):
        pairs.append((ReviewTargetType.RELATED_RULE_RELATION, rid))
    return pairs


def _aggregate_coverage_buckets(
    repo: AdjudicationRepository,
    index: CorpusTargetIndex,
    doc_map: dict[str, dict[str, Any]] | None,
    *,
    by_lesson: bool,
) -> tuple[bool, str | None, list[CoverageBucketRow]]:
    if doc_map is None:
        return (
            False,
            "Explorer corpus not configured; lesson/concept buckets require get_all_docs().",
            [],
        )

    buckets: dict[str, list[int]] = defaultdict(lambda: [0, 0])  # total, reviewed

    for tt, tid in _iter_inventory_targets(index):
        doc = doc_map.get(tid)
        lesson, concept = _lesson_and_concept_from_doc(doc)
        key = lesson if by_lesson else concept
        b = buckets[key]
        b[0] += 1
        if _is_not_unresolved(repo, tt, tid):
            b[1] += 1

    rows: list[CoverageBucketRow] = []
    for bid in sorted(buckets.keys()):
        tot, rev = buckets[bid]
        ratio = round(rev / tot, 6) if tot else None
        rows.append(
            CoverageBucketRow(
                bucket_id=bid,
                total_targets=tot,
                reviewed_not_unresolved=rev,
                coverage_ratio=ratio,
            )
        )
    return (True, None, rows)


def build_coverage_lessons(
    repo: AdjudicationRepository,
    index: CorpusTargetIndex,
    explorer: Any | None,
) -> CoverageLessonsResponse:
    computed_at = utc_now_iso()
    ok, note, rows = _aggregate_coverage_buckets(
        repo, index, _explorer_doc_map(explorer), by_lesson=True
    )
    return CoverageLessonsResponse(
        computed_at=computed_at,
        explorer_available=ok,
        note=note,
        buckets=rows,
    )


def build_coverage_concepts(
    repo: AdjudicationRepository,
    index: CorpusTargetIndex,
    explorer: Any | None,
) -> CoverageConceptsResponse:
    computed_at = utc_now_iso()
    ok, note, rows = _aggregate_coverage_buckets(
        repo, index, _explorer_doc_map(explorer), by_lesson=False
    )
    return CoverageConceptsResponse(
        computed_at=computed_at,
        explorer_available=ok,
        note=note,
        buckets=rows,
    )


def build_flags_distribution(
    repo: AdjudicationRepository,
    index: CorpusTargetIndex,
    explorer: Any | None,
) -> FlagsDistributionResponse:
    computed_at = utc_now_iso()
    doc_map = _explorer_doc_map(explorer)

    amb = _sql_count_ids(
        repo,
        table="rule_card_reviewed_state",
        id_column="target_id",
        ids=index.rule_card_ids,
        where_sql="is_ambiguous = 1 OR current_status = ?",
        where_args=(RuleCardCoarseStatus.AMBIGUOUS.value,),
    )
    split_req = _sql_count_ids(
        repo,
        table="rule_card_reviewed_state",
        id_column="target_id",
        ids=index.rule_card_ids,
        where_sql="current_status = ?",
        where_args=(RuleCardCoarseStatus.SPLIT_REQUIRED.value,),
    )
    c_inv = _sql_count_ids(
        repo,
        table="concept_link_reviewed_state",
        id_column="target_id",
        ids=index.concept_link_ids,
        where_sql="link_status = ?",
        where_args=(ConceptLinkStatus.INVALID.value,),
    )
    r_inv = _sql_count_ids(
        repo,
        table="related_rule_relation_reviewed_state",
        id_column="target_id",
        ids=index.related_rule_relation_ids,
        where_sql="relation_status = ?",
        where_args=(RelationStatus.INVALID.value,),
    )

    summary = FlagsSummaryBlock(
        ambiguity_rule_cards=amb,
        conflict_rule_split_required=split_req,
        conflict_concept_invalid=c_inv,
        conflict_relation_invalid=r_inv,
    )

    if doc_map is None:
        return FlagsDistributionResponse(
            computed_at=computed_at,
            explorer_available=False,
            note="Explorer corpus not configured; rule_card grouping skipped.",
            summary=summary,
            by_lesson=[],
            by_concept=[],
        )

    by_lesson: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    by_concept: dict[str, list[int]] = defaultdict(lambda: [0, 0])

    with repo.connect() as conn:
        cur = conn.execute(
            """
            SELECT target_id, is_ambiguous, current_status
            FROM rule_card_reviewed_state
            WHERE target_id IN ({})
            """.format(",".join("?" * len(index.rule_card_ids)) or "NULL"),
            tuple(sorted(index.rule_card_ids)),
        )
        rows_state = cur.fetchall() if index.rule_card_ids else []

    id_set = index.rule_card_ids
    for row in rows_state:
        tid = row["target_id"]
        if tid not in id_set:
            continue
        is_amb = row["is_ambiguous"] == 1
        st = row["current_status"]
        amb_hit = is_amb or st == RuleCardCoarseStatus.AMBIGUOUS.value
        split_hit = st == RuleCardCoarseStatus.SPLIT_REQUIRED.value
        if not amb_hit and not split_hit:
            continue
        doc = doc_map.get(tid)
        lesson, concept = _lesson_and_concept_from_doc(doc)
        if amb_hit:
            by_lesson[lesson][0] += 1
            by_concept[concept][0] += 1
        if split_hit:
            by_lesson[lesson][1] += 1
            by_concept[concept][1] += 1

    def _rows(d: dict[str, list[int]]) -> list[FlagDistributionRow]:
        out: list[FlagDistributionRow] = []
        for bid in sorted(d.keys()):
            a, s = d[bid]
            out.append(
                FlagDistributionRow(
                    bucket_id=bid,
                    ambiguity_rule_cards=a,
                    conflict_rule_split_required=s,
                )
            )
        return out

    return FlagsDistributionResponse(
        computed_at=computed_at,
        explorer_available=True,
        note=None,
        summary=summary,
        by_lesson=_rows(by_lesson),
        by_concept=_rows(by_concept),
    )

