"""HTTP API DTOs for Stage 5.2 (separate from storage domain models)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from pipeline.adjudication.enums import DecisionType, ReviewTargetType


class ReviewItemRequest(BaseModel):
    target_type: ReviewTargetType
    target_id: str = Field(min_length=1)


class ReviewHistoryRequest(BaseModel):
    target_type: ReviewTargetType
    target_id: str = Field(min_length=1)


class ReviewBundleRequest(BaseModel):
    target_type: ReviewTargetType
    target_id: str = Field(min_length=1)


class DecisionSubmissionRequest(BaseModel):
    target_type: ReviewTargetType
    target_id: str = Field(min_length=1)
    decision_type: DecisionType
    reviewer_id: str = Field(min_length=1)
    note: str | None = None
    reason_code: str | None = None
    related_target_id: str | None = None
    artifact_version: str | None = None
    proposal_id: str | None = None


class QueueRequestParams(BaseModel):
    """Query validation for queue list endpoints."""

    target_type: ReviewTargetType | None = None


QueueNameLiteral = Literal[
    "unresolved",
    "high_confidence_duplicates",
    "merge_candidates",
    "canonical_family_candidates",
]


class NextQueueItemRequest(BaseModel):
    queue: QueueNameLiteral = "unresolved"
    target_type: ReviewTargetType | None = None


class DecisionHistoryEntry(BaseModel):
    decision_id: str
    target_type: str
    target_id: str
    decision_type: str
    reviewer_id: str
    created_at: str
    note: str | None = None
    reason_code: str | None = None
    related_target_id: str | None = None
    artifact_version: str | None = None
    proposal_id: str | None = None


class ReviewItemResponse(BaseModel):
    target_type: ReviewTargetType
    target_id: str
    current_status: str | None = None
    latest_decision_type: str | None = None
    last_reviewed_at: str | None = None
    last_reviewer_id: str | None = None
    canonical_family_id: str | None = None
    summary: str | None = None
    # Rule-card flags (null when not applicable)
    is_duplicate: bool | None = None
    duplicate_of_rule_id: str | None = None
    is_ambiguous: bool | None = None
    is_deferred: bool | None = None
    is_unsupported: bool | None = None
    support_status: str | None = None
    link_status: str | None = None
    relation_status: str | None = None


class ReviewHistoryResponse(BaseModel):
    target_type: ReviewTargetType
    target_id: str
    decisions: list[DecisionHistoryEntry]


class FamilySummary(BaseModel):
    family_id: str
    canonical_title: str
    status: str
    member_count: int | None = None


class TierStateResponse(BaseModel):
    """Stage 5.4 resolved quality tier for one target."""

    target_type: ReviewTargetType
    target_id: str
    tier: str
    tier_reasons: list[str] = Field(default_factory=list)
    blocker_codes: list[str] = Field(default_factory=list)
    is_eligible_for_downstream_use: bool = False
    is_promotable_to_gold: bool = False
    resolved_at: str
    policy_version: str


class ProposalBundleEntry(BaseModel):
    """Open proposal row for the review bundle (non-authoritative context)."""

    proposal_id: str
    proposal_type: str
    source_target_type: str
    source_target_id: str
    queue_name_hint: str | None = None
    score: float
    queue_priority: float
    rationale_summary: str
    related_target_type: str | None = None
    related_target_id: str | None = None


class ReviewBundleResponse(BaseModel):
    target_type: ReviewTargetType
    target_id: str
    target_summary: str | None = None
    reviewed_state: ReviewItemResponse
    history: list[DecisionHistoryEntry]
    family: FamilySummary | None = None
    family_members_preview: list[dict[str, Any]] = Field(default_factory=list)
    optional_context: dict[str, Any] = Field(default_factory=dict)
    quality_tier: TierStateResponse | None = None
    open_proposals: list[ProposalBundleEntry] = Field(default_factory=list)


class DecisionSubmissionResponse(BaseModel):
    success: bool = True
    decision_id: str
    target_type: ReviewTargetType
    target_id: str
    updated_state: ReviewItemResponse
    family_linkage_summary: dict[str, Any] | None = None


class FamilyDetailResponse(BaseModel):
    family_id: str
    canonical_title: str
    normalized_summary: str | None = None
    status: str
    created_at: str
    updated_at: str
    created_by: str
    primary_concept: str | None = None
    primary_subconcept: str | None = None
    review_completeness: str | None = None


class FamilyMemberEntry(BaseModel):
    membership_id: str
    family_id: str
    rule_id: str
    membership_role: str
    added_by_decision_id: str | None = None
    created_at: str


class FamilyMembersResponse(BaseModel):
    family_id: str
    members: list[FamilyMemberEntry]


class QueueItemResponse(BaseModel):
    target_type: ReviewTargetType
    target_id: str
    current_status: str | None = None
    latest_decision_type: str | None = None
    last_reviewed_at: str | None = None
    canonical_family_id: str | None = None
    queue_reason: str | None = None
    summary: str | None = None
    support_status: str | None = None
    link_status: str | None = None
    relation_status: str | None = None
    quality_tier: str | None = Field(
        default=None,
        description="Stage 5.4 materialized tier when a row exists",
    )
    # Stage 5.5 proposal-backed queues (optional)
    proposal_id: str | None = None
    proposal_type: str | None = None
    related_target_type: str | None = None
    related_target_id: str | None = None
    proposal_score: float | None = None
    proposal_queue_priority: float | None = None
    proposal_rationale_summary: str | None = None
    proposal_updated_at: str | None = None


class QueueListResponse(BaseModel):
    queue: str
    items: list[QueueItemResponse]
    total: int


class TierListResponse(BaseModel):
    tier: str
    target_type: str | None = None
    items: list[TierStateResponse]
    total: int


class TierCountsResponse(BaseModel):
    by_target_type: dict[str, dict[str, int]]
    totals_by_tier: dict[str, int]


class TierRecomputeResponse(BaseModel):
    """Result of corpus-wide tier materialization (Stage 5.4)."""

    total: int
    by_target_type: dict[str, int] = Field(
        default_factory=dict,
        description="Count of inventory ids recomputed per target_type",
    )


class ProposalGenerateRequest(BaseModel):
    proposal_types: list[str] | None = None
    limit: int | None = Field(default=None, ge=0, le=50_000)
    generator_version: str | None = None
    dry_run: bool = False


class ProposalGenerateResponse(BaseModel):
    created: int = 0
    refreshed: int = 0
    marked_stale: int = 0
    skipped: int = 0
    generator_version: str = ""


class ProposalRecordResponse(BaseModel):
    proposal_id: str
    proposal_type: str
    source_target_type: str
    source_target_id: str
    related_target_type: str | None = None
    related_target_id: str | None = None
    proposal_status: str
    score: float
    score_breakdown_json: str | None = None
    rationale_summary: str
    signals_json: str | None = None
    evidence_refs_json: str | None = None
    adjudication_snapshot_json: str
    tier_snapshot_json: str
    queue_priority: float
    dedupe_key: str
    generator_version: str
    created_at: str
    updated_at: str
    last_generated_at: str
    accepted_decision_id: str | None = None
    stale_reason: str | None = None


class ProposalListResponse(BaseModel):
    items: list[ProposalRecordResponse]
    total: int


class ProposalDetailResponse(BaseModel):
    proposal: ProposalRecordResponse
    source_item: ReviewItemResponse
    related_item: ReviewItemResponse | None = None


class ProposalDismissRequest(BaseModel):
    note: str | None = None
