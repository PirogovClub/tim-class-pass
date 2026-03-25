"""Unit tests for Stage 5.5 proposal generation (deterministic scoring)."""

from __future__ import annotations

import pytest

from pipeline.adjudication.bootstrap import initialize_adjudication_storage
from pipeline.adjudication.corpus_inventory import CorpusTargetIndex
from pipeline.adjudication.enums import (
    CanonicalFamilyStatus,
    DecisionType,
    ProposalType,
    ReviewTargetType,
    ReviewerKind,
)
from pipeline.adjudication.models import NewCanonicalFamily, NewReviewDecision, NewReviewer
from pipeline.adjudication.proposal_generation import (
    RuleCardProposalContext,
    canonical_dedupe_key,
    generate_rule_card_proposal_records,
    rule_pair_dedupe_key,
)
from pipeline.adjudication.repository import AdjudicationRepository


MINI_INDEX = CorpusTargetIndex(
    rule_card_ids=frozenset({"r1", "r2", "r3", "r4"}),
    evidence_link_ids=frozenset(),
    concept_link_ids=frozenset(),
    related_rule_relation_ids=frozenset(),
)


@pytest.fixture
def repo(tmp_path):
    p = tmp_path / "prop.sqlite"
    initialize_adjudication_storage(p)
    r = AdjudicationRepository(p)
    r.create_reviewer(NewReviewer(reviewer_id="u1", reviewer_kind=ReviewerKind.HUMAN, display_name="A"))
    return r


def test_pair_dedupe_key_sorted_stable() -> None:
    assert rule_pair_dedupe_key("duplicate", "b", "a") == rule_pair_dedupe_key("duplicate", "a", "b")


def test_canonical_dedupe_key_format() -> None:
    assert canonical_dedupe_key("r1", "fam1") == "canonical|rule_card|r1|canonical_rule_family|fam1"


def test_duplicate_precedence_suppresses_merge(repo: AdjudicationRepository) -> None:
    # Two shared evidence ids => full shared-evidence weight (see _overlap_bonus).
    ev = frozenset({"e1", "e2"})
    ctxs = {
        "r1": RuleCardProposalContext(
            rule_id="r1",
            lesson_id="L1",
            rule_text="stop loss protects capital in volatile markets",
            concept="risk",
            subconcept="stop",
            evidence_doc_ids=ev,
            source_event_doc_ids=frozenset({"s1"}),
        ),
        "r2": RuleCardProposalContext(
            rule_id="r2",
            lesson_id="L2",
            rule_text="stop loss protects capital in volatile markets",
            concept="risk",
            subconcept="stop",
            evidence_doc_ids=ev,
            source_event_doc_ids=frozenset({"s1"}),
        ),
    }
    recs = generate_rule_card_proposal_records(repo, MINI_INDEX, ctxs, generator_version="t.v1")
    dups = [x for x in recs if x.proposal_type == ProposalType.DUPLICATE_CANDIDATE]
    merges = [x for x in recs if x.proposal_type == ProposalType.MERGE_CANDIDATE]
    assert len(dups) == 1
    assert len(merges) == 0


def test_merge_candidate_mid_band(repo: AdjudicationRepository) -> None:
    fam = repo.create_canonical_family(
        NewCanonicalFamily(
            canonical_title="Fam",
            created_by="u1",
            status=CanonicalFamilyStatus.ACTIVE,
            primary_concept="risk",
        )
    )
    repo.append_decision_and_refresh_state(
        NewReviewDecision(
            target_type=ReviewTargetType.RULE_CARD,
            target_id="r1",
            decision_type=DecisionType.MERGE_INTO,
            reviewer_id="u1",
            related_target_id=fam.family_id,
        )
    )
    ctxs = {
        "r1": RuleCardProposalContext(
            rule_id="r1",
            lesson_id="L1",
            rule_text="stop loss order day trade risk cap",
            concept="risk",
            subconcept=None,
            conditions=("price above ma20",),
            invalidation=("gap down",),
            evidence_doc_ids=frozenset({"e1", "e2"}),
            frame_ids=("f1",),
        ),
        "r2": RuleCardProposalContext(
            rule_id="r2",
            lesson_id="L9",
            rule_text="stop loss order day trading risk cap",
            concept="risk",
            subconcept=None,
            conditions=("ma20 filter",),
            invalidation=("large gap",),
            evidence_doc_ids=frozenset({"e1", "e2"}),
            frame_ids=("f2",),
        ),
    }
    recs = generate_rule_card_proposal_records(
        repo,
        MINI_INDEX,
        ctxs,
        proposal_types=[ProposalType.MERGE_CANDIDATE, ProposalType.DUPLICATE_CANDIDATE],
        generator_version="t.v2",
    )
    merges = [x for x in recs if x.proposal_type == ProposalType.MERGE_CANDIDATE]
    assert len(merges) >= 1


