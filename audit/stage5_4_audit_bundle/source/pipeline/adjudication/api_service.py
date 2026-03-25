"""Service layer for adjudication read/write APIs (Stage 5.2)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pipeline.adjudication.api_errors import AdjudicationApiError, ErrorCode, map_integrity_error
from pipeline.adjudication.api_models import (
    DecisionHistoryEntry,
    DecisionSubmissionRequest,
    DecisionSubmissionResponse,
    FamilyDetailResponse,
    FamilyMemberEntry,
    FamilyMembersResponse,
    ReviewHistoryResponse,
    ReviewItemResponse,
    TierListResponse,
    TierStateResponse,
    TierCountsResponse,
)
from pipeline.adjudication.corpus_inventory import CorpusTargetIndex
from pipeline.adjudication.enums import DecisionType, QualityTier, ReviewTargetType
from pipeline.adjudication.models import MaterializedTierRecord
from pipeline.adjudication.errors import AdjudicationIntegrityError
from pipeline.adjudication.models import NewReviewDecision, ReviewDecision
from pipeline.adjudication.repository import AdjudicationRepository

if TYPE_CHECKING:
    from pipeline.explorer.service import ExplorerService


def _decision_entry(d: ReviewDecision) -> DecisionHistoryEntry:
    return DecisionHistoryEntry(
        decision_id=d.decision_id,
        target_type=d.target_type.value,
        target_id=d.target_id,
        decision_type=d.decision_type.value,
        reviewer_id=d.reviewer_id,
        created_at=d.created_at,
        note=d.note,
        reason_code=d.reason_code,
        related_target_id=d.related_target_id,
        artifact_version=d.artifact_version,
        proposal_id=d.proposal_id,
    )


def _empty_review_item(tt: ReviewTargetType, target_id: str) -> ReviewItemResponse:
    return ReviewItemResponse(target_type=tt, target_id=target_id)


def get_review_item(repo: AdjudicationRepository, target_type: ReviewTargetType, target_id: str) -> ReviewItemResponse:
    if target_type == ReviewTargetType.CANONICAL_RULE_FAMILY:
        fam = repo.get_family(target_id)
        if fam is None:
            raise AdjudicationApiError(
                error_code=ErrorCode.NOT_FOUND,
                message=f"Canonical family {target_id!r} not found",
                status_code=404,
                details={"family_id": target_id},
            )
        decisions = repo.get_decisions_for_target(target_type, target_id)
        latest = decisions[-1].decision_type.value if decisions else None
        return ReviewItemResponse(
            target_type=target_type,
            target_id=target_id,
            current_status=fam.status.value,
            latest_decision_type=latest,
            last_reviewed_at=decisions[-1].created_at if decisions else None,
            last_reviewer_id=decisions[-1].reviewer_id if decisions else None,
            summary=fam.canonical_title,
        )

    if target_type == ReviewTargetType.RULE_CARD:
        st = repo.get_rule_card_state(target_id)
        if st is None:
            return _empty_review_item(target_type, target_id)
        return ReviewItemResponse(
            target_type=target_type,
            target_id=target_id,
            current_status=st.current_status.value if st.current_status else None,
            latest_decision_type=st.latest_decision_type.value if st.latest_decision_type else None,
            last_reviewed_at=st.last_reviewed_at,
            last_reviewer_id=st.last_reviewer_id,
            canonical_family_id=st.canonical_family_id,
            summary=st.notes_summary,
            is_duplicate=st.is_duplicate,
            duplicate_of_rule_id=st.duplicate_of_rule_id,
            is_ambiguous=st.is_ambiguous,
            is_deferred=st.is_deferred,
            is_unsupported=st.is_unsupported,
        )

    if target_type == ReviewTargetType.EVIDENCE_LINK:
        st = repo.get_evidence_link_state(target_id)
        if st is None:
            return _empty_review_item(target_type, target_id)
        return ReviewItemResponse(
            target_type=target_type,
            target_id=target_id,
            latest_decision_type=None,
            last_reviewed_at=st.last_reviewed_at,
            last_reviewer_id=st.last_reviewer_id,
            support_status=st.support_status.value if st.support_status else None,
        )

    if target_type == ReviewTargetType.CONCEPT_LINK:
        st = repo.get_concept_link_state(target_id)
        if st is None:
            return _empty_review_item(target_type, target_id)
        return ReviewItemResponse(
            target_type=target_type,
            target_id=target_id,
            last_reviewed_at=st.last_reviewed_at,
            last_reviewer_id=st.last_reviewer_id,
            link_status=st.link_status.value if st.link_status else None,
        )

    if target_type == ReviewTargetType.RELATED_RULE_RELATION:
        st = repo.get_related_rule_relation_state(target_id)
        if st is None:
            return _empty_review_item(target_type, target_id)
        return ReviewItemResponse(
            target_type=target_type,
            target_id=target_id,
            last_reviewed_at=st.last_reviewed_at,
            last_reviewer_id=st.last_reviewer_id,
            relation_status=st.relation_status.value if st.relation_status else None,
        )

    raise AdjudicationApiError(
        error_code=ErrorCode.BAD_REQUEST,
        message=f"Unsupported target_type {target_type!r}",
        status_code=400,
    )


def get_review_history(
    repo: AdjudicationRepository, target_type: ReviewTargetType, target_id: str
) -> ReviewHistoryResponse:
    if target_type == ReviewTargetType.CANONICAL_RULE_FAMILY and repo.get_family(target_id) is None:
        raise AdjudicationApiError(
            error_code=ErrorCode.NOT_FOUND,
            message=f"Canonical family {target_id!r} not found",
            status_code=404,
            details={"family_id": target_id},
        )
    decisions = repo.get_decisions_for_target(target_type, target_id)
    return ReviewHistoryResponse(
        target_type=target_type,
        target_id=target_id,
        decisions=[_decision_entry(d) for d in decisions],
    )


def get_family_detail(repo: AdjudicationRepository, family_id: str) -> FamilyDetailResponse:
    fam = repo.get_family(family_id)
    if fam is None:
        raise AdjudicationApiError(
            error_code=ErrorCode.NOT_FOUND,
            message=f"Family {family_id!r} not found",
            status_code=404,
            details={"family_id": family_id},
        )
    return FamilyDetailResponse(
        family_id=fam.family_id,
        canonical_title=fam.canonical_title,
        normalized_summary=fam.normalized_summary,
        status=fam.status.value,
        created_at=fam.created_at,
        updated_at=fam.updated_at,
        created_by=fam.created_by,
        primary_concept=fam.primary_concept,
        primary_subconcept=fam.primary_subconcept,
        review_completeness=fam.review_completeness,
    )


def _raise_unknown_corpus_target(
    target_type: ReviewTargetType,
    target_id: str,
    *,
    field: str = "target_id",
) -> None:
    raise AdjudicationApiError(
        error_code=ErrorCode.UNKNOWN_CORPUS_TARGET,
        message=f"Unknown corpus target {target_type.value} {target_id!r} (not in explorer inventory)",
        status_code=404,
        details={"target_type": target_type.value, "target_id": target_id, "field": field},
    )


def validate_corpus_targets_for_write(corpus_index: CorpusTargetIndex, req: DecisionSubmissionRequest) -> None:
    """Ensure primary and related rule targets exist in the corpus index before persistence."""
    if req.target_type == ReviewTargetType.CANONICAL_RULE_FAMILY:
        return
    if not corpus_index.contains(req.target_type, req.target_id):
        _raise_unknown_corpus_target(req.target_type, req.target_id)

    if req.decision_type == DecisionType.DUPLICATE_OF and req.target_type == ReviewTargetType.RULE_CARD:
        rid = req.related_target_id
        if not rid or not corpus_index.contains(ReviewTargetType.RULE_CARD, rid):
            _raise_unknown_corpus_target(
                ReviewTargetType.RULE_CARD,
                rid or "",
                field="related_target_id",
            )


def get_family_members(repo: AdjudicationRepository, family_id: str) -> FamilyMembersResponse:
    if repo.get_family(family_id) is None:
        raise AdjudicationApiError(
            error_code=ErrorCode.NOT_FOUND,
            message=f"Family {family_id!r} not found",
            status_code=404,
            details={"family_id": family_id},
        )
    rows = repo.list_family_members(family_id)
    return FamilyMembersResponse(
        family_id=family_id,
        members=[
            FamilyMemberEntry(
                membership_id=m.membership_id,
                family_id=m.family_id,
                rule_id=m.rule_id,
                membership_role=m.membership_role.value,
                added_by_decision_id=m.added_by_decision_id,
                created_at=m.created_at,
            )
            for m in rows
        ],
    )


def submit_decision(
    repo: AdjudicationRepository,
    req: DecisionSubmissionRequest,
    corpus_index: CorpusTargetIndex | None,
) -> DecisionSubmissionResponse:
    from pydantic import ValidationError

    try:
        payload = NewReviewDecision(
            target_type=req.target_type,
            target_id=req.target_id,
            decision_type=req.decision_type,
            reviewer_id=req.reviewer_id,
            note=req.note,
            reason_code=req.reason_code,
            related_target_id=req.related_target_id,
            artifact_version=req.artifact_version,
            proposal_id=req.proposal_id,
        )
    except ValidationError as e:
        safe_errors = [{k: v for k, v in err.items() if k != "ctx"} for err in e.errors()]
        raise AdjudicationApiError(
            error_code=ErrorCode.VALIDATION_ERROR,
            message="Invalid decision payload",
            status_code=422,
            details={"errors": safe_errors},
        ) from e

    if req.target_type != ReviewTargetType.CANONICAL_RULE_FAMILY:
        if corpus_index is None:
            raise AdjudicationApiError(
                error_code=ErrorCode.CORPUS_INDEX_UNAVAILABLE,
                message="Corpus index is not configured; cannot validate adjudication targets.",
                status_code=503,
                details={"target_type": req.target_type.value},
            )
        validate_corpus_targets_for_write(corpus_index, req)

    try:
        d = repo.append_decision_and_refresh_state(payload)
    except AdjudicationIntegrityError as e:
        raise map_integrity_error(e) from e

    updated = get_review_item(repo, req.target_type, req.target_id)
    fam_summary = None
    if req.decision_type == DecisionType.MERGE_INTO and req.related_target_id:
        fam_summary = {
            "merge_into_family_id": req.related_target_id,
            "rule_id": req.target_id,
        }
    return DecisionSubmissionResponse(
        decision_id=d.decision_id,
        target_type=req.target_type,
        target_id=req.target_id,
        updated_state=updated,
        family_linkage_summary=fam_summary,
    )


def _tier_state_response(rec: MaterializedTierRecord) -> TierStateResponse:
    return TierStateResponse(
        target_type=rec.target_type,
        target_id=rec.target_id,
        tier=rec.tier.value,
        tier_reasons=rec.tier_reasons,
        blocker_codes=rec.blocker_codes,
        is_eligible_for_downstream_use=rec.is_eligible_for_downstream_use,
        is_promotable_to_gold=rec.is_promotable_to_gold,
        resolved_at=rec.resolved_at,
        policy_version=rec.policy_version,
    )


def get_tier_for_target(
    repo: AdjudicationRepository,
    target_type: ReviewTargetType,
    target_id: str,
    *,
    refresh_if_missing: bool = True,
) -> TierStateResponse:
    from pipeline.adjudication.repository import TIER_MATERIALIZED_TARGET_TYPES

    if target_type not in TIER_MATERIALIZED_TARGET_TYPES:
        raise AdjudicationApiError(
            error_code=ErrorCode.BAD_REQUEST,
            message=f"Tiering not supported for target_type {target_type.value!r}",
            status_code=400,
            details={"target_type": target_type.value},
        )
    rec = repo.get_materialized_tier(target_type, target_id)
    if rec is None:
        if not refresh_if_missing:
            raise AdjudicationApiError(
                error_code=ErrorCode.NOT_FOUND,
                message="No tier row for target (run a decision or refresh tier)",
                status_code=404,
                details={"target_type": target_type.value, "target_id": target_id},
            )
        rec = repo.refresh_materialized_tier(target_type, target_id)
    return _tier_state_response(rec)


def list_tiers_by_tier(
    repo: AdjudicationRepository,
    tier: QualityTier,
    target_type: ReviewTargetType | None,
    limit: int,
) -> TierListResponse:
    rows = repo.list_materialized_tiers(tier=tier, target_type=target_type, limit=limit)
    return TierListResponse(
        tier=tier.value,
        target_type=target_type.value if target_type else None,
        items=[_tier_state_response(r) for r in rows],
        total=len(rows),
    )


def get_tier_counts(repo: AdjudicationRepository) -> TierCountsResponse:
    raw = repo.materialized_tier_counts()
    return TierCountsResponse(
        by_target_type=raw["by_target_type"],
        totals_by_tier=raw["totals_by_tier"],
    )


def fetch_optional_rule_context(explorer: ExplorerService | None, doc_id: str) -> dict:
    if explorer is None:
        return {}
    try:
        detail = explorer.get_rule_detail(doc_id)
        return {"rule_detail": detail.model_dump(mode="json")}
    except Exception:
        return {}
