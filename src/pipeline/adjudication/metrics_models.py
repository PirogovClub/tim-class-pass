"""Pydantic response models for Stage 5.7 metrics endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CorpusCurationSummaryResponse(BaseModel):
    computed_at: str
    total_supported_review_targets: int
    unresolved_count: int
    gold_count: int
    silver_count: int
    bronze_count: int
    tier_unresolved_count: int
    rejected_count: int
    unsupported_count: int
    canonical_family_count: int
    merge_decision_count: int


class ProposalQueueSizeRow(BaseModel):
    queue_name: str
    open_count: int


class QueueHealthResponse(BaseModel):
    computed_at: str
    unresolved_queue_size: int
    deferred_rule_cards: int
    proposal_queue_open_counts: list[ProposalQueueSizeRow]
    unresolved_by_target_type: dict[str, int]
    unresolved_backlog_by_tier: dict[str, int]
    oldest_unresolved_last_reviewed_at: str | None = None
    oldest_unresolved_age_seconds: float | None = None


class ProposalTypeMetricsRow(BaseModel):
    proposal_type: str
    total: int
    open: int
    accepted: int
    dismissed: int
    stale: int
    superseded: int
    terminal: int
    acceptance_rate_closed: float | None = None
    acceptance_rate_all: float | None = None


class ProposalUsefulnessResponse(BaseModel):
    computed_at: str
    total_proposals: int
    open_proposals: int
    accepted_proposals: int
    dismissed_proposals: int
    stale_proposals: int
    superseded_proposals: int
    stale_total: int = Field(description="stale + superseded (non-actionable volume)")
    terminal_proposals: int
    acceptance_rate_closed: float | None = None
    acceptance_rate_all: float | None = None
    median_seconds_to_disposition: float | None = None
    by_proposal_type: list[ProposalTypeMetricsRow]


class ThroughputBreakdownRow(BaseModel):
    decision_type: str
    count: int


class ReviewerThroughputRow(BaseModel):
    reviewer_id: str
    count: int


class ThroughputResponse(BaseModel):
    computed_at: str
    window: str
    window_start_utc: str
    decision_count: int
    by_decision_type: list[ThroughputBreakdownRow]
    by_reviewer_id: list[ReviewerThroughputRow]


class CoverageBucketRow(BaseModel):
    bucket_id: str
    total_targets: int
    reviewed_not_unresolved: int
    coverage_ratio: float | None = None


class CoverageLessonsResponse(BaseModel):
    computed_at: str
    explorer_available: bool
    note: str | None = None
    buckets: list[CoverageBucketRow]


class CoverageConceptsResponse(BaseModel):
    computed_at: str
    explorer_available: bool
    note: str | None = None
    buckets: list[CoverageBucketRow]


class FlagsSummaryBlock(BaseModel):
    ambiguity_rule_cards: int
    conflict_rule_split_required: int
    conflict_concept_invalid: int
    conflict_relation_invalid: int


class FlagDistributionRow(BaseModel):
    bucket_id: str
    ambiguity_rule_cards: int
    conflict_rule_split_required: int


class FlagsDistributionResponse(BaseModel):
    computed_at: str
    explorer_available: bool
    note: str | None = None
    summary: FlagsSummaryBlock
    by_lesson: list[FlagDistributionRow]
    by_concept: list[FlagDistributionRow]
