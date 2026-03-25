"""Derive materialized reviewed state from append-only decision history (last-decision-wins)."""

from __future__ import annotations

from pipeline.adjudication.enums import (
    ConceptLinkStatus,
    DecisionType,
    EvidenceSupportStatus,
    RelationStatus,
    ReviewTargetType,
    RuleCardCoarseStatus,
)
from pipeline.adjudication.models import (
    ConceptLinkReviewedState,
    EvidenceLinkReviewedState,
    RelatedRuleRelationReviewedState,
    ReviewDecision,
    RuleCardReviewedState,
)


def _sort_decisions(decisions: list[ReviewDecision]) -> list[ReviewDecision]:
    return sorted(
        decisions,
        key=lambda d: (d.created_at, d.decision_id),
    )


def _rule_coarse_status(last: DecisionType) -> RuleCardCoarseStatus:
    m: dict[DecisionType, RuleCardCoarseStatus] = {
        DecisionType.APPROVE: RuleCardCoarseStatus.APPROVED,
        DecisionType.REJECT: RuleCardCoarseStatus.REJECTED,
        DecisionType.DUPLICATE_OF: RuleCardCoarseStatus.DUPLICATE,
        DecisionType.MERGE_INTO: RuleCardCoarseStatus.MERGED,
        DecisionType.DEFER: RuleCardCoarseStatus.DEFERRED,
        DecisionType.UNSUPPORTED: RuleCardCoarseStatus.UNSUPPORTED,
        DecisionType.AMBIGUOUS: RuleCardCoarseStatus.AMBIGUOUS,
        DecisionType.NEEDS_REVIEW: RuleCardCoarseStatus.NEEDS_REVIEW,
        DecisionType.SPLIT_REQUIRED: RuleCardCoarseStatus.SPLIT_REQUIRED,
    }
    return m.get(last, RuleCardCoarseStatus.OTHER)


def resolve_rule_card_state(
    target_id: str, decisions: list[ReviewDecision]
) -> RuleCardReviewedState:
    ordered = _sort_decisions(decisions)
    if not ordered:
        return RuleCardReviewedState(target_id=target_id)

    last = ordered[-1]
    lt = last.decision_type
    coarse = _rule_coarse_status(lt)
    canonical_family_id = None
    if lt == DecisionType.MERGE_INTO:
        canonical_family_id = last.related_target_id

    return RuleCardReviewedState(
        target_id=target_id,
        current_status=coarse,
        latest_decision_type=lt,
        canonical_family_id=canonical_family_id,
        is_duplicate=(lt == DecisionType.DUPLICATE_OF),
        duplicate_of_rule_id=(last.related_target_id if lt == DecisionType.DUPLICATE_OF else None),
        is_ambiguous=(lt == DecisionType.AMBIGUOUS),
        is_deferred=(lt == DecisionType.DEFER),
        is_unsupported=(lt == DecisionType.UNSUPPORTED),
        last_reviewed_at=last.created_at,
        last_reviewer_id=last.reviewer_id,
        last_decision_id=last.decision_id,
        notes_summary=(last.note[:500] if last.note else None),
    )


def _evidence_support(last: DecisionType) -> EvidenceSupportStatus | None:
    m = {
        DecisionType.EVIDENCE_STRONG: EvidenceSupportStatus.STRONG,
        DecisionType.EVIDENCE_PARTIAL: EvidenceSupportStatus.PARTIAL,
        DecisionType.EVIDENCE_ILLUSTRATIVE_ONLY: EvidenceSupportStatus.ILLUSTRATIVE_ONLY,
        DecisionType.EVIDENCE_UNSUPPORTED: EvidenceSupportStatus.UNSUPPORTED,
    }
    return m.get(last)


def resolve_evidence_link_state(
    target_id: str, decisions: list[ReviewDecision]
) -> EvidenceLinkReviewedState:
    ordered = _sort_decisions(decisions)
    if not ordered:
        return EvidenceLinkReviewedState(target_id=target_id)

    last = ordered[-1]
    support = _evidence_support(last.decision_type)
    if support is None:
        support = EvidenceSupportStatus.UNKNOWN

    return EvidenceLinkReviewedState(
        target_id=target_id,
        support_status=support,
        last_reviewed_at=last.created_at,
        last_reviewer_id=last.reviewer_id,
        last_decision_id=last.decision_id,
    )


def _concept_status(last: DecisionType) -> ConceptLinkStatus | None:
    if last == DecisionType.CONCEPT_VALID:
        return ConceptLinkStatus.VALID
    if last == DecisionType.CONCEPT_INVALID:
        return ConceptLinkStatus.INVALID
    return None


def resolve_concept_link_state(
    target_id: str, decisions: list[ReviewDecision]
) -> ConceptLinkReviewedState:
    ordered = _sort_decisions(decisions)
    if not ordered:
        return ConceptLinkReviewedState(target_id=target_id)

    last = ordered[-1]
    st = _concept_status(last.decision_type)
    if st is None:
        st = ConceptLinkStatus.UNKNOWN

    return ConceptLinkReviewedState(
        target_id=target_id,
        link_status=st,
        last_reviewed_at=last.created_at,
        last_reviewer_id=last.reviewer_id,
        last_decision_id=last.decision_id,
    )


def _relation_status(last: DecisionType) -> RelationStatus | None:
    if last == DecisionType.RELATION_VALID:
        return RelationStatus.VALID
    if last == DecisionType.RELATION_INVALID:
        return RelationStatus.INVALID
    return None


def resolve_related_rule_relation_state(
    target_id: str, decisions: list[ReviewDecision]
) -> RelatedRuleRelationReviewedState:
    ordered = _sort_decisions(decisions)
    if not ordered:
        return RelatedRuleRelationReviewedState(target_id=target_id)

    last = ordered[-1]
    st = _relation_status(last.decision_type)
    if st is None:
        st = RelationStatus.UNKNOWN

    return RelatedRuleRelationReviewedState(
        target_id=target_id,
        relation_status=st,
        last_reviewed_at=last.created_at,
        last_reviewer_id=last.reviewer_id,
        last_decision_id=last.decision_id,
    )


def resolve_state_for_target(
    target_type: ReviewTargetType,
    target_id: str,
    decisions: list[ReviewDecision],
):
    if target_type == ReviewTargetType.RULE_CARD:
        return resolve_rule_card_state(target_id, decisions)
    if target_type == ReviewTargetType.EVIDENCE_LINK:
        return resolve_evidence_link_state(target_id, decisions)
    if target_type == ReviewTargetType.CONCEPT_LINK:
        return resolve_concept_link_state(target_id, decisions)
    if target_type == ReviewTargetType.RELATED_RULE_RELATION:
        return resolve_related_rule_relation_state(target_id, decisions)
    raise ValueError(f"No reviewed-state table for target_type={target_type!r}")
