from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from pipeline.adjudication.enums import (
    CanonicalFamilyStatus,
    ConceptLinkStatus,
    DecisionType,
    EvidenceSupportStatus,
    MembershipRole,
    ProposalStatus,
    ProposalType,
    QualityTier,
    RelationStatus,
    ReviewTargetType,
    ReviewerKind,
    RuleCardCoarseStatus,
)


class Reviewer(BaseModel):
    reviewer_id: str
    reviewer_kind: ReviewerKind
    display_name: str
    created_at: str


class ReviewDecision(BaseModel):
    decision_id: str
    target_type: ReviewTargetType
    target_id: str
    decision_type: DecisionType
    reviewer_id: str
    created_at: str
    note: str | None = None
    reason_code: str | None = None
    related_target_id: str | None = None
    artifact_version: str | None = None
    proposal_id: str | None = None
    prior_state_json: str | None = None
    new_state_json: str | None = None

    @model_validator(mode="after")
    def _related_required_for_linking_decisions(self) -> ReviewDecision:
        if self.decision_type in (DecisionType.DUPLICATE_OF, DecisionType.MERGE_INTO):
            if not (self.related_target_id and str(self.related_target_id).strip()):
                raise ValueError(
                    f"related_target_id is required for decision_type={self.decision_type.value}"
                )
        return self


class CanonicalRuleFamily(BaseModel):
    family_id: str
    canonical_title: str
    normalized_summary: str | None = None
    status: CanonicalFamilyStatus
    created_at: str
    updated_at: str
    created_by: str
    primary_concept: str | None = None
    primary_subconcept: str | None = None
    review_completeness: str | None = None


class CanonicalRuleMembership(BaseModel):
    membership_id: str
    family_id: str
    rule_id: str
    membership_role: MembershipRole
    added_by_decision_id: str | None = None
    created_at: str


class RuleCardReviewedState(BaseModel):
    target_id: str
    current_status: RuleCardCoarseStatus | None = None
    latest_decision_type: DecisionType | None = None
    canonical_family_id: str | None = None
    is_duplicate: bool = False
    duplicate_of_rule_id: str | None = None
    is_ambiguous: bool = False
    is_deferred: bool = False
    is_unsupported: bool = False
    last_reviewed_at: str | None = None
    last_reviewer_id: str | None = None
    last_decision_id: str | None = None
    notes_summary: str | None = None


class EvidenceLinkReviewedState(BaseModel):
    target_id: str
    support_status: EvidenceSupportStatus | None = None
    last_reviewed_at: str | None = None
    last_reviewer_id: str | None = None
    last_decision_id: str | None = None


class ConceptLinkReviewedState(BaseModel):
    target_id: str
    link_status: ConceptLinkStatus | None = None
    last_reviewed_at: str | None = None
    last_reviewer_id: str | None = None
    last_decision_id: str | None = None


class RelatedRuleRelationReviewedState(BaseModel):
    target_id: str
    relation_status: RelationStatus | None = None
    last_reviewed_at: str | None = None
    last_reviewer_id: str | None = None
    last_decision_id: str | None = None


class NewReviewDecision(BaseModel):
    """Input for appending a decision (server-generated decision_id and created_at)."""

    target_type: ReviewTargetType
    target_id: str
    decision_type: DecisionType
    reviewer_id: str
    note: str | None = None
    reason_code: str | None = None
    related_target_id: str | None = None
    artifact_version: str | None = None
    proposal_id: str | None = None
    prior_state_json: str | None = None
    new_state_json: str | None = None

    @model_validator(mode="after")
    def _related_required(self) -> NewReviewDecision:
        if self.decision_type in (DecisionType.DUPLICATE_OF, DecisionType.MERGE_INTO):
            if not (self.related_target_id and str(self.related_target_id).strip()):
                raise ValueError(
                    f"related_target_id is required for decision_type={self.decision_type.value}"
                )
        return self


class NewCanonicalFamily(BaseModel):
    family_id: str | None = None
    canonical_title: str
    normalized_summary: str | None = None
    status: CanonicalFamilyStatus = CanonicalFamilyStatus.DRAFT
    created_by: str
    primary_concept: str | None = None
    primary_subconcept: str | None = None
    review_completeness: str | None = None


class NewReviewer(BaseModel):
    reviewer_id: str
    reviewer_kind: ReviewerKind
    display_name: str


class NewMembership(BaseModel):
    family_id: str
    rule_id: str
    membership_role: MembershipRole
    added_by_decision_id: str | None = None


class MaterializedTierRecord(BaseModel):
    """Resolved quality tier for one adjudication target (Stage 5.4)."""

    target_type: ReviewTargetType
    target_id: str
    tier: QualityTier
    tier_reasons: list[str] = []
    blocker_codes: list[str] = []
    is_eligible_for_downstream_use: bool = False
    is_promotable_to_gold: bool = False
    resolved_at: str
    policy_version: str


class ProposalScoreBreakdown(BaseModel):
    """Audit-friendly score components (serialized to ``score_breakdown_json``)."""

    components: dict[str, float] = Field(default_factory=dict)


class ProposalRecord(BaseModel):
    """Durable adjudication proposal row (Stage 5.5)."""

    proposal_id: str
    proposal_type: ProposalType
    source_target_type: ReviewTargetType
    source_target_id: str
    related_target_type: ReviewTargetType | None = None
    related_target_id: str | None = None
    proposal_status: ProposalStatus
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


class ProposalGenerationResult(BaseModel):
    """Outcome of a generation run (persisted or dry-run)."""

    created: int = 0
    refreshed: int = 0
    marked_stale: int = 0
    skipped: int = 0
    generator_version: str = ""


class ProposalQueueItem(BaseModel):
    """One row in a proposal-backed review queue (see Stage 5.5 §15)."""

    proposal_id: str
    proposal_type: ProposalType
    source_target_type: ReviewTargetType
    source_target_id: str
    related_target_type: ReviewTargetType | None = None
    related_target_id: str | None = None
    score: float
    queue_priority: float
    rationale_summary: str
    current_tier: str | None = None
    current_status: str | None = None
    created_at: str
    updated_at: str
