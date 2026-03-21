"""Shared helpers for lesson-level regression tests (Task 14)."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


def load_json(path: Path) -> dict | list:
    return json.loads(path.read_text(encoding="utf-8"))


def index_by(items: list[dict], key: str) -> dict[str, dict]:
    return {item[key]: item for item in items if key in item}


def collect_all_rule_example_refs(rules: list[dict]) -> set[str]:
    refs: set[str] = set()
    for r in rules:
        refs.update(r.get("positive_example_refs", []))
        refs.update(r.get("negative_example_refs", []))
        refs.update(r.get("ambiguous_example_refs", []))
    return refs


def artifact_paths_for_lesson(base_dir: Path, lesson_slug: str) -> dict[str, Path]:
    intermediate = base_dir / "output_intermediate"
    return {
        "knowledge_events": intermediate / f"{lesson_slug}.knowledge_events.json",
        "rule_cards": intermediate / f"{lesson_slug}.rule_cards.json",
        "evidence_index": intermediate / f"{lesson_slug}.evidence_index.json",
        "concept_graph": intermediate / f"{lesson_slug}.concept_graph.json",
        "ml_manifest": intermediate / f"{lesson_slug}.ml_manifest.json",
        "labeling_manifest": intermediate / f"{lesson_slug}.labeling_manifest.json",
        "rag_ready": base_dir / "output_rag_ready" / f"{lesson_slug}.rag_ready.md",
        "review_markdown": base_dir / "output_review" / f"{lesson_slug}.review_markdown.md",
    }


def assert_artifact_existence(paths: dict[str, Path], *, require_markdown: bool = True) -> None:
    """A: Verify all expected structured artifacts exist."""
    for name in ("knowledge_events", "rule_cards", "evidence_index",
                 "concept_graph", "ml_manifest", "labeling_manifest"):
        assert paths[name].is_file(), f"Missing artifact: {paths[name].name}"
    if require_markdown:
        assert paths["rag_ready"].is_file(), f"Missing: {paths['rag_ready'].name}"
        assert paths["review_markdown"].is_file(), f"Missing: {paths['review_markdown'].name}"


def assert_knowledge_events_clean(events: list[dict]) -> None:
    """B/C/D: Knowledge events have required fields, no placeholders, valid timestamp confidence."""
    assert events, "knowledge_events must not be empty"

    forbidden_normalized = {"", "No normalized text extracted."}
    for e in events:
        assert (e.get("normalized_text") or "").strip() not in forbidden_normalized, (
            f"Event {e.get('event_id')} has placeholder/empty normalized_text"
        )
        for field in ("source_chunk_index", "source_line_start", "source_line_end",
                       "source_quote", "transcript_anchors", "timestamp_confidence"):
            assert field in e, f"Event {e.get('event_id')} missing Phase 2A field: {field}"

    for e in events:
        if e.get("timestamp_confidence") == "line" and (e.get("anchor_span_width") or 0) > 3:
            raise AssertionError(
                f"Event {e['event_id']}: timestamp_confidence='line' but anchor_span_width="
                f"{e['anchor_span_width']} > 3"
            )


def assert_rule_cards_provenance(rules: list[dict]) -> None:
    """B: Rule cards have provenance, no placeholder text."""
    assert rules, "rule_cards must not be empty"
    for r in rules:
        assert r.get("lesson_id"), f"Rule {r.get('rule_id')} missing lesson_id"
        assert r.get("source_event_ids"), f"Rule {r.get('rule_id')} has empty source_event_ids"
        assert "evidence_refs" in r, f"Rule {r.get('rule_id')} missing evidence_refs key"
        rule_text = (r.get("rule_text") or "").strip()
        assert rule_text != "No rule text extracted.", (
            f"Rule {r.get('rule_id')} has placeholder rule_text"
        )


def assert_evidence_backlinks(evidence: list[dict]) -> None:
    """E: Every evidence row has linked_rule_ids and source_event_ids."""
    for x in evidence:
        assert x.get("linked_rule_ids"), (
            f"Evidence {x['evidence_id']} missing linked_rule_ids"
        )
        assert x.get("source_event_ids"), (
            f"Evidence {x['evidence_id']} missing source_event_ids"
        )


def assert_ml_safety(ml_examples: list[dict], label_tasks: list[dict],
                     rules: list[dict]) -> None:
    """F: No illustration in ML examples; no weak-specificity evidence leaks."""
    for ex in ml_examples:
        assert ex.get("example_role") != "illustration", (
            f"Illustration leaked into ml_manifest.examples: {ex.get('evidence_id')}"
        )
        meta = ex.get("metadata", {})
        reason = (meta.get("promotion_reason") or "").lower()
        assert "insufficient_visual_specificity" not in reason, (
            f"Weak-specificity evidence in ml_manifest.examples: {ex.get('evidence_id')}"
        )
        assert "generic_teaching_visual" not in reason, (
            f"Generic-teaching evidence in ml_manifest.examples: {ex.get('evidence_id')}"
        )


def assert_concept_graph_structure(cg: dict) -> None:
    """Concept graph has valid structure: nodes, relations, stats, lesson_id."""
    assert "nodes" in cg, "concept_graph missing 'nodes'"
    assert "relations" in cg, "concept_graph missing 'relations'"
    assert "lesson_id" in cg, "concept_graph missing 'lesson_id'"
    assert "stats" in cg, "concept_graph missing 'stats'"
    assert "graph_version" in cg, "concept_graph missing 'graph_version'"
    assert isinstance(cg["nodes"], list)
    assert isinstance(cg["relations"], list)
    assert cg["stats"]["node_count"] == len(cg["nodes"]), (
        f"stats.node_count ({cg['stats']['node_count']}) != len(nodes) ({len(cg['nodes'])})"
    )
    assert cg["stats"]["edge_count"] == len(cg["relations"]), (
        f"stats.edge_count ({cg['stats']['edge_count']}) != len(relations) ({len(cg['relations'])})"
    )
    for node in cg["nodes"]:
        assert "concept_id" in node, f"Node missing concept_id: {node}"
        assert "name" in node, f"Node missing name: {node}"
        assert "type" in node, f"Node missing type: {node}"
    for rel in cg["relations"]:
        assert "relation_id" in rel, f"Relation missing relation_id: {rel}"
        assert "source_id" in rel, f"Relation missing source_id: {rel}"
        assert "target_id" in rel, f"Relation missing target_id: {rel}"
        assert "relation_type" in rel, f"Relation missing relation_type: {rel}"
        assert "weight" in rel, f"Relation missing weight: {rel}"
        assert isinstance(rel["weight"], int), f"Relation weight not int: {rel}"


def assert_cross_file_integrity(events: list[dict], rules: list[dict],
                                evidence: list[dict]) -> None:
    """H: All cross-file references resolve."""
    event_ids = {e["event_id"] for e in events}
    rule_ids = {r["rule_id"] for r in rules}
    evidence_ids = {x["evidence_id"] for x in evidence}

    for rule in rules:
        for eid in rule.get("source_event_ids", []):
            assert eid in event_ids, (
                f"Rule {rule['rule_id']}.source_event_ids refs missing event {eid}"
            )
        for eid in rule.get("evidence_refs", []):
            assert eid in evidence_ids, (
                f"Rule {rule['rule_id']}.evidence_refs refs missing evidence {eid}"
            )

    for item in evidence:
        for eid in item.get("source_event_ids", []):
            assert eid in event_ids, (
                f"Evidence {item['evidence_id']}.source_event_ids refs missing event {eid}"
            )
        for rid in item.get("linked_rule_ids", []):
            assert rid in rule_ids, (
                f"Evidence {item['evidence_id']}.linked_rule_ids refs missing rule {rid}"
            )


_STRUCTURAL_LABEL_PREFIXES = (
    "visual summary", "**algorithm notes**", "**conditions**",
    "**invalidation**", "**exceptions**", "**comparisons**",
    "**context**", "---", "##", "###", "####",
)


def assert_markdown_quality(rag_path: Path) -> None:
    """G: RAG markdown is derived from structures, not spammy frame narration."""
    if not rag_path.is_file():
        return
    rag_text = rag_path.read_text(encoding="utf-8")
    lines = [line for line in rag_text.splitlines() if line.strip()]
    assert lines, "rag_ready.md is empty"

    content_lines = [
        line for line in lines
        if not line.strip().lower().startswith(_STRUCTURAL_LABEL_PREFIXES)
    ]
    line_counts = Counter(content_lines)
    for line, count in line_counts.most_common(5):
        assert count <= 15, (
            f"Repetitive content line in rag_ready.md ({count}x): {line[:80]}"
        )

    ts_zero_lines = [line for line in lines if "[00:00]" in line]
    assert len(ts_zero_lines) < len(lines) * 0.5, (
        f"Too many timestamps collapsed to [00:00]: {len(ts_zero_lines)}/{len(lines)}"
    )


def assert_canonical_ids_on_events(events: list[dict]) -> None:
    """Verify canonical ID fields are present on knowledge events with non-empty concepts."""
    for e in events:
        assert e.get("source_language") == "ru", (
            f"Event {e.get('event_id')} missing source_language=ru"
        )
        concept = (e.get("concept") or "").strip()
        if concept:
            assert e.get("concept_id"), (
                f"Event {e.get('event_id')} has concept={concept!r} but no concept_id"
            )
            assert e["concept_id"].startswith("concept:"), (
                f"Event {e.get('event_id')} concept_id should start with 'concept:': {e['concept_id']}"
            )
        subconcept = (e.get("subconcept") or "").strip()
        if subconcept:
            assert e.get("subconcept_id"), (
                f"Event {e.get('event_id')} has subconcept={subconcept!r} but no subconcept_id"
            )


def assert_canonical_ids_on_rules(rules: list[dict]) -> None:
    """Verify canonical ID fields are present on rule cards."""
    for r in rules:
        assert r.get("source_language") == "ru", (
            f"Rule {r.get('rule_id')} missing source_language=ru"
        )
        concept = (r.get("concept") or "").strip()
        if concept:
            assert r.get("concept_id"), (
                f"Rule {r.get('rule_id')} has concept={concept!r} but no concept_id"
            )
        conditions = r.get("conditions", [])
        condition_ids = r.get("condition_ids", [])
        assert len(condition_ids) == len(conditions), (
            f"Rule {r.get('rule_id')}: condition_ids count ({len(condition_ids)}) "
            f"!= conditions count ({len(conditions)})"
        )
        invalidation = r.get("invalidation", [])
        invalidation_ids = r.get("invalidation_ids", [])
        assert len(invalidation_ids) == len(invalidation), (
            f"Rule {r.get('rule_id')}: invalidation_ids count ({len(invalidation_ids)}) "
            f"!= invalidation count ({len(invalidation)})"
        )
        exceptions = r.get("exceptions", [])
        exception_ids = r.get("exception_ids", [])
        assert len(exception_ids) == len(exceptions), (
            f"Rule {r.get('rule_id')}: exception_ids count ({len(exception_ids)}) "
            f"!= exceptions count ({len(exceptions)})"
        )


def assert_canonical_ids_on_evidence(evidence: list[dict]) -> None:
    """Verify canonical ID fields are present on evidence refs."""
    for x in evidence:
        assert x.get("source_language") == "ru", (
            f"Evidence {x.get('evidence_id')} missing source_language=ru"
        )
