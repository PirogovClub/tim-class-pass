"""Allowed decision types per review target (application-level integrity)."""

from __future__ import annotations

from pipeline.adjudication.enums import DecisionType, ReviewTargetType
from pipeline.adjudication.errors import InvalidDecisionForTargetError

# Per docs/requirements/stage 5/5-1-after 1st-audit.md
_ALLOWED: dict[ReviewTargetType, frozenset[DecisionType]] = {
    ReviewTargetType.RULE_CARD: frozenset(
        {
            DecisionType.APPROVE,
            DecisionType.REJECT,
            DecisionType.DUPLICATE_OF,
            DecisionType.MERGE_INTO,
            DecisionType.SPLIT_REQUIRED,
            DecisionType.UNSUPPORTED,
            DecisionType.AMBIGUOUS,
            DecisionType.NEEDS_REVIEW,
            DecisionType.DEFER,
        }
    ),
    ReviewTargetType.EVIDENCE_LINK: frozenset(
        {
            DecisionType.EVIDENCE_STRONG,
            DecisionType.EVIDENCE_PARTIAL,
            DecisionType.EVIDENCE_ILLUSTRATIVE_ONLY,
            DecisionType.EVIDENCE_UNSUPPORTED,
        }
    ),
    ReviewTargetType.CONCEPT_LINK: frozenset(
        {
            DecisionType.CONCEPT_VALID,
            DecisionType.CONCEPT_INVALID,
        }
    ),
    ReviewTargetType.RELATED_RULE_RELATION: frozenset(
        {
            DecisionType.RELATION_VALID,
            DecisionType.RELATION_INVALID,
        }
    ),
    # Subset used by _refresh_family_status_from_decision in repository
    ReviewTargetType.CANONICAL_RULE_FAMILY: frozenset(
        {
            DecisionType.APPROVE,
            DecisionType.REJECT,
            DecisionType.NEEDS_REVIEW,
            DecisionType.DEFER,
            DecisionType.AMBIGUOUS,
        }
    ),
}


def assert_decision_allowed_for_target(
    target_type: ReviewTargetType, decision_type: DecisionType
) -> None:
    allowed = _ALLOWED.get(target_type)
    if allowed is None or decision_type not in allowed:
        raise InvalidDecisionForTargetError(target_type, decision_type)


def allowed_decisions_for_target(target_type: ReviewTargetType) -> frozenset[DecisionType]:
    return _ALLOWED[target_type]
