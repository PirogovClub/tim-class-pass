"""Inclusion / exclusion rules for Stage 5.6 corpus export (documented, testable)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pipeline.adjudication.enums import QualityTier, ReviewTargetType
from pipeline.adjudication.quality_tier import TIER_POLICY_VERSION

if TYPE_CHECKING:
    from pipeline.adjudication.corpus_inventory import CorpusTargetIndex
    from pipeline.adjudication.models import MaterializedTierRecord, RuleCardReviewedState

GOLD_TIER = QualityTier.GOLD
SILVER_TIER = QualityTier.SILVER

INCLUSION_RULES_GOLD = [
    "Materialized tier row exists with tier == gold.",
    "is_eligible_for_downstream_use is true (tier materialization contract).",
    "Target is in corpus inventory when a CorpusTargetIndex is supplied.",
    "For rule_card: reviewed state exists and is_unsupported is false.",
    "No export-time writes to adjudication tables (read-only export).",
]

INCLUSION_RULES_SILVER = [
    "Materialized tier row exists with tier == silver.",
    "is_eligible_for_downstream_use is true.",
    "Target is in corpus inventory when a CorpusTargetIndex is supplied.",
    "For rule_card: reviewed state exists and is_unsupported is false.",
]

EXCLUDED_CATEGORIES = [
    "bronze_tier (not exported in 5.6 gold/silver bundles)",
    "unresolved_tier",
    "unsupported rule_card rows",
    "targets outside corpus inventory when inventory filter is enabled",
    "ineligible materialized rows (is_eligible_for_downstream_use == false)",
    "canonical families with no gold member rule (gold_canonical_families export only)",
]


def materialized_row_passes_base_tier_filter(
    rec: MaterializedTierRecord,
    *,
    expected_tier: QualityTier,
) -> bool:
    return rec.tier == expected_tier and rec.is_eligible_for_downstream_use


def passes_corpus_gate(
    target_type: ReviewTargetType,
    target_id: str,
    corpus_index: CorpusTargetIndex | None,
) -> bool:
    if corpus_index is None:
        return True
    return corpus_index.contains(target_type, target_id)


def gold_rule_card_allowed(
    rec: MaterializedTierRecord,
    state: RuleCardReviewedState | None,
    *,
    corpus_index: CorpusTargetIndex | None,
) -> bool:
    if not materialized_row_passes_base_tier_filter(rec, expected_tier=GOLD_TIER):
        return False
    if not passes_corpus_gate(rec.target_type, rec.target_id, corpus_index):
        return False
    if state is None:
        return False
    if state.is_unsupported:
        return False
    return True


def silver_rule_card_allowed(
    rec: MaterializedTierRecord,
    state: RuleCardReviewedState | None,
    *,
    corpus_index: CorpusTargetIndex | None,
) -> bool:
    if not materialized_row_passes_base_tier_filter(rec, expected_tier=SILVER_TIER):
        return False
    if not passes_corpus_gate(rec.target_type, rec.target_id, corpus_index):
        return False
    if state is None:
        return False
    if state.is_unsupported:
        return False
    return True


def gold_non_rule_allowed(
    rec: MaterializedTierRecord,
    *,
    corpus_index: CorpusTargetIndex | None,
) -> bool:
    if rec.target_type == ReviewTargetType.RULE_CARD:
        raise ValueError("use gold_rule_card_allowed for rule_card")
    if not materialized_row_passes_base_tier_filter(rec, expected_tier=GOLD_TIER):
        return False
    return passes_corpus_gate(rec.target_type, rec.target_id, corpus_index)


def silver_non_rule_allowed(
    rec: MaterializedTierRecord,
    *,
    corpus_index: CorpusTargetIndex | None,
) -> bool:
    if rec.target_type == ReviewTargetType.RULE_CARD:
        raise ValueError("use silver_rule_card_allowed for rule_card")
    if not materialized_row_passes_base_tier_filter(rec, expected_tier=SILVER_TIER):
        return False
    return passes_corpus_gate(rec.target_type, rec.target_id, corpus_index)


def tier_policy_version_label() -> str:
    return TIER_POLICY_VERSION
