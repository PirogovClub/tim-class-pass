"""Aggregated review bundle for one target (Stage 5.2)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pipeline.adjudication.api_errors import AdjudicationApiError
from pipeline.adjudication.api_models import FamilySummary, ProposalBundleEntry, ReviewBundleResponse
from pipeline.adjudication.api_service import (
    fetch_optional_rule_context,
    get_family_detail,
    get_family_members,
    get_review_history,
    get_review_item,
    get_tier_for_target,
)
from pipeline.adjudication.corpus_inventory import CorpusTargetIndex
from pipeline.adjudication.enums import ProposalType, ReviewTargetType
from pipeline.adjudication.repository import AdjudicationRepository, TIER_MATERIALIZED_TARGET_TYPES

if TYPE_CHECKING:
    from pipeline.explorer.service import ExplorerService


def get_review_bundle(
    repo: AdjudicationRepository,
    target_type: ReviewTargetType,
    target_id: str,
    *,
    explorer: ExplorerService | None = None,
    corpus_index: CorpusTargetIndex | None = None,
) -> ReviewBundleResponse:
    """Single fetch for review UI: state, history, family slice, optional explorer context."""
    state = get_review_item(repo, target_type, target_id)
    history = get_review_history(repo, target_type, target_id)

    family = None
    members_preview: list[dict] = []
    if target_type == ReviewTargetType.RULE_CARD and state.canonical_family_id:
        try:
            fd = get_family_detail(repo, state.canonical_family_id)
            mem = get_family_members(repo, state.canonical_family_id)
            family = FamilySummary(
                family_id=fd.family_id,
                canonical_title=fd.canonical_title,
                status=fd.status,
                member_count=len(mem.members),
            )
            members_preview = [m.model_dump() for m in mem.members[:20]]
        except AdjudicationApiError:
            family = None
            members_preview = []

    if target_type == ReviewTargetType.CANONICAL_RULE_FAMILY:
        fd = get_family_detail(repo, target_id)
        mem = get_family_members(repo, target_id)
        family = FamilySummary(
            family_id=fd.family_id,
            canonical_title=fd.canonical_title,
            status=fd.status,
            member_count=len(mem.members),
        )
        members_preview = [m.model_dump() for m in mem.members[:20]]

    optional: dict = {}
    if target_type == ReviewTargetType.RULE_CARD:
        optional = fetch_optional_rule_context(explorer, target_id)

    quality_tier = None
    if target_type in TIER_MATERIALIZED_TARGET_TYPES:
        quality_tier = get_tier_for_target(
            repo, target_type, target_id, corpus_index=corpus_index
        )

    open_proposals: list[ProposalBundleEntry] = []
    for pr in repo.list_open_proposals_for_target(target_type, target_id)[:20]:
        open_proposals.append(
            ProposalBundleEntry(
                proposal_id=pr.proposal_id,
                proposal_type=pr.proposal_type.value,
                source_target_type=pr.source_target_type.value,
                source_target_id=pr.source_target_id,
                queue_name_hint=_queue_hint(pr.proposal_type),
                score=pr.score,
                queue_priority=pr.queue_priority,
                rationale_summary=pr.rationale_summary,
                related_target_type=(
                    pr.related_target_type.value if pr.related_target_type else None
                ),
                related_target_id=pr.related_target_id,
            )
        )

    return ReviewBundleResponse(
        target_type=target_type,
        target_id=target_id,
        target_summary=state.summary,
        reviewed_state=state,
        history=history.decisions,
        family=family,
        family_members_preview=members_preview,
        optional_context=optional,
        quality_tier=quality_tier,
        open_proposals=open_proposals,
    )
