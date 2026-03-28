"""FastAPI routes for Stage 5.7 review metrics (read-only)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from pipeline.adjudication.api_routes import (
    get_adjudication_repo,
    get_corpus_index,
    get_explorer_optional,
)
from pipeline.adjudication.corpus_inventory import CorpusTargetIndex
from pipeline.adjudication.metrics_enums import ThroughputWindow
from pipeline.adjudication.metrics_models import (
    CorpusCurationSummaryResponse,
    CoverageConceptsResponse,
    CoverageLessonsResponse,
    FlagsDistributionResponse,
    ProposalUsefulnessResponse,
    QueueHealthResponse,
    ThroughputResponse,
)
from pipeline.adjudication.metrics_service import (
    build_corpus_curation_summary,
    build_coverage_concepts,
    build_coverage_lessons,
    build_flags_distribution,
    build_proposal_usefulness,
    build_queue_health_metrics,
    build_throughput_metrics,
)
from pipeline.adjudication.repository import AdjudicationRepository

metrics_router = APIRouter(prefix="/metrics", tags=["adjudication-metrics"])


def _parse_throughput_window_param(raw: str) -> ThroughputWindow:
    try:
        return ThroughputWindow(raw)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": "validation_error",
                "message": f"Invalid throughput window {raw!r}; use 7d or 30d",
                "window": raw,
            },
        ) from None


@metrics_router.get("/summary", response_model=CorpusCurationSummaryResponse)
def metrics_summary(
    repo: AdjudicationRepository = Depends(get_adjudication_repo),
    corpus_index: CorpusTargetIndex = Depends(get_corpus_index),
) -> CorpusCurationSummaryResponse:
    return build_corpus_curation_summary(repo, corpus_index)


@metrics_router.get("/queues", response_model=QueueHealthResponse)
def metrics_queues(
    repo: AdjudicationRepository = Depends(get_adjudication_repo),
    corpus_index: CorpusTargetIndex = Depends(get_corpus_index),
) -> QueueHealthResponse:
    return build_queue_health_metrics(repo, corpus_index)


@metrics_router.get("/proposals", response_model=ProposalUsefulnessResponse)
def metrics_proposals(
    repo: AdjudicationRepository = Depends(get_adjudication_repo),
) -> ProposalUsefulnessResponse:
    return build_proposal_usefulness(repo)


@metrics_router.get("/throughput", response_model=ThroughputResponse)
def metrics_throughput(
    window: str = Query("7d", description="7d | 30d"),
    repo: AdjudicationRepository = Depends(get_adjudication_repo),
) -> ThroughputResponse:
    w = _parse_throughput_window_param(window)
    return build_throughput_metrics(repo, w)


@metrics_router.get("/coverage/lessons", response_model=CoverageLessonsResponse)
def metrics_coverage_lessons(
    repo: AdjudicationRepository = Depends(get_adjudication_repo),
    corpus_index: CorpusTargetIndex = Depends(get_corpus_index),
    explorer=Depends(get_explorer_optional),
) -> CoverageLessonsResponse:
    return build_coverage_lessons(repo, corpus_index, explorer)


@metrics_router.get("/coverage/concepts", response_model=CoverageConceptsResponse)
def metrics_coverage_concepts(
    repo: AdjudicationRepository = Depends(get_adjudication_repo),
    corpus_index: CorpusTargetIndex = Depends(get_corpus_index),
    explorer=Depends(get_explorer_optional),
) -> CoverageConceptsResponse:
    return build_coverage_concepts(repo, corpus_index, explorer)


@metrics_router.get("/flags", response_model=FlagsDistributionResponse)
def metrics_flags(
    repo: AdjudicationRepository = Depends(get_adjudication_repo),
    corpus_index: CorpusTargetIndex = Depends(get_corpus_index),
    explorer=Depends(get_explorer_optional),
) -> FlagsDistributionResponse:
    return build_flags_distribution(repo, corpus_index, explorer)
