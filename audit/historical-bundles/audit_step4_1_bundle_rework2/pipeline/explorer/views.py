"""Deterministic doc-to-view mappers for the explorer backend."""

from __future__ import annotations

from collections import Counter
from typing import Any

from pipeline.explorer.contracts import (
    BrowserResultCard,
    ConceptDetailResponse,
    ConceptNeighbor,
    EvidenceDetailResponse,
    LessonDetailResponse,
    RuleDetailResponse,
)


def _first_nonempty(*values: str | None) -> str:
    for value in values:
        if value and value.strip():
            return value.strip()
    return ""


def _concept_ids(doc: dict[str, Any]) -> list[str]:
    concept_ids = list(doc.get("canonical_concept_ids") or [])
    for concept_id in doc.get("canonical_subconcept_ids") or []:
        if concept_id not in concept_ids:
            concept_ids.append(concept_id)
    return concept_ids


def _result_snippet(doc: dict[str, Any]) -> str:
    unit_type = doc.get("unit_type")
    if unit_type == "rule_card":
        return _first_nonempty(doc.get("rule_text_ru"), doc.get("rule_text"), doc.get("short_text"))
    if unit_type == "knowledge_event":
        return _first_nonempty(doc.get("normalized_text_ru"), doc.get("normalized_text"), doc.get("short_text"))
    if unit_type == "evidence_ref":
        return _first_nonempty(
            doc.get("visual_summary"),
            (doc.get("metadata") or {}).get("summary_primary"),
            doc.get("short_text"),
        )
    return _first_nonempty(doc.get("short_text"), doc.get("text"), doc.get("title"))


def _result_subtitle(doc: dict[str, Any]) -> str:
    unit_type = doc.get("unit_type")
    if unit_type == "rule_card":
        return _first_nonempty(doc.get("concept"), doc.get("lesson_id"))
    if unit_type == "knowledge_event":
        return _first_nonempty(doc.get("event_type"), doc.get("concept"), doc.get("lesson_id"))
    if unit_type == "evidence_ref":
        role_detail = (doc.get("metadata") or {}).get("evidence_role_detail")
        return _first_nonempty(role_detail, doc.get("lesson_id"))
    return _first_nonempty(doc.get("lesson_id"))


def build_result_card(
    doc: dict[str, Any],
    *,
    score: float | None = None,
    why_retrieved: list[str] | None = None,
) -> BrowserResultCard:
    doc_id = str(doc.get("doc_id") or "")
    source_rule_ids = {str(rule_id) for rule_id in doc.get("source_rule_ids") or []}
    source_rule_ids.discard(doc_id)
    return BrowserResultCard(
        doc_id=doc_id,
        unit_type=doc.get("unit_type", ""),
        lesson_id=doc.get("lesson_id"),
        title=_first_nonempty(doc.get("title"), doc_id),
        subtitle=_result_subtitle(doc),
        snippet=_result_snippet(doc),
        concept_ids=_concept_ids(doc),
        support_basis=doc.get("support_basis"),
        evidence_requirement=doc.get("evidence_requirement"),
        teaching_mode=doc.get("teaching_mode"),
        confidence_score=doc.get("confidence_score"),
        timestamps=list(doc.get("timestamps") or []),
        evidence_count=len(doc.get("evidence_ids") or []),
        related_rule_count=len(source_rule_ids),
        related_event_count=len(doc.get("source_event_ids") or []),
        score=score,
        why_retrieved=list(why_retrieved or []),
    )


