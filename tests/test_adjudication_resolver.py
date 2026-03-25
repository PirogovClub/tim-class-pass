"""Tests for pure resolver (last-decision-wins)."""

from __future__ import annotations

from pipeline.adjudication.enums import (
    ConceptLinkStatus,
    DecisionType,
    EvidenceSupportStatus,
    RelationStatus,
    ReviewTargetType,
    RuleCardCoarseStatus,
)
from pipeline.adjudication.models import ReviewDecision
from pipeline.adjudication.resolver import (
    resolve_concept_link_state,
    resolve_evidence_link_state,
    resolve_related_rule_relation_state,
    resolve_rule_card_state,
)


def _d(
    decision_id: str,
    target_id: str,
    dtype: DecisionType,
    *,
    related: str | None = None,
    created_at: str | None = None,
) -> ReviewDecision:
    return ReviewDecision(
        decision_id=decision_id,
        target_type=ReviewTargetType.RULE_CARD,
        target_id=target_id,
        decision_type=dtype,
        reviewer_id="u1",
        created_at=created_at or f"2024-01-01T00:00:0{decision_id[-1]}+00:00",
        related_target_id=related,
    )


def test_rule_card_no_decisions() -> None:
    st = resolve_rule_card_state("rule:x:1", [])
    assert st.target_id == "rule:x:1"
    assert st.latest_decision_type is None


def test_rule_card_needs_review_then_duplicate_of() -> None:
    decisions = [
        _d("1", "rule:x:1", DecisionType.NEEDS_REVIEW, created_at="2024-01-01T00:00:01+00:00"),
        _d(
            "2",
            "rule:x:1",
            DecisionType.DUPLICATE_OF,
            related="rule:x:2",
            created_at="2024-01-01T00:00:02+00:00",
        ),
    ]
    st = resolve_rule_card_state("rule:x:1", decisions)
    assert st.latest_decision_type == DecisionType.DUPLICATE_OF
    assert st.is_duplicate is True
    assert st.duplicate_of_rule_id == "rule:x:2"
    assert st.current_status == RuleCardCoarseStatus.DUPLICATE


def test_rule_card_defer_after_approve() -> None:
    decisions = [
        _d("1", "rule:x:1", DecisionType.APPROVE, created_at="2024-01-01T00:00:01+00:00"),
        _d("2", "rule:x:1", DecisionType.DEFER, created_at="2024-01-01T00:00:02+00:00"),
    ]
    st = resolve_rule_card_state("rule:x:1", decisions)
    assert st.is_deferred is True
    assert st.latest_decision_type == DecisionType.DEFER


def test_rule_card_approve_after_ambiguous_clears_ambiguous() -> None:
    decisions = [
        _d("1", "rule:x:1", DecisionType.AMBIGUOUS, created_at="2024-01-01T00:00:01+00:00"),
        _d("2", "rule:x:1", DecisionType.APPROVE, created_at="2024-01-01T00:00:02+00:00"),
    ]
    st = resolve_rule_card_state("rule:x:1", decisions)
    assert st.is_ambiguous is False
    assert st.current_status == RuleCardCoarseStatus.APPROVED


def test_evidence_partial_then_strong() -> None:
    base = dict(target_type=ReviewTargetType.EVIDENCE_LINK, target_id="ev:1", reviewer_id="u1")
    decisions = [
        ReviewDecision(
            decision_id="1",
            **base,
            decision_type=DecisionType.EVIDENCE_PARTIAL,
            created_at="2024-01-01T00:00:01+00:00",
        ),
        ReviewDecision(
            decision_id="2",
            **base,
            decision_type=DecisionType.EVIDENCE_STRONG,
            created_at="2024-01-01T00:00:02+00:00",
        ),
    ]
    st = resolve_evidence_link_state("ev:1", decisions)
    assert st.support_status == EvidenceSupportStatus.STRONG


def test_concept_invalid() -> None:
    decisions = [
        ReviewDecision(
            decision_id="1",
            target_type=ReviewTargetType.CONCEPT_LINK,
            target_id="cl:1",
            decision_type=DecisionType.CONCEPT_INVALID,
            reviewer_id="u1",
            created_at="2024-01-01T00:00:01+00:00",
        ),
    ]
    st = resolve_concept_link_state("cl:1", decisions)
    assert st.link_status == ConceptLinkStatus.INVALID


def test_relation_valid() -> None:
    decisions = [
        ReviewDecision(
            decision_id="1",
            target_type=ReviewTargetType.RELATED_RULE_RELATION,
            target_id="rel:a:b:c",
            decision_type=DecisionType.RELATION_VALID,
            reviewer_id="u1",
            created_at="2024-01-01T00:00:01+00:00",
        ),
    ]
    st = resolve_related_rule_relation_state("rel:a:b:c", decisions)
    assert st.relation_status == RelationStatus.VALID
