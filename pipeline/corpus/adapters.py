"""Load per-lesson JSON artifacts and convert local IDs to global corpus IDs.

Source files are never mutated -- adapters return new dicts with global IDs.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pipeline.corpus.contracts import (
    ConceptGraph,
    EvidenceIndex,
    KnowledgeEventCollection,
    RuleCardCollection,
)
from pipeline.corpus.id_utils import make_global_id, make_global_node_id, make_global_relation_id


ARTIFACT_SUFFIXES = {
    "knowledge_events": ".knowledge_events.json",
    "rule_cards": ".rule_cards.json",
    "evidence_index": ".evidence_index.json",
    "concept_graph": ".concept_graph.json",
}


def _load_json(path: Path) -> dict | list:
    return json.loads(path.read_text(encoding="utf-8"))


def find_artifact(intermediate_dir: Path, suffix: str) -> Path | None:
    """Find an artifact file by suffix pattern in the intermediate dir."""
    for f in intermediate_dir.iterdir():
        if f.name.endswith(suffix):
            return f
    return None


def load_lesson_knowledge_events(path: Path) -> KnowledgeEventCollection:
    data = _load_json(path)
    return KnowledgeEventCollection.model_validate(data)


def load_lesson_rule_cards(path: Path) -> RuleCardCollection:
    data = _load_json(path)
    return RuleCardCollection.model_validate(data)


def load_lesson_evidence_index(path: Path) -> EvidenceIndex:
    data = _load_json(path)
    return EvidenceIndex.model_validate(data)


def load_lesson_concept_graph(path: Path) -> ConceptGraph:
    data = _load_json(path)
    return ConceptGraph.model_validate(data)


def globalize_event(event_dict: dict[str, Any], lesson_slug: str) -> dict[str, Any]:
    """Return a copy of a KnowledgeEvent dict with global IDs."""
    out = dict(event_dict)
    out["global_id"] = make_global_id("event", lesson_slug, out["event_id"])
    out["lesson_slug"] = lesson_slug

    if out.get("evidence_refs"):
        out["evidence_refs"] = [
            make_global_id("evidence", lesson_slug, eid)
            for eid in out["evidence_refs"]
        ]
    if out.get("source_event_ids"):
        out["source_event_ids"] = [
            make_global_id("event", lesson_slug, eid)
            for eid in out["source_event_ids"]
        ]
    return out


def globalize_rule(rule_dict: dict[str, Any], lesson_slug: str) -> dict[str, Any]:
    """Return a copy of a RuleCard dict with global IDs."""
    out = dict(rule_dict)
    out["global_id"] = make_global_id("rule", lesson_slug, out["rule_id"])
    out["lesson_slug"] = lesson_slug

    if out.get("source_event_ids"):
        out["source_event_ids"] = [
            make_global_id("event", lesson_slug, eid)
            for eid in out["source_event_ids"]
        ]
    if out.get("evidence_refs"):
        out["evidence_refs"] = [
            make_global_id("evidence", lesson_slug, eid)
            for eid in out["evidence_refs"]
        ]
    for ref_key in ("positive_example_refs", "negative_example_refs", "ambiguous_example_refs"):
        if out.get(ref_key):
            out[ref_key] = [
                make_global_id("evidence", lesson_slug, eid)
                for eid in out[ref_key]
            ]
    return out


def globalize_evidence(evidence_dict: dict[str, Any], lesson_slug: str) -> dict[str, Any]:
    """Return a copy of an EvidenceRef dict with global IDs."""
    out = dict(evidence_dict)
    out["global_id"] = make_global_id("evidence", lesson_slug, out["evidence_id"])
    out["lesson_slug"] = lesson_slug

    if out.get("linked_rule_ids"):
        out["linked_rule_ids"] = [
            make_global_id("rule", lesson_slug, rid)
            for rid in out["linked_rule_ids"]
        ]
    if out.get("source_event_ids"):
        out["source_event_ids"] = [
            make_global_id("event", lesson_slug, eid)
            for eid in out["source_event_ids"]
        ]
    return out


def globalize_concept_node(node_dict: dict[str, Any], lesson_slug: str) -> dict[str, Any]:
    """Return a copy of a ConceptNode dict with global IDs."""
    out = dict(node_dict)
    out["global_id"] = make_global_node_id(out["name"])
    out["lesson_slug"] = lesson_slug
    if out.get("source_rule_ids"):
        out["source_rule_ids"] = [
            make_global_id("rule", lesson_slug, rid)
            for rid in out["source_rule_ids"]
        ]
    if out.get("parent_id"):
        parent_name = out["parent_id"]
        out["parent_id"] = make_global_node_id(parent_name)
    return out


def globalize_concept_relation(
    rel_dict: dict[str, Any],
    lesson_slug: str,
    node_id_map: dict[str, str],
) -> dict[str, Any]:
    """Return a copy of a ConceptRelation dict with global IDs.

    node_id_map maps local concept_id -> global node ID.
    """
    out = dict(rel_dict)
    src_global = node_id_map.get(out["source_id"], out["source_id"])
    dst_global = node_id_map.get(out["target_id"], out["target_id"])
    out["source_id"] = src_global
    out["target_id"] = dst_global
    out["relation_id"] = make_global_relation_id(src_global, out["relation_type"], dst_global)
    out["lesson_slug"] = lesson_slug
    if out.get("source_rule_ids"):
        out["source_rule_ids"] = [
            make_global_id("rule", lesson_slug, rid)
            for rid in out["source_rule_ids"]
        ]
    return out
