"""Task 7: Exporters — derive review and RAG markdown from structured artifacts."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pipeline.io_utils import atomic_write_text, atomic_write_json
from pipeline.component2.provenance import format_compact_provenance
from pipeline.component2.visual_compaction import (
    VisualCompactionConfig,
    summarize_evidence_for_rag_markdown,
    summarize_evidence_for_review_markdown,
    validate_markdown_visual_compaction,
)
from pipeline.schemas import (
    ConceptGraph,
    EvidenceIndex,
    EvidenceRef,
    KnowledgeEvent,
    KnowledgeEventCollection,
    RuleCard,
    RuleCardCollection,
)

logger = logging.getLogger(__name__)

# Confidence sort: high first, then medium, then low
_CONFIDENCE_ORDER = {"high": 0, "medium": 1, "low": 2}


# ----- Loaders -----


def load_rule_cards(path: Path) -> RuleCardCollection:
    """Load and validate RuleCardCollection from JSON."""
    text = path.read_text(encoding="utf-8")
    return RuleCardCollection.model_validate_json(text)


def load_evidence_index(path: Path) -> EvidenceIndex:
    """Load and validate EvidenceIndex from JSON."""
    text = path.read_text(encoding="utf-8")
    return EvidenceIndex.model_validate_json(text)


def load_knowledge_events(path: Path) -> KnowledgeEventCollection | None:
    """Load KnowledgeEventCollection from JSON. Return None if file is missing."""
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    return KnowledgeEventCollection.model_validate_json(text)


# ----- Export context -----


@dataclass
class ExportContext:
    lesson_id: str
    lesson_title: str | None
    rule_cards: list[RuleCard]
    evidence_refs: list[EvidenceRef]
    knowledge_events: list[KnowledgeEvent] | None = None
    rules_by_id: dict[str, RuleCard] = field(default_factory=dict)
    evidence_by_id: dict[str, EvidenceRef] = field(default_factory=dict)
    compaction_cfg: VisualCompactionConfig | None = None


def build_export_context(
    rule_cards: RuleCardCollection,
    evidence_index: EvidenceIndex,
    knowledge_events: KnowledgeEventCollection | None = None,
    lesson_title: str | None = None,
    compaction_cfg: VisualCompactionConfig | None = None,
) -> ExportContext:
    """Build a normalized export context from collections."""
    rules = rule_cards.rules
    refs = evidence_index.evidence_refs
    title = lesson_title or evidence_index.lesson_title or rule_cards.lesson_id
    rules_by_id = {r.rule_id: r for r in rules}
    evidence_by_id = {e.evidence_id: e for e in refs}
    events_list: list[KnowledgeEvent] | None = (
        list(knowledge_events.events) if knowledge_events else None
    )
    return ExportContext(
        lesson_id=rule_cards.lesson_id,
        lesson_title=title,
        rule_cards=rules,
        evidence_refs=refs,
        knowledge_events=events_list,
        rules_by_id=rules_by_id,
        evidence_by_id=evidence_by_id,
        compaction_cfg=compaction_cfg,
    )


# ----- Grouping and sorting -----


def group_rule_cards_for_export(rules: list[RuleCard]) -> dict[str, list[RuleCard]]:
    """Group rule cards by concept; use 'Unclassified' when concept is missing."""
    groups: dict[str, list[RuleCard]] = {}
    for r in rules:
        concept = (r.concept or "").strip() or "Unclassified"
        groups.setdefault(concept, []).append(r)
    return groups


def sort_rule_cards(rules: list[RuleCard]) -> list[RuleCard]:
    """Deterministic order: section, subsection, concept, subconcept, confidence desc, rule_id."""
    def key(r: RuleCard) -> tuple:
        section = getattr(r, "section", None) or ""
        subsection = getattr(r, "subsection", None) or ""
        conf_rank = _CONFIDENCE_ORDER.get(r.confidence, 1)
        return (
            str(section),
            str(subsection),
            r.concept,
            r.subconcept or "",
            conf_rank,
            -(r.confidence_score or 0),
            r.rule_id,
        )
    return sorted(rules, key=key)


# ----- Formatting helpers -----


def format_bullet_block(title: str, items: list[str]) -> str:
    """Format a titled bullet list; return empty string if items empty."""
    cleaned = [clean_markdown_text(s) for s in items if s and str(s).strip()]
    if not cleaned:
        return ""
    lines = [f"**{title}**", ""] + [f"- {item}" for item in cleaned]
    return "\n".join(lines)


def format_compact_text_list(items: list[str]) -> list[str]:
    """Return trimmed, non-empty items from list."""
    return [clean_markdown_text(s) for s in items if s and str(s).strip()]


def dedupe_preserve_order(items: list[str]) -> list[str]:
    """Deduplicate while preserving first occurrence order."""
    seen: set[str] = set()
    out: list[str] = []
    for x in items:
        x = (x or "").strip()
        if not x:
            continue
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def clean_markdown_text(text: str) -> str:
    """Trim and normalize whitespace for markdown."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", str(text).strip()).strip()


