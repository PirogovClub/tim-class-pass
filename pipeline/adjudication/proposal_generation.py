"""Deterministic rule_card proposal generation (Stage 5.5)."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Collection, Mapping

from pipeline.component2.rule_reducer import normalize_text_for_match, simple_text_similarity

from pipeline.adjudication.corpus_inventory import CorpusTargetIndex
from pipeline.adjudication.enums import (
    CanonicalFamilyStatus,
    ProposalStatus,
    ProposalType,
    QualityTier,
    ReviewTargetType,
    RuleCardCoarseStatus,
)
from pipeline.adjudication.models import ProposalRecord
from pipeline.adjudication.proposal_policy import (
    CANONICAL_THRESHOLD,
    DEFAULT_GENERATOR_VERSION,
    DUPLICATE_THRESHOLD,
    MERGE_SCORE_MAX_EXCLUSIVE,
    MERGE_SCORE_MIN,
    PENALTY_SAME_LESSON,
    Q_BONUS_RELATED_ACTIVE_FAMILY,
    Q_BONUS_SOURCE_NOT_GOLD,
    Q_BONUS_UNRESOLVED,
    TOKEN_OVERLAP_PRUNE_MIN,
    W_CANON_ACTIVE,
    W_CANON_CONCEPT,
    W_CANON_MEMBER_OVERLAP,
    W_CANON_SUBCONCEPT,
    W_CANON_TEXT,
    W_DUP_NON_GOLD_PAIR,
    W_DUP_SAME_CONCEPT,
    W_DUP_SAME_SUBCONCEPT,
    W_DUP_SHARED_EVIDENCE,
    W_DUP_SHARED_SOURCE_EVENT,
    W_DUP_TEXT,
    W_MERGE_BOTH_PROVENANCE,
    W_MERGE_CONDITION_COMPAT,
    W_MERGE_ONE_IN_ACTIVE_FAMILY,
    W_MERGE_SAME_CONCEPT,
    W_MERGE_SAME_SUBCONCEPT,
    W_MERGE_SHARED_EVIDENCE,
    W_MERGE_TEXT,
)
from pipeline.adjudication.quality_tier import (
    INVALID_DUPLICATE_LINK,
    INVALID_FAMILY_LINK,
    resolve_tier_for_target,
)
from pipeline.adjudication.repository import AdjudicationRepository
from pipeline.adjudication.time_utils import utc_now_iso

if TYPE_CHECKING:
    from pipeline.explorer.service import ExplorerService

BROKEN_LINK_BLOCKERS = frozenset({INVALID_FAMILY_LINK, INVALID_DUPLICATE_LINK})


@dataclass(frozen=True)
class RuleCardProposalContext:
    rule_id: str
    lesson_id: str = ""
    rule_text: str = ""
    rule_text_ru: str = ""
    concept: str | None = None
    subconcept: str | None = None
    conditions: tuple[str, ...] = ()
    invalidation: tuple[str, ...] = ()
    evidence_doc_ids: frozenset[str] = field(default_factory=frozenset)
    source_event_doc_ids: frozenset[str] = field(default_factory=frozenset)
    frame_ids: tuple[str, ...] = field(default_factory=tuple)

    def primary_text(self) -> str:
        t = (self.rule_text or "").strip()
        if t:
            return t
        return (self.rule_text_ru or "").strip()

    def has_provenance(self) -> bool:
        return bool(self.evidence_doc_ids or self.frame_ids)


def rule_pair_dedupe_key(kind: str, rule_a: str, rule_b: str) -> str:
    low, high = sorted((rule_a, rule_b))
    return f"{kind}|rule_card|{low}|rule_card|{high}"


def canonical_dedupe_key(rule_id: str, family_id: str) -> str:
    return f"canonical|rule_card|{rule_id}|canonical_rule_family|{family_id}"


def load_rule_contexts_from_explorer(
    explorer: ExplorerService,
    rule_ids: Iterable[str],
) -> dict[str, RuleCardProposalContext]:
    out: dict[str, RuleCardProposalContext] = {}
    for rid in rule_ids:
        try:
            d = explorer.get_rule_detail(rid)
        except Exception:
            continue
        ev = frozenset(str(c.doc_id) for c in d.evidence_refs)
        se = frozenset(str(c.doc_id) for c in d.source_events)
        out[rid] = RuleCardProposalContext(
            rule_id=rid,
            lesson_id=d.lesson_id or "",
            rule_text=d.rule_text or "",
            rule_text_ru=d.rule_text_ru or "",
            concept=(d.concept or "").strip() or None,
            subconcept=(d.subconcept or "").strip() or None,
            conditions=tuple(d.conditions or ()),
            invalidation=tuple(d.invalidation or ()),
            evidence_doc_ids=ev,
            source_event_doc_ids=se,
            frame_ids=tuple(d.frame_ids or ()),
        )
    return out


def is_eligible_rule(
    repo: AdjudicationRepository,
    corpus_index: CorpusTargetIndex,
    rule_id: str,
    ctx: RuleCardProposalContext,
) -> bool:
    if rule_id not in corpus_index.rule_card_ids:
        return False
    if not ctx.primary_text():
        return False
    if not (ctx.concept or ctx.subconcept):
        return False
    st = repo.get_rule_card_state(rule_id)
    if st:
        if st.is_duplicate or st.is_unsupported:
            return False
        if st.current_status in (
            RuleCardCoarseStatus.REJECTED,
            RuleCardCoarseStatus.UNSUPPORTED,
            RuleCardCoarseStatus.DUPLICATE,
        ):
            return False
    tier_rec = resolve_tier_for_target(repo, ReviewTargetType.RULE_CARD, rule_id)
    if set(tier_rec.blocker_codes) & BROKEN_LINK_BLOCKERS:
        return False
    return True


def prune_pair_ok(ctx_a: RuleCardProposalContext, ctx_b: RuleCardProposalContext) -> bool:
    if ctx_a.concept and ctx_b.concept and ctx_a.concept == ctx_b.concept:
        return True
    if ctx_a.subconcept and ctx_b.subconcept and ctx_a.subconcept == ctx_b.subconcept:
        return True
    if simple_text_similarity(ctx_a.primary_text(), ctx_b.primary_text()) >= TOKEN_OVERLAP_PRUNE_MIN:
        return True
    if ctx_a.evidence_doc_ids & ctx_b.evidence_doc_ids:
        return True
    if ctx_a.source_event_doc_ids & ctx_b.source_event_doc_ids:
        return True
    return False


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _overlap_bonus(shared: int, weight: float) -> float:
    if shared <= 0:
        return 0.0
    return weight * min(1.0, shared / 2.0)


def _merge_condition_compat(ctx_a: RuleCardProposalContext, ctx_b: RuleCardProposalContext) -> float:
    parts_a = list(ctx_a.conditions) + list(ctx_a.invalidation)
    parts_b = list(ctx_b.conditions) + list(ctx_b.invalidation)
    sa = " ".join(p for p in (normalize_text_for_match(x) for x in parts_a) if p)
    sb = " ".join(p for p in (normalize_text_for_match(x) for x in parts_b) if p)
    if not sa.strip() and not sb.strip():
        return 0.05
    sim = simple_text_similarity(sa, sb)
    return W_MERGE_CONDITION_COMPAT * sim


def score_duplicate_pair(
    repo: AdjudicationRepository,
    ctx_a: RuleCardProposalContext,
    ctx_b: RuleCardProposalContext,
) -> tuple[float, dict[str, Any]]:
    ts = simple_text_similarity(ctx_a.primary_text(), ctx_b.primary_text())
    s = W_DUP_TEXT * ts
    signals: dict[str, Any] = {"text_similarity": ts}
    if ctx_a.concept and ctx_b.concept and ctx_a.concept == ctx_b.concept:
        s += W_DUP_SAME_CONCEPT
        signals["concept_match"] = True
    if ctx_a.subconcept and ctx_b.subconcept and ctx_a.subconcept == ctx_b.subconcept:
        s += W_DUP_SAME_SUBCONCEPT
        signals["subconcept_match"] = True
    sev = len(ctx_a.evidence_doc_ids & ctx_b.evidence_doc_ids)
    s += _overlap_bonus(sev, W_DUP_SHARED_EVIDENCE)
    signals["shared_evidence_count"] = sev
    sse = len(ctx_a.source_event_doc_ids & ctx_b.source_event_doc_ids)
    s += _overlap_bonus(sse, W_DUP_SHARED_SOURCE_EVENT)
    signals["shared_source_event_count"] = sse
    ta = resolve_tier_for_target(repo, ReviewTargetType.RULE_CARD, ctx_a.rule_id).tier
    tb = resolve_tier_for_target(repo, ReviewTargetType.RULE_CARD, ctx_b.rule_id).tier
    if ta != QualityTier.GOLD and tb != QualityTier.GOLD:
        s += W_DUP_NON_GOLD_PAIR
        signals["both_non_gold"] = True
    if ctx_a.lesson_id and ctx_a.lesson_id == ctx_b.lesson_id:
        s += PENALTY_SAME_LESSON
        signals["same_lesson_penalty"] = True
    return _clamp01(s), signals


def score_merge_pair(
    repo: AdjudicationRepository,
    ctx_a: RuleCardProposalContext,
    ctx_b: RuleCardProposalContext,
) -> tuple[float, dict[str, Any]]:
    ts = simple_text_similarity(ctx_a.primary_text(), ctx_b.primary_text())
    s = W_MERGE_TEXT * ts
    signals: dict[str, Any] = {"text_similarity": ts}
    if ctx_a.concept and ctx_b.concept and ctx_a.concept == ctx_b.concept:
        s += W_MERGE_SAME_CONCEPT
        signals["concept_match"] = True
    if ctx_a.subconcept and ctx_b.subconcept and ctx_a.subconcept == ctx_b.subconcept:
        s += W_MERGE_SAME_SUBCONCEPT
        signals["subconcept_match"] = True
    s += _merge_condition_compat(ctx_a, ctx_b)
    sev = len(ctx_a.evidence_doc_ids & ctx_b.evidence_doc_ids)
    s += _overlap_bonus(sev, W_MERGE_SHARED_EVIDENCE)
    signals["shared_evidence_count"] = sev
    fa = repo.get_active_family_id_for_rule(ctx_a.rule_id)
    fb = repo.get_active_family_id_for_rule(ctx_b.rule_id)
    if (fa and not fb) or (fb and not fa):
        s += W_MERGE_ONE_IN_ACTIVE_FAMILY
        signals["one_in_active_family"] = True
        signals["family_id"] = fa or fb
    if ctx_a.has_provenance() and ctx_b.has_provenance():
        s += W_MERGE_BOTH_PROVENANCE
        signals["both_provenance"] = True
    return _clamp01(s), signals


def _family_bundle_text(
    repo: AdjudicationRepository,
    family_id: str,
    contexts: Mapping[str, RuleCardProposalContext],
) -> tuple[str, list[str]]:
    fam = repo.get_family(family_id)
    if fam is None:
        return "", []
    bits = [fam.canonical_title or "", fam.normalized_summary or ""]
    member_texts: list[str] = []
    for m in repo.list_family_members(family_id):
        ctx = contexts.get(m.rule_id)
        if ctx:
            member_texts.append(ctx.primary_text())
        bits.append(ctx.primary_text() if ctx else "")
    return " ".join(bits), member_texts


def score_canonical_family(
    repo: AdjudicationRepository,
    ctx: RuleCardProposalContext,
    family_id: str,
    contexts: Mapping[str, RuleCardProposalContext],
) -> tuple[float, dict[str, Any]]:
    fam = repo.get_family(family_id)
    signals: dict[str, Any] = {"family_id": family_id}
    if fam is None or fam.status != CanonicalFamilyStatus.ACTIVE:
        return 0.0, signals
    bundle, member_texts = _family_bundle_text(repo, family_id, contexts)
    ts = simple_text_similarity(ctx.primary_text(), bundle)
    s = W_CANON_TEXT * ts
    signals["text_similarity"] = ts
    if fam.primary_concept and ctx.concept and fam.primary_concept == ctx.concept:
        s += W_CANON_CONCEPT
        signals["concept_match"] = True
    if fam.primary_subconcept and ctx.subconcept and fam.primary_subconcept == ctx.subconcept:
        s += W_CANON_SUBCONCEPT
        signals["subconcept_match"] = True
    if member_texts:
        best = max(simple_text_similarity(ctx.primary_text(), mt) for mt in member_texts if mt)
        s += W_CANON_MEMBER_OVERLAP * best
        signals["member_text_best_similarity"] = best
    s += W_CANON_ACTIVE
    signals["active_family"] = True
    return _clamp01(s), signals


def _snapshots_for_rule(
    repo: AdjudicationRepository, rule_id: str
) -> tuple[str, str]:
    st = repo.get_rule_card_state(rule_id)
    tr = resolve_tier_for_target(repo, ReviewTargetType.RULE_CARD, rule_id)
    adj = {
        "target_id": rule_id,
        "current_status": st.current_status.value if st and st.current_status else None,
        "is_duplicate": bool(st and st.is_duplicate),
        "canonical_family_id": st.canonical_family_id if st else None,
        "is_unsupported": bool(st and st.is_unsupported),
    }
    tier = {"tier": tr.tier.value, "blockers": tr.blocker_codes[:8]}
    return json.dumps(adj, sort_keys=True), json.dumps(tier, sort_keys=True)


def _rationale_from_signals(signals: Mapping[str, Any]) -> str:
    parts: list[str] = []
    ts = signals.get("text_similarity")
    if isinstance(ts, (int, float)):
        if ts >= 0.85:
            parts.append("High text overlap")
        elif ts >= 0.5:
            parts.append("Moderate text overlap")
    if signals.get("concept_match"):
        parts.append("same concept")
    if signals.get("subconcept_match"):
        parts.append("same subconcept")
    if signals.get("shared_evidence_count", 0) > 0:
        parts.append("shared evidence refs")
    if signals.get("shared_source_event_count", 0) > 0:
        parts.append("shared source events")
    if signals.get("one_in_active_family"):
        parts.append("one rule in an active family")
    if signals.get("member_text_best_similarity") is not None:
        parts.append("overlaps family member rules")
    if not parts:
        return "Heuristic proposal from corpus signals"
    return ", ".join(parts[:6])


def _queue_priority_for_pair(
    repo: AdjudicationRepository,
    base_score: float,
    rule_a: str,
    rule_b: str,
    *,
    related_in_active_family: bool,
) -> float:
    ta = resolve_tier_for_target(repo, ReviewTargetType.RULE_CARD, rule_a).tier
    tb = resolve_tier_for_target(repo, ReviewTargetType.RULE_CARD, rule_b).tier
    p = base_score
    if ta == QualityTier.UNRESOLVED:
        p += Q_BONUS_UNRESOLVED
    if tb == QualityTier.UNRESOLVED:
        p += Q_BONUS_UNRESOLVED
    if ta != QualityTier.GOLD:
        p += Q_BONUS_SOURCE_NOT_GOLD
    if related_in_active_family:
        p += Q_BONUS_RELATED_ACTIVE_FAMILY
    return p


def _queue_priority_canonical(
    repo: AdjudicationRepository,
    base_score: float,
    rule_id: str,
) -> float:
    t = resolve_tier_for_target(repo, ReviewTargetType.RULE_CARD, rule_id).tier
    p = base_score + Q_BONUS_RELATED_ACTIVE_FAMILY
    if t == QualityTier.UNRESOLVED:
        p += Q_BONUS_UNRESOLVED
    if t != QualityTier.GOLD:
        p += Q_BONUS_SOURCE_NOT_GOLD
    return p


def _build_pair_proposal(
    repo: AdjudicationRepository,
    *,
    proposal_type: ProposalType,
    score: float,
    signals: dict[str, Any],
    low_id: str,
    high_id: str,
    dedupe_key: str,
    generator_version: str,
) -> ProposalRecord:
    adj_src, tier_src = _snapshots_for_rule(repo, low_id)
    adj_rel, tier_rel = _snapshots_for_rule(repo, high_id)
    combined_adj = {"source": json.loads(adj_src), "related": json.loads(adj_rel)}
    combined_tier = {"source": json.loads(tier_src), "related": json.loads(tier_rel)}
    af = repo.get_active_family_id_for_rule(high_id) or repo.get_active_family_id_for_rule(low_id)
    qp = _queue_priority_for_pair(
        repo, score, low_id, high_id, related_in_active_family=bool(af)
    )
    rationale = _rationale_from_signals(signals)
    now = utc_now_iso()
    return ProposalRecord(
        proposal_id=str(uuid.uuid4()),
        proposal_type=proposal_type,
        source_target_type=ReviewTargetType.RULE_CARD,
        source_target_id=low_id,
        related_target_type=ReviewTargetType.RULE_CARD,
        related_target_id=high_id,
        proposal_status=ProposalStatus.NEW,
        score=score,
        score_breakdown_json=json.dumps({"raw_signals": signals}, sort_keys=True),
        rationale_summary=rationale,
        signals_json=json.dumps(signals, sort_keys=True),
        evidence_refs_json=None,
        adjudication_snapshot_json=json.dumps(combined_adj, sort_keys=True),
        tier_snapshot_json=json.dumps(combined_tier, sort_keys=True),
        queue_priority=qp,
        dedupe_key=dedupe_key,
        generator_version=generator_version,
        created_at=now,
        updated_at=now,
        last_generated_at=now,
    )


def _build_canonical_proposal(
    repo: AdjudicationRepository,
    *,
    rule_id: str,
    family_id: str,
    score: float,
    signals: dict[str, Any],
    generator_version: str,
) -> ProposalRecord:
    adj_src, tier_src = _snapshots_for_rule(repo, rule_id)
    fam = repo.get_family(family_id)
    fam_adj = {
        "family_id": family_id,
        "status": fam.status.value if fam else None,
        "title": fam.canonical_title if fam else None,
    }
    combined_adj = {"source": json.loads(adj_src), "family": fam_adj}
    tr = resolve_tier_for_target(repo, ReviewTargetType.RULE_CARD, rule_id)
    combined_tier = {"source": json.loads(tier_src), "family_id": family_id, "rule_tier": tr.tier.value}
    qp = _queue_priority_canonical(repo, score, rule_id)
    rationale = _rationale_from_signals(signals)
    now = utc_now_iso()
    dk = canonical_dedupe_key(rule_id, family_id)
    return ProposalRecord(
        proposal_id=str(uuid.uuid4()),
        proposal_type=ProposalType.CANONICAL_FAMILY_CANDIDATE,
        source_target_type=ReviewTargetType.RULE_CARD,
        source_target_id=rule_id,
        related_target_type=ReviewTargetType.CANONICAL_RULE_FAMILY,
        related_target_id=family_id,
        proposal_status=ProposalStatus.NEW,
        score=score,
        score_breakdown_json=json.dumps({"raw_signals": signals}, sort_keys=True),
        rationale_summary=rationale,
        signals_json=json.dumps(signals, sort_keys=True),
        evidence_refs_json=None,
        adjudication_snapshot_json=json.dumps(combined_adj, sort_keys=True),
        tier_snapshot_json=json.dumps(combined_tier, sort_keys=True),
        queue_priority=qp,
        dedupe_key=dk,
        generator_version=generator_version,
        created_at=now,
        updated_at=now,
        last_generated_at=now,
    )


def generate_rule_card_proposal_records(
    repo: AdjudicationRepository,
    corpus_index: CorpusTargetIndex,
    contexts: Mapping[str, RuleCardProposalContext],
    *,
    proposal_types: Collection[ProposalType] | None = None,
    limit: int | None = None,
    generator_version: str = DEFAULT_GENERATOR_VERSION,
) -> list[ProposalRecord]:
    types = frozenset(proposal_types) if proposal_types else frozenset(ProposalType)
    eligible: list[str] = []
    for rid in sorted(corpus_index.rule_card_ids):
        ctx = contexts.get(rid)
        if ctx is None:
            continue
        if is_eligible_rule(repo, corpus_index, rid, ctx):
            eligible.append(rid)

    records: list[ProposalRecord] = []

    if ProposalType.DUPLICATE_CANDIDATE in types or ProposalType.MERGE_CANDIDATE in types:
        for i, a in enumerate(eligible):
            for b in eligible[i + 1 :]:
                ctx_a = contexts[a]
                ctx_b = contexts[b]
                if not prune_pair_ok(ctx_a, ctx_b):
                    continue
                dk_dup = rule_pair_dedupe_key("duplicate", a, b)
                dk_merge = rule_pair_dedupe_key("merge", a, b)
                low, high = sorted((a, b))

                dup_score, dup_sig = score_duplicate_pair(repo, ctx_a, ctx_b)
                if dup_score >= DUPLICATE_THRESHOLD:
                    if ProposalType.DUPLICATE_CANDIDATE in types:
                        records.append(
                            _build_pair_proposal(
                                repo,
                                proposal_type=ProposalType.DUPLICATE_CANDIDATE,
                                score=dup_score,
                                signals=dup_sig,
                                low_id=low,
                                high_id=high,
                                dedupe_key=dk_dup,
                                generator_version=generator_version,
                            )
                        )
                    continue

                if ProposalType.MERGE_CANDIDATE in types:
                    ms, msig = score_merge_pair(repo, ctx_a, ctx_b)
                    if MERGE_SCORE_MIN <= ms < MERGE_SCORE_MAX_EXCLUSIVE:
                        records.append(
                            _build_pair_proposal(
                                repo,
                                proposal_type=ProposalType.MERGE_CANDIDATE,
                                score=ms,
                                signals=msig,
                                low_id=low,
                                high_id=high,
                                dedupe_key=dk_merge,
                                generator_version=generator_version,
                            )
                        )

    if ProposalType.CANONICAL_FAMILY_CANDIDATE in types:
        active_families: list[str] = []
        with repo.connect() as conn:
            cur = conn.execute(
                "SELECT family_id FROM canonical_rule_families WHERE status = ?",
                (CanonicalFamilyStatus.ACTIVE.value,),
            )
            active_families = [str(r["family_id"]) for r in cur.fetchall()]

        for rid in eligible:
            if repo.get_active_family_id_for_rule(rid):
                continue
            ctx = contexts[rid]
            best_f: str | None = None
            best_s = 0.0
            best_sig: dict[str, Any] = {}
            for fid in active_families:
                sc, sig = score_canonical_family(repo, ctx, fid, contexts)
                if sc > best_s:
                    best_s = sc
                    best_f = fid
                    best_sig = sig
            if best_f and best_s >= CANONICAL_THRESHOLD:
                records.append(
                    _build_canonical_proposal(
                        repo,
                        rule_id=rid,
                        family_id=best_f,
                        score=best_s,
                        signals=best_sig,
                        generator_version=generator_version,
                    )
                )

    records.sort(key=lambda r: (-r.queue_priority, -r.score, r.proposal_id))
    if limit is not None and limit >= 0:
        records = records[:limit]
    return records