def test_canonical_family_candidate_when_rule_unlinked(
    repo: AdjudicationRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "pipeline.adjudication.proposal_generation.CANONICAL_THRESHOLD",
        0.25,
    )
    fam = repo.create_canonical_family(
        NewCanonicalFamily(
            canonical_title="day trading stop loss risk control rules",
            normalized_summary="use stop loss orders for day trading risk control intraday",
            created_by="u1",
            status=CanonicalFamilyStatus.ACTIVE,
            primary_concept="risk",
            primary_subconcept="stops",
        )
    )
    ctxs = {
        "r3": RuleCardProposalContext(
            rule_id="r3",
            lesson_id="L1",
            rule_text="day trading stop loss risk control intraday protection",
            concept="risk",
            subconcept="stops",
            evidence_doc_ids=frozenset({"e9"}),
        ),
    }
    recs = generate_rule_card_proposal_records(
        repo,
        CorpusTargetIndex(
            rule_card_ids=frozenset({"r3"}),
            evidence_link_ids=frozenset(),
            concept_link_ids=frozenset(),
            related_rule_relation_ids=frozenset(),
        ),
        ctxs,
        proposal_types=[ProposalType.CANONICAL_FAMILY_CANDIDATE],
        generator_version="t.v3",
    )
    canon = [x for x in recs if x.proposal_type == ProposalType.CANONICAL_FAMILY_CANDIDATE]
    assert len(canon) == 1
    assert canon[0].related_target_id == fam.family_id


def test_rejected_rule_excluded_from_generation(repo: AdjudicationRepository) -> None:
    repo.append_decision_and_refresh_state(
        NewReviewDecision(
            target_type=ReviewTargetType.RULE_CARD,
            target_id="r4",
            decision_type=DecisionType.REJECT,
            reviewer_id="u1",
        )
    )
    ctxs = {
        "r4": RuleCardProposalContext(
            rule_id="r4",
            rule_text="some rule text for testing exclusion",
            concept="c",
        ),
    }
    idx = CorpusTargetIndex(
        rule_card_ids=frozenset({"r4"}),
        evidence_link_ids=frozenset(),
        concept_link_ids=frozenset(),
        related_rule_relation_ids=frozenset(),
    )
    recs = generate_rule_card_proposal_records(repo, idx, ctxs, generator_version="t.v4")
    assert recs == []


def test_unsupported_rule_excluded_from_generation(repo: AdjudicationRepository) -> None:
    repo.append_decision_and_refresh_state(
        NewReviewDecision(
            target_type=ReviewTargetType.RULE_CARD,
            target_id="r4",
            decision_type=DecisionType.UNSUPPORTED,
            reviewer_id="u1",
        )
    )
    ctxs = {
        "r4": RuleCardProposalContext(
            rule_id="r4",
            rule_text="some rule text for testing exclusion",
            concept="c",
        ),
    }
    idx = CorpusTargetIndex(
        rule_card_ids=frozenset({"r4"}),
        evidence_link_ids=frozenset(),
        concept_link_ids=frozenset(),
        related_rule_relation_ids=frozenset(),
    )
    recs = generate_rule_card_proposal_records(repo, idx, ctxs, generator_version="t.v5")
    assert recs == []


def test_duplicate_of_rule_excluded_from_generation(repo: AdjudicationRepository) -> None:
    repo.append_decision_and_refresh_state(
        NewReviewDecision(
            target_type=ReviewTargetType.RULE_CARD,
            target_id="r4",
            decision_type=DecisionType.DUPLICATE_OF,
            reviewer_id="u1",
            related_target_id="r1",
        )
    )
    ctxs = {
        "r4": RuleCardProposalContext(
            rule_id="r4",
            rule_text="some rule text for testing exclusion",
            concept="c",
        ),
    }
    idx = CorpusTargetIndex(
        rule_card_ids=frozenset({"r4", "r1"}),
        evidence_link_ids=frozenset(),
        concept_link_ids=frozenset(),
        related_rule_relation_ids=frozenset(),
    )
    recs = generate_rule_card_proposal_records(repo, idx, ctxs, generator_version="t.v6")
    assert recs == []