# ----- Timestamp resolution (Task 17) -----


def _parse_mmss(ts: str | None) -> int | None:
    """Parse 'MM:SS' or 'HH:MM:SS' to total seconds; return None on failure."""
    if not ts:
        return None
    ts = ts.strip()
    parts = ts.split(":")
    try:
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    except (ValueError, IndexError):
        pass
    return None


def _seconds_to_mmss(total_seconds: int) -> str:
    m, s = divmod(total_seconds, 60)
    return f"{m:02d}:{s:02d}"


def resolve_rule_timestamp(
    rule: RuleCard,
    events_by_id: dict[str, KnowledgeEvent],
) -> str | None:
    """Resolve earliest confident timestamp from source events, formatted as MM:SS.

    Returns None if no timestamp can be derived. Never fabricates [00:00].
    """
    earliest_sec: int | None = None
    for eid in rule.source_event_ids or []:
        ev = events_by_id.get(eid)
        if ev is None:
            continue
        sec = _parse_mmss(getattr(ev, "timestamp_start", None))
        if sec is not None and sec > 0:
            if earliest_sec is None or sec < earliest_sec:
                earliest_sec = sec
    if earliest_sec is None or earliest_sec <= 0:
        return None
    return _seconds_to_mmss(earliest_sec)


# ----- Deterministic renderers -----


def _rule_evidence_refs_compact(rule: RuleCard, evidence_by_id: dict[str, EvidenceRef]) -> str:
    """Compact line of evidence refs for a rule."""
    ref_ids = dedupe_preserve_order(rule.evidence_refs or [])
    if not ref_ids:
        return ""
    return ", ".join(ref_ids)


def _rule_source_events_compact(rule: RuleCard) -> str:
    """Compact line of source event ids for a rule."""
    ids = getattr(rule, "source_event_ids", None) or []
    ids = dedupe_preserve_order(list(ids))
    if not ids:
        return ""
    return ", ".join(ids)


