"""Backfill transcript-first support fields on existing lesson artifacts.

Light-touch approach: only patches new fields on existing JSONs.
Does NOT re-run evidence linking or rule grouping, preserving all
existing associations (linked_rule_ids, evidence_refs, etc.).
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

from pipeline.component2.knowledge_builder import (
    AdaptedChunk,
    adapt_chunks,
    load_chunks_json,
    score_transcript_support,
    score_visual_support,
    score_event_confidence,
)
from pipeline.component2.support_policy import (
    classify_evidence_requirement,
    classify_support_basis,
    classify_teaching_mode,
    classify_transcript_support_level,
    classify_visual_support_level,
)
from pipeline.component2.evidence_linker import (
    classify_evidence_strength,
    classify_evidence_role_detail,
    VisualEvidenceCandidate,
)
from pipeline.component2.rule_reducer import (
    _aggregate_transcript_support,
    _aggregate_visual_support,
    score_rule_candidate_confidence,
    RuleCandidate,
)
from pipeline.component2.exporters import (
    build_export_context,
    render_review_markdown_deterministic,
    render_rag_markdown_deterministic,
    save_review_markdown,
    save_rag_markdown,
)
from pipeline.schemas import (
    KnowledgeEvent,
    KnowledgeEventCollection,
    RuleCard,
    RuleCardCollection,
    EvidenceRef,
    EvidenceIndex,
)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _save_json(data, path: Path):
    path.write_text(
        data.model_dump_json(indent=2, exclude_none=False)
        if hasattr(data, "model_dump_json")
        else json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def backfill_single_event(ev: KnowledgeEvent, chunk: AdaptedChunk | None) -> KnowledgeEvent:
    anchor_density = ev.anchor_density or 0.0
    anchor_line_count = ev.anchor_line_count or 0
    ts_conf = ev.timestamp_confidence or "chunk"

    ts_score = score_transcript_support(anchor_density, anchor_line_count, ts_conf, ev.raw_text)
    vs_score = score_visual_support(chunk, ev.event_type) if chunk else 0.0

    linked_visual_count = len(chunk.visual_events) if chunk else 0
    first_example_type = None
    if chunk and chunk.candidate_example_types:
        first_example_type = chunk.candidate_example_types[0]

    tm = classify_teaching_mode(ev.event_type, ev.raw_text, linked_visual_count=linked_visual_count, visual_example_type=first_example_type)
    ev_req = classify_evidence_requirement(ev.event_type, tm, ev.concept, ev.subconcept)
    s_basis = classify_support_basis(ts_score, vs_score, tm)
    t_level = classify_transcript_support_level(ts_score)
    v_level = classify_visual_support_level(vs_score, example_role=first_example_type)

    return ev.model_copy(update={
        "support_basis": s_basis,
        "evidence_requirement": ev_req,
        "teaching_mode": tm,
        "visual_support_level": v_level,
        "transcript_support_level": t_level,
        "transcript_support_score": round(ts_score, 4),
        "visual_support_score": round(vs_score, 4),
    })


def backfill_single_rule(rule: RuleCard, events_by_id: dict[str, KnowledgeEvent]) -> RuleCard:
    source_events = [events_by_id[eid] for eid in (rule.source_event_ids or []) if eid in events_by_id]
    if not source_events:
        return rule

    ts_scores = [e.transcript_support_score for e in source_events if e.transcript_support_score is not None]
    vs_scores = [e.visual_support_score for e in source_events if e.visual_support_score is not None]
    ts_score = max(ts_scores) if ts_scores else 0.5
    vs_score = max(vs_scores) if vs_scores else 0.0

    anchor_count = sum(e.anchor_line_count or 0 for e in source_events)
    line_conf_count = sum(1 for e in source_events if e.timestamp_confidence == "line")

    primary_event = source_events[0]
    ev_type = primary_event.event_type
    raw_text = primary_event.raw_text or ""
    linked_visual_count = sum(1 for e in source_events if (e.visual_support_score or 0) > 0.1)
    first_example_type = None
    for e in source_events:
        if e.visual_support_level and e.visual_support_level not in ("none", "ambiguous"):
            first_example_type = e.visual_support_level
            break

    tm = classify_teaching_mode(ev_type, raw_text, linked_visual_count=linked_visual_count, visual_example_type=first_example_type)
    ev_req = classify_evidence_requirement(ev_type, tm, rule.concept, rule.subconcept)
    s_basis = classify_support_basis(ts_score, vs_score, tm)
    t_level = classify_transcript_support_level(ts_score)
    v_level = classify_visual_support_level(vs_score, example_role=first_example_type)

    has_visual = bool(rule.evidence_refs) and len(rule.evidence_refs) > 0

    return rule.model_copy(update={
        "support_basis": s_basis,
        "evidence_requirement": ev_req,
        "teaching_mode": tm,
        "visual_support_level": v_level,
        "transcript_support_level": t_level,
        "transcript_support_score": round(ts_score, 4),
        "visual_support_score": round(vs_score, 4),
        "has_visual_evidence": has_visual,
        "transcript_anchor_count": anchor_count,
        "transcript_repetition_count": line_conf_count,
    })


def backfill_single_evidence_ref(ref: EvidenceRef, events: list[KnowledgeEvent]) -> EvidenceRef:
    summary = ref.compact_visual_summary or ref.visual_summary or ""

    vc = VisualEvidenceCandidate(
        candidate_id=ref.evidence_id,
        lesson_id=ref.lesson_id,
        chunk_index=0,
        timestamp_start=0.0,
        timestamp_end=0.0,
        compact_visual_summary=summary,
    )

    linked_events = [e for e in events if e.event_id in (ref.source_event_ids or [])]
    strength = classify_evidence_strength(vc, linked_events)
    role = ref.example_role or "illustration"
    role_detail = classify_evidence_role_detail(role, vc, linked_events)

    return ref.model_copy(update={
        "evidence_strength": strength,
        "evidence_role_detail": role_detail,
    })


def rebuild_lesson(lesson_dir: Path, lesson_name: str) -> dict:
    intermediate = lesson_dir / "output_intermediate"
    chunks_path = intermediate / f"{lesson_name}.chunks.json"
    ke_path = intermediate / f"{lesson_name}.knowledge_events.json"
    rc_path = intermediate / f"{lesson_name}.rule_cards.json"
    ei_path = intermediate / f"{lesson_name}.evidence_index.json"

    if not ke_path.exists():
        return {"error": f"Missing {ke_path}"}

    raw_chunks = load_chunks_json(chunks_path) if chunks_path.exists() else []
    ke_data = _load_json(ke_path)
    lesson_id = ke_data.get("lesson_id", lesson_name)
    adapted = adapt_chunks(raw_chunks, lesson_id=lesson_id, lesson_title=lesson_name) if raw_chunks else []
    chunk_by_index: dict[int, AdaptedChunk] = {c.chunk_index: c for c in adapted}

    ke_col = KnowledgeEventCollection.model_validate(ke_data)
    updated_events: list[KnowledgeEvent] = []
    for ev in ke_col.events:
        ci = (ev.metadata or {}).get("chunk_index")
        chunk = chunk_by_index.get(ci) if ci is not None else None
        updated_events.append(backfill_single_event(ev, chunk))
    ke_col = ke_col.model_copy(update={"events": updated_events})
    _save_json(ke_col, ke_path)
    logger.info("Backfilled %d events in %s", len(updated_events), ke_path.name)

    events_by_id = {e.event_id: e for e in ke_col.events}

    if ei_path.exists():
        ei_col = EvidenceIndex.model_validate(_load_json(ei_path))
        updated_refs = [backfill_single_evidence_ref(ref, list(ke_col.events)) for ref in ei_col.evidence_refs]
        ei_col = ei_col.model_copy(update={"evidence_refs": updated_refs})
        _save_json(ei_col, ei_path)
        logger.info("Backfilled %d evidence refs in %s", len(updated_refs), ei_path.name)
    else:
        ei_col = EvidenceIndex(lesson_id=lesson_id, evidence_refs=[])

    if rc_path.exists():
        rc_col = RuleCardCollection.model_validate(_load_json(rc_path))
        updated_rules = [backfill_single_rule(r, events_by_id) for r in rc_col.rules]
        rc_col = rc_col.model_copy(update={"rules": updated_rules})
        _save_json(rc_col, rc_path)
        logger.info("Backfilled %d rules in %s", len(updated_rules), rc_path.name)
    else:
        rc_col = RuleCardCollection(lesson_id=lesson_id, rules=[])

    ctx = build_export_context(rc_col, ei_col, knowledge_events=ke_col, lesson_title=lesson_name)
    review_md = render_review_markdown_deterministic(ctx)
    rag_md = render_rag_markdown_deterministic(ctx)

    review_dir = lesson_dir / "output_review"
    review_dir.mkdir(parents=True, exist_ok=True)
    save_review_markdown(review_md, review_dir / f"{lesson_name}.review_markdown.md")

    rag_dir = lesson_dir / "output_rag_ready"
    rag_dir.mkdir(parents=True, exist_ok=True)
    save_rag_markdown(rag_md, rag_dir / f"{lesson_name}.md")
    logger.info("Rebuilt exports for %s", lesson_name)

    sb_counts: dict[str, int] = {}
    for r in rc_col.rules:
        sb = r.support_basis or "null"
        sb_counts[sb] = sb_counts.get(sb, 0) + 1

    return {
        "lesson": lesson_name,
        "events": len(ke_col.events),
        "evidence_refs": len(ei_col.evidence_refs),
        "rules": len(rc_col.rules),
        "support_basis_distribution": sb_counts,
    }


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    data_root = Path("data")

    lessons = [
        (data_root / "Lesson 2. Levels part 1", "Lesson 2. Levels part 1"),
        (data_root / "2025-09-29-sviatoslav-chornyi", "2025-09-29-sviatoslav-chornyi"),
    ]

    results = []
    for lesson_dir, lesson_name in lessons:
        logger.info("=== Backfilling %s ===", lesson_name)
        result = rebuild_lesson(lesson_dir, lesson_name)
        results.append(result)
        logger.info("Result: %s", json.dumps(result, ensure_ascii=False, indent=2))

    print("\n=== BACKFILL SUMMARY ===")
    for r in results:
        print(json.dumps(r, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
