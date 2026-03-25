from __future__ import annotations

from enum import Enum


class ReviewTargetType(str, Enum):
    RULE_CARD = "rule_card"
    EVIDENCE_LINK = "evidence_link"
    CONCEPT_LINK = "concept_link"
    RELATED_RULE_RELATION = "related_rule_relation"
    CANONICAL_RULE_FAMILY = "canonical_rule_family"


class DecisionType(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"
    DUPLICATE_OF = "duplicate_of"
    MERGE_INTO = "merge_into"
    SPLIT_REQUIRED = "split_required"
    UNSUPPORTED = "unsupported"
    AMBIGUOUS = "ambiguous"
    NEEDS_REVIEW = "needs_review"
    DEFER = "defer"

    RELATION_VALID = "relation_valid"
    RELATION_INVALID = "relation_invalid"

    CONCEPT_VALID = "concept_valid"
    CONCEPT_INVALID = "concept_invalid"

    EVIDENCE_STRONG = "evidence_strong"
    EVIDENCE_PARTIAL = "evidence_partial"
    EVIDENCE_ILLUSTRATIVE_ONLY = "evidence_illustrative_only"
    EVIDENCE_UNSUPPORTED = "evidence_unsupported"


class ReviewerKind(str, Enum):
    HUMAN = "human"
    AGENT = "agent"
    SYSTEM = "system"


class MembershipRole(str, Enum):
    CANONICAL = "canonical"
    MEMBER = "member"
    VARIANT = "variant"
    DUPLICATE = "duplicate"


class CanonicalFamilyStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class RuleCardCoarseStatus(str, Enum):
    """Coarse bucket for RuleCardReviewedState.current_status (last-decision-wins)."""

    NEEDS_REVIEW = "needs_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    DUPLICATE = "duplicate"
    MERGED = "merged"
    DEFERRED = "deferred"
    UNSUPPORTED = "unsupported"
    AMBIGUOUS = "ambiguous"
    SPLIT_REQUIRED = "split_required"
    OTHER = "other"


class EvidenceSupportStatus(str, Enum):
    STRONG = "strong"
    PARTIAL = "partial"
    ILLUSTRATIVE_ONLY = "illustrative_only"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"


class ConceptLinkStatus(str, Enum):
    VALID = "valid"
    INVALID = "invalid"
    UNKNOWN = "unknown"


class RelationStatus(str, Enum):
    VALID = "valid"
    INVALID = "invalid"
    UNKNOWN = "unknown"


class QualityTier(str, Enum):
    """Materialized corpus quality stratification (Stage 5.4)."""

    GOLD = "gold"
    SILVER = "silver"
    BRONZE = "bronze"
    UNRESOLVED = "unresolved"


class ProposalType(str, Enum):
    """Stage 5.5 durable adjudication proposals (rule_card slice)."""

    DUPLICATE_CANDIDATE = "duplicate_candidate"
    MERGE_CANDIDATE = "merge_candidate"
    CANONICAL_FAMILY_CANDIDATE = "canonical_family_candidate"


class ProposalStatus(str, Enum):
    NEW = "new"
    DISMISSED = "dismissed"
    SUPERSEDED = "superseded"
    ACCEPTED = "accepted"
    STALE = "stale"


class ProposalQueueName(str, Enum):
    """Proposal-backed queue identifiers (API / UI)."""

    HIGH_CONFIDENCE_DUPLICATES = "high_confidence_duplicates"
    MERGE_CANDIDATES = "merge_candidates"
    CANONICAL_FAMILY_CANDIDATES = "canonical_family_candidates"