def _review_rule_block(
    rule: RuleCard,
    evidence_by_id: dict[str, EvidenceRef],
    compaction_cfg: VisualCompactionConfig | None = None,
) -> str:
    """Single rule as review markdown block; omit empty sections."""
    cfg = compaction_cfg or VisualCompactionConfig()
    parts: list[str] = []
    title = rule.title or "Rule"
    parts.append(f"### Rule: {clean_markdown_text(rule.rule_text)}")
    if rule.subconcept:
        parts.append(f"**Subconcept:** {clean_markdown_text(rule.subconcept)}")
    conf = rule.confidence or "medium"
    score = rule.confidence_score
    if score is not None:
        parts.append(f"**Confidence:** {conf} ({score:.2f})")
    else:
        parts.append(f"**Confidence:** {conf}")

    sb = getattr(rule, "support_basis", None)
    tm = getattr(rule, "teaching_mode", None)
    er = getattr(rule, "evidence_requirement", None)
    support_parts: list[str] = []
    if sb:
        support_parts.append(f"support={sb}")
    if tm:
        support_parts.append(f"mode={tm}")
    if er:
        support_parts.append(f"evidence={er}")
    if support_parts:
        parts.append(f"**Support:** {', '.join(support_parts)}")
    parts.append("")

    block = format_bullet_block("Conditions", (rule.conditions or []))
    if block:
        parts.append(block)
        parts.append("")
    block = format_bullet_block("Invalidation", (rule.invalidation or []))
    if block:
        parts.append(block)
        parts.append("")
    block = format_bullet_block("Exceptions", (rule.exceptions or []))
    if block:
        parts.append(block)
        parts.append("")
    block = format_bullet_block("Comparisons", (rule.comparisons or []))
    if block:
        parts.append(block)
        parts.append("")
    block = format_bullet_block("Algorithm notes", (rule.algorithm_notes or []))
    if block:
        parts.append(block)
        parts.append("")

    refs = [evidence_by_id[eid] for eid in (rule.evidence_refs or []) if eid in evidence_by_id]
    review_visuals = summarize_evidence_for_review_markdown(refs, cfg)
    if review_visuals:
        parts.append("**Visual evidence**")
        for line in review_visuals[: cfg.max_visual_bullets_review]:
            parts.append(f"- {clean_markdown_text(line)}")
        parts.append("")

    prov_block = format_compact_provenance(rule)
    if prov_block:
        parts.append(prov_block)
    if parts and parts[-1] == "":
        parts.pop()
    return "\n".join(parts)


def render_review_markdown_deterministic(ctx: ExportContext) -> str:
    """Full review markdown: lesson title, concept groups, rule blocks, compact refs. Omit empty sections."""
    title = ctx.lesson_title or ctx.lesson_id
    lines: list[str] = [f"# Lesson: {title}", ""]
    grouped = group_rule_cards_for_export(ctx.rule_cards)
    for concept in sorted(grouped.keys()):
        rules = sort_rule_cards(grouped[concept])
        lines.append(f"## Concept: {concept}")
        lines.append("")
        for rule in rules:
            lines.append(_review_rule_block(rule, ctx.evidence_by_id, ctx.compaction_cfg))
            lines.append("")
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines) if lines else ""


def _rag_rule_block(
    rule: RuleCard,
    evidence_by_id: dict[str, EvidenceRef],
    compaction_cfg: VisualCompactionConfig | None = None,
    events_by_id: dict[str, KnowledgeEvent] | None = None,
) -> str:
    """Compact RAG rule block: no verbose provenance. Task 17: optional [MM:SS] timestamp."""
    cfg = compaction_cfg or VisualCompactionConfig()
    parts: list[str] = []
    sub = rule.subconcept or rule.title
    if sub:
        parts.append(f"### {clean_markdown_text(sub)}")
    ts = resolve_rule_timestamp(rule, events_by_id or {}) if events_by_id else None
    rule_line = f"Rule: {clean_markdown_text(rule.rule_text)}"
    if ts:
        rule_line = f"[{ts}] {rule_line}"
    parts.append(rule_line)
    parts.append("")
    block = format_bullet_block("Conditions", (rule.conditions or [])[:5])
    if block:
        parts.append(block)
        parts.append("")
    block = format_bullet_block("Invalidation", (rule.invalidation or [])[:3])
    if block:
        parts.append(block)
        parts.append("")
    block = format_bullet_block("Algorithm notes", (rule.algorithm_notes or [])[:5])
    if block:
        parts.append(block)
        parts.append("")
    refs = [evidence_by_id[eid] for eid in (rule.evidence_refs or []) if eid in evidence_by_id]
    rag_visuals = summarize_evidence_for_rag_markdown(refs, cfg)
    if rag_visuals:
        parts.append("Visual summary:")
        for line in rag_visuals[: cfg.max_visual_bullets_rag]:
            parts.append(f"- {clean_markdown_text(line)}")
    if parts and parts[-1] == "":
        parts.pop()
    return "\n".join(parts)


