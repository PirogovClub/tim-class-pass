"""Orchestration layer for the Step 4.1 explorer backend."""

from __future__ import annotations

from collections import Counter
from typing import Any

from pipeline.explorer.contracts import (
    BrowserResultCard,
    BrowserSearchFilters,
    BrowserSearchRequest,
    BrowserSearchResponse,
    ConceptDetailResponse,
    ConceptLessonListResponse,
    ConceptNeighbor,
    ConceptRuleListResponse,
    EvidenceDetailResponse,
    EventDetailResponse,
    LessonCompareResponse,
    LessonDetailResponse,
    RelatedRulesResponse,
    RuleCompareResponse,
    RuleDetailResponse,
    UnitCompareItemRef,
    UnitCompareResponse,
)
from pipeline.explorer.loader import ExplorerRepository, _concept_keys
from pipeline.explorer.views import (
    build_concept_detail,
    build_concept_lesson_list,
    build_concept_rule_list,
    build_event_detail,
    build_evidence_detail,
    build_lesson_compare_response,
    build_lesson_detail,
    build_related_rules_response,
    build_result_card,
    build_rule_compare_response,
    build_rule_detail,
    build_unit_compare_response,
)
from pipeline.rag.query_intents import analyze_query_intents
from pipeline.rag.retriever import HybridRetriever

_BROWSE_ORDER: dict[str, int] = {
    "rule_card": 0,
    "knowledge_event": 1,
    "evidence_ref": 2,
    "concept_node": 3,
    "concept_relation": 4,
}
_FACET_QUERY_CANDIDATE_LIMIT = 2000


def _doc_confidence(doc: dict[str, Any]) -> float:
    return float(doc.get("confidence_score") or 0.0)


def _doc_matches_concepts(doc: dict[str, Any], concept_ids: list[str]) -> bool:
    if not concept_ids:
        return True
    doc_concepts = {
        key
        for concept_id in (doc.get("canonical_concept_ids") or []) + (doc.get("canonical_subconcept_ids") or [])
        for key in _concept_keys(str(concept_id))
    }
    query_concepts = {key for concept_id in concept_ids for key in _concept_keys(str(concept_id))}
    if doc_concepts & query_concepts:
        return True

    rule_ids = {str(rule_id) for rule_id in doc.get("source_rule_ids") or []}
    if not rule_ids:
        return False
    return any(any(key in rule_id.lower() for key in query_concepts) for rule_id in rule_ids)


