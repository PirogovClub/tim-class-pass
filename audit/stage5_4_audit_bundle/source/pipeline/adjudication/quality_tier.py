"""Deterministic Stage 5.4 quality tier resolution (consumes materialized reviewed state)."""

from __future__ import annotations

from pipeline.adjudication.enums import (
    CanonicalFamilyStatus,
    ConceptLinkStatus,
    EvidenceSupportStatus,
    QualityTier,
    RelationStatus,
    ReviewTargetType,
    RuleCardCoarseStatus,
)
from pipeline.adjudication.models import (
    CanonicalRuleFamily,
    ConceptLinkReviewedState,
    EvidenceLinkReviewedState,
    MaterializedTierRecord,
    RelatedRuleRelationReviewedState,
    RuleCardReviewedState,
)
from pipeline.adjudication.time_utils import utc_now_iso

TIER_POLICY_VERSION = "tier_policy.v1"

# Stable blocker codes (see notes/stage5_4_tier_policy.md)
NO_ADJUDICATION = "no_adjudication_state"
NEEDS_REVIEW = "needs_review"
AMBIGUOUS_STATE = "ambiguous_state"
DEFERRED_STATE = "deferred_state"
UNSUPPORTED_STATE = "unsupported_state"
REJECTED_STATE = "rejected_state"
INVALID_FAMILY_LINK = "invalid_family_link"
FAMILY_NOT_ACTIVE = "family_not_active"
INVALID_DUPLICATE_LINK = "invalid_duplicate_link"
DUPLICATE_CAPS_TIER = "duplicate_not_gold_eligible"
WEAK_EVIDENCE = "weak_evidence_only"
MISSING_REQUIRED_REVIEW = "missing_required_review"


def _record(
    target_type: ReviewTargetType,
    target_id: str,
    *,
    tier: QualityTier,
    reasons: list[str],
    blockers: list[str],
) -> MaterializedTierRecord:
    eligible = tier in (QualityTier.GOLD, QualityTier.SILVER)
    hard = {NO_ADJUDICATION, NEEDS_REVIEW, AMBIGUOUS_STATE, DEFERRED_STATE, UNSUPPORTED_STATE, INVALID_FAMILY_LINK, FAMILY_NOT_ACTIVE, INVALID_DUPLICATE_LINK, MISSING_REQUIRED_REVIEW}
    promotable = tier in (QualityTier.SILVER, QualityTier.BRONZE) and not (set(blockers) & hard)
    return MaterializedTierRecord(
        target_type=target_type,
        target_id=target_id,
        tier=tier,
        tier_reasons=reasons,
        blocker_codes=blockers,
        is_eligible_for_downstream_use=eligible,
        is_promotable_to_gold=promotable,
        resolved_at=utc_now_iso(),
        policy_version=TIER_POLICY_VERSION,
    )


