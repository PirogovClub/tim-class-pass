"""Orchestrates corpus creation: discover, validate, merge, enrich, export."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pipeline.corpus.adapters import (
    ARTIFACT_SUFFIXES,
    find_artifact,
    globalize_concept_node,
    globalize_concept_relation,
    globalize_event,
    globalize_evidence,
    globalize_rule,
    load_lesson_concept_graph,
    load_lesson_evidence_index,
    load_lesson_knowledge_events,
    load_lesson_rule_cards,
)
from pipeline.corpus.contracts import SCHEMA_VERSIONS, CorpusMetadata, LessonRecord
from pipeline.corpus.id_utils import make_global_node_id, slugify_lesson_id
from pipeline.corpus.lesson_registry import build_registry, discover_lessons, save_registry
from pipeline.corpus.validator import (
    ValidationResult,
    save_validation_report,
    validate_cross_lesson,
    validate_lesson,
)


def _write_jsonl(items: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")


def _write_json(data: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _merge_concept_graphs(
    all_nodes: list[dict],
    all_relations: list[dict],
) -> tuple[list[dict], list[dict]]:
    """Deduplicate concept nodes by global_id, merge aliases and source_rule_ids.

    Relations are deduplicated by relation_id, merging source_rule_ids.
    """
    node_map: dict[str, dict] = {}
    for node in all_nodes:
        gid = node["global_id"]
        if gid in node_map:
            existing = node_map[gid]
            all_aliases = set(existing.get("aliases", []))
            all_aliases.update(node.get("aliases", []))
            existing["aliases"] = sorted(all_aliases)
            all_rules = set(existing.get("source_rule_ids", []))
            all_rules.update(node.get("source_rule_ids", []))
            existing["source_rule_ids"] = sorted(all_rules)
            lessons = set(existing.get("source_lessons", []))
            lessons.add(node.get("lesson_slug", ""))
            existing["source_lessons"] = sorted(lessons)
        else:
            node_copy = dict(node)
            node_copy["source_lessons"] = [node.get("lesson_slug", "")]
            node_map[gid] = node_copy

    rel_map: dict[str, dict] = {}
    for rel in all_relations:
        rid = rel["relation_id"]
        if rid in rel_map:
            existing = rel_map[rid]
            existing["weight"] = existing.get("weight", 1) + rel.get("weight", 1)
            all_rules = set(existing.get("source_rule_ids", []))
            all_rules.update(rel.get("source_rule_ids", []))
            existing["source_rule_ids"] = sorted(all_rules)
            lessons = set(existing.get("source_lessons", []))
            lessons.add(rel.get("lesson_slug", ""))
            existing["source_lessons"] = sorted(lessons)
        else:
            rel_copy = dict(rel)
            rel_copy["source_lessons"] = [rel.get("lesson_slug", "")]
            rel_map[rid] = rel_copy

    for node in node_map.values():
        node.pop("lesson_slug", None)
    for rel in rel_map.values():
        rel.pop("lesson_slug", None)

    merged_nodes = sorted(node_map.values(), key=lambda n: n.get("global_id", ""))
    merged_rels = sorted(rel_map.values(), key=lambda r: r.get("relation_id", ""))
    return merged_nodes, merged_rels


def _build_concept_alias_registry(merged_nodes: list[dict]) -> dict[str, Any]:
    registry: dict[str, Any] = {}
    for node in merged_nodes:
        gid = node.get("global_id", "")
        registry[gid] = {
            "name": node.get("name", ""),
            "aliases": node.get("aliases", []),
            "source_lessons": node.get("source_lessons", []),
            "type": node.get("type", "concept"),
        }
    return registry


def _build_concept_frequencies(
    merged_nodes: list[dict],
    global_events: list[dict],
    global_rules: list[dict],
    global_evidence: list[dict],
) -> dict[str, Any]:
    """Per-concept counts of rules, events, evidence, and lessons."""
    freq: dict[str, dict[str, int | list]] = {}

    node_names: dict[str, str] = {}
    for node in merged_nodes:
        gid = node.get("global_id", "")
        freq[gid] = {
            "name": node.get("name", ""),
            "rule_count": 0,
            "event_count": 0,
            "evidence_count": 0,
            "lesson_count": len(node.get("source_lessons", [])),
        }
        node_names[node.get("name", "").lower()] = gid

    for ev in global_events:
        concept = (ev.get("concept") or "").lower()
        if concept in node_names:
            freq[node_names[concept]]["event_count"] += 1

    for rc in global_rules:
        concept = (rc.get("concept") or "").lower()
        if concept in node_names:
            freq[node_names[concept]]["rule_count"] += 1

    for ev in global_evidence:
        for cid in ev.get("related_concept_ids", []):
            if cid in freq:
                freq[cid]["evidence_count"] += 1

    return freq


def _build_concept_rule_map(global_rules: list[dict]) -> dict[str, list[str]]:
    """Concept global_id -> list of global rule IDs."""
    from pipeline.corpus.id_utils import make_global_node_id

    mapping: dict[str, list[str]] = defaultdict(list)
    for rc in global_rules:
        concept = rc.get("concept", "")
        if concept:
            node_id = make_global_node_id(concept)
            mapping[node_id].append(rc.get("global_id", ""))
    return dict(mapping)


def _build_rule_family_index(global_rules: list[dict]) -> dict[str, list[str]]:
    """Group rules by normalized concept+subconcept key."""
    from pipeline.corpus.id_utils import _slugify

    families: dict[str, list[str]] = defaultdict(list)
    for rc in global_rules:
        concept = rc.get("concept", "")
        subconcept = rc.get("subconcept") or ""
        key = _slugify(f"{concept}__{subconcept}") if subconcept else _slugify(concept)
        families[key].append(rc.get("global_id", ""))
    return dict(families)


def _build_concept_overlap_report(merged_nodes: list[dict]) -> list[dict]:
    """Which concepts appear in multiple lessons."""
    overlaps: list[dict] = []
    for node in merged_nodes:
        lessons = node.get("source_lessons", [])
        if len(lessons) > 1:
            overlaps.append({
                "concept_id": node.get("global_id", ""),
                "name": node.get("name", ""),
                "lessons": sorted(lessons),
                "lesson_count": len(lessons),
            })
    overlaps.sort(key=lambda x: x.get("lesson_count", 0), reverse=True)
    return overlaps


def build_corpus(
    input_root: Path,
    output_root: Path,
    strict: bool = False,
    selected_project_roots: list[Path] | None = None,
) -> dict[str, Any]:
    """Main entry point: discover -> validate -> merge -> enrich -> export.

    Returns a summary dict.
    """
    output_root.mkdir(parents=True, exist_ok=True)

    lessons = discover_lessons(input_root, selected_project_roots=selected_project_roots)
    if not lessons:
        raise RuntimeError(f"No lessons found under {input_root}")

    registry_data = build_registry(lessons)
    save_registry(registry_data, output_root / "lesson_registry.json")

    all_validation = ValidationResult()
    for lesson in lessons:
        vr = validate_lesson(lesson, strict=strict)
        all_validation.errors.extend(vr.errors)
        all_validation.warnings.extend(vr.warnings)

    if strict and all_validation.has_errors:
        report = all_validation.to_dict()
        save_validation_report(report, output_root / "validation_report.json")
        raise RuntimeError(
            f"Strict validation failed with {len(all_validation.errors)} error(s). "
            f"See validation_report.json."
        )

    global_events: list[dict] = []
    global_rules: list[dict] = []
    global_evidence: list[dict] = []
    all_nodes: list[dict] = []
    all_relations: list[dict] = []

    for lesson in lessons:
        slug = lesson.lesson_slug
        intermediate = Path(lesson.artifact_paths.get("knowledge_events", "")).parent

        ke_path = lesson.artifact_paths.get("knowledge_events")
        if ke_path and Path(ke_path).exists():
            col = load_lesson_knowledge_events(Path(ke_path))
            for ev in col.events:
                global_events.append(globalize_event(ev.model_dump(), slug))

        rc_path = lesson.artifact_paths.get("rule_cards")
        if rc_path and Path(rc_path).exists():
            col = load_lesson_rule_cards(Path(rc_path))
            for rc in col.rules:
                global_rules.append(globalize_rule(rc.model_dump(), slug))

        ei_path = lesson.artifact_paths.get("evidence_index")
        if ei_path and Path(ei_path).exists():
            idx = load_lesson_evidence_index(Path(ei_path))
            for ev in idx.evidence_refs:
                global_evidence.append(globalize_evidence(ev.model_dump(), slug))

        cg_path = lesson.artifact_paths.get("concept_graph")
        if cg_path and Path(cg_path).exists():
            cg = load_lesson_concept_graph(Path(cg_path))
            node_id_map: dict[str, str] = {}
            for node in cg.nodes:
                gnode = globalize_concept_node(node.model_dump(), slug)
                node_id_map[node.concept_id] = gnode["global_id"]
                all_nodes.append(gnode)
            for rel in cg.relations:
                all_relations.append(
                    globalize_concept_relation(rel.model_dump(), slug, node_id_map)
                )

    cross_result = validate_cross_lesson(
        lessons, global_events, global_rules, global_evidence, all_nodes, all_relations,
    )
    all_validation.errors.extend(cross_result.errors)
    all_validation.warnings.extend(cross_result.warnings)

    _write_jsonl(global_events, output_root / "corpus_knowledge_events.jsonl")
    _write_jsonl(global_rules, output_root / "corpus_rule_cards.jsonl")
    _write_jsonl(global_evidence, output_root / "corpus_evidence_index.jsonl")
    _write_jsonl([lr.model_dump() for lr in lessons], output_root / "corpus_lessons.jsonl")

    merged_nodes, merged_relations = _merge_concept_graphs(all_nodes, all_relations)
    corpus_graph = {
        "lesson_id": "corpus",
        "graph_version": "1.0",
        "nodes": merged_nodes,
        "relations": merged_relations,
        "stats": {
            "node_count": len(merged_nodes),
            "edge_count": len(merged_relations),
        },
    }
    _write_json(corpus_graph, output_root / "corpus_concept_graph.json")

    alias_reg = _build_concept_alias_registry(merged_nodes)
    _write_json(alias_reg, output_root / "concept_alias_registry.json")

    freqs = _build_concept_frequencies(merged_nodes, global_events, global_rules, global_evidence)
    _write_json(freqs, output_root / "concept_frequencies.json")

    crm = _build_concept_rule_map(global_rules)
    _write_json(crm, output_root / "concept_rule_map.json")

    rfi = _build_rule_family_index(global_rules)
    _write_json(rfi, output_root / "rule_family_index.json")

    overlap = _build_concept_overlap_report(merged_nodes)
    _write_json(overlap, output_root / "concept_overlap_report.json")

    rules_total = len(global_rules)
    rules_no_ev = sum(1 for r in global_rules if not r.get("evidence_refs"))
    rules_fallback = sum(
        1 for r in global_rules if r.get("metadata", {}).get("proximity_fallback")
    )
    ev_coverage = (
        round((rules_total - rules_no_ev) / rules_total * 100, 1)
        if rules_total
        else 0.0
    )

    sb_counts: dict[str, int] = {
        "transcript_primary": 0,
        "transcript_plus_visual": 0,
        "visual_primary": 0,
        "inferred": 0,
    }
    for r in global_rules:
        sb = r.get("support_basis") or "inferred"
        if sb in sb_counts:
            sb_counts[sb] += 1
        else:
            sb_counts["inferred"] += 1

    now = datetime.now(timezone.utc).isoformat()
    meta = CorpusMetadata(
        corpus_contract_version=SCHEMA_VERSIONS["corpus_contract_version"],
        generated_at=now,
        lesson_count=len(lessons),
        knowledge_event_count=len(global_events),
        rule_card_count=rules_total,
        evidence_ref_count=len(global_evidence),
        concept_node_count=len(merged_nodes),
        concept_relation_count=len(merged_relations),
        source_root=str(input_root),
        builder_version="1.0.0",
        validation_status=all_validation.status,
        evidence_coverage_pct=ev_coverage,
        rules_without_evidence=rules_no_ev,
        fallback_linked_rules=rules_fallback,
        transcript_primary_rules=sb_counts["transcript_primary"],
        transcript_plus_visual_rules=sb_counts["transcript_plus_visual"],
        visual_primary_rules=sb_counts["visual_primary"],
        inferred_rules=sb_counts["inferred"],
        notes=[],
    )
    _write_json(meta.model_dump(), output_root / "corpus_metadata.json")

    _write_json(dict(SCHEMA_VERSIONS), output_root / "schema_versions.json")

    report = all_validation.to_dict()
    save_validation_report(report, output_root / "validation_report.json")

    summary = {
        "lessons": len(lessons),
        "events": len(global_events),
        "rules": len(global_rules),
        "evidence": len(global_evidence),
        "concept_nodes": len(merged_nodes),
        "concept_relations": len(merged_relations),
        "validation_status": all_validation.status,
        "output_root": str(output_root),
    }
    return summary
