"""Retrieval document models derived from Step 2 corpus entities.

Each unit type has a dedicated subclass that assembles structured retrieval
text while preserving the original corpus fields and provenance.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from pipeline.rag.config import UnitType


class RetrievalDocBase(BaseModel):
    doc_id: str
    unit_type: UnitType
    lesson_id: str
    lesson_slug: str = ""
    language: str = "ru"
    canonical_concept_ids: list[str] = Field(default_factory=list)
    canonical_subconcept_ids: list[str] = Field(default_factory=list)
    alias_terms: list[str] = Field(default_factory=list)
    title: str = ""
    text: str = ""
    short_text: str = ""
    provenance: dict[str, Any] = Field(default_factory=dict)
    confidence_score: Optional[float] = None
    timestamps: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    source_event_ids: list[str] = Field(default_factory=list)
    source_rule_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


def _trunc(text: str, limit: int = 200) -> str:
    return text[:limit] if len(text) > limit else text


def _join_nonempty(*parts: str | None, sep: str = " | ") -> str:
    return sep.join(p.strip() for p in parts if p and p.strip())


# ── Rule Card ────────────────────────────────────────────────────────────


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

        text = "\n".join(p for p in parts if p)
        ts: list[str] = []
        for eid in raw.get("source_event_ids", []):
            if isinstance(eid, str):
                ts.append(eid)

        return RuleCardDoc(
            doc_id=raw.get("global_id", raw.get("rule_id", "")),
            lesson_id=raw.get("lesson_id", ""),
            lesson_slug=raw.get("lesson_slug", ""),
            language=raw.get("source_language", "ru"),
            canonical_concept_ids=[raw["concept_id"]] if raw.get("concept_id") else [],
            canonical_subconcept_ids=[raw["subconcept_id"]] if raw.get("subconcept_id") else [],
            title=_join_nonempty(concept, subconcept, sep=" / "),
            text=text,
            short_text=_trunc(text),
            confidence_score=raw.get("confidence_score"),
            evidence_ids=raw.get("evidence_refs") or [],
            source_event_ids=raw.get("source_event_ids") or [],
            provenance={
                "section": raw.get("section"),
                "subsection": raw.get("subsection"),
                "confidence": raw.get("confidence"),
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
        )


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

        text = " ".join(p for p in parts if p)
        timestamps = [t for t in [ts_start, ts_end] if t]

        return KnowledgeEventDoc(
            doc_id=raw.get("global_id", raw.get("event_id", "")),
            lesson_id=raw.get("lesson_id", ""),
            lesson_slug=raw.get("lesson_slug", ""),
            language=raw.get("source_language", "ru"),
            canonical_concept_ids=[raw["concept_id"]] if raw.get("concept_id") else [],
            canonical_subconcept_ids=[raw["subconcept_id"]] if raw.get("subconcept_id") else [],
            title=_join_nonempty(event_type, concept, sep=" / "),
            text=text,
            short_text=_trunc(text),
            confidence_score=raw.get("confidence_score"),
            timestamps=timestamps,
            source_event_ids=raw.get("source_event_ids") or [],
            evidence_ids=raw.get("evidence_refs") or [],
            provenance={
                "section": raw.get("section"),
                "subsection": raw.get("subsection"),
                "chunk_index": raw.get("source_chunk_index"),
            },
            event_type=event_type,
            normalized_text=norm,
            normalized_text_ru=norm_ru,
            concept=concept,
            subconcept=subconcept,
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
        summary_ru = raw.get("summary_ru") or ""
        summary_en = raw.get("summary_en") or ""
        summary = raw.get("compact_visual_summary") or summary_ru or summary_en
        linked_rules = raw.get("linked_rule_ids") or []
        ts_start = raw.get("timestamp_start") or ""
        ts_end = raw.get("timestamp_end") or ""

        parts = [
            f"[{role}]" if role else "",
            summary,
            f"[Rules] {', '.join(linked_rules[:5])}" if linked_rules else "",
            f"[Time] {ts_start}–{ts_end}" if ts_start else "",
        ]
        text = " ".join(p for p in parts if p)
        timestamps = [t for t in [ts_start, ts_end] if t]

        return EvidenceRefDoc(
            doc_id=raw.get("global_id", raw.get("evidence_id", "")),
            lesson_id=raw.get("lesson_id", ""),
            lesson_slug=raw.get("lesson_slug", ""),
            language=raw.get("source_language", "ru"),
            title=f"Evidence: {role}",
            text=text,
            short_text=_trunc(text),
            timestamps=timestamps,
            source_event_ids=raw.get("source_event_ids") or [],
            source_rule_ids=linked_rules,
            provenance={
                "section": raw.get("section"),
                "subsection": raw.get("subsection"),
                "frame_count": len(raw.get("frame_ids") or []),
            },
            example_role=role,
            visual_summary=summary,
            visual_type=raw.get("visual_type") or "",
            frame_ids=raw.get("frame_ids") or [],
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
            source_rule_ids=raw.get("source_rule_ids") or [],
            provenance={"source_lessons": source_lessons},
            concept_name=name,
            concept_type=ctype,
            aliases=aliases,
            source_lessons=source_lessons,
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
            source_rule_ids=raw.get("source_rule_ids") or [],
            provenance={"source_lessons": source_lessons},
            source_concept=src_name,
            target_concept=tgt_name,
            relation_type=rel_type,
            weight=raw.get("weight", 1),
        )