def resolve_rule_card_tier(
    target_id: str,
    state: RuleCardReviewedState | None,
    *,
    family: CanonicalRuleFamily | None,
) -> MaterializedTierRecord:
    """Family is the row for ``state.canonical_family_id`` when set; ``None`` if missing or unlinked."""
    if state is None or state.last_decision_id is None:
        return _record(
            ReviewTargetType.RULE_CARD,
            target_id,
            tier=QualityTier.UNRESOLVED,
            reasons=["No adjudication recorded for this rule card."],
            blockers=[NO_ADJUDICATION],
        )

    blockers: list[str] = []
    reasons: list[str] = []

    if state.is_ambiguous:
        blockers.append(AMBIGUOUS_STATE)
    if state.is_deferred:
        blockers.append(DEFERRED_STATE)
    if state.is_unsupported:
        blockers.append(UNSUPPORTED_STATE)
    if state.current_status == RuleCardCoarseStatus.NEEDS_REVIEW:
        blockers.append(NEEDS_REVIEW)
    if state.current_status == RuleCardCoarseStatus.UNSUPPORTED:
        blockers.append(UNSUPPORTED_STATE)

    if state.canonical_family_id:
        if family is None:
            blockers.append(INVALID_FAMILY_LINK)
        elif family.status != CanonicalFamilyStatus.ACTIVE:
            blockers.append(FAMILY_NOT_ACTIVE)

    dup_cap = False
    if state.is_duplicate:
        if not state.duplicate_of_rule_id:
            blockers.append(INVALID_DUPLICATE_LINK)
        else:
            dup_cap = True

    if blockers:
        return _record(
            ReviewTargetType.RULE_CARD,
            target_id,
            tier=QualityTier.UNRESOLVED,
            reasons=["Hard blockers prevent stable quality assignment."]
            + [f"blocker:{c}" for c in blockers],
            blockers=sorted(set(blockers)),
        )

    dup_blockers = [DUPLICATE_CAPS_TIER] if dup_cap else []

    if state.current_status == RuleCardCoarseStatus.REJECTED:
        return _record(
            ReviewTargetType.RULE_CARD,
            target_id,
            tier=QualityTier.BRONZE,
            reasons=["Rejected — retained for search/discovery only."],
            blockers=[REJECTED_STATE],
        )

    if state.current_status == RuleCardCoarseStatus.APPROVED and not dup_cap:
        return _record(
            ReviewTargetType.RULE_CARD,
            target_id,
            tier=QualityTier.GOLD,
            reasons=["Approved with no ambiguity, deferral, or unsupported flags."],
            blockers=[],
        )

    if dup_cap and state.duplicate_of_rule_id:
        return _record(
            ReviewTargetType.RULE_CARD,
            target_id,
            tier=QualityTier.SILVER,
            reasons=["Valid duplicate_of — high utility, capped below Gold."],
            blockers=dup_blockers,
        )

    if state.current_status in (
        RuleCardCoarseStatus.MERGED,
        RuleCardCoarseStatus.SPLIT_REQUIRED,
    ):
        return _record(
            ReviewTargetType.RULE_CARD,
            target_id,
            tier=QualityTier.SILVER,
            reasons=[f"Structured adjudication state: {state.current_status.value}."],
            blockers=[],
        )

    return _record(
        ReviewTargetType.RULE_CARD,
        target_id,
        tier=QualityTier.BRONZE,
        reasons=["Present in corpus with adjudication below Silver/Gold bar."],
        blockers=dup_blockers,
    )


def resolve_evidence_link_tier(
    target_id: str,
    state: EvidenceLinkReviewedState | None,
) -> MaterializedTierRecord:
    if state is None or state.last_decision_id is None:
        return _record(
            ReviewTargetType.EVIDENCE_LINK,
            target_id,
            tier=QualityTier.UNRESOLVED,
            reasons=["No evidence adjudication."],
            blockers=[NO_ADJUDICATION],
        )
    ss = state.support_status
    if ss is None or ss == EvidenceSupportStatus.UNKNOWN:
        return _record(
            ReviewTargetType.EVIDENCE_LINK,
            target_id,
            tier=QualityTier.UNRESOLVED,
            reasons=["Support strength unknown or unset."],
            blockers=[MISSING_REQUIRED_REVIEW],
        )
    if ss == EvidenceSupportStatus.UNSUPPORTED:
        return _record(
            ReviewTargetType.EVIDENCE_LINK,
            target_id,
            tier=QualityTier.UNRESOLVED,
            reasons=["Marked unsupported."],
            blockers=[UNSUPPORTED_STATE],
        )
    if ss == EvidenceSupportStatus.STRONG:
        return _record(
            ReviewTargetType.EVIDENCE_LINK,
            target_id,
            tier=QualityTier.GOLD,
            reasons=["Strong evidence support."],
            blockers=[],
        )
    if ss == EvidenceSupportStatus.PARTIAL:
        return _record(
            ReviewTargetType.EVIDENCE_LINK,
            target_id,
            tier=QualityTier.SILVER,
            reasons=["Partial evidence support."],
            blockers=[],
        )
    return _record(
        ReviewTargetType.EVIDENCE_LINK,
        target_id,
        tier=QualityTier.BRONZE,
        reasons=["Illustrative or weak evidence tier."],
        blockers=[WEAK_EVIDENCE],
    )