def render_rag_markdown_deterministic(ctx: ExportContext) -> str:
    """Compact RAG markdown; no verbose provenance. Task 17: timestamps from source events."""
    title = ctx.lesson_title or ctx.lesson_id
    lines: list[str] = [f"# Lesson: {title}", ""]
    ebi: dict[str, KnowledgeEvent] = {}
    if ctx.knowledge_events:
        ebi = {e.event_id: e for e in ctx.knowledge_events}
    grouped = group_rule_cards_for_export(ctx.rule_cards)
    for concept in sorted(grouped.keys()):
        rules = sort_rule_cards(grouped[concept])
        lines.append(f"## {concept}")
        lines.append("")
        for rule in rules:
            lines.append(_rag_rule_block(rule, ctx.evidence_by_id, ctx.compaction_cfg, events_by_id=ebi))
            lines.append("")
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines) if lines else ""


# ----- LLM-backed renderers -----


def render_review_markdown(
    ctx: ExportContext,
    *,
    use_llm: bool = False,
    video_id: str | None = None,
    model: str | None = None,
    provider: str | None = None,
) -> tuple[str, list[dict]]:
    """Review markdown: deterministic or LLM (render_mode=review). Returns (markdown, usage_records)."""
    if not use_llm:
        return (render_review_markdown_deterministic(ctx), [])
    from pipeline.component2.llm_processor import process_rule_cards_markdown_render

    result, usage = process_rule_cards_markdown_render(
        lesson_id=ctx.lesson_id,
        lesson_title=ctx.lesson_title,
        rule_cards=ctx.rule_cards,
        evidence_refs=ctx.evidence_refs,
        render_mode="review",
        video_id=video_id,
        model=model,
        provider=provider,
    )
    return (result.markdown, usage)


def render_rag_markdown(
    ctx: ExportContext,
    *,
    use_llm: bool = False,
    video_id: str | None = None,
    model: str | None = None,
    provider: str | None = None,
) -> tuple[str, list[dict]]:
    """RAG markdown: deterministic or LLM (render_mode=rag). Returns (markdown, usage_records)."""
    if not use_llm:
        return (render_rag_markdown_deterministic(ctx), [])
    from pipeline.component2.llm_processor import process_rule_cards_markdown_render

    result, usage = process_rule_cards_markdown_render(
        lesson_id=ctx.lesson_id,
        lesson_title=ctx.lesson_title,
        rule_cards=ctx.rule_cards,
        evidence_refs=ctx.evidence_refs,
        render_mode="rag",
        video_id=video_id,
        model=model,
        provider=provider,
    )
    return (result.markdown, usage)


# ----- File helpers -----


def ensure_parent_dir(path: Path) -> None:
    """Create parent directory of path if it does not exist."""
    path.parent.mkdir(parents=True, exist_ok=True)


def save_review_markdown(markdown: str, output_path: Path) -> None:
    """Write review markdown to file."""
    ensure_parent_dir(output_path)
    atomic_write_text(output_path, markdown, encoding="utf-8")


def save_rag_markdown(markdown: str, output_path: Path) -> None:
    """Write RAG markdown to file."""
    ensure_parent_dir(output_path)
    atomic_write_text(output_path, markdown, encoding="utf-8")


def save_export_debug(debug_rows: list[dict], output_path: Path) -> None:
    """Write debug rows as JSON."""
    ensure_parent_dir(output_path)
    atomic_write_json(output_path, debug_rows)


def write_export_manifest(manifest_dict: dict[str, Any], path: Path) -> None:
    """Write export manifest JSON (lesson_id, paths, counts, LLM flags)."""
    ensure_parent_dir(path)
    atomic_write_json(path, manifest_dict)


# ----- Optional debug when LLM used -----


def _write_render_debug(
    path: Path,
    usage: list[dict],
    markdown_preview: str,
    render_type: str,
) -> None:
    """Write optional debug JSON (usage + preview) when LLM render was used."""
    preview = (markdown_preview or "")[:2000]
    payload = {
        "render_type": render_type,
        "usage": usage,
        "markdown_preview": preview,
    }
    ensure_parent_dir(path)
    atomic_write_json(path, payload)


