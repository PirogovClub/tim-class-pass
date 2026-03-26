"""Append-only adjudication repository and materialized state upserts."""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from pipeline.adjudication.enums import (
    CanonicalFamilyStatus,
    ConceptLinkStatus,
    DecisionType,
    EvidenceSupportStatus,
    MembershipRole,
    ProposalQueueName,
    ProposalStatus,
    ProposalType,
    QualityTier,
    RelationStatus,
    ReviewTargetType,
    ReviewerKind,
    RuleCardCoarseStatus,
)
from pipeline.adjudication.errors import FamilyNotFoundError, ReviewerNotFoundError
from pipeline.adjudication.models import (
    CanonicalRuleFamily,
    CanonicalRuleMembership,
    ConceptLinkReviewedState,
    EvidenceLinkReviewedState,
    MaterializedTierRecord,
    NewCanonicalFamily,
    NewMembership,
    NewReviewDecision,
    NewReviewer,
    ProposalRecord,
    RelatedRuleRelationReviewedState,
    ReviewDecision,
    Reviewer,
    RuleCardReviewedState,
)
from pipeline.adjudication.corpus_inventory import CorpusTargetIndex
from pipeline.adjudication.quality_tier import resolve_tier_for_target
from pipeline.adjudication.policy import assert_decision_allowed_for_target
from pipeline.adjudication.resolver import (
    resolve_concept_link_state,
    resolve_evidence_link_state,
    resolve_related_rule_relation_state,
    resolve_rule_card_state,
)
from pipeline.adjudication.time_utils import utc_now_iso

logger = logging.getLogger(__name__)

REQUIRED_TABLES = (
    "reviewers",
    "review_decisions",
    "canonical_rule_families",
    "canonical_rule_memberships",
    "rule_card_reviewed_state",
    "evidence_link_reviewed_state",
    "concept_link_reviewed_state",
    "related_rule_relation_reviewed_state",
    "materialized_tier_state",
    "adjudication_proposal",
)

TIER_MATERIALIZED_TARGET_TYPES = frozenset(
    {
        ReviewTargetType.RULE_CARD,
        ReviewTargetType.EVIDENCE_LINK,
        ReviewTargetType.CONCEPT_LINK,
        ReviewTargetType.RELATED_RULE_RELATION,
    }
)


def _bool_int(b: bool) -> int:
    return 1 if b else 0


def _row_reviewer(row: sqlite3.Row) -> Reviewer:
    return Reviewer(
        reviewer_id=row["reviewer_id"],
        reviewer_kind=ReviewerKind(row["reviewer_kind"]),
        display_name=row["display_name"],
        created_at=row["created_at"],
    )


def _row_decision(row: sqlite3.Row) -> ReviewDecision:
    return ReviewDecision(
        decision_id=row["decision_id"],
        target_type=ReviewTargetType(row["target_type"]),
        target_id=row["target_id"],
        decision_type=DecisionType(row["decision_type"]),
        reviewer_id=row["reviewer_id"],
        created_at=row["created_at"],
        note=row["note"],
        reason_code=row["reason_code"],
        related_target_id=row["related_target_id"],
        artifact_version=row["artifact_version"],
        proposal_id=row["proposal_id"],
        prior_state_json=row["prior_state_json"],
        new_state_json=row["new_state_json"],
    )