def build_rule_detail(
    doc: dict[str, Any],
    *,
    evidence_docs: list[dict[str, Any]],
    source_events: list[dict[str, Any]],
    related_rules: list[dict[str, Any]],
) -> RuleDetailResponse:
    return RuleDetailResponse(
        doc_id=str(doc.get("doc_id") or ""),
        lesson_id=str(doc.get("lesson_id") or ""),
        lesson_slug=doc.get("lesson_slug"),
        title=_first_nonempty(doc.get("title"), str(doc.get("doc_id") or "")),
        concept=doc.get("concept"),
        subconcept=doc.get("subconcept"),
        canonical_concept_ids=_concept_ids(doc),
        rule_text=doc.get("rule_text") or "",
        rule_text_ru=doc.get("rule_text_ru") or "",
        conditions=list(doc.get("conditions") or []),
        invalidation=list(doc.get("invalidation") or []),
        exceptions=list(doc.get("exceptions") or []),
        comparisons=list(doc.get("comparisons") or []),
        visual_summary=doc.get("visual_summary"),
        support_basis=doc.get("support_basis"),
        evidence_requirement=doc.get("evidence_requirement"),
        teaching_mode=doc.get("teaching_mode"),
        confidence_score=doc.get("confidence_score"),
        timestamps=list(doc.get("timestamps") or []),
        evidence_refs=[build_result_card(candidate) for candidate in evidence_docs],
        source_events=[build_result_card(candidate) for candidate in source_events],
        related_rules=[build_result_card(candidate) for candidate in related_rules],
    )


def build_evidence_detail(
    doc: dict[str, Any],
    *,
    source_rules: list[dict[str, Any]],
    source_events: list[dict[str, Any]],
) -> EvidenceDetailResponse:
    metadata = doc.get("metadata") or {}
    return EvidenceDetailResponse(
        doc_id=str(doc.get("doc_id") or ""),
        lesson_id=str(doc.get("lesson_id") or ""),
        title=_first_nonempty(doc.get("title"), str(doc.get("doc_id") or "")),
        snippet=_result_snippet(doc),
        timestamps=list(doc.get("timestamps") or []),
        support_basis=doc.get("support_basis"),
        confidence_score=doc.get("confidence_score"),
        evidence_strength=metadata.get("evidence_strength"),
        evidence_role_detail=metadata.get("evidence_role_detail"),
        visual_summary=doc.get("visual_summary"),
        source_rules=[build_result_card(candidate) for candidate in source_rules],
        source_events=[build_result_card(candidate) for candidate in source_events],
    )


def build_concept_detail(
    concept_id: str,
    *,
    aliases: list[str],
    neighbors: list[dict[str, Any]],
    top_rules: list[dict[str, Any]],
    top_events: list[dict[str, Any]],
    lessons: list[str],
    evidence_count: int = 0,
    rule_count: int = 0,
    event_count: int = 0,
) -> ConceptDetailResponse:
    return ConceptDetailResponse(
        concept_id=concept_id,
        aliases=list(aliases),
        top_rules=[build_result_card(candidate) for candidate in top_rules],
        top_events=[build_result_card(candidate) for candidate in top_events],
        lessons=list(lessons),
        neighbors=[ConceptNeighbor(**neighbor) for neighbor in neighbors],
        rule_count=rule_count,
        event_count=event_count,
        evidence_count=evidence_count,
    )


def build_lesson_detail(
    lesson_id: str,
    lesson_meta: dict[str, Any] | None,
    docs: list[dict[str, Any]],
) -> LessonDetailResponse:
    support_basis_counts = Counter(
        str(doc.get("support_basis"))
        for doc in docs
        if doc.get("support_basis")
    )
    concept_counts = Counter()
    for doc in docs:
        for concept_id in _concept_ids(doc):
            concept_counts[concept_id] += 1

    top_rules = [
        build_result_card(doc)
        for doc in docs
        if doc.get("unit_type") == "rule_card"
    ][:5]
    top_evidence = [
        build_result_card(doc)
        for doc in docs
        if doc.get("unit_type") == "evidence_ref"
    ][:5]

    return LessonDetailResponse(
        lesson_id=lesson_id,
        lesson_title=(lesson_meta or {}).get("lesson_title") or (lesson_meta or {}).get("lesson_slug"),
        rule_count=sum(1 for doc in docs if doc.get("unit_type") == "rule_card"),
        event_count=sum(1 for doc in docs if doc.get("unit_type") == "knowledge_event"),
        evidence_count=sum(1 for doc in docs if doc.get("unit_type") == "evidence_ref"),
        concept_count=len(concept_counts),
        support_basis_counts=dict(sorted(support_basis_counts.items())),
        top_concepts=[
            concept_id
            for concept_id, _count in sorted(concept_counts.items(), key=lambda item: (-item[1], item[0]))[:10]
        ],
        top_rules=top_rules,
        top_evidence=top_evidence,
    )
