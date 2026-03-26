"""FastAPI routes for Stage 5.2 adjudication API."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Query

from pipeline.adjudication.api_errors import AdjudicationApiError, ErrorCode
from pipeline.adjudication.api_models import (
    DecisionSubmissionRequest,
    DecisionSubmissionResponse,
    FamilyDetailResponse,
    FamilyMembersResponse,
    ProposalDetailResponse,
    ProposalDismissRequest,
    ProposalGenerateRequest,
    ProposalGenerateResponse,
    ProposalListResponse,
    ProposalRecordResponse,
    QueueItemResponse,
    QueueListResponse,
    ReviewBundleResponse,
    ReviewHistoryResponse,
    ReviewItemResponse,
    TierCountsResponse,
    TierListResponse,
    TierRecomputeResponse,
    TierStateResponse,
)
from pipeline.adjudication.api_service import (
    dismiss_proposal,
    generate_proposals,
    get_family_detail,
    get_family_members,
    get_proposal_detail,
    get_review_history,
    get_review_item,
    get_tier_counts,
    get_tier_for_target,
    list_proposals_api,
    list_tiers_by_tier,
    recompute_all_tier_rows,
    submit_decision,
)
from pipeline.adjudication.bootstrap import initialize_adjudication_storage
from pipeline.adjudication.bundle_service import get_review_bundle
from pipeline.adjudication.corpus_inventory import CorpusTargetIndex
from pipeline.adjudication.enums import QualityTier, ReviewTargetType
from pipeline.adjudication.queue_service import (
    get_next_queue_item,
    list_proposal_queue,
    list_queue_by_target,
    list_unresolved_queue,
)
from pipeline.adjudication.repository import AdjudicationRepository

if TYPE_CHECKING:
    from pipeline.explorer.service import ExplorerService

adjudication_router = APIRouter(prefix="/adjudication", tags=["adjudication"])

_adjudication_repo: AdjudicationRepository | None = None
_explorer_for_bundle: ExplorerService | None = None
_corpus_index: CorpusTargetIndex | None = None


def init_adjudication(
    db_path: str | Path,
    explorer: ExplorerService | None = None,
    *,
    corpus_index: CorpusTargetIndex | None = None,
) -> None:
    """Initialize SQLite schema and repository. Call once at app startup.

    When ``explorer`` is set and ``corpus_index`` is omitted, the index is built from
    ``explorer._repo`` (retrieval corpus). Queue and non-family writes require a corpus index.
    """
    global _adjudication_repo, _explorer_for_bundle, _corpus_index
    path = Path(db_path)
    initialize_adjudication_storage(path)
    _adjudication_repo = AdjudicationRepository(path)
    _explorer_for_bundle = explorer
    if corpus_index is not None:
        _corpus_index = corpus_index
    elif explorer is not None:
        _corpus_index = CorpusTargetIndex.from_explorer_repository(explorer._repo)
    else:
        _corpus_index = None


def get_corpus_index_optional() -> CorpusTargetIndex | None:
    """May be None when explorer was not wired; family-only writes still allowed."""
    return _corpus_index


def get_explorer_optional() -> ExplorerService | None:
    return _explorer_for_bundle


def get_corpus_index() -> CorpusTargetIndex:
    if _corpus_index is None:
        raise HTTPException(
            status_code=503,
            detail={
                "error_code": "corpus_index_unavailable",
                "message": "Corpus index not configured; queues and corpus target writes unavailable",
            },
        )
    return _corpus_index


def get_adjudication_repo() -> AdjudicationRepository:
    if _adjudication_repo is None:
        raise HTTPException(
            status_code=503,
            detail={
                "error_code": "service_unavailable",
                "message": "Adjudication API not initialized",
            },
        )
    return _adjudication_repo


def _parse_target_type(raw: str) -> ReviewTargetType:
    try:
        return ReviewTargetType(raw)
    except ValueError:
        raise AdjudicationApiError(
            error_code=ErrorCode.VALIDATION_ERROR,
            message=f"Invalid target_type {raw!r}",
            status_code=400,
            details={"target_type": raw},
        )


def _parse_optional_quality_tier(raw: str | None) -> str | None:
    if raw is None or raw == "":
        return None
    try:
        return QualityTier(raw).value
    except ValueError:
        raise AdjudicationApiError(
            error_code=ErrorCode.VALIDATION_ERROR,
            message=f"Invalid quality_tier {raw!r}",
            status_code=400,
            details={"quality_tier": raw},
        ) from None


@adjudication_router.get("/review-item", response_model=ReviewItemResponse)
def review_item(
    target_type: str = Query(..., description="ReviewTargetType value"),
    target_id: str = Query(..., min_length=1),
    repo: AdjudicationRepository = Depends(get_adjudication_repo),
) -> ReviewItemResponse:
    tt = _parse_target_type(target_type)
    return get_review_item(repo, tt, target_id)


@adjudication_router.get("/review-history", response_model=ReviewHistoryResponse)
def review_history(
    target_type: str = Query(...),
    target_id: str = Query(..., min_length=1),
    repo: AdjudicationRepository = Depends(get_adjudication_repo),
) -> ReviewHistoryResponse:
    tt = _parse_target_type(target_type)
    return get_review_history(repo, tt, target_id)


@adjudication_router.get("/review-bundle", response_model=ReviewBundleResponse)
def review_bundle(
    target_type: str = Query(...),
    target_id: str = Query(..., min_length=1),
    repo: AdjudicationRepository = Depends(get_adjudication_repo),
    corpus_index: CorpusTargetIndex | None = Depends(get_corpus_index_optional),
) -> ReviewBundleResponse:
    tt = _parse_target_type(target_type)
    return get_review_bundle(
        repo, tt, target_id, explorer=_explorer_for_bundle, corpus_index=corpus_index
    )


@adjudication_router.get("/families/{family_id}", response_model=FamilyDetailResponse)
def family_detail(
    family_id: str,
    repo: AdjudicationRepository = Depends(get_adjudication_repo),
) -> FamilyDetailResponse:
    return get_family_detail(repo, family_id)


@adjudication_router.get("/families/{family_id}/members", response_model=FamilyMembersResponse)
def family_members(
    family_id: str,
    repo: AdjudicationRepository = Depends(get_adjudication_repo),
) -> FamilyMembersResponse:
    return get_family_members(repo, family_id)


@adjudication_router.post("/decision", response_model=DecisionSubmissionResponse)
def post_decision(
    body: DecisionSubmissionRequest,
    repo: AdjudicationRepository = Depends(get_adjudication_repo),
    corpus_index: CorpusTargetIndex | None = Depends(get_corpus_index_optional),
) -> DecisionSubmissionResponse:
    return submit_decision(repo, body, corpus_index)


@adjudication_router.get("/queues/unresolved")
def queues_unresolved(
    repo: AdjudicationRepository = Depends(get_adjudication_repo),
    corpus_index: CorpusTargetIndex = Depends(get_corpus_index),
) -> dict:
    return list_unresolved_queue(repo, corpus_index).model_dump()


@adjudication_router.get("/queues/by-target")
def queues_by_target(
    target_type: str = Query(...),
    repo: AdjudicationRepository = Depends(get_adjudication_repo),
    corpus_index: CorpusTargetIndex = Depends(get_corpus_index),
) -> dict:
    tt = _parse_target_type(target_type)
    return list_queue_by_target(repo, tt, corpus_index).model_dump()


@adjudication_router.get("/tier", response_model=TierStateResponse)
def adjudication_tier(
    target_type: str = Query(...),
    target_id: str = Query(..., min_length=1),
    repo: AdjudicationRepository = Depends(get_adjudication_repo),
    corpus_index: CorpusTargetIndex = Depends(get_corpus_index),
) -> TierStateResponse:
    tt = _parse_target_type(target_type)
    return get_tier_for_target(repo, tt, target_id, corpus_index=corpus_index)


@adjudication_router.get("/tiers/by-tier", response_model=TierListResponse)
def tiers_by_tier(
    tier: str = Query(..., description="gold|silver|bronze|unresolved"),
    target_type: str | None = Query(None),
    limit: int = Query(500, ge=1, le=10_000),
    repo: AdjudicationRepository = Depends(get_adjudication_repo),
) -> TierListResponse:
    try:
        t = QualityTier(tier)
    except ValueError as e:
        raise AdjudicationApiError(
            error_code=ErrorCode.VALIDATION_ERROR,
            message=f"Invalid tier {tier!r}",
            status_code=400,
            details={"tier": tier},
        ) from e
    tt = _parse_target_type(target_type) if target_type else None
    return list_tiers_by_tier(repo, t, tt, limit)


@adjudication_router.get("/tiers/counts", response_model=TierCountsResponse)
def tiers_counts(
    repo: AdjudicationRepository = Depends(get_adjudication_repo),
) -> TierCountsResponse:
    return get_tier_counts(repo)


@adjudication_router.post("/tiers/recompute-all", response_model=TierRecomputeResponse)
def tiers_recompute_all(
    repo: AdjudicationRepository = Depends(get_adjudication_repo),
    corpus_index: CorpusTargetIndex = Depends(get_corpus_index),
) -> TierRecomputeResponse:
    """Recompute and upsert tier rows for every corpus inventory id; purge orphan tier rows."""
    return recompute_all_tier_rows(repo, corpus_index)


@adjudication_router.get("/queues/next", response_model=QueueItemResponse | None)
def queues_next(
    queue: str = Query(
        "unresolved",
        description="unresolved | high_confidence_duplicates | merge_candidates | canonical_family_candidates",
    ),
    target_type: str | None = Query(None),
    quality_tier: str | None = Query(
        None, description="Optional materialized tier filter for proposal queues (gold|silver|bronze|unresolved)"
    ),
    repo: AdjudicationRepository = Depends(get_adjudication_repo),
    corpus_index: CorpusTargetIndex = Depends(get_corpus_index),
) -> QueueItemResponse | None:
    tt = _parse_target_type(target_type) if target_type else None
    qt = _parse_optional_quality_tier(quality_tier)
    return get_next_queue_item(repo, queue, tt, corpus_index, quality_tier=qt)


@adjudication_router.get("/queues/proposals", response_model=QueueListResponse)
def queues_proposals(
    queue: str = Query(
        ...,
        description="high_confidence_duplicates | merge_candidates | canonical_family_candidates",
    ),
    limit: int = Query(500, ge=1, le=10_000),
    offset: int = Query(0, ge=0),
    target_type: str | None = Query(None, description="Filter by proposal source_target_type"),
    quality_tier: str | None = Query(
        None, description="Filter by materialized tier of the proposal source target"
    ),
    repo: AdjudicationRepository = Depends(get_adjudication_repo),
) -> QueueListResponse:
    tt = _parse_target_type(target_type) if target_type else None
    qt = _parse_optional_quality_tier(quality_tier)
    return list_proposal_queue(
        repo, queue, limit=limit, offset=offset, source_target_type=tt, quality_tier=qt
    )


@adjudication_router.post("/proposals/generate", response_model=ProposalGenerateResponse)
def proposals_generate(
    body: ProposalGenerateRequest,
    repo: AdjudicationRepository = Depends(get_adjudication_repo),
    corpus_index: CorpusTargetIndex = Depends(get_corpus_index),
    explorer: ExplorerService | None = Depends(get_explorer_optional),
) -> ProposalGenerateResponse:
    return generate_proposals(repo, corpus_index, explorer, body)


@adjudication_router.get("/proposals", response_model=ProposalListResponse)
def proposals_list(
    proposal_type: str | None = Query(None),
    proposal_status: str | None = Query(None),
    source_target_type: str | None = Query(None),
    source_target_id: str | None = Query(None),
    queue_name: str | None = Query(None),
    min_score: float | None = Query(None),
    limit: int = Query(100, ge=1, le=10_000),
    offset: int = Query(0, ge=0),
    repo: AdjudicationRepository = Depends(get_adjudication_repo),
) -> ProposalListResponse:
    return list_proposals_api(
        repo,
        proposal_type=proposal_type,
        proposal_status=proposal_status,
        source_target_type=source_target_type,
        source_target_id=source_target_id,
        queue_name=queue_name,
        min_score=min_score,
        limit=limit,
        offset=offset,
    )


@adjudication_router.get("/proposals/{proposal_id}", response_model=ProposalDetailResponse)
def proposals_detail(
    proposal_id: str,
    repo: AdjudicationRepository = Depends(get_adjudication_repo),
) -> ProposalDetailResponse:
    return get_proposal_detail(repo, proposal_id)


@adjudication_router.post("/proposals/{proposal_id}/dismiss", response_model=ProposalRecordResponse)
def proposals_dismiss(
    proposal_id: str,
    body: ProposalDismissRequest,
    repo: AdjudicationRepository = Depends(get_adjudication_repo),
) -> ProposalRecordResponse:
    return dismiss_proposal(repo, proposal_id, body)


# Deferred import: metrics_routes depends on this module's DI getters.
from pipeline.adjudication.metrics_routes import metrics_router as _metrics_router  # noqa: E402

adjudication_router.include_router(_metrics_router)
