"""Append-only adjudication repository and materialized state upserts."""

from __future__ import annotations

import logging
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from pipeline.adjudication.enums import (
    CanonicalFamilyStatus,
    ConceptLinkStatus,
    DecisionType,
    EvidenceSupportStatus,
    MembershipRole,
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
    NewCanonicalFamily,
    NewMembership,
    NewReviewDecision,
    NewReviewer,
    RelatedRuleRelationReviewedState,
    ReviewDecision,
    Reviewer,
    RuleCardReviewedState,
)
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

        return row

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
