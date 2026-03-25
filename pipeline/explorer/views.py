"""Deterministic doc-to-view mappers for the explorer backend."""

from __future__ import annotations

from collections import Counter
from typing import Any

from pipeline.explorer.contracts import (
    BrowserResultCard,
    ComparisonDifference,
    ComparisonSummary,
    ConceptDetailResponse,
    ConceptLessonListResponse,
    ConceptNeighbor,
    ConceptRuleListResponse,
    EvidenceDetailResponse,
    LessonCompareItem,
    LessonCompareResponse,
    LessonDetailResponse,
    RelatedRuleItem,
    RelatedRulesResponse,
    RuleCompareItem,
    RuleCompareResponse,
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


def _frame_ids_from_evidence_docs(evidence_docs: list[dict[str, Any]]) -> list[str]:
    return sorted(
        {
            str(frame_id)
            for evidence_doc in evidence_docs
            for frame_id in (evidence_doc.get("frame_ids") or [])
            if frame_id
        }
    )


def _lesson_unit_type_counts(docs: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(str(doc.get("unit_type") or "") for doc in docs if doc.get("unit_type"))
    return dict(sorted(counts.items()))


def _normalize_text(value: str | None) -> str:
    return " ".join((value or "").strip().lower().split())


def _rule_compare_item(
    doc: dict[str, Any],
    *,
    related_rules: list[dict[str, Any]] | None = None,
) -> RuleCompareItem:
    evidence_ids = set(str(evidence_id) for evidence_id in doc.get("evidence_ids") or [])
    source_rule_ids = {str(rule_id) for rule_id in doc.get("source_rule_ids") or []}
    source_rule_ids.discard(str(doc.get("doc_id") or ""))
    return RuleCompareItem(
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
        frame_ids=list(doc.get("frame_ids") or []),
        support_basis=doc.get("support_basis"),
        evidence_requirement=doc.get("evidence_requirement"),
        teaching_mode=doc.get("teaching_mode"),
        confidence_score=doc.get("confidence_score"),
        timestamps=list(doc.get("timestamps") or []),
        linked_evidence_count=len(evidence_ids),
        linked_source_event_count=len(doc.get("source_event_ids") or []),
        related_rule_count=len(source_rule_ids) + len(list(related_rules or [])),
        related_rules=[build_result_card(candidate) for candidate in related_rules or []],
    )


def _build_comparison_summary(items: list[RuleCompareItem]) -> ComparisonSummary:
    if not items:
        return ComparisonSummary()

    concept_sets = [set(item.canonical_concept_ids) for item in items]
    shared_concepts = sorted(set.intersection(*concept_sets)) if concept_sets else []

    lesson_values = [item.lesson_id for item in items if item.lesson_id]
    shared_lessons = sorted({lesson_values[0]}) if lesson_values and len(set(lesson_values)) == 1 else []

    support_values = [item.support_basis for item in items if item.support_basis]
    shared_support_basis = (
        sorted({support_values[0]})
        if support_values and len(support_values) == len(items) and len(set(support_values)) == 1
        else []
    )

    field_map: dict[str, list[str]] = {
        "lesson_id": [item.lesson_id for item in items],
        "concept": [item.concept or "" for item in items],
        "subconcept": [item.subconcept or "" for item in items],
        "support_basis": [item.support_basis or "" for item in items],
        "evidence_requirement": [item.evidence_requirement or "" for item in items],
        "teaching_mode": [item.teaching_mode or "" for item in items],
        "conditions": [" | ".join(item.conditions) for item in items],
        "invalidation": [" | ".join(item.invalidation) for item in items],
        "exceptions": [" | ".join(item.exceptions) for item in items],
    }
    differences = [
        ComparisonDifference(field=field_name, labels=labels)
        for field_name, labels in field_map.items()
        if len(set(labels)) > 1
    ]

    possible_relationships: list[str] = []
    if shared_concepts:
        possible_relationships.append("same_concept")
    if shared_lessons:
        possible_relationships.append("same_lesson")
    if shared_support_basis:
        possible_relationships.append("same_support_basis")

    normalized_texts = {_normalize_text(item.rule_text_ru or item.rule_text) for item in items}
    if len(normalized_texts) == 1:
        possible_relationships.append("possible_duplicate")
    elif shared_concepts and len({item.lesson_id for item in items}) > 1:
        possible_relationships.append("cross_lesson_variant")
    elif shared_concepts:
        possible_relationships.append("same_lesson_sibling")
    else:
        possible_relationships.append("contrastive")

    return ComparisonSummary(
        shared_concepts=shared_concepts,
        shared_lessons=shared_lessons,
        shared_support_basis=shared_support_basis,
        differences=differences,
        possible_relationships=possible_relationships,
    )


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
        frame_ids=_frame_ids_from_evidence_docs(evidence_docs),
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
        frame_ids=list(doc.get("frame_ids") or []),
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


def build_rule_compare_response(
    rule_docs: list[dict[str, Any]],
    *,
    related_context: dict[str, list[dict[str, Any]]] | None = None,
) -> RuleCompareResponse:
    items = [
        _rule_compare_item(
            doc,
            related_rules=(related_context or {}).get(str(doc.get("doc_id") or ""), []),
        )
        for doc in rule_docs
    ]
    return RuleCompareResponse(rules=items, summary=_build_comparison_summary(items))


def build_lesson_compare_response(
    lesson_metas: dict[str, dict[str, Any] | None],
    lesson_docs_map: dict[str, list[dict[str, Any]]],
    overlap: dict[str, Any] | None = None,
) -> LessonCompareResponse:
    lesson_items: list[LessonCompareItem] = []
    per_lesson_concepts: dict[str, set[str]] = {}
    for lesson_id, docs in lesson_docs_map.items():
        detail = build_lesson_detail(lesson_id, lesson_metas.get(lesson_id), docs)
        lesson_items.append(
            LessonCompareItem(
                lesson_id=detail.lesson_id,
                lesson_title=detail.lesson_title,
                unit_type_counts=_lesson_unit_type_counts(docs),
                support_basis_counts=detail.support_basis_counts,
                top_concepts=detail.top_concepts,
                top_rules=detail.top_rules,
                top_evidence=detail.top_evidence,
                rule_count=detail.rule_count,
                event_count=detail.event_count,
                evidence_count=detail.evidence_count,
                concept_count=detail.concept_count,
            )
        )
        per_lesson_concepts[lesson_id] = set(detail.top_concepts)
        for doc in docs:
            for concept_id in _concept_ids(doc):
                per_lesson_concepts[lesson_id].add(concept_id)

    shared_concepts = sorted(set.intersection(*per_lesson_concepts.values())) if per_lesson_concepts else []
    unique_concepts = {
        lesson_id: sorted(
            concept_ids - set().union(*(other for other_lesson_id, other in per_lesson_concepts.items() if other_lesson_id != lesson_id))
        )
        for lesson_id, concept_ids in per_lesson_concepts.items()
    }
    shared_rule_families = sorted((overlap or {}).get("rule_families", []))
    return LessonCompareResponse(
        lessons=lesson_items,
        shared_concepts=shared_concepts,
        unique_concepts=unique_concepts,
        shared_rule_families=shared_rule_families,
    )


def build_related_rules_response(
    source_doc_id: str,
    grouped_docs: dict[str, list[dict[str, Any]]],
) -> RelatedRulesResponse:
    groups = {
        reason: [
            RelatedRuleItem(
                card=build_result_card(doc),
                relation_reason=reason,
            )
            for doc in docs
        ]
        for reason, docs in grouped_docs.items()
        if docs
    }
    return RelatedRulesResponse(source_doc_id=source_doc_id, groups=groups)


def build_concept_rule_list(concept_id: str, rule_docs: list[dict[str, Any]]) -> ConceptRuleListResponse:
    return ConceptRuleListResponse(
        concept_id=concept_id,
        rules=[build_result_card(doc) for doc in rule_docs],
        total=len(rule_docs),
    )


def build_concept_lesson_list(
    concept_id: str,
    lesson_ids: list[str],
    lesson_metas: dict[str, dict[str, Any] | None],
    lesson_docs_map: dict[str, list[dict[str, Any]]],
) -> ConceptLessonListResponse:
    lesson_details = [
        build_lesson_detail(lesson_id, lesson_metas.get(lesson_id), lesson_docs_map.get(lesson_id, []))
        for lesson_id in lesson_ids
    ]
    return ConceptLessonListResponse(
        concept_id=concept_id,
        lessons=lesson_ids,
        lesson_details=lesson_details,
        total=len(lesson_ids),
    )
