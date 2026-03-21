"""Build grounded, structured answer payloads from retrieval results.

Default mode is extractive: summaries come from retrieved content only.
"""

from __future__ import annotations

from typing import Any


def build_answer(retrieval_result: dict[str, Any], return_summary: bool = True) -> dict[str, Any]:
    query = retrieval_result.get("query", "")
    top_hits = retrieval_result.get("top_hits", [])
    expansion = retrieval_result.get("expansion", {})

    grouped: dict[str, list[dict[str, Any]]] = {
        "rule_cards": [],
        "knowledge_events": [],
        "evidence_refs": [],
        "concepts": [],
    }
    for hit in top_hits:
        ut = hit.get("unit_type", "")
        if ut == "rule_card":
            grouped["rule_cards"].append(hit)
        elif ut == "knowledge_event":
            grouped["knowledge_events"].append(hit)
        elif ut == "evidence_ref":
            grouped["evidence_refs"].append(hit)
        elif ut in ("concept_node", "concept_relation"):
            grouped["concepts"].append(hit)

    citations: list[dict[str, Any]] = []
    for hit in top_hits:
        citations.append({
            "doc_id": hit["doc_id"],
            "unit_type": hit.get("unit_type", ""),
            "lesson_id": hit.get("lesson_id", ""),
            "title": hit.get("title", ""),
            "timestamps": hit.get("timestamps", []),
            "evidence_ids": hit.get("evidence_ids", []),
        })

    answer_summary: str | None = None
    if return_summary and grouped["rule_cards"]:
        snippets = [h.get("text_snippet", "") for h in grouped["rule_cards"][:5] if h.get("text_snippet")]
        if snippets:
            answer_summary = "\n---\n".join(snippets)

    return {
        "query": query,
        "detected_concepts": expansion.get("detected_concepts", []),
        "expansion_trace": expansion.get("expansion_trace", []),
        "top_hits": top_hits,
        "grouped_results": grouped,
        "answer_summary": answer_summary,
        "citations": citations,
        "facets": retrieval_result.get("facets", {}),
    }
