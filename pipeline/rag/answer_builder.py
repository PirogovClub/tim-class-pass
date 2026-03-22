"""Build grounded, structured answer payloads from retrieval results."""

from __future__ import annotations

from typing import Any


def build_answer(retrieval_result: dict[str, Any], return_summary: bool = True) -> dict[str, Any]:
    query = retrieval_result.get("query", "")
    normalized_query = retrieval_result.get("normalized_query", query)
    top_hits = retrieval_result.get("top_hits", [])
    expansion = retrieval_result.get("expansion", {})
    detected_unit_bias = retrieval_result.get("detected_unit_bias", "mixed")

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

    citation_doc_ids = [hit["doc_id"] for hit in top_hits]
    limitations: list[str] = []
    if not top_hits:
        limitations.append("No grounded retrieval hits were found for this query.")
    if not any(hit.get("timestamps") for hit in top_hits):
        limitations.append("Top hits do not include timestamp evidence.")
    if not any(hit.get("evidence_ids") for hit in top_hits):
        limitations.append("Top hits do not include explicit evidence IDs.")

    answer_text: str | None = None
    if return_summary:
        preferred_hits = grouped["rule_cards"] or grouped["knowledge_events"] or top_hits
        snippets = [hit.get("text_snippet", "") for hit in preferred_hits[:5] if hit.get("text_snippet")]
        if snippets:
            answer_text = "\n".join(snippets)

    return {
        "query": query,
        "query_analysis": {
            "normalized_query": normalized_query,
            "detected_concepts": expansion.get("canonical_concept_ids", []),
            "detected_unit_bias": detected_unit_bias,
            "expansion_trace": expansion,
        },
        "top_hits": top_hits,
        "grouped_results": grouped,
        "summary": {
            "answer_text": answer_text,
            "limitations": limitations,
            "citation_doc_ids": citation_doc_ids,
        },
        "facets": retrieval_result.get("facets", {}),
        "hit_count": retrieval_result.get("hit_count", len(top_hits)),
    }
