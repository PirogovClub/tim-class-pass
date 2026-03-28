"""Graph-style related lookups for RAG item inspection (Stage 6.3)."""

from __future__ import annotations

from typing import Any

from pipeline.rag.store import DocStore


def _compact_doc(doc: dict[str, Any]) -> dict[str, Any]:
    """Strip heavy fields; keep provenance for API responses."""
    keys = (
        "doc_id",
        "unit_type",
        "lesson_id",
        "lesson_slug",
        "title",
        "short_text",
        "text",
        "canonical_concept_ids",
        "timestamps",
        "evidence_ids",
        "source_event_ids",
        "source_rule_ids",
        "confidence_score",
        "support_basis",
        "provenance",
        "metadata",
    )
    return {k: doc.get(k) for k in keys if k in doc}


def _rules_for_event(store: DocStore, event_id: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for d in store.get_by_unit("rule_card"):
        if event_id in (d.get("source_event_ids") or []):
            out.append(_compact_doc(d))
    return out


def related_for_document(store: DocStore, unit_type: str, doc_id: str) -> dict[str, Any]:
    doc = store.get(doc_id)
    if doc is None:
        return {"found": False, "unit_type": unit_type, "doc_id": doc_id, "related": {}}

    actual = doc.get("unit_type", "")
    if actual != unit_type:
        return {
            "found": False,
            "unit_type": unit_type,
            "doc_id": doc_id,
            "mismatch": True,
            "actual_unit_type": actual,
            "related": {},
        }

    related: dict[str, list[dict[str, Any]]] = {
        "evidence_refs": [],
        "knowledge_events": [],
        "rule_cards": [],
        "concept_nodes": [],
        "concept_relations": [],
    }

    for eid in doc.get("evidence_ids") or []:
        ev = store.get(eid)
        if ev:
            related["evidence_refs"].append(_compact_doc(ev))

    for eid in doc.get("source_event_ids") or []:
        ev = store.get(eid)
        if ev:
            related["knowledge_events"].append(_compact_doc(ev))

    for rid in doc.get("source_rule_ids") or []:
        r = store.get(rid)
        if r:
            related["rule_cards"].append(_compact_doc(r))

    for cid in doc.get("canonical_concept_ids") or []:
        for cdoc in store.get_by_concept(cid):
            ut = cdoc.get("unit_type")
            if ut == "concept_node":
                related["concept_nodes"].append(_compact_doc(cdoc))
            elif ut == "concept_relation":
                related["concept_relations"].append(_compact_doc(cdoc))

    if unit_type == "knowledge_event":
        related["rule_cards"].extend(_rules_for_event(store, doc_id))
        # Dedupe by doc_id
        seen: set[str] = set()
        deduped: list[dict[str, Any]] = []
        for row in related["rule_cards"]:
            did = row.get("doc_id")
            if did and did not in seen:
                seen.add(did)
                deduped.append(row)
        related["rule_cards"] = deduped

    if unit_type == "evidence_ref":
        for rid in doc.get("source_rule_ids") or []:
            r = store.get(rid)
            if r:
                related["rule_cards"].append(_compact_doc(r))

    return {
        "found": True,
        "unit_type": unit_type,
        "doc_id": doc_id,
        "source": _compact_doc(doc),
        "related": related,
    }