class ExplorerService:
    def __init__(self, repo: ExplorerRepository, retriever: HybridRetriever) -> None:
        self._repo = repo
        self._retriever = retriever

    @property
    def doc_count(self) -> int:
        return self._repo.doc_count

    @property
    def corpus_contract_version(self) -> str:
        return self._repo.corpus_contract_version

    def _matches_filters(self, doc: dict[str, Any], filters: BrowserSearchFilters) -> bool:
        if filters.unit_types and doc.get("unit_type") not in filters.unit_types:
            return False
        if filters.lesson_ids and doc.get("lesson_id") not in filters.lesson_ids:
            return False
        if filters.support_basis and doc.get("support_basis") not in filters.support_basis:
            return False
        if filters.evidence_requirement and doc.get("evidence_requirement") not in filters.evidence_requirement:
            return False
        if filters.teaching_mode and doc.get("teaching_mode") not in filters.teaching_mode:
            return False
        if filters.min_confidence_score is not None and _doc_confidence(doc) < filters.min_confidence_score:
            return False
        if not _doc_matches_concepts(doc, filters.concept_ids):
            return False
        return True

    def _sort_browse_docs(self, docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return sorted(
            docs,
            key=lambda doc: (
                _BROWSE_ORDER.get(str(doc.get("unit_type") or ""), 99),
                -_doc_confidence(doc),
                str(doc.get("lesson_id") or ""),
                str(doc.get("doc_id") or ""),
            ),
        )

    def _compute_facets(self, docs: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
        by_unit = Counter()
        by_lesson = Counter()
        by_concept = Counter()
        by_support_basis = Counter()
        by_evidence_requirement = Counter()
        by_teaching_mode = Counter()

        for doc in docs:
            unit_type = str(doc.get("unit_type") or "")
            if unit_type:
                by_unit[unit_type] += 1
            lesson_id = str(doc.get("lesson_id") or "")
            if lesson_id:
                by_lesson[lesson_id] += 1
            for concept_id in (doc.get("canonical_concept_ids") or []) + (doc.get("canonical_subconcept_ids") or []):
                by_concept[str(concept_id)] += 1
            support_basis = str(doc.get("support_basis") or "")
            if support_basis:
                by_support_basis[support_basis] += 1
            evidence_requirement = str(doc.get("evidence_requirement") or "")
            if evidence_requirement:
                by_evidence_requirement[evidence_requirement] += 1
            teaching_mode = str(doc.get("teaching_mode") or "")
            if teaching_mode:
                by_teaching_mode[teaching_mode] += 1

        return {
            "by_unit_type": dict(sorted(by_unit.items())),
            "by_lesson": dict(sorted(by_lesson.items())),
            "by_concept": dict(sorted(by_concept.items())),
            "by_support_basis": dict(sorted(by_support_basis.items())),
            "by_evidence_requirement": dict(sorted(by_evidence_requirement.items())),
            "by_teaching_mode": dict(sorted(by_teaching_mode.items())),
        }

    def _group_cards(self, cards: list[BrowserResultCard]) -> dict[str, list[BrowserResultCard]]:
        groups: dict[str, list[BrowserResultCard]] = {
            "rules": [],
            "events": [],
            "evidence": [],
            "concepts": [],
            "relations": [],
        }
        for card in cards:
            if card.unit_type == "rule_card":
                groups["rules"].append(card)
            elif card.unit_type == "knowledge_event":
                groups["events"].append(card)
            elif card.unit_type == "evidence_ref":
                groups["evidence"].append(card)
            elif card.unit_type == "concept_node":
                groups["concepts"].append(card)
            elif card.unit_type == "concept_relation":
                groups["relations"].append(card)
        return {key: value for key, value in groups.items() if value}

    def _search_candidate_top_k(self, top_k: int) -> int:
        return max(top_k, min(top_k * 4, 100))

    def _facet_candidate_top_k(self) -> int:
        return max(100, min(self._repo.doc_count, _FACET_QUERY_CANDIDATE_LIMIT))

    def _postprocess_query_hit_rows(self, query: str, hit_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        iq = analyze_query_intents(query.strip().lower())
        if iq.mentions_timeframe and iq.prefers_explicit_rules:
            return sorted(
                hit_rows,
                key=lambda hit: (
                    0 if hit["resolved_doc"].get("unit_type") == "rule_card" else 1,
                    -float(hit.get("score") or 0.0),
                ),
            )
        return hit_rows

    def _validate_compare_ids(self, ids: list[str], *, label: str) -> list[str]:
        cleaned = [str(doc_id) for doc_id in ids if str(doc_id).strip()]
        if len(cleaned) < 2:
            raise ValueError(f"{label} comparison requires at least two ids")
        if len(cleaned) > 4:
            raise ValueError(f"{label} comparison supports at most four ids")
        if len(set(cleaned)) != len(cleaned):
            raise ValueError(f"{label} comparison ids must be unique")
        return cleaned

    def _query_hit_rows(
        self,
        query: str,
        filters: BrowserSearchFilters,
        *,
        candidate_top_k: int,
    ) -> list[dict[str, Any]]:
        result = self._retriever.search(
            query=query,
            top_k=candidate_top_k,
            unit_types=filters.unit_types or None,
            lesson_ids=filters.lesson_ids or None,
            concept_ids=filters.concept_ids or None,
            min_confidence=filters.min_confidence_score,
        )
        return [
            hit
            for hit in self._postprocess_query_hit_rows(query, result["top_hits"])
            if self._matches_filters(hit["resolved_doc"], filters)
        ]

    def _filtered_docs(
        self,
        query: str,
        filters: BrowserSearchFilters,
        *,
        candidate_top_k: int | None = None,
    ) -> list[dict[str, Any]]:
        if query.strip():
            hit_rows = self._query_hit_rows(
                query,
                filters,
                candidate_top_k=candidate_top_k or self._facet_candidate_top_k(),
            )
            return [hit["resolved_doc"] for hit in hit_rows]
        return [
            doc
            for doc in self._sort_browse_docs(self._repo.get_all_docs())
            if self._matches_filters(doc, filters)
        ]

    def search(self, req: BrowserSearchRequest) -> BrowserSearchResponse:
        filters = req.filters
        if req.query.strip():
            hit_rows = self._query_hit_rows(
                req.query,
                filters,
                candidate_top_k=self._search_candidate_top_k(req.top_k),
            )
            hit_rows = hit_rows[: req.top_k]
            docs = [hit["resolved_doc"] for hit in hit_rows]
            cards = [
                build_result_card(
                    hit["resolved_doc"],
                    score=hit.get("score"),
                    why_retrieved=hit.get("why_retrieved") or [],
                )
                for hit in hit_rows
            ]
        else:
            docs = self._filtered_docs(req.query, filters)[: req.top_k]
            cards = [build_result_card(doc) for doc in docs]

        groups = self._group_cards(cards) if req.return_groups else {}
        facets = self._compute_facets(docs)
        return BrowserSearchResponse(
            query=req.query,
            cards=cards,
            groups=groups,
            facets=facets,
            hit_count=len(cards),
        )

    def get_rule_detail(self, doc_id: str) -> RuleDetailResponse:
        doc = self._repo.get_doc(doc_id)
        if doc is None:
            raise KeyError(doc_id)
        if doc.get("unit_type") != "rule_card":
            raise ValueError("Document is not a rule_card")
        return build_rule_detail(
            doc,
            evidence_docs=self._repo.get_evidence_docs_for_rule(doc),
            source_events=self._repo.get_source_event_docs_for_rule(doc),
            related_rules=self._repo.get_related_rule_docs(doc),
        )

    def get_evidence_detail(self, doc_id: str) -> EvidenceDetailResponse:
        doc = self._repo.get_doc(doc_id)
        if doc is None:
            raise KeyError(doc_id)
        if doc.get("unit_type") != "evidence_ref":
            raise ValueError("Document is not an evidence_ref")
        return build_evidence_detail(
            doc,
            source_rules=self._repo.get_source_rule_docs_for_evidence(doc),
            source_events=self._repo.get_source_event_docs_for_evidence(doc),
        )

    def get_event_detail(self, doc_id: str) -> EventDetailResponse:
        doc = self._repo.get_doc(doc_id)
        if doc is None:
            raise KeyError(doc_id)
        if doc.get("unit_type") != "knowledge_event":
            raise ValueError("Document is not a knowledge_event")
        return build_event_detail(
            doc,
            linked_evidence=self._repo.get_evidence_docs_for_event(doc),
            linked_rules=self._repo.get_linked_rule_docs_for_event(doc),
            linked_events=self._repo.get_linked_event_docs_for_event(doc),
        )

    def get_concept_detail(self, concept_id: str) -> ConceptDetailResponse:
        docs = self._repo.get_docs_by_concept(concept_id)
        meta = self._repo.get_concept_meta(concept_id) or {}
        if not docs and not meta:
            raise KeyError(concept_id)
        rule_docs = [doc for doc in docs if doc.get("unit_type") == "rule_card"]
        event_docs = [doc for doc in docs if doc.get("unit_type") == "knowledge_event"]
        top_rules = rule_docs[:10]
        top_events = event_docs[:10]
        evidence_count = sum(1 for doc in docs if doc.get("unit_type") == "evidence_ref")
        lessons = sorted({
            *list(meta.get("source_lessons") or []),
            *[str(doc.get("lesson_id") or "") for doc in docs if doc.get("lesson_id")],
        })
        return build_concept_detail(
            concept_id=meta.get("concept_id") or concept_id,
            aliases=self._repo.get_concept_aliases(concept_id),
            neighbors=self._repo.get_concept_neighbors(concept_id),
            top_rules=top_rules,
            top_events=top_events,
            lessons=lessons,
            evidence_count=evidence_count,
            rule_count=len(rule_docs),
            event_count=len(event_docs),
        )

    def get_lesson_detail(self, lesson_id: str) -> LessonDetailResponse:
        docs = self._repo.get_docs_by_lesson(lesson_id)
        if not docs and self._repo.get_lesson_meta(lesson_id) is None:
            raise KeyError(lesson_id)
        return build_lesson_detail(
            lesson_id,
            self._repo.get_lesson_meta(lesson_id),
            docs,
        )

    def get_neighbors(self, concept_id: str) -> list[ConceptNeighbor]:
        return [ConceptNeighbor(**neighbor) for neighbor in self._repo.get_concept_neighbors(concept_id)]

    def get_facets(
        self,
        query: str | None = None,
        filters: BrowserSearchFilters | None = None,
    ) -> dict[str, dict[str, int]]:
        active_filters = filters or BrowserSearchFilters()
        docs = self._filtered_docs(
            query or "",
            active_filters,
            candidate_top_k=self._facet_candidate_top_k(),
        )
        return self._compute_facets(docs)

    def compare_rules(
        self,
        rule_ids: list[str],
        *,
        include_related_context: bool = True,
    ) -> RuleCompareResponse:
        validated_ids = self._validate_compare_ids(rule_ids, label="Rule")
        docs: list[dict[str, Any]] = []
        related_context: dict[str, list[dict[str, Any]]] = {}
        for rule_id in validated_ids:
            doc = self._repo.get_doc(rule_id)
            if doc is None:
                raise KeyError(rule_id)
            if doc.get("unit_type") != "rule_card":
                raise ValueError(f"Document {rule_id!r} is not a rule_card")
            docs.append(doc)
            if include_related_context:
                related_context[rule_id] = self._repo.get_related_rule_docs(doc)
        return build_rule_compare_response(docs, related_context=related_context)

    def compare_units(self, refs: list[UnitCompareItemRef]) -> UnitCompareResponse:
        pairs = [(str(ref.unit_type), str(ref.doc_id).strip()) for ref in refs]
        pairs = [(ut, did) for ut, did in pairs if did]
        if len(pairs) < 2:
            raise ValueError("Unit comparison requires at least two items")
        if len(pairs) > 4:
            raise ValueError("Unit comparison supports at most four items")
        if len({did for _, did in pairs}) != len(pairs):
            raise ValueError("Comparison ids must be unique")
        docs: list[dict[str, Any]] = []
        for unit_type, doc_id in pairs:
            doc = self._repo.get_doc(doc_id)
            if doc is None:
                raise KeyError(doc_id)
            if str(doc.get("unit_type")) != unit_type:
                raise ValueError(f"Document {doc_id!r} is not a {unit_type}")
            docs.append(doc)
        return build_unit_compare_response(docs)

    def compare_lessons(self, lesson_ids: list[str]) -> LessonCompareResponse:
        validated_ids = self._validate_compare_ids(lesson_ids, label="Lesson")
        lesson_docs_map: dict[str, list[dict[str, Any]]] = {}
        lesson_metas: dict[str, dict[str, Any] | None] = {}
        for lesson_id in validated_ids:
            lesson_meta = self._repo.get_lesson_meta(lesson_id)
            docs = self._repo.get_docs_by_lesson(lesson_id)
            if lesson_meta is None and not docs:
                raise KeyError(lesson_id)
            lesson_metas[lesson_id] = lesson_meta
            lesson_docs_map[lesson_id] = docs

        overlap = self._repo.get_rule_overlap_between_lessons(validated_ids)
        return build_lesson_compare_response(
            lesson_metas,
            lesson_docs_map,
            overlap={"rule_families": sorted(overlap.keys())},
        )

    def get_related_rules(self, doc_id: str) -> RelatedRulesResponse:
        grouped_docs = self._repo.get_related_rule_docs_grouped(doc_id)
        return build_related_rules_response(doc_id, grouped_docs)

    def get_concept_rules(self, concept_id: str) -> ConceptRuleListResponse:
        rule_docs = self._repo.get_rules_for_concept(concept_id)
        meta = self._repo.get_concept_meta(concept_id) or {}
        if not rule_docs and not meta:
            raise KeyError(concept_id)
        resolved_concept_id = str(meta.get("concept_id") or concept_id)
        return build_concept_rule_list(resolved_concept_id, rule_docs)

    def get_concept_lessons(self, concept_id: str) -> ConceptLessonListResponse:
        lesson_ids = self._repo.get_lessons_for_concept(concept_id)
        meta = self._repo.get_concept_meta(concept_id) or {}
        if not lesson_ids and not meta:
            raise KeyError(concept_id)
        resolved_concept_id = str(meta.get("concept_id") or concept_id)
        lesson_metas = {lesson_id: self._repo.get_lesson_meta(lesson_id) for lesson_id in lesson_ids}
        lesson_docs_map = {lesson_id: self._repo.get_docs_by_lesson(lesson_id) for lesson_id in lesson_ids}
        return build_concept_lesson_list(resolved_concept_id, lesson_ids, lesson_metas, lesson_docs_map)