def _row_family(row: sqlite3.Row) -> CanonicalRuleFamily:
    return CanonicalRuleFamily(
        family_id=row["family_id"],
        canonical_title=row["canonical_title"],
        normalized_summary=row["normalized_summary"],
        status=CanonicalFamilyStatus(row["status"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        created_by=row["created_by"],
        primary_concept=row["primary_concept"],
        primary_subconcept=row["primary_subconcept"],
        review_completeness=row["review_completeness"],
    )


def _row_membership(row: sqlite3.Row) -> CanonicalRuleMembership:
    return CanonicalRuleMembership(
        membership_id=row["membership_id"],
        family_id=row["family_id"],
        rule_id=row["rule_id"],
        membership_role=MembershipRole(row["membership_role"]),
        added_by_decision_id=row["added_by_decision_id"],
        created_at=row["created_at"],
    )


def _assert_reviewer_exists(conn: sqlite3.Connection, reviewer_id: str) -> None:
    cur = conn.execute("SELECT 1 FROM reviewers WHERE reviewer_id = ?", (reviewer_id,))
    if cur.fetchone() is None:
        raise ReviewerNotFoundError(reviewer_id)


def _assert_family_exists(conn: sqlite3.Connection, family_id: str) -> None:
    cur = conn.execute(
        "SELECT 1 FROM canonical_rule_families WHERE family_id = ?",
        (family_id,),
    )
    if cur.fetchone() is None:
        raise FamilyNotFoundError(family_id)


def _prepare_decision_append(conn: sqlite3.Connection, payload: NewReviewDecision) -> None:
    assert_decision_allowed_for_target(payload.target_type, payload.decision_type)
    _assert_reviewer_exists(conn, payload.reviewer_id)
    if payload.target_type == ReviewTargetType.CANONICAL_RULE_FAMILY:
        _assert_family_exists(conn, payload.target_id)
    if (
        payload.target_type == ReviewTargetType.RULE_CARD
        and payload.decision_type == DecisionType.MERGE_INTO
        and payload.related_target_id
    ):
        _assert_family_exists(conn, payload.related_target_id)


STALE_AFTER_DECISION_REASON = "adjudication_decision_on_target"
STALE_NOT_IN_INVENTORY_REASON = "target_not_in_inventory"


def _proposal_list_filter_sql(
    *,
    proposal_type: ProposalType | None,
    proposal_status: ProposalStatus | None,
    source_target_type: ReviewTargetType | None,
    source_target_id: str | None,
    min_score: float | None,
) -> tuple[str, list[Any]]:
    where: list[str] = []
    args: list[Any] = []
    if proposal_type is not None:
        where.append("proposal_type = ?")
        args.append(proposal_type.value)
    if proposal_status is not None:
        where.append("proposal_status = ?")
        args.append(proposal_status.value)
    if source_target_type is not None:
        where.append("source_target_type = ?")
        args.append(source_target_type.value)
    if source_target_id is not None:
        where.append("source_target_id = ?")
        args.append(source_target_id)
    if min_score is not None:
        where.append("score >= ?")
        args.append(min_score)
    if not where:
        return "", []
    return f"WHERE {' AND '.join(where)}", args


def _decision_stale_touch_pairs(payload: NewReviewDecision) -> list[tuple[ReviewTargetType, str]]:
    """Targets touched by this decision; open proposals involving any pair become stale."""
    pairs: list[tuple[ReviewTargetType, str]] = [(payload.target_type, payload.target_id)]
    rid = (payload.related_target_id or "").strip()
    if not rid:
        return pairs
    if payload.target_type == ReviewTargetType.RULE_CARD:
        if payload.decision_type == DecisionType.DUPLICATE_OF:
            pairs.append((ReviewTargetType.RULE_CARD, rid))
        elif payload.decision_type == DecisionType.MERGE_INTO:
            pairs.append((ReviewTargetType.CANONICAL_RULE_FAMILY, rid))
    return pairs


class AdjudicationRepository:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def create_reviewer(self, reviewer: NewReviewer) -> Reviewer:
        created_at = utc_now_iso()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO reviewers (reviewer_id, reviewer_kind, display_name, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    reviewer.reviewer_id,
                    reviewer.reviewer_kind.value,
                    reviewer.display_name,
                    created_at,
                ),
            )
        logger.debug("Created reviewer %s", reviewer.reviewer_id)
        return Reviewer(
            reviewer_id=reviewer.reviewer_id,
            reviewer_kind=reviewer.reviewer_kind,
            display_name=reviewer.display_name,
            created_at=created_at,
        )

    def append_decision(self, payload: NewReviewDecision) -> ReviewDecision:
        payload = NewReviewDecision.model_validate(payload.model_dump())
        decision_id = str(uuid.uuid4())
        created_at = utc_now_iso()
        row = ReviewDecision(
            decision_id=decision_id,
            target_type=payload.target_type,
            target_id=payload.target_id,
            decision_type=payload.decision_type,
            reviewer_id=payload.reviewer_id,
            created_at=created_at,
            note=payload.note,
            reason_code=payload.reason_code,
            related_target_id=payload.related_target_id,
            artifact_version=payload.artifact_version,
            proposal_id=payload.proposal_id,
            prior_state_json=payload.prior_state_json,
            new_state_json=payload.new_state_json,
        )
        with self.connect() as conn:
            _prepare_decision_append(conn, payload)
            conn.execute(
                """
                INSERT INTO review_decisions (
                    decision_id, target_type, target_id, decision_type, reviewer_id,
                    created_at, note, reason_code, related_target_id, artifact_version,
                    proposal_id, prior_state_json, new_state_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row.decision_id,
                    row.target_type.value,
                    row.target_id,
                    row.decision_type.value,
                    row.reviewer_id,
                    row.created_at,
                    row.note,
                    row.reason_code,
                    row.related_target_id,
                    row.artifact_version,
                    row.proposal_id,
                    row.prior_state_json,
                    row.new_state_json,
                ),
            )
        logger.info(
            "Appended decision %s type=%s target=%s:%s",
            decision_id,
            row.decision_type.value,
            row.target_type.value,
            row.target_id,
        )
        return row

    def get_decisions_for_target(
        self, target_type: ReviewTargetType, target_id: str
    ) -> list[ReviewDecision]:
        with self.connect() as conn:
            cur = conn.execute(
                """
                SELECT * FROM review_decisions
                WHERE target_type = ? AND target_id = ?
                ORDER BY created_at ASC, decision_id ASC
                """,
                (target_type.value, target_id),
            )
            return [_row_decision(r) for r in cur.fetchall()]

    def get_decision_by_id(self, decision_id: str) -> ReviewDecision | None:
        with self.connect() as conn:
            cur = conn.execute(
                "SELECT * FROM review_decisions WHERE decision_id = ?",
                (decision_id,),
            )
            row = cur.fetchone()
            return _row_decision(row) if row else None

    def create_canonical_family(self, payload: NewCanonicalFamily) -> CanonicalRuleFamily:
        family_id = payload.family_id or str(uuid.uuid4())
        now = utc_now_iso()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO canonical_rule_families (
                    family_id, canonical_title, normalized_summary, status,
                    created_at, updated_at, created_by, primary_concept,
                    primary_subconcept, review_completeness
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    family_id,
                    payload.canonical_title,
                    payload.normalized_summary,
                    payload.status.value,
                    now,
                    now,
                    payload.created_by,
                    payload.primary_concept,
                    payload.primary_subconcept,
                    payload.review_completeness,
                ),
            )
        logger.info("Created canonical family %s", family_id)
        fam = self.get_family(family_id)
        assert fam is not None
        return fam

    def get_family(self, family_id: str) -> CanonicalRuleFamily | None:
        with self.connect() as conn:
            cur = conn.execute(
                "SELECT * FROM canonical_rule_families WHERE family_id = ?",
                (family_id,),
            )
            row = cur.fetchone()
            return _row_family(row) if row else None

    def list_family_members(self, family_id: str) -> list[CanonicalRuleMembership]:
        with self.connect() as conn:
            cur = conn.execute(
                """
                SELECT * FROM canonical_rule_memberships
                WHERE family_id = ?
                ORDER BY created_at ASC, membership_id ASC
                """,
                (family_id,),
            )
            return [_row_membership(r) for r in cur.fetchall()]

    def add_rule_to_family(self, payload: NewMembership) -> CanonicalRuleMembership:
        membership_id = str(uuid.uuid4())
        created_at = utc_now_iso()
        with self.connect() as conn:
            _assert_family_exists(conn, payload.family_id)
            conn.execute(
                """
                INSERT INTO canonical_rule_memberships (
                    membership_id, family_id, rule_id, membership_role,
                    added_by_decision_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(family_id, rule_id) DO UPDATE SET
                    membership_role = excluded.membership_role,
                    added_by_decision_id = COALESCE(excluded.added_by_decision_id, canonical_rule_memberships.added_by_decision_id)
                """,
                (
                    membership_id,
                    payload.family_id,
                    payload.rule_id,
                    payload.membership_role.value,
                    payload.added_by_decision_id,
                    created_at,
                ),
            )
        logger.debug(
            "Added rule %s to family %s role=%s",
            payload.rule_id,
            payload.family_id,
            payload.membership_role.value,
        )
        with self.connect() as conn:
            cur = conn.execute(
                """
                SELECT * FROM canonical_rule_memberships
                WHERE family_id = ? AND rule_id = ?
                """,
                (payload.family_id, payload.rule_id),
            )
            row = cur.fetchone()
        assert row is not None
        return _row_membership(row)

    def _family_id_for_rule(self, conn: sqlite3.Connection, rule_id: str) -> str | None:
        cur = conn.execute(
            """
            SELECT family_id FROM canonical_rule_memberships
            WHERE rule_id = ?
            ORDER BY family_id ASC
            LIMIT 1
            """,
            (rule_id,),
        )
        row = cur.fetchone()
        return str(row["family_id"]) if row else None

    def _upsert_rule_card_state(self, conn: sqlite3.Connection, state: RuleCardReviewedState) -> None:
        fam = state.canonical_family_id
        if fam is None:
            fam = self._family_id_for_rule(conn, state.target_id)
            state = state.model_copy(update={"canonical_family_id": fam})

        conn.execute(
            """
            INSERT OR REPLACE INTO rule_card_reviewed_state (
                target_id, current_status, latest_decision_type, canonical_family_id,
                is_duplicate, duplicate_of_rule_id, is_ambiguous, is_deferred, is_unsupported,
                last_reviewed_at, last_reviewer_id, last_decision_id, notes_summary
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                state.target_id,
                state.current_status.value if state.current_status else None,
                state.latest_decision_type.value if state.latest_decision_type else None,
                state.canonical_family_id,
                _bool_int(state.is_duplicate),
                state.duplicate_of_rule_id,
                _bool_int(state.is_ambiguous),
                _bool_int(state.is_deferred),
                _bool_int(state.is_unsupported),
                state.last_reviewed_at,
                state.last_reviewer_id,
                state.last_decision_id,
                state.notes_summary,
            ),
        )

    def _upsert_evidence_state(self, conn: sqlite3.Connection, state: EvidenceLinkReviewedState) -> None:
        conn.execute(
            """
            INSERT OR REPLACE INTO evidence_link_reviewed_state (
                target_id, support_status, last_reviewed_at, last_reviewer_id, last_decision_id
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                state.target_id,
                state.support_status.value if state.support_status else None,
                state.last_reviewed_at,
                state.last_reviewer_id,
                state.last_decision_id,
            ),
        )

    def _upsert_concept_state(self, conn: sqlite3.Connection, state: ConceptLinkReviewedState) -> None:
        conn.execute(
            """
            INSERT OR REPLACE INTO concept_link_reviewed_state (
                target_id, link_status, last_reviewed_at, last_reviewer_id, last_decision_id
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                state.target_id,
                state.link_status.value if state.link_status else None,
                state.last_reviewed_at,
                state.last_reviewer_id,
                state.last_decision_id,
            ),
        )

    def _upsert_relation_state(
        self, conn: sqlite3.Connection, state: RelatedRuleRelationReviewedState
    ) -> None:
        conn.execute(
            """
            INSERT OR REPLACE INTO related_rule_relation_reviewed_state (
                target_id, relation_status, last_reviewed_at, last_reviewer_id, last_decision_id
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                state.target_id,
                state.relation_status.value if state.relation_status else None,
                state.last_reviewed_at,
                state.last_reviewer_id,
                state.last_decision_id,
            ),
        )

    def _refresh_family_status_from_decision(
        self, conn: sqlite3.Connection, target_id: str, decision: ReviewDecision
    ) -> None:
        dt = decision.decision_type
        if dt == DecisionType.APPROVE:
            status = CanonicalFamilyStatus.ACTIVE.value
        elif dt == DecisionType.REJECT:
            status = CanonicalFamilyStatus.ARCHIVED.value
        elif dt in (DecisionType.NEEDS_REVIEW, DecisionType.DEFER, DecisionType.AMBIGUOUS):
            status = CanonicalFamilyStatus.DRAFT.value
        else:
            return
        now = utc_now_iso()
        conn.execute(
            """
            UPDATE canonical_rule_families
            SET status = ?, updated_at = ?
            WHERE family_id = ?
            """,
            (status, now, target_id),
        )

    def append_decision_and_refresh_state(self, payload: NewReviewDecision) -> ReviewDecision:
        payload = NewReviewDecision.model_validate(payload.model_dump())
        with self.connect() as conn:
            _prepare_decision_append(conn, payload)
            decision_id = str(uuid.uuid4())
            created_at = utc_now_iso()
            row = ReviewDecision(
                decision_id=decision_id,
                target_type=payload.target_type,
                target_id=payload.target_id,
                decision_type=payload.decision_type,
                reviewer_id=payload.reviewer_id,
                created_at=created_at,
                note=payload.note,
                reason_code=payload.reason_code,
                related_target_id=payload.related_target_id,
                artifact_version=payload.artifact_version,
                proposal_id=payload.proposal_id,
                prior_state_json=payload.prior_state_json,
                new_state_json=payload.new_state_json,
            )
            conn.execute(
                """
                INSERT INTO review_decisions (
                    decision_id, target_type, target_id, decision_type, reviewer_id,
                    created_at, note, reason_code, related_target_id, artifact_version,
                    proposal_id, prior_state_json, new_state_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row.decision_id,
                    row.target_type.value,
                    row.target_id,
                    row.decision_type.value,
                    row.reviewer_id,
                    row.created_at,
                    row.note,
                    row.reason_code,
                    row.related_target_id,
                    row.artifact_version,
                    row.proposal_id,
                    row.prior_state_json,
                    row.new_state_json,
                ),
            )
            logger.info(
                "Appended decision %s type=%s target=%s:%s",
                decision_id,
                row.decision_type.value,
                row.target_type.value,
                row.target_id,
            )

            if (
                payload.target_type == ReviewTargetType.RULE_CARD
                and payload.decision_type == DecisionType.MERGE_INTO
                and payload.related_target_id
            ):
                mid = str(uuid.uuid4())
                conn.execute(
                    """
                    INSERT INTO canonical_rule_memberships (
                        membership_id, family_id, rule_id, membership_role,
                        added_by_decision_id, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(family_id, rule_id) DO UPDATE SET
                        membership_role = excluded.membership_role,
                        added_by_decision_id = excluded.added_by_decision_id
                    """,
                    (
                        mid,
                        payload.related_target_id,
                        payload.target_id,
                        MembershipRole.MEMBER.value,
                        decision_id,
                        created_at,
                    ),
                )
                logger.debug(
                    "Linked rule %s to family %s via merge_into",
                    payload.target_id,
                    payload.related_target_id,
                )

            cur = conn.execute(
                """
                SELECT * FROM review_decisions
                WHERE target_type = ? AND target_id = ?
                ORDER BY created_at ASC, decision_id ASC
                """,
                (payload.target_type.value, payload.target_id),
            )
            decisions = [_row_decision(r) for r in cur.fetchall()]

            if payload.target_type == ReviewTargetType.RULE_CARD:
                st = resolve_rule_card_state(payload.target_id, decisions)
                self._upsert_rule_card_state(conn, st)
            elif payload.target_type == ReviewTargetType.EVIDENCE_LINK:
                st = resolve_evidence_link_state(payload.target_id, decisions)
                self._upsert_evidence_state(conn, st)
            elif payload.target_type == ReviewTargetType.CONCEPT_LINK:
                st = resolve_concept_link_state(payload.target_id, decisions)
                self._upsert_concept_state(conn, st)
            elif payload.target_type == ReviewTargetType.RELATED_RULE_RELATION:
                st = resolve_related_rule_relation_state(payload.target_id, decisions)
                self._upsert_relation_state(conn, st)
            elif payload.target_type == ReviewTargetType.CANONICAL_RULE_FAMILY:
                self._refresh_family_status_from_decision(conn, payload.target_id, row)
            else:
                raise ValueError(f"Unknown target_type {payload.target_type!r}")

            if payload.target_type != ReviewTargetType.CANONICAL_RULE_FAMILY:
                logger.debug(
                    "Refreshed reviewed state for %s:%s",
                    payload.target_type.value,
                    payload.target_id,
                )

            out_row = row

        if payload.target_type in TIER_MATERIALIZED_TARGET_TYPES:
            rec = resolve_tier_for_target(self, payload.target_type, payload.target_id)
            with self.connect() as conn:
                self._upsert_materialized_tier(conn, rec)

        if payload.target_type == ReviewTargetType.CANONICAL_RULE_FAMILY:
            self._refresh_rule_card_tiers_for_family(payload.target_id)

        if (
            payload.target_type == ReviewTargetType.RULE_CARD
            and payload.decision_type == DecisionType.MERGE_INTO
            and payload.related_target_id
        ):
            self._refresh_rule_card_tiers_for_family(payload.related_target_id)

        self.mark_new_proposals_stale_after_decision(
            payload, exclude_proposal_id=payload.proposal_id
        )

        return out_row

    def get_rule_card_state(self, target_id: str) -> RuleCardReviewedState | None:
        with self.connect() as conn:
            cur = conn.execute(
                "SELECT * FROM rule_card_reviewed_state WHERE target_id = ?",
                (target_id,),
            )
            row = cur.fetchone()
        if not row:
            return None

        return RuleCardReviewedState(
            target_id=row["target_id"],
            current_status=(
                RuleCardCoarseStatus(row["current_status"]) if row["current_status"] else None
            ),
            latest_decision_type=(
                DecisionType(row["latest_decision_type"]) if row["latest_decision_type"] else None
            ),
            canonical_family_id=row["canonical_family_id"],
            is_duplicate=bool(row["is_duplicate"]),
            duplicate_of_rule_id=row["duplicate_of_rule_id"],
            is_ambiguous=bool(row["is_ambiguous"]),
            is_deferred=bool(row["is_deferred"]),
            is_unsupported=bool(row["is_unsupported"]),
            last_reviewed_at=row["last_reviewed_at"],
            last_reviewer_id=row["last_reviewer_id"],
            last_decision_id=row["last_decision_id"],
            notes_summary=row["notes_summary"],
        )

    def get_evidence_link_state(self, target_id: str) -> EvidenceLinkReviewedState | None:
        with self.connect() as conn:
            cur = conn.execute(
                "SELECT * FROM evidence_link_reviewed_state WHERE target_id = ?",
                (target_id,),
            )
            row = cur.fetchone()
        if not row:
            return None
        return EvidenceLinkReviewedState(
            target_id=row["target_id"],
            support_status=(
                EvidenceSupportStatus(row["support_status"]) if row["support_status"] else None
            ),
            last_reviewed_at=row["last_reviewed_at"],
            last_reviewer_id=row["last_reviewer_id"],
            last_decision_id=row["last_decision_id"],
        )

    def get_concept_link_state(self, target_id: str) -> ConceptLinkReviewedState | None:
        with self.connect() as conn:
            cur = conn.execute(
                "SELECT * FROM concept_link_reviewed_state WHERE target_id = ?",
                (target_id,),
            )
            row = cur.fetchone()
        if not row:
            return None
        return ConceptLinkReviewedState(
            target_id=row["target_id"],
            link_status=ConceptLinkStatus(row["link_status"]) if row["link_status"] else None,
            last_reviewed_at=row["last_reviewed_at"],
            last_reviewer_id=row["last_reviewer_id"],
            last_decision_id=row["last_decision_id"],
        )

    def get_related_rule_relation_state(self, target_id: str) -> RelatedRuleRelationReviewedState | None:
        with self.connect() as conn:
            cur = conn.execute(
                "SELECT * FROM related_rule_relation_reviewed_state WHERE target_id = ?",
                (target_id,),
            )
            row = cur.fetchone()
        if not row:
            return None
        return RelatedRuleRelationReviewedState(
            target_id=row["target_id"],
            relation_status=(
                RelationStatus(row["relation_status"]) if row["relation_status"] else None
            ),
            last_reviewed_at=row["last_reviewed_at"],
            last_reviewer_id=row["last_reviewer_id"],
            last_decision_id=row["last_decision_id"],
        )

    def _upsert_materialized_tier(self, conn: sqlite3.Connection, rec: MaterializedTierRecord) -> None:
        conn.execute(
            """
            INSERT OR REPLACE INTO materialized_tier_state (
                target_type, target_id, tier, tier_reasons_json, blocker_codes_json,
                is_eligible, is_promotable_to_gold, resolved_at, policy_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                rec.target_type.value,
                rec.target_id,
                rec.tier.value,
                json.dumps(rec.tier_reasons),
                json.dumps(rec.blocker_codes),
                _bool_int(rec.is_eligible_for_downstream_use),
                _bool_int(rec.is_promotable_to_gold),
                rec.resolved_at,
                rec.policy_version,
            ),
        )

    def get_materialized_tier(
        self, target_type: ReviewTargetType, target_id: str
    ) -> MaterializedTierRecord | None:
        with self.connect() as conn:
            cur = conn.execute(
                """
                SELECT * FROM materialized_tier_state
                WHERE target_type = ? AND target_id = ?
                """,
                (target_type.value, target_id),
            )
            row = cur.fetchone()
        if not row:
            return None
        return MaterializedTierRecord(
            target_type=ReviewTargetType(row["target_type"]),
            target_id=row["target_id"],
            tier=QualityTier(row["tier"]),
            tier_reasons=json.loads(row["tier_reasons_json"]),
            blocker_codes=json.loads(row["blocker_codes_json"]),
            is_eligible_for_downstream_use=bool(row["is_eligible"]),
            is_promotable_to_gold=bool(row["is_promotable_to_gold"]),
            resolved_at=row["resolved_at"],
            policy_version=row["policy_version"],
        )

    def refresh_materialized_tier(
        self, target_type: ReviewTargetType, target_id: str
    ) -> MaterializedTierRecord:
        if target_type not in TIER_MATERIALIZED_TARGET_TYPES:
            raise ValueError(f"Unsupported target_type for tier materialization: {target_type!r}")
        rec = resolve_tier_for_target(self, target_type, target_id)
        with self.connect() as conn:
            self._upsert_materialized_tier(conn, rec)
        return rec

    def _rule_ids_for_family(self, conn: sqlite3.Connection, family_id: str) -> set[str]:
        ids: set[str] = set()
        cur = conn.execute(
            "SELECT rule_id FROM canonical_rule_memberships WHERE family_id = ?",
            (family_id,),
        )
        ids.update(str(r["rule_id"]) for r in cur.fetchall())
        cur = conn.execute(
            "SELECT target_id FROM rule_card_reviewed_state WHERE canonical_family_id = ?",
            (family_id,),
        )
        ids.update(str(r["target_id"]) for r in cur.fetchall())
        return ids

    def _refresh_rule_card_tiers_for_family(self, family_id: str) -> None:
        """Recompute materialized tiers for every rule linked to this family (status changes)."""
        with self.connect() as conn:
            rule_ids = self._rule_ids_for_family(conn, family_id)
            for rid in sorted(rule_ids):
                rec = resolve_tier_for_target(self, ReviewTargetType.RULE_CARD, rid)
                self._upsert_materialized_tier(conn, rec)

    def recompute_all_materialized_tiers(self, corpus_index: CorpusTargetIndex) -> dict[str, Any]:
        """Upsert tier rows for every inventory id; delete tier rows for ids not in inventory."""
        inv_by_type: dict[str, frozenset[str]] = {
            ReviewTargetType.RULE_CARD.value: corpus_index.rule_card_ids,
            ReviewTargetType.EVIDENCE_LINK.value: corpus_index.evidence_link_ids,
            ReviewTargetType.CONCEPT_LINK.value: corpus_index.concept_link_ids,
            ReviewTargetType.RELATED_RULE_RELATION.value: corpus_index.related_rule_relation_ids,
        }
        pairs: list[tuple[ReviewTargetType, str]] = []
        by_target_type: dict[str, int] = {}
        for tt, ids in (
            (ReviewTargetType.RULE_CARD, corpus_index.rule_card_ids),
            (ReviewTargetType.EVIDENCE_LINK, corpus_index.evidence_link_ids),
            (ReviewTargetType.CONCEPT_LINK, corpus_index.concept_link_ids),
            (ReviewTargetType.RELATED_RULE_RELATION, corpus_index.related_rule_relation_ids),
        ):
            by_target_type[tt.value] = len(ids)
            for tid in sorted(ids):
                pairs.append((tt, tid))

        with self.connect() as conn:
            cur = conn.execute("SELECT target_type, target_id FROM materialized_tier_state")
            for r in cur.fetchall():
                tt_s = str(r["target_type"])
                tid = str(r["target_id"])
                allowed = inv_by_type.get(tt_s)
                if allowed is None or tid not in allowed:
                    conn.execute(
                        "DELETE FROM materialized_tier_state WHERE target_type = ? AND target_id = ?",
                        (tt_s, tid),
                    )

            for tt, tid in pairs:
                rec = resolve_tier_for_target(self, tt, tid)
                self._upsert_materialized_tier(conn, rec)

        return {"total": len(pairs), "by_target_type": by_target_type}

    def list_materialized_tiers(
        self,
        *,
        tier: QualityTier,
        target_type: ReviewTargetType | None = None,
        limit: int = 500,
    ) -> list[MaterializedTierRecord]:
        lim = max(1, min(limit, 10_000))
        with self.connect() as conn:
            if target_type is None:
                cur = conn.execute(
                    """
                    SELECT * FROM materialized_tier_state
                    WHERE tier = ?
                    ORDER BY target_type, target_id
                    LIMIT ?
                    """,
                    (tier.value, lim),
                )
            else:
                cur = conn.execute(
                    """
                    SELECT * FROM materialized_tier_state
                    WHERE tier = ? AND target_type = ?
                    ORDER BY target_id
                    LIMIT ?
                    """,
                    (tier.value, target_type.value, lim),
                )
            rows = cur.fetchall()
        return [
            MaterializedTierRecord(
                target_type=ReviewTargetType(r["target_type"]),
                target_id=r["target_id"],
                tier=QualityTier(r["tier"]),
                tier_reasons=json.loads(r["tier_reasons_json"]),
                blocker_codes=json.loads(r["blocker_codes_json"]),
                is_eligible_for_downstream_use=bool(r["is_eligible"]),
                is_promotable_to_gold=bool(r["is_promotable_to_gold"]),
                resolved_at=r["resolved_at"],
                policy_version=r["policy_version"],
            )
            for r in rows
        ]

    def list_all_materialized_tiers(
        self,
        *,
        tier: QualityTier | None = None,
        target_type: ReviewTargetType | None = None,
    ) -> list[MaterializedTierRecord]:
        """All matching tier rows (no LIMIT), stable order for reproducible exports."""
        clauses: list[str] = []
        args: list[Any] = []
        if tier is not None:
            clauses.append("tier = ?")
            args.append(tier.value)
        if target_type is not None:
            clauses.append("target_type = ?")
            args.append(target_type.value)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"""
            SELECT * FROM materialized_tier_state
            {where}
            ORDER BY target_type ASC, target_id ASC
        """
        with self.connect() as conn:
            cur = conn.execute(sql, args)
            rows = cur.fetchall()
        return [
            MaterializedTierRecord(
                target_type=ReviewTargetType(r["target_type"]),
                target_id=r["target_id"],
                tier=QualityTier(r["tier"]),
                tier_reasons=json.loads(r["tier_reasons_json"]),
                blocker_codes=json.loads(r["blocker_codes_json"]),
                is_eligible_for_downstream_use=bool(r["is_eligible"]),
                is_promotable_to_gold=bool(r["is_promotable_to_gold"]),
                resolved_at=r["resolved_at"],
                policy_version=r["policy_version"],
            )
            for r in rows
        ]

    def list_canonical_families_by_status(
        self, status: CanonicalFamilyStatus
    ) -> list[CanonicalRuleFamily]:
        with self.connect() as conn:
            cur = conn.execute(
                """
                SELECT * FROM canonical_rule_families
                WHERE status = ?
                ORDER BY family_id ASC
                """,
                (status.value,),
            )
            rows = cur.fetchall()
        return [_row_family(r) for r in rows]

    def materialized_tier_counts(self) -> dict[str, Any]:
        """Nested counts: ``by_target_type`` and ``totals_by_tier``."""
        with self.connect() as conn:
            cur = conn.execute(
                """
                SELECT target_type, tier, COUNT(*) AS c
                FROM materialized_tier_state
                GROUP BY target_type, tier
                """
            )
            rows = cur.fetchall()
        by_tt: dict[str, dict[str, int]] = {}
        totals: dict[str, int] = {}
        for r in rows:
            tt = r["target_type"]
            tr = r["tier"]
            c = int(r["c"])
            by_tt.setdefault(tt, {})[tr] = c
            totals[tr] = totals.get(tr, 0) + c
        return {"by_target_type": by_tt, "totals_by_tier": totals}

    # ----- Stage 5.5 proposals -----

    def _row_proposal(self, row: sqlite3.Row) -> ProposalRecord:
        return ProposalRecord(
            proposal_id=row["proposal_id"],
            proposal_type=ProposalType(row["proposal_type"]),
            source_target_type=ReviewTargetType(row["source_target_type"]),
            source_target_id=row["source_target_id"],
            related_target_type=(
                ReviewTargetType(row["related_target_type"])
                if row["related_target_type"]
                else None
            ),
            related_target_id=row["related_target_id"],
            proposal_status=ProposalStatus(row["proposal_status"]),
            score=float(row["score"]),
            score_breakdown_json=row["score_breakdown_json"],
            rationale_summary=row["rationale_summary"],
            signals_json=row["signals_json"],
            evidence_refs_json=row["evidence_refs_json"],
            adjudication_snapshot_json=row["adjudication_snapshot_json"],
            tier_snapshot_json=row["tier_snapshot_json"],
            queue_priority=float(row["queue_priority"]),
            dedupe_key=row["dedupe_key"],
            generator_version=row["generator_version"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            last_generated_at=row["last_generated_at"],
            accepted_decision_id=row["accepted_decision_id"],
            stale_reason=row["stale_reason"],
        )

    def upsert_proposal(self, record: ProposalRecord) -> tuple[ProposalRecord, str]:
        """Insert or update by ``dedupe_key``. Returns (record, 'created'|'refreshed'|'unchanged')."""
        existing = self.get_proposal_by_dedupe_key(record.dedupe_key)
        if existing and existing.proposal_status in (
            ProposalStatus.DISMISSED,
            ProposalStatus.ACCEPTED,
        ):
            return existing, "unchanged"

        now = utc_now_iso()
        if existing:
            proposal_id = existing.proposal_id
            created_at = existing.created_at
            new_status = (
                ProposalStatus.NEW
                if existing.proposal_status == ProposalStatus.STALE
                else existing.proposal_status
            )
            if new_status == ProposalStatus.SUPERSEDED:
                new_status = ProposalStatus.NEW
            row_data = record.model_dump()
            row_data["proposal_id"] = proposal_id
            row_data["created_at"] = created_at
            row_data["updated_at"] = now
            row_data["last_generated_at"] = now
            row_data["proposal_status"] = new_status
            row_data["accepted_decision_id"] = None
            row_data["stale_reason"] = None
            rec = ProposalRecord.model_validate(row_data)
            with self.connect() as conn:
                conn.execute(
                    """
                    UPDATE adjudication_proposal SET
                        proposal_type = ?, source_target_type = ?, source_target_id = ?,
                        related_target_type = ?, related_target_id = ?,
                        proposal_status = ?, score = ?, score_breakdown_json = ?,
                        rationale_summary = ?, signals_json = ?, evidence_refs_json = ?,
                        adjudication_snapshot_json = ?, tier_snapshot_json = ?,
                        queue_priority = ?, generator_version = ?, updated_at = ?,
                        last_generated_at = ?, accepted_decision_id = ?, stale_reason = ?
                    WHERE proposal_id = ?
                    """,
                    (
                        rec.proposal_type.value,
                        rec.source_target_type.value,
                        rec.source_target_id,
                        rec.related_target_type.value if rec.related_target_type else None,
                        rec.related_target_id,
                        rec.proposal_status.value,
                        rec.score,
                        rec.score_breakdown_json,
                        rec.rationale_summary,
                        rec.signals_json,
                        rec.evidence_refs_json,
                        rec.adjudication_snapshot_json,
                        rec.tier_snapshot_json,
                        rec.queue_priority,
                        rec.generator_version,
                        rec.updated_at,
                        rec.last_generated_at,
                        rec.accepted_decision_id,
                        rec.stale_reason,
                        proposal_id,
                    ),
                )
            return self.get_proposal(proposal_id) or rec, "refreshed"

        proposal_id = (record.proposal_id or "").strip() or str(uuid.uuid4())
        rec = record.model_copy(
            update={
                "proposal_id": proposal_id,
                "created_at": now,
                "updated_at": now,
                "last_generated_at": now,
                "proposal_status": ProposalStatus.NEW,
            }
        )
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO adjudication_proposal (
                    proposal_id, proposal_type, source_target_type, source_target_id,
                    related_target_type, related_target_id, proposal_status, score,
                    score_breakdown_json, rationale_summary, signals_json, evidence_refs_json,
                    adjudication_snapshot_json, tier_snapshot_json, queue_priority, dedupe_key,
                    generator_version, created_at, updated_at, last_generated_at,
                    accepted_decision_id, stale_reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    rec.proposal_id,
                    rec.proposal_type.value,
                    rec.source_target_type.value,
                    rec.source_target_id,
                    rec.related_target_type.value if rec.related_target_type else None,
                    rec.related_target_id,
                    rec.proposal_status.value,
                    rec.score,
                    rec.score_breakdown_json,
                    rec.rationale_summary,
                    rec.signals_json,
                    rec.evidence_refs_json,
                    rec.adjudication_snapshot_json,
                    rec.tier_snapshot_json,
                    rec.queue_priority,
                    rec.dedupe_key,
                    rec.generator_version,
                    rec.created_at,
                    rec.updated_at,
                    rec.last_generated_at,
                    rec.accepted_decision_id,
                    rec.stale_reason,
                ),
            )
        return rec, "created"

    def get_proposal(self, proposal_id: str) -> ProposalRecord | None:
        with self.connect() as conn:
            cur = conn.execute(
                "SELECT * FROM adjudication_proposal WHERE proposal_id = ?",
                (proposal_id,),
            )
            row = cur.fetchone()
        return self._row_proposal(row) if row else None

    def get_proposal_by_dedupe_key(self, dedupe_key: str) -> ProposalRecord | None:
        with self.connect() as conn:
            cur = conn.execute(
                "SELECT * FROM adjudication_proposal WHERE dedupe_key = ?",
                (dedupe_key,),
            )
            row = cur.fetchone()
        return self._row_proposal(row) if row else None

    def mark_new_proposals_stale_after_decision(
        self,
        payload: NewReviewDecision,
        *,
        exclude_proposal_id: str | None = None,
    ) -> int:
        touch = _decision_stale_touch_pairs(payload)
        seen: set[tuple[str, str]] = set()
        uniq: list[tuple[ReviewTargetType, str]] = []
        for tt, tid in touch:
            key = (tt.value, tid)
            if key not in seen:
                seen.add(key)
                uniq.append((tt, tid))
        clauses: list[str] = []
        args: list[Any] = []
        for tt, tid in uniq:
            clauses.append("(source_target_type = ? AND source_target_id = ?)")
            args.extend([tt.value, tid])
            clauses.append(
                "(related_target_type IS NOT NULL AND TRIM(related_target_id) != '' "
                "AND related_target_type = ? AND related_target_id = ?)"
            )
            args.extend([tt.value, tid])
        if not clauses:
            return 0
        now = utc_now_iso()
        where_touch = " OR ".join(clauses)
        sql = f"""
            UPDATE adjudication_proposal
            SET proposal_status = ?, stale_reason = ?, updated_at = ?
            WHERE proposal_status = ?
              AND ({where_touch})
        """
        bind: list[Any] = [
            ProposalStatus.STALE.value,
            STALE_AFTER_DECISION_REASON,
            now,
            ProposalStatus.NEW.value,
        ] + args
        if exclude_proposal_id:
            sql += " AND proposal_id != ?"
            bind.append(exclude_proposal_id)
        with self.connect() as conn:
            cur = conn.execute(sql, bind)
            return int(cur.rowcount)

    def count_proposals(
        self,
        *,
        proposal_type: ProposalType | None = None,
        proposal_status: ProposalStatus | None = None,
        source_target_type: ReviewTargetType | None = None,
        source_target_id: str | None = None,
        min_score: float | None = None,
    ) -> int:
        clause, args = _proposal_list_filter_sql(
            proposal_type=proposal_type,
            proposal_status=proposal_status,
            source_target_type=source_target_type,
            source_target_id=source_target_id,
            min_score=min_score,
        )
        sql = f"SELECT COUNT(*) AS c FROM adjudication_proposal {clause}"
        with self.connect() as conn:
            cur = conn.execute(sql, args)
            row = cur.fetchone()
        return int(row["c"]) if row else 0

    def list_proposals(
        self,
        *,
        proposal_type: ProposalType | None = None,
        proposal_status: ProposalStatus | None = None,
        source_target_type: ReviewTargetType | None = None,
        source_target_id: str | None = None,
        min_score: float | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ProposalRecord]:
        lim = max(1, min(limit, 10_000))
        off = max(0, offset)
        clause, args = _proposal_list_filter_sql(
            proposal_type=proposal_type,
            proposal_status=proposal_status,
            source_target_type=source_target_type,
            source_target_id=source_target_id,
            min_score=min_score,
        )
        sql = f"""
            SELECT * FROM adjudication_proposal
            {clause}
            ORDER BY updated_at DESC, proposal_id
            LIMIT ? OFFSET ?
        """
        args = [*args, lim, off]
        with self.connect() as conn:
            cur = conn.execute(sql, args)
            rows = cur.fetchall()
        return [self._row_proposal(r) for r in rows]

    def mark_new_proposals_stale_when_missing_from_inventory(
        self, corpus_index: CorpusTargetIndex
    ) -> int:
        """Mark NEW proposals referencing rule_card ids or families absent from inventory / DB."""
        now = utc_now_iso()
        rule_ids = sorted(corpus_index.rule_card_ids)
        touch: list[str] = []
        args: list[Any] = [
            ProposalStatus.STALE.value,
            STALE_NOT_IN_INVENTORY_REASON,
            now,
            ProposalStatus.NEW.value,
        ]
        if rule_ids:
            ph = ",".join("?" * len(rule_ids))
            touch.append(
                f"(source_target_type = ? AND source_target_id NOT IN ({ph}))"
            )
            args.extend([ReviewTargetType.RULE_CARD.value, *rule_ids])
            touch.append(
                f"(related_target_type = ? AND TRIM(related_target_id) != '' "
                f"AND related_target_id NOT IN ({ph}))"
            )
            args.extend([ReviewTargetType.RULE_CARD.value, *rule_ids])
        else:
            touch.append("(source_target_type = ?)")
            args.append(ReviewTargetType.RULE_CARD.value)
            touch.append(
                "(related_target_type = ? AND TRIM(related_target_id) != '')"
            )
            args.append(ReviewTargetType.RULE_CARD.value)
        touch.append(
            "(related_target_type = ? AND (related_target_id IS NULL OR TRIM(related_target_id) = '' "
            "OR NOT EXISTS (SELECT 1 FROM canonical_rule_families f "
            "WHERE f.family_id = adjudication_proposal.related_target_id)))"
        )
        args.append(ReviewTargetType.CANONICAL_RULE_FAMILY.value)
        where_touch = " OR ".join(touch)
        sql = f"""
            UPDATE adjudication_proposal
            SET proposal_status = ?, stale_reason = ?, updated_at = ?
            WHERE proposal_status = ?
              AND ({where_touch})
        """
        with self.connect() as conn:
            cur = conn.execute(sql, args)
            return int(cur.rowcount)

    def mark_missing_generated_proposals_stale(
        self, generator_version: str, still_present_keys: set[str]
    ) -> int:
        now = utc_now_iso()
        with self.connect() as conn:
            if still_present_keys:
                placeholders = ",".join("?" * len(still_present_keys))
                cur = conn.execute(
                    f"""
                    UPDATE adjudication_proposal
                    SET proposal_status = ?, stale_reason = ?, updated_at = ?
                    WHERE generator_version = ?
                      AND proposal_status = ?
                      AND dedupe_key NOT IN ({placeholders})
                    """,
                    (
                        ProposalStatus.STALE.value,
                        "no_longer_generated",
                        now,
                        generator_version,
                        ProposalStatus.NEW.value,
                        *sorted(still_present_keys),
                    ),
                )
            else:
                cur = conn.execute(
                    """
                    UPDATE adjudication_proposal
                    SET proposal_status = ?, stale_reason = ?, updated_at = ?
                    WHERE generator_version = ?
                      AND proposal_status = ?
                    """,
                    (
                        ProposalStatus.STALE.value,
                        "no_longer_generated",
                        now,
                        generator_version,
                        ProposalStatus.NEW.value,
                    ),
                )
            return cur.rowcount

    def replace_or_refresh_generated_proposals(
        self, records: list[ProposalRecord], generator_version: str
    ) -> dict[str, int]:
        """Upsert all records; mark other NEW rows for this generator version stale."""
        created = 0
        refreshed = 0
        unchanged = 0
        keys: set[str] = set()
        for rec in records:
            r = rec.model_copy(update={"generator_version": generator_version})
            out, kind = self.upsert_proposal(r)
            keys.add(out.dedupe_key)
            if kind == "created":
                created += 1
            elif kind == "refreshed":
                refreshed += 1
            else:
                unchanged += 1
        stale = self.mark_missing_generated_proposals_stale(generator_version, keys)
        return {
            "created": created,
            "refreshed": refreshed,
            "marked_stale": stale,
            "skipped_unchanged_dedupe": unchanged,
        }

    def mark_proposal_accepted(self, proposal_id: str, decision_id: str) -> None:
        now = utc_now_iso()
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE adjudication_proposal
                SET proposal_status = ?, accepted_decision_id = ?, updated_at = ?,
                    stale_reason = NULL
                WHERE proposal_id = ?
                """,
                (ProposalStatus.ACCEPTED.value, decision_id, now, proposal_id),
            )

    def mark_proposal_dismissed(self, proposal_id: str, note: str | None = None) -> None:
        now = utc_now_iso()
        reason = note or "dismissed_by_reviewer"
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE adjudication_proposal
                SET proposal_status = ?, stale_reason = ?, updated_at = ?
                WHERE proposal_id = ?
                """,
                (ProposalStatus.DISMISSED.value, reason, now, proposal_id),
            )

    def mark_proposal_superseded(self, proposal_id: str, stale_reason: str) -> None:
        now = utc_now_iso()
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE adjudication_proposal
                SET proposal_status = ?, stale_reason = ?, updated_at = ?
                WHERE proposal_id = ?
                """,
                (ProposalStatus.SUPERSEDED.value, stale_reason, now, proposal_id),
            )

    def _open_proposal_queue_proposal_type(self, queue_name: str) -> ProposalType | None:
        try:
            qn = ProposalQueueName(queue_name)
        except ValueError:
            return None
        type_map = {
            ProposalQueueName.HIGH_CONFIDENCE_DUPLICATES: ProposalType.DUPLICATE_CANDIDATE,
            ProposalQueueName.MERGE_CANDIDATES: ProposalType.MERGE_CANDIDATE,
            ProposalQueueName.CANONICAL_FAMILY_CANDIDATES: ProposalType.CANONICAL_FAMILY_CANDIDATE,
        }
        return type_map.get(qn)

    def _open_proposal_queue_where(
        self,
        ptype: ProposalType,
        *,
        source_target_type: ReviewTargetType | None,
        quality_tier: str | None,
    ) -> tuple[str, list[Any]]:
        parts = ["proposal_type = ?", "proposal_status = ?"]
        args: list[Any] = [ptype.value, ProposalStatus.NEW.value]
        if source_target_type is not None:
            parts.append("source_target_type = ?")
            args.append(source_target_type.value)
        if quality_tier:
            parts.append(
                """EXISTS (
                SELECT 1 FROM materialized_tier_state m
                WHERE m.target_type = adjudication_proposal.source_target_type
                  AND m.target_id = adjudication_proposal.source_target_id
                  AND m.tier = ?
            )"""
            )
            args.append(quality_tier)
        return " AND ".join(parts), args

    def count_open_proposals_by_queue(
        self,
        queue_name: str,
        *,
        source_target_type: ReviewTargetType | None = None,
        quality_tier: str | None = None,
    ) -> int:
        ptype = self._open_proposal_queue_proposal_type(queue_name)
        if ptype is None:
            return 0
        where, args = self._open_proposal_queue_where(
            ptype,
            source_target_type=source_target_type,
            quality_tier=quality_tier,
        )
        sql = f"SELECT COUNT(*) AS c FROM adjudication_proposal WHERE {where}"
        with self.connect() as conn:
            cur = conn.execute(sql, args)
            row = cur.fetchone()
        return int(row["c"]) if row else 0

    def list_open_proposals_by_queue(
        self,
        queue_name: str,
        limit: int = 100,
        offset: int = 0,
        *,
        source_target_type: ReviewTargetType | None = None,
        quality_tier: str | None = None,
    ) -> list[ProposalRecord]:
        ptype = self._open_proposal_queue_proposal_type(queue_name)
        if ptype is None:
            return []
        where, args = self._open_proposal_queue_where(
            ptype,
            source_target_type=source_target_type,
            quality_tier=quality_tier,
        )
        lim = max(1, min(limit, 10_000))
        off = max(0, offset)
        sql = f"""
            SELECT * FROM adjudication_proposal
            WHERE {where}
            ORDER BY queue_priority DESC, score DESC, updated_at DESC, proposal_id
            LIMIT ? OFFSET ?
        """
        qargs = [*args, lim, off]
        with self.connect() as conn:
            cur = conn.execute(sql, qargs)
            rows = cur.fetchall()
        return [self._row_proposal(r) for r in rows]

    def list_open_proposals_for_target(
        self, target_type: ReviewTargetType, target_id: str
    ) -> list[ProposalRecord]:
        with self.connect() as conn:
            cur = conn.execute(
                """
                SELECT * FROM adjudication_proposal
                WHERE proposal_status = ?
                  AND (
                    (source_target_type = ? AND source_target_id = ?)
                    OR (related_target_type = ? AND related_target_id = ?)
                  )
                ORDER BY queue_priority DESC, score DESC, updated_at DESC, proposal_id
                """,
                (
                    ProposalStatus.NEW.value,
                    target_type.value,
                    target_id,
                    target_type.value,
                    target_id,
                ),
            )
            rows = cur.fetchall()
        return [self._row_proposal(r) for r in rows]

    def get_active_family_id_for_rule(self, rule_id: str) -> str | None:
        """Active canonical family id if the rule is linked (state or membership)."""
        state = self.get_rule_card_state(rule_id)
        if state and state.canonical_family_id:
            fam = self.get_family(state.canonical_family_id)
            if fam is not None and fam.status == CanonicalFamilyStatus.ACTIVE:
                return fam.family_id
        with self.connect() as conn:
            cur = conn.execute(
                """
                SELECT m.family_id
                FROM canonical_rule_memberships m
                JOIN canonical_rule_families f ON f.family_id = m.family_id
                WHERE m.rule_id = ? AND f.status = ?
                LIMIT 1
                """,
                (rule_id, CanonicalFamilyStatus.ACTIVE.value),
            )
            row = cur.fetchone()
        return str(row["family_id"]) if row else None
