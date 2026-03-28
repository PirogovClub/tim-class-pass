"""Integrity violations for adjudication persistence (Stage 5.1 post-audit)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pipeline.adjudication.enums import DecisionType, ReviewTargetType


class AdjudicationIntegrityError(ValueError):
    """Base class for rejected writes to adjudication storage."""


class ReviewerNotFoundError(AdjudicationIntegrityError):
    def __init__(self, reviewer_id: str) -> None:
        super().__init__(f"Unknown reviewer_id={reviewer_id!r}; create reviewer first.")
        self.reviewer_id = reviewer_id


class FamilyNotFoundError(AdjudicationIntegrityError):
    def __init__(self, family_id: str) -> None:
        super().__init__(f"Unknown family_id={family_id!r}; create canonical family first.")
        self.family_id = family_id


class InvalidDecisionForTargetError(AdjudicationIntegrityError):
    def __init__(
        self,
        target_type: ReviewTargetType,
        decision_type: DecisionType,
    ) -> None:
        super().__init__(
            f"Decision type {decision_type.value!r} is not allowed for "
            f"target_type={target_type.value!r}."
        )
        self.target_type = target_type
        self.decision_type = decision_type