def resolve_concept_link_tier(
    target_id: str,
    state: ConceptLinkReviewedState | None,
) -> MaterializedTierRecord:
    if state is None or state.last_decision_id is None:
        return _record(
            ReviewTargetType.CONCEPT_LINK,
            target_id,
            tier=QualityTier.UNRESOLVED,
            reasons=["No concept link adjudication."],
            blockers=[NO_ADJUDICATION],
        )
    ls = state.link_status
    if ls == ConceptLinkStatus.INVALID:
        return _record(
            ReviewTargetType.CONCEPT_LINK,
            target_id,
            tier=QualityTier.UNRESOLVED,
            reasons=["Concept link marked invalid."],
            blockers=[MISSING_REQUIRED_REVIEW],
        )
    if ls == ConceptLinkStatus.UNKNOWN:
        return _record(
            ReviewTargetType.CONCEPT_LINK,
            target_id,
            tier=QualityTier.UNRESOLVED,
            reasons=["Concept link validity unknown."],
            blockers=[MISSING_REQUIRED_REVIEW],
        )
    return _record(
        ReviewTargetType.CONCEPT_LINK,
        target_id,
        tier=QualityTier.GOLD,
        reasons=["Concept link explicitly valid."],
        blockers=[],
    )


def resolve_related_rule_relation_tier(
    target_id: str,
    state: RelatedRuleRelationReviewedState | None,
) -> MaterializedTierRecord:
    if state is None or state.last_decision_id is None:
        return _record(
            ReviewTargetType.RELATED_RULE_RELATION,
            target_id,
            tier=QualityTier.UNRESOLVED,
            reasons=["No relation adjudication."],
            blockers=[NO_ADJUDICATION],
        )
    rs = state.relation_status
    if rs == RelationStatus.INVALID:
        return _record(
            ReviewTargetType.RELATED_RULE_RELATION,
            target_id,
            tier=QualityTier.UNRESOLVED,
            reasons=["Relation marked invalid."],
            blockers=[MISSING_REQUIRED_REVIEW],
        )
    if rs == RelationStatus.UNKNOWN:
        return _record(
            ReviewTargetType.RELATED_RULE_RELATION,
            target_id,
            tier=QualityTier.UNRESOLVED,
            reasons=["Relation validity unknown."],
            blockers=[MISSING_REQUIRED_REVIEW],
        )
    return _record(
        ReviewTargetType.RELATED_RULE_RELATION,
        target_id,
        tier=QualityTier.GOLD,
        reasons=["Relation explicitly valid."],
        blockers=[],
    )


def resolve_tier_for_target(
    repo: object,
    target_type: ReviewTargetType,
    target_id: str,
) -> MaterializedTierRecord:
    """Load reviewed state from ``repo`` (AdjudicationRepository) and resolve tier."""
    # Late import to avoid circular dependency
    from pipeline.adjudication.repository import AdjudicationRepository

    assert isinstance(repo, AdjudicationRepository)

    if target_type == ReviewTargetType.RULE_CARD:
        st = repo.get_rule_card_state(target_id)
        fam = None
        if st and st.canonical_family_id:
            fam = repo.get_family(st.canonical_family_id)
        return resolve_rule_card_tier(target_id, st, family=fam)

    if target_type == ReviewTargetType.EVIDENCE_LINK:
        return resolve_evidence_link_tier(target_id, repo.get_evidence_link_state(target_id))

    if target_type == ReviewTargetType.CONCEPT_LINK:
        return resolve_concept_link_tier(target_id, repo.get_concept_link_state(target_id))

    if target_type == ReviewTargetType.RELATED_RULE_RELATION:
        return resolve_related_rule_relation_tier(
            target_id, repo.get_related_rule_relation_state(target_id)
        )

    raise ValueError(f"Tiering not supported for target_type={target_type!r}")
