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


class NextQueueItemRequest(BaseModel):
    queue: Literal["unresolved"] = "unresolved"
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


class ReviewBundleResponse(BaseModel):
    target_type: ReviewTargetType
    target_id: str
    target_summary: str | None = None
    reviewed_state: ReviewItemResponse
    history: list[DecisionHistoryEntry]
    family: FamilySummary | None = None
    family_members_preview: list[dict[str, Any]] = Field(default_factory=list)
    optional_context: dict[str, Any] = Field(default_factory=dict)


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


class QueueListResponse(BaseModel):
    queue: str
    items: list[QueueItemResponse]
    total: int
