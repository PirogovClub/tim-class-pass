"""Retrieval document models derived from Step 2 corpus entities."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from pipeline.rag.config import UnitType


class RetrievalDocBase(BaseModel):
    doc_id: str
    unit_type: UnitType
    lesson_id: str | None = None
    lesson_slug: str | None = None
    language: str | None = "ru"
    canonical_concept_ids: list[str] = Field(default_factory=list)
    canonical_subconcept_ids: list[str] = Field(default_factory=list)
    alias_terms: list[str] = Field(default_factory=list)
    title: str = ""
    text: str = ""
    short_text: str = ""
    keywords: list[str] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)
    confidence_score: Optional[float] = None
    support_basis: Optional[str] = None
    evidence_requirement: Optional[str] = None
    teaching_mode: Optional[str] = None
    timestamps: list[dict[str, Any]] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    source_event_ids: list[str] = Field(default_factory=list)
    source_rule_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


def _trunc(text: str, limit: int = 200) -> str:
    return text[:limit] if len(text) > limit else text


def _join_nonempty(*parts: str | None, sep: str = " | ") -> str:
    return sep.join(p.strip() for p in parts if p and p.strip())


def _compact_keywords(*groups: Any) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for group in groups:
        if isinstance(group, str):
            values = [group]
        elif isinstance(group, list):
            values = [item for item in group if isinstance(item, str)]
        else:
            values = []
        for value in values:
            normalized = " ".join(value.split()).strip()
            if not normalized:
                continue
            key = normalized.lower()
            if key in seen:
                continue
            seen.add(key)
            output.append(normalized)
    return output


def _humanize_identifier(value: str | None) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    if ":" in raw:
        raw = raw.split(":")[-1]
    return raw.replace("_", " ").strip()


def _timestamp_entries(raw: dict[str, Any]) -> list[dict[str, Any]]:
    start = raw.get("timestamp_start")
    end = raw.get("timestamp_end")
    if not start and not end:
        return []
    return [{
        "start": start,
        "end": end,
    }]


def _evidence_strength_confidence(raw_strength: str | None) -> float | None:
    strength = (raw_strength or "").strip().lower()
    if not strength:
        return None
    if strength in {"strong"}:
        return 0.95
    if strength in {"moderate", "medium"}:
        return 0.8
    if strength in {"weak", "low"}:
        return 0.6
    return 0.7


def _teaching_mode_from_example_role(role: str | None) -> str | None:
    lowered = (role or "").strip().lower()
    if not lowered:
        return None
    if lowered in {"positive_example", "negative_example", "counterexample", "example", "illustration"}:
        return "example"
    if lowered in {"mixed", "supporting_example"}:
        return "mixed"
    return "example"


def _base_kwargs(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "lesson_id": raw.get("lesson_id"),
        "lesson_slug": raw.get("lesson_slug"),
        "language": raw.get("source_language"),
        "canonical_concept_ids": [raw["concept_id"]] if raw.get("concept_id") else [],
        "canonical_subconcept_ids": [raw["subconcept_id"]] if raw.get("subconcept_id") else [],
        "confidence_score": raw.get("confidence_score"),
        "support_basis": raw.get("support_basis"),
        "evidence_requirement": raw.get("evidence_requirement"),
        "teaching_mode": raw.get("teaching_mode"),
        "timestamps": _timestamp_entries(raw),
        "evidence_ids": raw.get("evidence_refs") or [],
        "source_event_ids": raw.get("source_event_ids") or [],
    }


class RuleCardDoc(RetrievalDocBase):
    unit_type: UnitType = "rule_card"  # type: ignore[assignment]
    rule_text: str = ""
    rule_text_ru: str = ""
    conditions: list[str] = Field(default_factory=list)
    invalidation: list[str] = Field(default_factory=list)
    exceptions: list[str] = Field(default_factory=list)
    comparisons: list[str] = Field(default_factory=list)
    visual_summary: str = ""
    concept: str = ""
    subconcept: str = ""

    @staticmethod
    def from_corpus(raw: dict[str, Any]) -> RuleCardDoc:
        concept = raw.get("concept", "")
        subconcept = raw.get("subconcept") or ""
        rule_text = raw.get("rule_text") or ""
        rule_text_ru = raw.get("rule_text_ru") or ""
        conditions = raw.get("conditions") or []
        invalidation = raw.get("invalidation") or []
        exceptions = raw.get("exceptions") or []
        comparisons = raw.get("comparisons") or []
        visual_summary = raw.get("visual_summary") or ""

        parts = [
            f"[Concept] {concept}",
            f"[Subconcept] {subconcept}" if subconcept else "",
            f"[Rule] {rule_text_ru or rule_text}",
        ]
        if conditions:
            parts.append(f"[Conditions] {'; '.join(conditions)}")
        if invalidation:
            parts.append(f"[Invalidation] {'; '.join(invalidation)}")
        if exceptions:
            parts.append(f"[Exceptions] {'; '.join(exceptions)}")
        if comparisons:
            parts.append(f"[Comparisons] {'; '.join(comparisons)}")
        if visual_summary:
            parts.append(f"[Visual] {visual_summary}")
        if raw.get("support_basis"):
            parts.append(f"[Support Basis] {raw['support_basis']}")
        if raw.get("evidence_requirement"):
            parts.append(f"[Evidence Requirement] {raw['evidence_requirement']}")
        if raw.get("teaching_mode"):
            parts.append(f"[Teaching Mode] {raw['teaching_mode']}")

        text = "\n".join(p for p in parts if p)
        alias_terms = _compact_keywords(
            concept,
            subconcept,
            raw.get("concept_label_ru"),
            raw.get("subconcept_label_ru"),
        )
        keywords = _compact_keywords(
            concept,
            subconcept,
            conditions,
            invalidation,
            exceptions,
            comparisons,
            raw.get("pattern_tags") or [],
            raw.get("algorithm_notes") or [],
        )

        doc = RuleCardDoc(
            doc_id=raw.get("global_id", raw.get("rule_id", "")),
            alias_terms=alias_terms,
            title=_join_nonempty(concept, subconcept, sep=" / "),
            text=text,
            short_text=_trunc(text),
            keywords=keywords,
            provenance={
                "lesson_title": raw.get("lesson_title"),
                "section": raw.get("section"),
                "subsection": raw.get("subsection"),
                "confidence": raw.get("confidence"),
                "support_basis": raw.get("support_basis"),
            },
            source_rule_ids=[raw.get("global_id", raw.get("rule_id", ""))],
            metadata={
                **(raw.get("metadata") or {}),
                "conditions": conditions,
                "invalidation": invalidation,
                "exceptions": exceptions,
                "comparisons": comparisons,
                "algorithm_notes": raw.get("algorithm_notes") or [],
                "visual_support_level": raw.get("visual_support_level"),
                "transcript_support_level": raw.get("transcript_support_level"),
                "transcript_support_score": raw.get("transcript_support_score"),
                "visual_support_score": raw.get("visual_support_score"),
                "has_visual_evidence": raw.get("has_visual_evidence"),
                "transcript_anchor_count": raw.get("transcript_anchor_count"),
                "transcript_repetition_count": raw.get("transcript_repetition_count"),
            },
            rule_text=rule_text,
            rule_text_ru=rule_text_ru,
            conditions=conditions,
            invalidation=invalidation,
            exceptions=exceptions,
            comparisons=comparisons,
            visual_summary=visual_summary,
            concept=concept,
            subconcept=subconcept,
            **_base_kwargs(raw),
        )
        return doc


# ── Knowledge Event ──────────────────────────────────────────────────────


class KnowledgeEventDoc(RetrievalDocBase):
    unit_type: UnitType = "knowledge_event"  # type: ignore[assignment]
    event_type: str = ""
    normalized_text: str = ""
    normalized_text_ru: str = ""
    concept: str = ""
    subconcept: str = ""

    @staticmethod
    def from_corpus(raw: dict[str, Any]) -> KnowledgeEventDoc:
        concept = raw.get("concept", "")
        subconcept = raw.get("subconcept") or ""
        event_type = raw.get("event_type") or ""
        norm = raw.get("normalized_text") or ""
        norm_ru = raw.get("normalized_text_ru") or ""
        ts_start = raw.get("timestamp_start") or ""
        ts_end = raw.get("timestamp_end") or ""

        parts = [
            f"[{event_type}]" if event_type else "",
            f"[Concept] {concept}" if concept else "",
            norm_ru or norm,
        ]
        if ts_start:
            parts.append(f"[Time] {ts_start}–{ts_end}")
        if raw.get("support_basis"):
            parts.append(f"[Support Basis] {raw['support_basis']}")

        text = " ".join(p for p in parts if p)
        alias_terms = _compact_keywords(
            concept,
            subconcept,
            raw.get("concept_label_ru"),
            raw.get("subconcept_label_ru"),
            raw.get("pattern_tags") or [],
        )
        keywords = _compact_keywords(
            concept,
            subconcept,
            event_type,
            raw.get("rule_type"),
            raw.get("pattern_tags") or [],
            raw.get("condition_ids") or [],
            raw.get("invalidation_ids") or [],
            raw.get("exception_ids") or [],
        )

        return KnowledgeEventDoc(
            doc_id=raw.get("global_id", raw.get("event_id", "")),
            alias_terms=alias_terms,
            title=_join_nonempty(event_type, concept, sep=" / "),
            text=text,
            short_text=_trunc(text),
            keywords=keywords,
            provenance={
                "lesson_title": raw.get("lesson_title"),
                "section": raw.get("section"),
                "subsection": raw.get("subsection"),
                "chunk_index": raw.get("source_chunk_index"),
                "source_line_start": raw.get("source_line_start"),
                "source_line_end": raw.get("source_line_end"),
            },
            event_type=event_type,
            normalized_text=norm,
            normalized_text_ru=norm_ru,
            concept=concept,
            subconcept=subconcept,
            metadata={
                **(raw.get("metadata") or {}),
                "rule_type": raw.get("rule_type"),
                "pattern_tags": raw.get("pattern_tags") or [],
                "source_quote": raw.get("source_quote"),
                "transcript_anchors": raw.get("transcript_anchors") or [],
                "timestamp_confidence": raw.get("timestamp_confidence"),
                "anchor_match_source": raw.get("anchor_match_source"),
                "anchor_line_count": raw.get("anchor_line_count"),
                "anchor_span_width": raw.get("anchor_span_width"),
                "anchor_density": raw.get("anchor_density"),
                "visual_support_level": raw.get("visual_support_level"),
                "transcript_support_level": raw.get("transcript_support_level"),
                "transcript_support_score": raw.get("transcript_support_score"),
                "visual_support_score": raw.get("visual_support_score"),
            },
            **_base_kwargs(raw),
        )


# ── Evidence Ref ─────────────────────────────────────────────────────────


class EvidenceRefDoc(RetrievalDocBase):
    unit_type: UnitType = "evidence_ref"  # type: ignore[assignment]
    example_role: str = ""
    visual_summary: str = ""
    visual_type: str = ""
    frame_ids: list[str] = Field(default_factory=list)

    @staticmethod
    def from_corpus(raw: dict[str, Any]) -> EvidenceRefDoc:
        role = raw.get("example_role") or ""
        evidence_id = raw.get("global_id", raw.get("evidence_id", ""))
        summary_ru = raw.get("summary_ru") or ""
        summary_en = raw.get("summary_en") or ""
        summary = raw.get("compact_visual_summary") or raw.get("summary_primary") or summary_ru or summary_en
        linked_rules = raw.get("linked_rule_ids") or []
        related_concepts = raw.get("related_concept_ids") or []
        concept_labels = [_humanize_identifier(cid) for cid in related_concepts]
        rule_labels = [_humanize_identifier(rid) for rid in linked_rules]
        ts_start = raw.get("timestamp_start") or ""
        ts_end = raw.get("timestamp_end") or ""
        evidence_strength = raw.get("evidence_strength")
        role_detail = raw.get("evidence_role_detail")

        parts = [
            f"[{role}]" if role else "",
            summary,
            f"[Concepts] {', '.join(label for label in concept_labels[:5] if label)}" if concept_labels else "",
            f"[Rules] {', '.join(label for label in rule_labels[:5] if label)}" if rule_labels else "",
            f"[Time] {ts_start}–{ts_end}" if ts_start else "",
        ]
        if raw.get("evidence_strength"):
            parts.append(f"[Strength] {raw['evidence_strength']}")
        if raw.get("evidence_role_detail"):
            parts.append(f"[Role Detail] {raw['evidence_role_detail']}")
        text = " ".join(p for p in parts if p)
        keywords = _compact_keywords(
            role,
            raw.get("visual_type"),
            raw.get("evidence_strength"),
            raw.get("evidence_role_detail"),
            related_concepts,
            concept_labels,
            rule_labels,
            raw.get("frame_ids") or [],
        )

        return EvidenceRefDoc(
            doc_id=evidence_id,
            lesson_id=raw.get("lesson_id"),
            lesson_slug=raw.get("lesson_slug"),
            language=raw.get("source_language"),
            alias_terms=_compact_keywords(role, role_detail, raw.get("visual_type"), concept_labels),
            title=f"Evidence: {role}" + (f" / {concept_labels[0]}" if concept_labels else ""),
            text=text,
            short_text=_trunc(text),
            keywords=keywords,
            provenance={
                "lesson_title": raw.get("lesson_title"),
                "section": raw.get("section"),
                "subsection": raw.get("subsection"),
                "frame_count": len(raw.get("frame_ids") or []),
                "evidence_strength": evidence_strength,
                "evidence_role_detail": role_detail,
            },
            canonical_concept_ids=related_concepts,
            confidence_score=_evidence_strength_confidence(evidence_strength),
            support_basis="transcript_plus_visual",
            evidence_requirement="required",
            teaching_mode=_teaching_mode_from_example_role(role),
            timestamps=_timestamp_entries(raw),
            evidence_ids=[evidence_id] if evidence_id else [],
            source_event_ids=raw.get("source_event_ids") or [],
            source_rule_ids=linked_rules,
            example_role=role,
            visual_summary=summary,
            visual_type=raw.get("visual_type") or "",
            frame_ids=raw.get("frame_ids") or [],
            metadata={
                **(raw.get("metadata") or {}),
                "screenshot_paths": raw.get("screenshot_paths") or [],
                "summary_primary": raw.get("summary_primary"),
                "summary_ru": summary_ru,
                "summary_en": summary_en,
                "summary_language": raw.get("summary_language"),
                "evidence_strength": evidence_strength,
                "evidence_role_detail": role_detail,
                "raw_visual_event_ids": raw.get("raw_visual_event_ids") or [],
            },
        )


# ── Concept Node ─────────────────────────────────────────────────────────


class ConceptNodeDoc(RetrievalDocBase):
    unit_type: UnitType = "concept_node"  # type: ignore[assignment]
    concept_name: str = ""
    concept_type: str = "concept"
    aliases: list[str] = Field(default_factory=list)
    source_lessons: list[str] = Field(default_factory=list)

    @staticmethod
    def from_corpus(
        raw: dict[str, Any],
        frequencies: dict[str, Any] | None = None,
    ) -> ConceptNodeDoc:
        name = raw.get("name", "")
        aliases = raw.get("aliases") or []
        source_lessons = raw.get("source_lessons") or []
        ctype = raw.get("type", "concept")

        freq_str = ""
        if frequencies:
            freq = frequencies.get(raw.get("global_id", ""), {})
            freq_str = (
                f"[Frequency] rules={freq.get('rule_count', 0)}, "
                f"events={freq.get('event_count', 0)}, "
                f"lessons={freq.get('lesson_count', 0)}"
            )

        parts = [
            f"[Concept] {name}",
            f"[Type] {ctype}",
            f"[Aliases] {', '.join(aliases)}" if aliases else "",
            f"[Lessons] {', '.join(source_lessons)}" if source_lessons else "",
            freq_str,
        ]
        text = "\n".join(p for p in parts if p)

        return ConceptNodeDoc(
            doc_id=raw.get("global_id", ""),
            lesson_id="corpus",
            language="ru",
            canonical_concept_ids=[raw.get("global_id", "")],
            alias_terms=aliases,
            title=name,
            text=text,
            short_text=_trunc(text),
            keywords=_compact_keywords(name, aliases, ctype, raw.get("canonical_label")),
            source_rule_ids=raw.get("source_rule_ids") or [],
            provenance={"source_lessons": source_lessons, "type": ctype},
            concept_name=name,
            concept_type=ctype,
            aliases=aliases,
            source_lessons=source_lessons,
            metadata={
                **(raw.get("metadata") or {}),
                "canonical_label": raw.get("canonical_label"),
                "parent_id": raw.get("parent_id"),
            },
        )


# ── Concept Relation ─────────────────────────────────────────────────────


class ConceptRelationDoc(RetrievalDocBase):
    unit_type: UnitType = "concept_relation"  # type: ignore[assignment]
    source_concept: str = ""
    target_concept: str = ""
    relation_type: str = ""
    weight: int = 1

    @staticmethod
    def from_corpus(
        raw: dict[str, Any],
        node_name_map: dict[str, str] | None = None,
    ) -> ConceptRelationDoc:
        nm = node_name_map or {}
        src_id = raw.get("source_id", "")
        tgt_id = raw.get("target_id", "")
        src_name = nm.get(src_id, src_id)
        tgt_name = nm.get(tgt_id, tgt_id)
        rel_type = raw.get("relation_type", "")

        text = f"{src_name} –[{rel_type}]→ {tgt_name}"
        source_lessons = raw.get("source_lessons") or []

        return ConceptRelationDoc(
            doc_id=raw.get("relation_id", ""),
            lesson_id="corpus",
            language="ru",
            canonical_concept_ids=[src_id, tgt_id],
            title=f"{src_name} → {tgt_name}",
            text=text,
            short_text=_trunc(text),
            keywords=_compact_keywords(src_name, tgt_name, rel_type),
            alias_terms=_compact_keywords(src_name, tgt_name),
            source_rule_ids=raw.get("source_rule_ids") or [],
            provenance={"source_lessons": source_lessons, "relation_type": rel_type},
            source_concept=src_name,
            target_concept=tgt_name,
            relation_type=rel_type,
            weight=raw.get("weight", 1),
            metadata={
                "source_id": src_id,
                "target_id": tgt_id,
                "source_lessons": source_lessons,
            },
        )
