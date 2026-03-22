"""Task 5: Rule normalization and merge logic — group KnowledgeEvents into RuleCards."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from pipeline.io_utils import atomic_write_text, atomic_write_json
from pipeline.component2.provenance import (
    build_rule_card_provenance,
    validate_rule_card_provenance,
)
from pipeline.component2.visual_compaction import (
    VisualCompactionConfig,
    assert_no_raw_visual_blob_leak,
    strip_raw_visual_blobs_from_metadata,
    summarize_evidence_for_rule_card,
    trim_rule_card_visual_refs,
)
from pipeline.schemas import (
    EvidenceIndex,
    EvidenceRef,
    KnowledgeEvent,
    KnowledgeEventCollection,
    RuleCard,
    RuleCardCollection,
    validate_rule_card,
)
from pipeline.component2.canonicalization import (
    canonicalize_concept,
    canonicalize_subconcept,
    canonicalize_short_statement,
    classify_rule_type,
)
from pipeline.component2.parser import timestamp_to_seconds
from pipeline.component2.support_policy import (
    classify_evidence_requirement,
    classify_support_basis,
    classify_teaching_mode,
    classify_transcript_support_level,
    classify_visual_support_level,
)


# ----- Internal model -----


@dataclass
class RuleCandidate:
    candidate_id: str
    lesson_id: str
    concept: str | None
    subconcept: str | None
    title_hint: str | None
    from_split: bool = False
    primary_events: list[KnowledgeEvent] = field(default_factory=list)
    condition_events: list[KnowledgeEvent] = field(default_factory=list)
    invalidation_events: list[KnowledgeEvent] = field(default_factory=list)
    exception_events: list[KnowledgeEvent] = field(default_factory=list)
    comparison_events: list[KnowledgeEvent] = field(default_factory=list)
    warning_events: list[KnowledgeEvent] = field(default_factory=list)
    process_events: list[KnowledgeEvent] = field(default_factory=list)
    algorithm_hint_events: list[KnowledgeEvent] = field(default_factory=list)
    example_events: list[KnowledgeEvent] = field(default_factory=list)
    linked_evidence: list[EvidenceRef] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


# ----- Loaders -----


def load_knowledge_events(path: Path) -> KnowledgeEventCollection:
    """Load and validate KnowledgeEventCollection from JSON."""
    text = path.read_text(encoding="utf-8")
    return KnowledgeEventCollection.model_validate_json(text)


def load_evidence_index(path: Path) -> EvidenceIndex:
    """Load and validate EvidenceIndex from JSON."""
    text = path.read_text(encoding="utf-8")
    return EvidenceIndex.model_validate_json(text)


# ----- Text helpers -----


def normalize_text_for_match(text: str) -> str:
    """Lowercase, normalize whitespace, strip trivial punctuation."""
    if not text:
        return ""
    s = text.lower().strip()
    s = re.sub(r"\s+", " ", s)
    s = s.rstrip(".,;:")
    return s.strip()


def simple_text_similarity(a: str, b: str) -> float:
    """Token-set overlap similarity in [0, 1]. No LLM."""
    na = set(normalize_text_for_match(a).split())
    nb = set(normalize_text_for_match(b).split())
    if not na and not nb:
        return 1.0
    if not na or not nb:
        return 0.0
    inter = len(na & nb)
    union = len(na | nb)
    return inter / union if union else 0.0


# ----- Role compatibility -----


def is_role_compatible(event_type: str, candidate: RuleCandidate) -> bool:
    """True if event can attach to this candidate by role."""
    has_primary = len(candidate.primary_events) > 0
    cand_concept = (candidate.concept or "").strip()
    cand_sub = (candidate.subconcept or "").strip()

    if event_type == "rule_statement":
        return True
    if event_type == "definition":
        if not has_primary:
            return True
        return True
    if event_type in ("condition", "invalidation", "exception", "algorithm_hint"):
        return True
    if event_type == "example":
        return bool(candidate.linked_evidence or cand_concept)
    if event_type == "comparison":
        return has_primary and bool(cand_concept)
    if event_type in ("warning", "process_step", "observation"):
        return bool(cand_concept)

    return False


# ----- Match scoring -----

ATTACH_THRESHOLD = 0.60

WEIGHT_CONCEPT = 0.35
WEIGHT_SUBCONCEPT = 0.20
WEIGHT_SECTION = 0.15
WEIGHT_CHUNK = 0.10
WEIGHT_ROLE = 0.10
WEIGHT_TEXT = 0.10


def _event_chunk_index(event: KnowledgeEvent) -> int | None:
    m = getattr(event, "metadata", None) or {}
    v = m.get("chunk_index")
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _candidate_chunk_indexes(candidate: RuleCandidate) -> set[int]:
    out: set[int] = set()
    for ev in (
        candidate.primary_events
        + candidate.condition_events
        + candidate.invalidation_events
        + candidate.exception_events
    ):
        ci = _event_chunk_index(ev)
        if ci is not None:
            out.add(ci)
    return out


def score_event_candidate_match(
    event: KnowledgeEvent,
    candidate: RuleCandidate,
) -> tuple[float, dict]:
    """Score how well event fits candidate. Returns (score in [0,1], breakdown dict)."""
    breakdown: dict[str, float] = {
        "concept_match": 0.0,
        "subconcept_match": 0.0,
        "section_match": 0.0,
        "chunk_proximity": 0.0,
        "role_compatibility": 0.0,
        "text_similarity": 0.0,
    }

    if event.lesson_id != candidate.lesson_id:
        return (0.0, {**breakdown, "total": 0.0})

    if event.concept and candidate.concept:
        if event.concept.strip().lower() == candidate.concept.strip().lower():
            breakdown["concept_match"] = WEIGHT_CONCEPT
    elif event.concept or candidate.concept:
        breakdown["concept_match"] = WEIGHT_CONCEPT * 0.5

    if event.subconcept and candidate.subconcept:
        if event.subconcept.strip().lower() == candidate.subconcept.strip().lower():
            breakdown["subconcept_match"] = WEIGHT_SUBCONCEPT
    elif not event.subconcept or not candidate.subconcept:
        if event.concept and candidate.concept:
            breakdown["subconcept_match"] = WEIGHT_SUBCONCEPT * 0.5

    if event.section and candidate.primary_events:
        first = candidate.primary_events[0]
        if getattr(first, "section", None) and event.section == first.section:
            breakdown["section_match"] = WEIGHT_SECTION * 0.5
        if getattr(first, "subsection", None) and event.subsection == first.subsection:
            breakdown["section_match"] += WEIGHT_SECTION * 0.5
    if breakdown["section_match"] == 0 and (event.section or event.subsection):
        breakdown["section_match"] = WEIGHT_SECTION * 0.25

    cand_chunks = _candidate_chunk_indexes(candidate)
    ev_chunk = _event_chunk_index(event)
    if ev_chunk is not None and cand_chunks:
        if ev_chunk in cand_chunks:
            breakdown["chunk_proximity"] = WEIGHT_CHUNK
        elif any(abs(ev_chunk - c) <= 1 for c in cand_chunks):
            breakdown["chunk_proximity"] = WEIGHT_CHUNK * 0.5

    if is_role_compatible(event.event_type, candidate):
        breakdown["role_compatibility"] = WEIGHT_ROLE

    primary_texts = [e.normalized_text for e in candidate.primary_events]
    if primary_texts:
        sims = [simple_text_similarity(event.normalized_text, t) for t in primary_texts]
        breakdown["text_similarity"] = max(sims) * WEIGHT_TEXT if sims else 0.0
    else:
        breakdown["text_similarity"] = WEIGHT_TEXT * 0.5

    total = min(1.0, sum(breakdown.values()))
    breakdown["total"] = total
    return (total, breakdown)


def _route_event_into_candidate(event: KnowledgeEvent, candidate: RuleCandidate) -> None:
    """Append event to the appropriate list on candidate."""
    t = event.event_type
    if t in ("rule_statement", "definition"):
        candidate.primary_events.append(event)
    elif t == "condition":
        candidate.condition_events.append(event)
    elif t == "invalidation":
        candidate.invalidation_events.append(event)
    elif t == "exception":
        candidate.exception_events.append(event)
    elif t == "comparison":
        candidate.comparison_events.append(event)
    elif t == "warning":
        candidate.warning_events.append(event)
    elif t == "process_step":
        candidate.process_events.append(event)
    elif t == "algorithm_hint":
        candidate.algorithm_hint_events.append(event)
    elif t == "example":
        candidate.example_events.append(event)
    else:
        candidate.primary_events.append(event)


def group_events_into_rule_candidates(
    knowledge_events: list[KnowledgeEvent],
    evidence_index: EvidenceIndex,
    *,
    threshold: float = ATTACH_THRESHOLD,
) -> tuple[list[RuleCandidate], list[dict]]:
    """Group events into rule candidates; return (candidates, debug_rows)."""
    candidates: list[RuleCandidate] = []
    debug_rows: list[dict] = []
    lesson_id = evidence_index.lesson_id

    for event in knowledge_events:
        if event.lesson_id != lesson_id:
            continue
        best_score = -1.0
        best_candidate: RuleCandidate | None = None
        best_breakdown: dict | None = None
        for c in candidates:
            score, breakdown = score_event_candidate_match(event, c)
            if score >= threshold and score > best_score:
                best_score = score
                best_candidate = c
                best_breakdown = breakdown
        if best_candidate is not None and best_breakdown is not None:
            _route_event_into_candidate(event, best_candidate)
            debug_rows.append(
                {
                    "event_id": event.event_id,
                    "candidate_id": best_candidate.candidate_id,
                    "score_breakdown": best_breakdown,
                }
            )
        else:
            cid = f"rcand_{lesson_id}_{len(candidates)}"
            new_cand = RuleCandidate(
                candidate_id=cid,
                lesson_id=event.lesson_id,
                concept=event.concept,
                subconcept=event.subconcept,
                title_hint=None,
            )
            _route_event_into_candidate(event, new_cand)
            candidates.append(new_cand)
            debug_rows.append(
                {
                    "event_id": event.event_id,
                    "candidate_id": cid,
                    "score_breakdown": {"total": 0.0, "new_candidate": True},
                }
            )

    return (candidates, debug_rows)


# ----- Evidence attachment -----


def _candidate_event_ids(c: RuleCandidate) -> set[str]:
    ids: set[str] = set()
    for ev in (
        c.primary_events
        + c.condition_events
        + c.invalidation_events
        + c.exception_events
        + c.comparison_events
        + c.example_events
    ):
        ids.add(ev.event_id)
    return ids


def attach_evidence_to_candidates(
    candidates: list[RuleCandidate],
    evidence_index: EvidenceIndex,
) -> list[RuleCandidate]:
    """Attach EvidenceRefs to candidates when source_event_ids overlap."""
    for ref in evidence_index.evidence_refs:
        ref_ids = set(ref.source_event_ids or [])
        if not ref_ids:
            continue
        for c in candidates:
            cand_ids = _candidate_event_ids(c)
            if ref_ids & cand_ids:
                if ref not in c.linked_evidence:
                    c.linked_evidence.append(ref)
    return candidates


def _candidate_time_range(candidate: RuleCandidate) -> tuple[float, float] | None:
    """Return (min_start, max_end) in seconds across all events, or None."""
    all_events = (
        candidate.primary_events
        + candidate.condition_events
        + candidate.invalidation_events
        + candidate.exception_events
        + candidate.comparison_events
        + candidate.example_events
    )
    starts: list[float] = []
    ends: list[float] = []
    for ev in all_events:
        try:
            if ev.timestamp_start:
                starts.append(timestamp_to_seconds(ev.timestamp_start))
            if ev.timestamp_end:
                ends.append(timestamp_to_seconds(ev.timestamp_end))
        except (ValueError, TypeError):
            continue
    if not starts and not ends:
        return None
    lo = min(starts) if starts else min(ends)
    hi = max(ends) if ends else max(starts)
    return (lo, hi)


def _evidence_time_range(ref: EvidenceRef) -> tuple[float, float] | None:
    try:
        s = timestamp_to_seconds(ref.timestamp_start) if ref.timestamp_start else None
        e = timestamp_to_seconds(ref.timestamp_end) if ref.timestamp_end else None
    except (ValueError, TypeError):
        return None
    if s is not None and e is not None:
        return (s, e)
    if s is not None:
        return (s, s)
    if e is not None:
        return (e, e)
    return None


def attach_evidence_by_proximity(
    candidates: list[RuleCandidate],
    evidence_index: EvidenceIndex,
    max_proximity_seconds: float = 60.0,
) -> list[RuleCandidate]:
    """Fallback: for candidates with 0 linked_evidence, attach the nearest evidence by time."""
    ref_ranges: list[tuple[EvidenceRef, tuple[float, float]]] = []
    for ref in evidence_index.evidence_refs:
        tr = _evidence_time_range(ref)
        if tr is not None:
            ref_ranges.append((ref, tr))
    if not ref_ranges:
        return candidates

    for c in candidates:
        if c.linked_evidence:
            continue
        ctr = _candidate_time_range(c)
        if ctr is None:
            continue
        c_start, c_end = ctr

        best_ref: EvidenceRef | None = None
        best_gap = float("inf")
        for ref, (r_start, r_end) in ref_ranges:
            if r_start <= c_end and r_end >= c_start:
                gap = 0.0
            else:
                gap = min(abs(c_start - r_end), abs(c_end - r_start))
            if gap < best_gap:
                best_gap = gap
                best_ref = ref
        if best_ref is not None and best_gap <= max_proximity_seconds:
            c.linked_evidence.append(best_ref)
            c.metadata["proximity_fallback"] = True
            c.metadata["proximity_gap_seconds"] = round(best_gap, 2)

    return candidates


# ----- Duplicate merge -----


def merge_duplicate_primary_events(
    primary_events: list[KnowledgeEvent],
) -> list[KnowledgeEvent]:
    """Dedupe primary events by normalized text; keep one per group."""
    if len(primary_events) <= 1:
        return list(primary_events)
    seen_norm: dict[str, KnowledgeEvent] = {}
    for ev in primary_events:
        norm = normalize_text_for_match(ev.normalized_text)
        if not norm:
            continue
        if norm not in seen_norm:
            seen_norm[norm] = ev
        else:
            existing = seen_norm[norm]
            if (ev.confidence_score or 0) > (existing.confidence_score or 0):
                seen_norm[norm] = ev
    return list(seen_norm.values())


# ----- Split over-broad -----


def split_overbroad_candidate(candidate: RuleCandidate) -> list[RuleCandidate]:
    """Split when multiple subconcepts or distinct primary rules; prefer over-splitting."""
    subconcepts = set()
    for ev in candidate.primary_events + candidate.condition_events:
        if ev.subconcept and ev.subconcept.strip():
            subconcepts.add(ev.subconcept.strip().lower())
    if len(subconcepts) > 1:
        by_sub: dict[str, RuleCandidate] = {}
        for ev in candidate.primary_events:
            sub = (ev.subconcept or "general").strip().lower() or "general"
            if sub not in by_sub:
                by_sub[sub] = RuleCandidate(
                    candidate_id=f"{candidate.candidate_id}_{sub}",
                    lesson_id=candidate.lesson_id,
                    concept=candidate.concept,
                    subconcept=ev.subconcept or candidate.subconcept,
                    title_hint=candidate.title_hint,
                    from_split=True,
                    linked_evidence=list(candidate.linked_evidence),
                    metadata=dict(candidate.metadata),
                )
            by_sub[sub].primary_events.append(ev)
        for ev in candidate.condition_events:
            sub = (ev.subconcept or "general").strip().lower() or "general"
            if sub in by_sub:
                by_sub[sub].condition_events.append(ev)
        for ev in candidate.invalidation_events:
            sub = (ev.subconcept or "general").strip().lower() or "general"
            if sub in by_sub:
                by_sub[sub].invalidation_events.append(ev)
        for ev in candidate.exception_events:
            sub = (ev.subconcept or "general").strip().lower() or "general"
            if sub in by_sub:
                by_sub[sub].exception_events.append(ev)
        for ev in candidate.algorithm_hint_events:
            sub = (ev.subconcept or "general").strip().lower() or "general"
            if sub in by_sub:
                by_sub[sub].algorithm_hint_events.append(ev)
        for ev in candidate.example_events:
            sub = (ev.subconcept or "general").strip().lower() or "general"
            if sub in by_sub:
                by_sub[sub].example_events.append(ev)
        for c in by_sub.values():
            for ref in candidate.linked_evidence:
                if ref not in c.linked_evidence:
                    cand_ids = _candidate_event_ids(c)
                    if set(ref.source_event_ids or []) & cand_ids:
                        c.linked_evidence.append(ref)
        return list(by_sub.values())

    primaries = merge_duplicate_primary_events(candidate.primary_events)
    if len(primaries) <= 1:
        return [candidate]
    sim_matrix: list[tuple[int, int, float]] = []
    for i in range(len(primaries)):
        for j in range(i + 1, len(primaries)):
            sim = simple_text_similarity(primaries[i].normalized_text, primaries[j].normalized_text)
            sim_matrix.append((i, j, sim))
    low_sim_set = {(i, j) for i, j, s in sim_matrix if s < 0.4}
    if not low_sim_set:
        return [candidate]
    # Union-find: merge indices that have high similarity (not in low_sim_set)
    parent: list[int] = list(range(len(primaries)))

    def find(x: int) -> int:
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]

    def union(i: int, j: int) -> None:
        parent[find(i)] = find(j)

    for i in range(len(primaries)):
        for j in range(i + 1, len(primaries)):
            if (i, j) not in low_sim_set:
                union(i, j)
    groups: dict[int, list[int]] = {}
    for idx in range(len(primaries)):
        g = find(idx)
        groups.setdefault(g, []).append(idx)
    if len(groups) <= 1:
        return [candidate]
    result: list[RuleCandidate] = []
    for gid, indices in groups.items():
        sub = RuleCandidate(
            candidate_id=f"{candidate.candidate_id}_g{gid}",
            lesson_id=candidate.lesson_id,
            concept=candidate.concept,
            subconcept=candidate.subconcept,
            title_hint=candidate.title_hint,
            from_split=True,
            linked_evidence=list(candidate.linked_evidence),
            metadata=dict(candidate.metadata),
        )
        for i in indices:
            sub.primary_events.append(primaries[i])
        sub.condition_events = list(candidate.condition_events)
        sub.invalidation_events = list(candidate.invalidation_events)
        sub.exception_events = list(candidate.exception_events)
        sub.algorithm_hint_events = list(candidate.algorithm_hint_events)
        sub.example_events = list(candidate.example_events)
        result.append(sub)
    return result


# ----- Canonical rule text -----


def choose_canonical_rule_text(candidate: RuleCandidate) -> str:
    """Pick one canonical sentence: rule_statement > definition > condition."""
    primaries = candidate.primary_events
    if not primaries:
        return "No rule text extracted."

    rule_stmts = [e for e in primaries if e.event_type == "rule_statement"]
    definitions = [e for e in primaries if e.event_type == "definition"]
    others = [e for e in primaries if e.event_type not in ("rule_statement", "definition")]

    def score(e: KnowledgeEvent) -> tuple[int, float, int]:
        type_rank = 0 if e.event_type == "rule_statement" else (1 if e.event_type == "definition" else 2)
        conf = e.confidence_score if e.confidence_score is not None else 0.5
        length = len(e.normalized_text)
        return (type_rank, conf, -length)

    pool = rule_stmts or definitions or others
    pool_sorted = sorted(pool, key=score)
    return pool_sorted[0].normalized_text.strip() if pool_sorted else "No rule text extracted."


# ----- Collect texts -----


def _dedupe_short(texts: list[str], max_len: int = 200) -> list[str]:
    seen = set()
    out: list[str] = []
    for t in texts:
        n = normalize_text_for_match(t)
        if not n or n in seen or len(t) > max_len:
            continue
        seen.add(n)
        out.append(t.strip())
    return out


def collect_condition_texts(candidate: RuleCandidate) -> list[str]:
    return _dedupe_short([e.normalized_text for e in candidate.condition_events])


def collect_invalidation_texts(candidate: RuleCandidate) -> list[str]:
    return _dedupe_short([e.normalized_text for e in candidate.invalidation_events])


def collect_exception_texts(candidate: RuleCandidate) -> list[str]:
    return _dedupe_short([e.normalized_text for e in candidate.exception_events])


def collect_comparison_texts(candidate: RuleCandidate) -> list[str]:
    return _dedupe_short([e.normalized_text for e in candidate.comparison_events])


def collect_algorithm_notes(candidate: RuleCandidate) -> list[str]:
    return _dedupe_short([e.normalized_text for e in candidate.algorithm_hint_events])


# ----- Rule ID -----


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (s or "").lower()).strip("_") or "unknown"


def make_rule_id(
    lesson_id: str,
    concept: str | None,
    subconcept: str | None,
    candidate_index: int,
) -> str:
    return f"rule_{_slug(lesson_id)}_{_slug(concept)}_{_slug(subconcept)}_{candidate_index}"


# ----- Example refs -----


def distribute_example_refs(candidate: RuleCandidate) -> dict[str, list[str]]:
    """Map example_role to positive/negative/ambiguous evidence_id lists.
    Illustration is not treated as positive (Task 13: conservative ML labeling).
    """
    out: dict[str, list[str]] = {
        "positive_example_refs": [],
        "negative_example_refs": [],
        "ambiguous_example_refs": [],
    }
    for ref in candidate.linked_evidence:
        eid = ref.evidence_id
        role = (getattr(ref, "example_role", None) or "unknown").lower()
        if role == "positive_example":
            out["positive_example_refs"].append(eid)
        elif role in ("negative_example", "counterexample"):
            out["negative_example_refs"].append(eid)
        elif role == "ambiguous_example":
            out["ambiguous_example_refs"].append(eid)
        # illustration: do not add to positive (reserved for future ML prep)
    return out


# ----- Confidence -----


def _aggregate_transcript_support(candidate: RuleCandidate) -> tuple[float, int, int]:
    """Aggregate transcript support from source events.

    Returns (avg_transcript_score, total_anchor_count, repetition_count).
    """
    all_events = (
        candidate.primary_events
        + candidate.condition_events
        + candidate.invalidation_events
        + candidate.exception_events
    )
    scores: list[float] = []
    total_anchors = 0
    for ev in all_events:
        ts = getattr(ev, "transcript_support_score", None)
        if ts is not None:
            scores.append(ts)
        total_anchors += len(getattr(ev, "transcript_anchors", []))
    avg_score = sum(scores) / len(scores) if scores else 0.40
    repetition = max(len(candidate.primary_events) - 1, 0)
    return (avg_score, total_anchors, repetition)


def _aggregate_visual_support(candidate: RuleCandidate) -> float:
    """Aggregate visual support from source events."""
    all_events = (
        candidate.primary_events
        + candidate.condition_events
        + candidate.invalidation_events
        + candidate.exception_events
    )
    scores: list[float] = []
    for ev in all_events:
        vs = getattr(ev, "visual_support_score", None)
        if vs is not None:
            scores.append(vs)
    if candidate.linked_evidence:
        scores.append(0.50)
    return max(scores) if scores else 0.0


def score_rule_candidate_confidence(
    candidate: RuleCandidate,
    *,
    transcript_support_score: float = 0.5,
) -> tuple[str, float]:
    """Transcript-first confidence: strong transcript grounding lifts score
    even when visual evidence is absent."""
    score = 0.25 + transcript_support_score * 0.35
    if candidate.primary_events:
        score += 0.10
    if candidate.concept and candidate.concept.strip():
        score += 0.08
    if candidate.subconcept and candidate.subconcept.strip():
        score += 0.04
    if len(candidate.condition_events) + len(candidate.invalidation_events) > 0:
        score += 0.05
    if candidate.linked_evidence:
        score += 0.06
    if len(candidate.primary_events) + len(candidate.condition_events) > 1:
        score += 0.05
    score = max(0.0, min(1.0, score))
    if score >= 0.75:
        label = "high"
    elif score >= 0.5:
        label = "medium"
    else:
        label = "low"
    return (label, float(score))


# ----- RuleCard build -----


def candidate_to_rule_card(
    candidate: RuleCandidate,
    candidate_index: int,
    compaction_cfg: VisualCompactionConfig | None = None,
) -> RuleCard:
    """Convert RuleCandidate to RuleCard."""
    cfg = compaction_cfg if compaction_cfg is not None else VisualCompactionConfig()
    all_source_events = (
        candidate.primary_events
        + candidate.condition_events
        + candidate.invalidation_events
        + candidate.exception_events
        + candidate.comparison_events
        + candidate.example_events
    )
    prov = build_rule_card_provenance(
        lesson_id=candidate.lesson_id,
        source_events=all_source_events,
        linked_evidence=candidate.linked_evidence,
    )
    source_event_ids = prov.get("source_event_ids", [])
    evidence_refs = trim_rule_card_visual_refs(
        prov.get("evidence_refs", []), max_refs=3
    )

    concept = (candidate.concept or "unknown").strip() or "unknown"
    rule_id = make_rule_id(candidate.lesson_id, candidate.concept, candidate.subconcept, candidate_index)
    rule_text = choose_canonical_rule_text(candidate)

    ts_score, anchor_count, repetition_count = _aggregate_transcript_support(candidate)
    vs_score = _aggregate_visual_support(candidate)

    dominant_event_type_for_policy = "rule_statement"
    if candidate.primary_events:
        from collections import Counter as _Counter
        _tc = _Counter(e.event_type for e in candidate.primary_events)
        dominant_event_type_for_policy = _tc.most_common(1)[0][0]

    teaching_mode = classify_teaching_mode(
        dominant_event_type_for_policy,
        rule_text,
        linked_visual_count=len(candidate.linked_evidence),
        visual_example_type=None,
    )
    ev_req = classify_evidence_requirement(
        dominant_event_type_for_policy, teaching_mode, concept, candidate.subconcept,
    )
    s_basis = classify_support_basis(ts_score, vs_score, teaching_mode)
    t_level = classify_transcript_support_level(ts_score)

    primary_example_role = None
    if candidate.linked_evidence:
        primary_example_role = getattr(candidate.linked_evidence[0], "example_role", None)
    v_level = classify_visual_support_level(vs_score, example_role=primary_example_role)

    conf_label, conf_score = score_rule_candidate_confidence(
        candidate, transcript_support_score=ts_score,
    )
    example_map = distribute_example_refs(candidate)
    section = None
    subsection = None
    if candidate.primary_events:
        first = candidate.primary_events[0]
        section = getattr(first, "section", None)
        subsection = getattr(first, "subsection", None)

    metadata = dict(strip_raw_visual_blobs_from_metadata(candidate.metadata))
    metadata["source_sections"] = prov.get("source_sections", [])
    metadata["source_subsections"] = prov.get("source_subsections", [])
    metadata["source_chunk_indexes"] = prov.get("source_chunk_indexes", [])

    conditions = collect_condition_texts(candidate)
    invalidation = collect_invalidation_texts(candidate)
    exceptions = collect_exception_texts(candidate)

    return RuleCard(
        rule_id=rule_id,
        lesson_id=candidate.lesson_id,
        lesson_title=None,
        section=section,
        subsection=subsection,
        source_event_ids=source_event_ids,
        concept=concept,
        subconcept=candidate.subconcept,
        title=candidate.title_hint,
        rule_text=rule_text,
        conditions=conditions,
        context=[],
        invalidation=invalidation,
        exceptions=exceptions,
        comparisons=collect_comparison_texts(candidate),
        algorithm_notes=collect_algorithm_notes(candidate),
        visual_summary=summarize_evidence_for_rule_card(candidate.linked_evidence, cfg),
        evidence_refs=evidence_refs,
        confidence=conf_label,
        confidence_score=conf_score,
        positive_example_refs=example_map["positive_example_refs"],
        negative_example_refs=example_map["negative_example_refs"],
        ambiguous_example_refs=example_map["ambiguous_example_refs"],
        metadata=metadata,
        source_language="ru",
        concept_id=canonicalize_concept(concept),
        subconcept_id=canonicalize_subconcept(candidate.subconcept),
        condition_ids=[canonicalize_short_statement("condition", t) for t in conditions],
        invalidation_ids=[canonicalize_short_statement("invalidation", t) for t in invalidation],
        exception_ids=[canonicalize_short_statement("exception", t) for t in exceptions],
        rule_type=classify_rule_type(dominant_event_type_for_policy),
        rule_text_ru=rule_text if rule_text else None,
        concept_label_ru=concept if concept else None,
        subconcept_label_ru=candidate.subconcept if candidate.subconcept else None,
        support_basis=s_basis,
        evidence_requirement=ev_req,
        teaching_mode=teaching_mode,
        visual_support_level=v_level,
        transcript_support_level=t_level,
        transcript_support_score=round(ts_score, 4),
        visual_support_score=round(vs_score, 4),
        has_visual_evidence=bool(candidate.linked_evidence),
        transcript_anchor_count=anchor_count,
        transcript_repetition_count=repetition_count,
    )


# ----- Build and save -----


def build_rule_cards(
    knowledge_collection: KnowledgeEventCollection,
    evidence_index: EvidenceIndex,
    *,
    attach_threshold: float = ATTACH_THRESHOLD,
    compaction_cfg: VisualCompactionConfig | None = None,
) -> tuple[RuleCardCollection, list[dict]]:
    """Group → attach evidence → merge duplicates → split → convert to RuleCards; return collection and debug rows."""
    events = list(knowledge_collection.events)
    candidates, group_debug = group_events_into_rule_candidates(events, evidence_index, threshold=attach_threshold)
    candidates = attach_evidence_to_candidates(candidates, evidence_index)
    candidates = attach_evidence_by_proximity(candidates, evidence_index)
    all_candidates: list[RuleCandidate] = []
    for c in candidates:
        c.primary_events = merge_duplicate_primary_events(c.primary_events)
        for split_c in split_overbroad_candidate(c):
            all_candidates.append(split_c)
    cards: list[RuleCard] = []
    debug_rows: list[dict] = []
    for i, cand in enumerate(all_candidates):
        card = candidate_to_rule_card(cand, i, compaction_cfg=compaction_cfg)
        warnings = validate_rule_card(card)
        if warnings:
            debug_rows.append({
                "stage": "rule_reducer",
                "entity_type": "rule_card",
                "entity_id": card.rule_id,
                "rule_id": card.rule_id,
                "reason_rejected": warnings,
                "source_event_ids": list(card.source_event_ids or []),
                "concept": cand.concept,
                "subconcept": cand.subconcept,
                "provenance_warnings": validate_rule_card_provenance(card),
            })
            continue
        cards.append(card)
        debug_rows.append(
            {
                "candidate_id": cand.candidate_id,
                "concept": cand.concept,
                "subconcept": cand.subconcept,
                "source_event_ids": [e.event_id for e in cand.primary_events + cand.condition_events + cand.invalidation_events],
                "linked_evidence_ids": [r.evidence_id for r in cand.linked_evidence],
                "canonical_rule_text": card.rule_text,
                "conditions": card.conditions,
                "invalidation": card.invalidation,
                "split_applied": getattr(cand, "from_split", False),
                "confidence_score": card.confidence_score,
                "provenance_warnings": validate_rule_card_provenance(card),
            }
        )
    collection = RuleCardCollection(
        schema_version="1.0",
        lesson_id=knowledge_collection.lesson_id,
        rules=cards,
    )
    return (collection, debug_rows)


def save_rule_cards(collection: RuleCardCollection, output_path: Path) -> None:
    """Write RuleCardCollection to JSON."""
    assert_no_raw_visual_blob_leak(collection.model_dump())
    atomic_write_text(output_path, collection.model_dump_json(indent=2), encoding="utf-8")


def save_rule_debug(debug_rows: list[dict], output_path: Path) -> None:
    """Write debug rows to JSON."""
    atomic_write_json(output_path, debug_rows)