# ----- Export orchestration -----


def _format_concept_relationships_section(graph: ConceptGraph) -> str:
    """Compact markdown lines for Concept relationships (Task 12 optional)."""
    lines: list[str] = []
    for r in graph.relations:
        if r.relation_type == "contrasts_with":
            lines.append(f"- {r.source_id} contrasts_with {r.target_id}")
        else:
            lines.append(f"- {r.source_id} -> {r.target_id} ({r.relation_type})")
    if not lines:
        return ""
    return "\n\n## Concept relationships\n\n" + "\n".join(lines)


def export_review_markdown(
    *,
    lesson_id: str,
    lesson_title: str | None,
    rule_cards_path: Path,
    evidence_index_path: Path,
    knowledge_events_path: Path | None = None,
    concept_graph_path: Path | None = None,
    output_path: Path,
    use_llm: bool = False,
    video_id: str | None = None,
    model: str | None = None,
    provider: str | None = None,
    review_render_debug_path: Path | None = None,
    compaction_cfg: VisualCompactionConfig | None = None,
) -> tuple[str, list[dict]]:
    """Load artifacts, build context, render review markdown, save. Returns (markdown, usage)."""
    rule_cards = load_rule_cards(rule_cards_path)
    evidence_index = load_evidence_index(evidence_index_path)
    knowledge_events = (
        load_knowledge_events(knowledge_events_path) if knowledge_events_path else None
    )
    ctx = build_export_context(
        rule_cards,
        evidence_index,
        knowledge_events=knowledge_events,
        lesson_title=lesson_title,
        compaction_cfg=compaction_cfg,
    )
    md, usage = render_review_markdown(
        ctx,
        use_llm=use_llm,
        video_id=video_id,
        model=model,
        provider=provider,
    )
    if concept_graph_path and concept_graph_path.exists():
        graph = ConceptGraph.model_validate_json(
            concept_graph_path.read_text(encoding="utf-8")
        )
        extra = _format_concept_relationships_section(graph)
        if extra:
            md = md.rstrip() + "\n" + extra
    warnings = validate_markdown_visual_compaction(md)
    if warnings:
        logger.warning("Visual compaction warnings: %d", len(warnings))
    ensure_parent_dir(output_path)
    save_review_markdown(md, output_path)
    if use_llm and review_render_debug_path is not None:
        _write_render_debug(
            review_render_debug_path,
            usage,
            md,
            "review",
        )
    return (md, usage)


def export_rag_markdown(
    *,
    lesson_id: str,
    lesson_title: str | None,
    rule_cards_path: Path,
    evidence_index_path: Path,
    knowledge_events_path: Path | None = None,
    output_path: Path,
    use_llm: bool = False,
    video_id: str | None = None,
    model: str | None = None,
    provider: str | None = None,
    rag_render_debug_path: Path | None = None,
    compaction_cfg: VisualCompactionConfig | None = None,
) -> tuple[str, list[dict]]:
    """Load artifacts, build context, render RAG markdown, save. Returns (markdown, usage)."""
    rule_cards = load_rule_cards(rule_cards_path)
    evidence_index = load_evidence_index(evidence_index_path)
    knowledge_events = (
        load_knowledge_events(knowledge_events_path) if knowledge_events_path else None
    )
    ctx = build_export_context(
        rule_cards,
        evidence_index,
        knowledge_events=knowledge_events,
        lesson_title=lesson_title,
        compaction_cfg=compaction_cfg,
    )
    md, usage = render_rag_markdown(
        ctx,
        use_llm=use_llm,
        video_id=video_id,
        model=model,
        provider=provider,
    )
    warnings = validate_markdown_visual_compaction(md)
    if warnings:
        logger.warning("Visual compaction warnings: %d", len(warnings))
    ensure_parent_dir(output_path)
    save_rag_markdown(md, output_path)
    if use_llm and rag_render_debug_path is not None:
        _write_render_debug(
            rag_render_debug_path,
            usage,
            md,
            "rag",
        )
    return (md, usage)
