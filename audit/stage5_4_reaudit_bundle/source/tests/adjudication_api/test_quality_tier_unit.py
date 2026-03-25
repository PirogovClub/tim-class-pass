"""Unit tests for Stage 5.4 tier resolver (audit re-submission)."""

from __future__ import annotations

import pytest

from pipeline.adjudication.enums import (
    CanonicalFamilyStatus,
    ConceptLinkStatus,
    EvidenceSupportStatus,
    QualityTier,
    RelationStatus,
    RuleCardCoarseStatus,
)
from pipeline.adjudication.models import (
    CanonicalRuleFamily,
    ConceptLinkReviewedState,
    EvidenceLinkReviewedState,
    RelatedRuleRelationReviewedState,
    RuleCardReviewedState,
)
from pipeline.adjudication.quality_tier import (
    DUPLICATE_CAPS_TIER,
    REJECTED_STATE,
    resolve_concept_link_tier,
    resolve_evidence_link_tier,
    resolve_related_rule_relation_tier,
    resolve_rule_card_tier,
)


def _rule(**kwargs: object) -> RuleCardReviewedState:
    base: dict = {
        "target_id": "rule:x",
        "current_status": RuleCardCoarseStatus.APPROVED,
        "last_decision_id": "d1",
    }
    kw = dict(kwargs)
    if "status" in kw:
        kw["current_status"] = kw.pop("status")
    base.update(kw)
    return RuleCardReviewedState(**base)


def test_rule_gold() -> None:
    rec = resolve_rule_card_tier(
        "rule:x",
        _rule(status=RuleCardCoarseStatus.APPROVED),
        family=None,
    )
    assert rec.tier == QualityTier.GOLD
    assert rec.is_promotable_to_gold is False
    assert rec.blocker_codes == []


def test_rule_silver_duplicate_not_promotable() -> None:
    rec = resolve_rule_card_tier(
        "rule:x",
        _rule(
            status=RuleCardCoarseStatus.APPROVED,
            is_duplicate=True,
            duplicate_of_rule_id="rule:other",
        ),
        family=None,
    )
    assert rec.tier == QualityTier.SILVER
    assert DUPLICATE_CAPS_TIER in rec.blocker_codes
    assert rec.is_promotable_to_gold is False


def test_rule_bronze_rejected_not_promotable() -> None:
    rec = resolve_rule_card_tier(
        "rule:x",
        _rule(status=RuleCardCoarseStatus.REJECTED),
        family=None,
    )
    assert rec.tier == QualityTier.BRONZE
    assert REJECTED_STATE in rec.blocker_codes
    assert rec.is_promotable_to_gold is False


def test_rule_unresolved_no_adjudication() -> None:
    rec = resolve_rule_card_tier("rule:x", None, family=None)
    assert rec.tier == QualityTier.UNRESOLVED
    assert rec.is_promotable_to_gold is False


def test_rule_unresolved_ambiguous() -> None:
    rec = resolve_rule_card_tier(
        "rule:x",
        _rule(status=RuleCardCoarseStatus.APPROVED, is_ambiguous=True),
        family=None,
    )
    assert rec.tier == QualityTier.UNRESOLVED
    assert "ambiguous_state" in rec.blocker_codes


def test_rule_unresolved_defer() -> None:
    rec = resolve_rule_card_tier(
        "rule:x",
        _rule(status=RuleCardCoarseStatus.APPROVED, is_deferred=True),
        family=None,
    )
    assert rec.tier == QualityTier.UNRESOLVED
    assert "deferred_state" in rec.blocker_codes


def test_rule_unresolved_invalid_family() -> None:
    rec = resolve_rule_card_tier(
        "rule:x",
        _rule(status=RuleCardCoarseStatus.APPROVED, canonical_family_id="fam-missing"),
        family=None,
    )
    assert rec.tier == QualityTier.UNRESOLVED
    assert "invalid_family_link" in rec.blocker_codes


def test_rule_unresolved_family_not_active() -> None:
    fam = CanonicalRuleFamily(
        family_id="f1",
        canonical_title="T",
        status=CanonicalFamilyStatus.DRAFT,
        created_at="t",
        updated_at="t",
        created_by="u",
    )
    rec = resolve_rule_card_tier(
        "rule:x",
        _rule(status=RuleCardCoarseStatus.APPROVED, canonical_family_id="f1"),
        family=fam,
    )
    assert rec.tier == QualityTier.UNRESOLVED
    assert "family_not_active" in rec.blocker_codes


def test_evidence_gold() -> None:
    st = EvidenceLinkReviewedState(
        target_id="e1",
        support_status=EvidenceSupportStatus.STRONG,
        last_decision_id="d1",
    )
    rec = resolve_evidence_link_tier("e1", st)
    assert rec.tier == QualityTier.GOLD


def test_concept_unresolved_unknown() -> None:
    st = ConceptLinkReviewedState(
        target_id="c1",
        link_status=ConceptLinkStatus.UNKNOWN,
        last_decision_id="d1",
    )
    rec = resolve_concept_link_tier("c1", st)
    assert rec.tier == QualityTier.UNRESOLVED


def test_relation_unresolved_invalid() -> None:
    st = RelatedRuleRelationReviewedState(
        target_id="r1",
        relation_status=RelationStatus.INVALID,
        last_decision_id="d1",
    )
    rec = resolve_related_rule_relation_tier("r1", st)
    assert rec.tier == QualityTier.UNRESOLVED


def test_silver_merged_promotable_if_clean() -> None:
    fam = CanonicalRuleFamily(
        family_id="f1",
        canonical_title="T",
        status=CanonicalFamilyStatus.ACTIVE,
        created_at="t",
        updated_at="t",
        created_by="u",
    )
    rec = resolve_rule_card_tier(
        "rule:x",
        _rule(
            status=RuleCardCoarseStatus.MERGED,
            canonical_family_id="f1",
        ),
        family=fam,
    )
    assert rec.tier == QualityTier.SILVER
    assert rec.is_promotable_to_gold is True


@pytest.mark.parametrize(
    "concept_status,tier",
    [
        (ConceptLinkStatus.VALID, QualityTier.GOLD),
        (ConceptLinkStatus.INVALID, QualityTier.UNRESOLVED),
    ],
)
def test_concept_tiers(concept_status: ConceptLinkStatus, tier: QualityTier) -> None:
    st = ConceptLinkReviewedState(
        target_id="c1",
        link_status=concept_status,
        last_decision_id="d1",
    )
    assert resolve_concept_link_tier("c1", st).tier == tier
